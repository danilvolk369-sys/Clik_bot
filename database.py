# ======================================================
# РАБОТА С БАЗОЙ ДАННЫХ — КликТохн v1.0.1
# ======================================================
import time
import aiosqlite
from config import DB_NAME, RANK_THRESHOLDS

_user_cache: dict = {}
_cache_ts: dict = {}
_CACHE_TTL = 30
_db_pool: aiosqlite.Connection | None = None


async def get_db() -> aiosqlite.Connection:
    global _db_pool
    if _db_pool is None:
        _db_pool = await aiosqlite.connect(DB_NAME)
        await _db_pool.execute("PRAGMA journal_mode = WAL")
        await _db_pool.execute("PRAGMA synchronous = NORMAL")
        await _db_pool.execute("PRAGMA cache_size = 10000")
        await _db_pool.execute("PRAGMA temp_store = MEMORY")
        await _db_pool.execute("PRAGMA mmap_size = 268435456")
    return _db_pool


# ==========================================================
#  ИНИЦИАЛИЗАЦИЯ
# ==========================================================
async def init_db():
    db = await get_db()

    await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id        INTEGER PRIMARY KEY,
            username       TEXT,
            clicks         REAL    DEFAULT 0,
            total_clicks   INTEGER DEFAULT 0,
            bonus_click    REAL    DEFAULT 0,
            passive_income REAL    DEFAULT 0,
            income_capacity REAL   DEFAULT 150,
            last_income_claim TEXT  DEFAULT NULL,
            rank           INTEGER DEFAULT 1,
            referrals      INTEGER DEFAULT 0,
            referrer_id    INTEGER DEFAULT 0,
            nft_count      INTEGER DEFAULT 0,
            nft_slots      INTEGER DEFAULT 5,
            is_banned      INTEGER DEFAULT 0,
            banned_until   TEXT    DEFAULT NULL,
            anonymous      INTEGER DEFAULT 0,
            last_active    TEXT    DEFAULT NULL,
            vip_type       TEXT    DEFAULT NULL,
            vip_multiplier_click  REAL DEFAULT 1,
            vip_multiplier_income REAL DEFAULT 1,
            vip_expires    TEXT    DEFAULT NULL,
            created_at     TEXT
        )
    """)
    await db.execute("CREATE INDEX IF NOT EXISTS idx_clicks ON users(clicks)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_banned ON users(is_banned)")

    await db.execute("""
        CREATE TABLE IF NOT EXISTS chat_queue (user_id INTEGER PRIMARY KEY)
    """)

    await db.execute("""
        CREATE TABLE IF NOT EXISTS active_chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            u1 INTEGER, u2 INTEGER, created_at TEXT
        )
    """)

    await db.execute("""
        CREATE TABLE IF NOT EXISTS chat_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER, sender_id INTEGER,
            message TEXT, created_at TEXT
        )
    """)

    await db.execute("""
        CREATE TABLE IF NOT EXISTS pvp_games (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            creator_id INTEGER, opponent_id INTEGER DEFAULT NULL,
            bet REAL, game_type TEXT,
            status TEXT DEFAULT 'open',
            rounds INTEGER DEFAULT 1, round_num INTEGER DEFAULT 1,
            creator_score INTEGER DEFAULT 0, opponent_score INTEGER DEFAULT 0,
            creator_move TEXT DEFAULT NULL, opponent_move TEXT DEFAULT NULL,
            winner_id INTEGER DEFAULT NULL, created_at TEXT
        )
    """)
    await db.execute("CREATE INDEX IF NOT EXISTS idx_pvp_status ON pvp_games(status)")

    await db.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER, type TEXT, message TEXT,
            status TEXT DEFAULT 'open',
            claimed_by INTEGER DEFAULT NULL,
            created_at TEXT
        )
    """)

    await db.execute("""
        CREATE TABLE IF NOT EXISTS ticket_replies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER NOT NULL,
            sender_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            created_at TEXT,
            FOREIGN KEY (ticket_id) REFERENCES tickets(id)
        )
    """)

    await db.execute("""
        CREATE TABLE IF NOT EXISTS nft_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            collection_num INTEGER DEFAULT 0,
            rarity_name TEXT DEFAULT 'Обычный',
            rarity_pct REAL DEFAULT 10.0,
            income_per_hour REAL DEFAULT 0,
            price REAL DEFAULT 0,
            status TEXT DEFAULT 'active',
            created_by INTEGER,
            created_at TEXT
        )
    """)

    await db.execute("""
        CREATE TABLE IF NOT EXISTS user_nfts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            nft_id INTEGER NOT NULL,
            bought_price REAL DEFAULT 0,
            created_at TEXT,
            FOREIGN KEY (nft_id) REFERENCES nft_templates(id)
        )
    """)
    await db.execute("CREATE INDEX IF NOT EXISTS idx_user_nfts ON user_nfts(user_id)")

    await db.execute("""
        CREATE TABLE IF NOT EXISTS nft_market (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            seller_id INTEGER NOT NULL,
            user_nft_id INTEGER NOT NULL,
            nft_id INTEGER NOT NULL,
            price REAL NOT NULL,
            status TEXT DEFAULT 'open',
            created_at TEXT,
            FOREIGN KEY (user_nft_id) REFERENCES user_nfts(id),
            FOREIGN KEY (nft_id) REFERENCES nft_templates(id)
        )
    """)
    await db.execute("CREATE INDEX IF NOT EXISTS idx_market_status ON nft_market(status)")

    await db.execute("""
        CREATE TABLE IF NOT EXISTS bot_settings (
            key TEXT PRIMARY KEY, value TEXT NOT NULL
        )
    """)

    await db.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY,
            username TEXT, added_by INTEGER, added_at TEXT,
            permissions TEXT DEFAULT '{}'
        )
    """)

    await db.execute("""
        CREATE TABLE IF NOT EXISTS admin_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE NOT NULL,
            created_by INTEGER, used_by INTEGER DEFAULT NULL,
            status TEXT DEFAULT 'active',
            created_at TEXT, used_at TEXT DEFAULT NULL
        )
    """)

    await db.execute("""
        CREATE TABLE IF NOT EXISTS admin_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id INTEGER NOT NULL, action TEXT NOT NULL,
            target_id INTEGER DEFAULT NULL,
            details TEXT DEFAULT NULL, created_at TEXT
        )
    """)

    await db.execute("""
        CREATE TABLE IF NOT EXISTS nft_trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER NOT NULL,
            receiver_id INTEGER DEFAULT NULL,
            offer_clicks REAL DEFAULT 0,
            want_clicks REAL DEFAULT 0,
            want_nft_count INTEGER DEFAULT 0,
            status TEXT DEFAULT 'pending',
            created_at TEXT
        )
    """)
    await db.execute("CREATE INDEX IF NOT EXISTS idx_trade_status ON nft_trades(status)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_trade_sender ON nft_trades(sender_id)")

    await db.execute("""
        CREATE TABLE IF NOT EXISTS nft_trade_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_id INTEGER NOT NULL,
            side TEXT NOT NULL,
            user_nft_id INTEGER NOT NULL,
            FOREIGN KEY (trade_id) REFERENCES nft_trades(id),
            FOREIGN KEY (user_nft_id) REFERENCES user_nfts(id)
        )
    """)
    await db.execute("CREATE INDEX IF NOT EXISTS idx_trade_items ON nft_trade_items(trade_id)")

    await db.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            nft_prize_name TEXT,
            nft_rarity INTEGER DEFAULT 3,
            nft_income REAL DEFAULT 0,
            bet_amount REAL DEFAULT 0,
            max_participants INTEGER DEFAULT 25,
            duration_min INTEGER DEFAULT 5,
            status TEXT DEFAULT 'active',
            created_by INTEGER, created_at TEXT, ends_at TEXT
        )
    """)
    await db.execute("CREATE INDEX IF NOT EXISTS idx_event_status ON events(status)")

    await db.execute("""
        CREATE TABLE IF NOT EXISTS event_participants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            bid_amount REAL DEFAULT 0,
            joined_at TEXT,
            UNIQUE(event_id, user_id),
            FOREIGN KEY (event_id) REFERENCES events(id)
        )
    """)

    await db.execute("""
        CREATE TABLE IF NOT EXISTS auction_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            chat_id INTEGER NOT NULL,
            message_id INTEGER NOT NULL,
            FOREIGN KEY (event_id) REFERENCES events(id)
        )
    """)

    await db.execute("""
        CREATE TABLE IF NOT EXISTS prize_claims (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            claimed_at TEXT,
            active INTEGER DEFAULT 1
        )
    """)

    await db.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            user2_id INTEGER DEFAULT NULL,
            amount REAL DEFAULT 0,
            details TEXT DEFAULT '',
            ref_id INTEGER DEFAULT NULL,
            status TEXT DEFAULT 'completed',
            created_at TEXT
        )
    """)
    await db.execute("CREATE INDEX IF NOT EXISTS idx_tx_user ON transactions(user_id)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_tx_type ON transactions(type)")

    await db.execute("""
        CREATE TABLE IF NOT EXISTS complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transaction_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            reason TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            admin_id INTEGER DEFAULT NULL,
            admin_action TEXT DEFAULT NULL,
            admin_comment TEXT DEFAULT NULL,
            created_at TEXT,
            resolved_at TEXT DEFAULT NULL,
            FOREIGN KEY (transaction_id) REFERENCES transactions(id)
        )
    """)

    # ━━━━━━━━━━━━━━━━━━━ Логи (для владельца — без кликов и доходов) ━━━━━━━━━━━━━━━━━━━
    await db.execute("""
        CREATE TABLE IF NOT EXISTS activity_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            details TEXT DEFAULT '',
            created_at TEXT
        )
    """)
    await db.execute("CREATE INDEX IF NOT EXISTS idx_actlog_user ON activity_logs(user_id)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_actlog_action ON activity_logs(action)")

    # ━━━━━━━━━━━━━━━━━━━ Заказы на оплату ━━━━━━━━━━━━━━━━━━━
    await db.execute("""
        CREATE TABLE IF NOT EXISTS payment_orders (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       INTEGER NOT NULL,
            package_type  TEXT NOT NULL,
            package_id    TEXT NOT NULL,
            pay_method    TEXT NOT NULL,
            amount_rub    REAL NOT NULL,
            status        TEXT DEFAULT 'pending',
            admin_id      INTEGER DEFAULT NULL,
            created_at    TEXT,
            resolved_at   TEXT DEFAULT NULL
        )
    """)

    # ━━━━━━━━━━━━━━━━━━━ Онлайн-отслеживание ━━━━━━━━━━━━━━━━━━━
    await db.execute("""
        CREATE TABLE IF NOT EXISTS online_users (
            user_id INTEGER PRIMARY KEY,
            last_seen TEXT
        )
    """)

    # ━━━━━━━━━━━━━━━━━━━ Лайки ━━━━━━━━━━━━━━━━━━━
    await db.execute("""
        CREATE TABLE IF NOT EXISTS user_likes (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            from_uid INTEGER NOT NULL,
            to_uid   INTEGER NOT NULL,
            created_at TEXT,
            UNIQUE(from_uid, to_uid)
        )
    """)
    await db.execute("CREATE INDEX IF NOT EXISTS idx_likes_to ON user_likes(to_uid)")

    # ━━━━━━━━━━━━━━━━━━━ Миграции для существующих таблиц ━━━━━━━━━━━━━━━━━━━
    migrations = [
        ("users", "nft_slots", "INTEGER DEFAULT 5"),
        ("users", "last_active", "TEXT DEFAULT NULL"),
        ("users", "income_capacity", "REAL DEFAULT 150"),
        ("users", "last_income_claim", "TEXT DEFAULT NULL"),
        ("users", "banned_until", "TEXT DEFAULT NULL"),
        ("users", "anonymous", "INTEGER DEFAULT 0"),
        ("admins", "permissions", "TEXT DEFAULT '{}'"),
        ("nft_templates", "collection_num", "INTEGER DEFAULT 0"),
        ("nft_templates", "rarity_name", "TEXT DEFAULT 'Обычный'"),
        ("nft_templates", "rarity_pct", "REAL DEFAULT 10.0"),
        ("nft_templates", "status", "TEXT DEFAULT 'active'"),
        ("events", "nft_rarity", "INTEGER DEFAULT 3"),
        ("events", "nft_income", "REAL DEFAULT 0"),
        ("events", "max_participants", "INTEGER DEFAULT 25"),
        ("event_participants", "bid_amount", "REAL DEFAULT 0"),
        ("nft_trades", "want_nft_count", "INTEGER DEFAULT 0"),
        ("tickets", "claimed_by", "INTEGER DEFAULT NULL"),
        ("pvp_games", "rounds", "INTEGER DEFAULT 1"),
        ("pvp_games", "round_num", "INTEGER DEFAULT 1"),
        ("pvp_games", "creator_score", "INTEGER DEFAULT 0"),
        ("pvp_games", "opponent_score", "INTEGER DEFAULT 0"),
        ("users", "vip_type", "TEXT DEFAULT NULL"),
        ("users", "vip_multiplier_click", "REAL DEFAULT 1"),
        ("users", "vip_multiplier_income", "REAL DEFAULT 1"),
        ("users", "vip_expires", "TEXT DEFAULT NULL"),
        ("payment_orders", "screenshot_file_id", "TEXT DEFAULT NULL"),
        ("users", "payment_banned", "INTEGER DEFAULT 0"),
        ("users", "pinned_nft_id", "INTEGER DEFAULT 0"),
        ("users", "likes", "INTEGER DEFAULT 0"),
    ]
    for table, col, typedef in migrations:
        try:
            await db.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typedef}")
        except Exception:
            pass

    await db.commit()


# ==========================================================
#  КЭШИРОВАНИЕ
# ==========================================================
def _invalidate(user_id: int):
    _user_cache.pop(user_id, None)
    _cache_ts.pop(user_id, None)


def invalidate_cache(user_id: int):
    _invalidate(user_id)


# ==========================================================
#  ПОЛЬЗОВАТЕЛИ
# ==========================================================
async def get_user(user_id: int):
    now = time.time()
    if user_id in _user_cache and (now - _cache_ts.get(user_id, 0)) < _CACHE_TTL:
        return _user_cache[user_id]
    db = await get_db()
    db.row_factory = aiosqlite.Row
    cur = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = await cur.fetchone()
    if row:
        _user_cache[user_id] = row
        _cache_ts[user_id] = now
    else:
        _invalidate(user_id)
    return row


async def create_user(user_id: int, username: str):
    from datetime import datetime
    db = await get_db()
    await db.execute(
        """INSERT OR IGNORE INTO users
           (user_id, username, clicks, rank, created_at)
           VALUES (?, ?, 0, 1, ?)""",
        (user_id, username, datetime.now().isoformat()),
    )
    await db.commit()


async def count_users() -> int:
    db = await get_db()
    cur = await db.execute("SELECT COUNT(*) FROM users WHERE is_banned = 0")
    return (await cur.fetchone())[0]


async def count_users_all() -> int:
    db = await get_db()
    cur = await db.execute("SELECT COUNT(*) FROM users")
    return (await cur.fetchone())[0]


async def is_user_banned(user_id: int) -> bool:
    u = await get_user(user_id)
    return bool(u and u["is_banned"])


# ━━━━━━━━━━━━━━━━━━━ Онлайн ━━━━━━━━━━━━━━━━━━━
async def set_user_online(user_id: int):
    from datetime import datetime
    db = await get_db()
    now = datetime.now().isoformat()
    await db.execute(
        "INSERT OR REPLACE INTO online_users (user_id, last_seen) VALUES (?, ?)",
        (user_id, now),
    )
    await db.execute(
        "UPDATE users SET last_active = ? WHERE user_id = ?", (now, user_id)
    )
    await db.commit()


async def get_online_count(minutes: int = 5) -> int:
    from datetime import datetime, timedelta
    db = await get_db()
    threshold = (datetime.now() - timedelta(minutes=minutes)).isoformat()
    cur = await db.execute(
        "SELECT COUNT(*) FROM online_users WHERE last_seen > ?", (threshold,)
    )
    return (await cur.fetchone())[0]


async def remove_user_online(user_id: int):
    db = await get_db()
    await db.execute("DELETE FROM online_users WHERE user_id = ?", (user_id,))
    await db.commit()


# ━━━━━━━━━━━━━━━━━━━ Клики ━━━━━━━━━━━━━━━━━━━
async def update_clicks(user_id: int, amount: float):
    db = await get_db()
    await db.execute(
        "UPDATE users SET clicks = clicks + ?, total_clicks = total_clicks + ? WHERE user_id = ?",
        (amount, max(amount, 0), user_id),
    )
    await db.commit()
    _invalidate(user_id)


async def set_clicks(user_id: int, amount: float):
    db = await get_db()
    await db.execute("UPDATE users SET clicks = ? WHERE user_id = ?", (amount, user_id))
    await db.commit()
    _invalidate(user_id)


async def update_bonus_click(user_id: int, amount: float):
    db = await get_db()
    await db.execute(
        "UPDATE users SET bonus_click = bonus_click + ? WHERE user_id = ?",
        (amount, user_id),
    )
    await db.commit()
    _invalidate(user_id)


async def update_passive_income(user_id: int, amount: float):
    db = await get_db()
    await db.execute(
        "UPDATE users SET passive_income = passive_income + ? WHERE user_id = ?",
        (amount, user_id),
    )
    await db.commit()
    _invalidate(user_id)


async def update_income_capacity(user_id: int, amount: float):
    db = await get_db()
    await db.execute(
        "UPDATE users SET income_capacity = income_capacity + ? WHERE user_id = ?",
        (amount, user_id),
    )
    await db.commit()
    _invalidate(user_id)


async def claim_passive_income(user_id: int) -> tuple[float, float]:
    """Собрать доход. Без ограничения в 1 час — накапливается за всё время."""
    from datetime import datetime
    db = await get_db()
    db.row_factory = aiosqlite.Row
    cur = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = await cur.fetchone()
    if not user:
        return 0.0, 0.0

    income_rate = float(user["passive_income"] or 0)
    capacity = float(user["income_capacity"] or 150)
    last_claim = user["last_income_claim"]

    if not last_claim:
        await db.execute(
            "UPDATE users SET last_income_claim = ? WHERE user_id = ?",
            (datetime.now().isoformat(), user_id),
        )
        await db.commit()
        _invalidate(user_id)
        return -1.0, 0.0

    try:
        last_dt = datetime.fromisoformat(last_claim)
    except (ValueError, TypeError):
        last_dt = datetime.now()

    diff = (datetime.now() - last_dt).total_seconds()
    hours = diff / 3600.0
    earned = min(income_rate * hours, capacity)

    # Применяем VIP-множитель дохода (inline, чтобы не зацикливаться)
    vip_mi = float(user["vip_multiplier_income"] or 1)
    vip_expires = user["vip_expires"]
    if vip_mi > 1 and vip_expires and vip_expires != "permanent":
        try:
            if datetime.now() > datetime.fromisoformat(vip_expires):
                vip_mi = 1.0  # VIP истёк
        except (ValueError, TypeError):
            pass
    earned *= vip_mi

    if earned < 0.01:
        remaining = max(60 - diff, 0)
        return 0.0, remaining

    await db.execute(
        "UPDATE users SET clicks = clicks + ?, last_income_claim = ? WHERE user_id = ?",
        (earned, datetime.now().isoformat(), user_id),
    )
    await db.commit()
    _invalidate(user_id)
    return earned, hours


# ━━━━━━━━━━━━━━━━━━━ НФТ слоты ━━━━━━━━━━━━━━━━━━━
async def get_user_nft_slots(user_id: int) -> int:
    user = await get_user(user_id)
    if not user:
        return 5
    try:
        return int(user["nft_slots"] or 5)
    except (KeyError, TypeError):
        return 5


async def add_nft_slot(user_id: int, count: int = 1):
    db = await get_db()
    await db.execute(
        "UPDATE users SET nft_slots = nft_slots + ? WHERE user_id = ?",
        (count, user_id),
    )
    await db.commit()
    _invalidate(user_id)


async def remove_nft_slot(user_id: int, count: int = 1):
    db = await get_db()
    await db.execute(
        "UPDATE users SET nft_slots = MAX(nft_slots - ?, 0) WHERE user_id = ?",
        (count, user_id),
    )
    await db.commit()
    _invalidate(user_id)


# ━━━━━━━━━━━━━━━━━━━ Ранги ━━━━━━━━━━━━━━━━━━━
async def update_rank(user_id: int):
    db = await get_db()
    db.row_factory = aiosqlite.Row
    cur = await db.execute("SELECT total_clicks, rank FROM users WHERE user_id = ?", (user_id,))
    row = await cur.fetchone()
    if not row:
        return
    tc = row["total_clicks"] or 0
    new_rank = 1
    for i, t in enumerate(RANK_THRESHOLDS):
        if tc >= t:
            new_rank = i + 1
    if new_rank != row["rank"]:
        await db.execute("UPDATE users SET rank = ? WHERE user_id = ?", (new_rank, user_id))
        await db.commit()
        _invalidate(user_id)


# ━━━━━━━━━━━━━━━━━━━ Рефералы ━━━━━━━━━━━━━━━━━━━
async def add_referral(user_id: int, referrer_id: int):
    from config import REF_FIRST_CLICKS, REF_FIRST_POWER, REF_EACH_CLICKS, REF_EACH_POWER
    db = await get_db()
    await db.execute("UPDATE users SET referrer_id = ? WHERE user_id = ?", (referrer_id, user_id))
    cur = await db.execute("SELECT referrals FROM users WHERE user_id = ?", (referrer_id,))
    row = await cur.fetchone()
    ref_count = (row[0] or 0) + 1
    await db.execute("UPDATE users SET referrals = ? WHERE user_id = ?", (ref_count, referrer_id))

    if ref_count == 1:
        await db.execute(
            "UPDATE users SET clicks = clicks + ?, bonus_click = bonus_click + ? WHERE user_id = ?",
            (REF_FIRST_CLICKS, REF_FIRST_POWER, referrer_id),
        )
    else:
        await db.execute(
            "UPDATE users SET clicks = clicks + ?, bonus_click = bonus_click + ? WHERE user_id = ?",
            (REF_EACH_CLICKS, REF_EACH_POWER, referrer_id),
        )
    # НФТ-слоты за рефералов отключены (теперь через подписку на канал)
    # from config import REF_NFT_SLOT_BONUS, REF_MAX_NFT_SLOTS
    # if REF_NFT_SLOT_BONUS and ref_count <= REF_MAX_NFT_SLOTS:
    #     await db.execute(
    #         "UPDATE users SET nft_slots = nft_slots + 1 WHERE user_id = ?", (referrer_id,)
    #     )
    await db.commit()
    _invalidate(referrer_id)
    _invalidate(user_id)


async def remove_referral_slot(referrer_id: int):
    """Убрать 1 слот НФТ (устаревшая функция, оставлена для совместимости)."""
    db = await get_db()
    await db.execute(
        "UPDATE users SET nft_slots = MAX(nft_slots - 1, 1) WHERE user_id = ?",
        (referrer_id,),
    )
    await db.commit()
    _invalidate(referrer_id)


# ━━━━━━━━━━━━━━━━━━━ Рейтинг ━━━━━━━━━━━━━━━━━━━
async def get_top_players(limit: int = 15, offset: int = 0):
    db = await get_db()
    cur = await db.execute(
        """SELECT user_id, username, clicks, bonus_click, passive_income,
                  rank, anonymous
           FROM users WHERE is_banned = 0
           ORDER BY clicks DESC LIMIT ? OFFSET ?""",
        (limit, offset),
    )
    return await cur.fetchall()


async def count_top_players() -> int:
    db = await get_db()
    cur = await db.execute("SELECT COUNT(*) FROM users WHERE is_banned = 0")
    row = await cur.fetchone()
    return row[0] if row else 0


async def get_user_anonymous(user_id: int) -> bool:
    u = await get_user(user_id)
    if not u:
        return False
    try:
        return bool(u["anonymous"])
    except (KeyError, TypeError):
        return False


async def set_user_anonymous(user_id: int, val: bool):
    db = await get_db()
    await db.execute("UPDATE users SET anonymous = ? WHERE user_id = ?", (1 if val else 0, user_id))
    await db.commit()
    _invalidate(user_id)


# ━━━━━━━━━━━━━━━━━━━ Лайки ━━━━━━━━━━━━━━━━━━━
async def has_liked(from_uid: int, to_uid: int) -> bool:
    db = await get_db()
    cur = await db.execute(
        "SELECT 1 FROM user_likes WHERE from_uid = ? AND to_uid = ?",
        (from_uid, to_uid),
    )
    return (await cur.fetchone()) is not None


async def add_like(from_uid: int, to_uid: int) -> bool:
    """Ставит лайк. Возвращает True если новый, False если уже стоит."""
    if from_uid == to_uid:
        return False
    if await has_liked(from_uid, to_uid):
        return False
    from datetime import datetime
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO user_likes (from_uid, to_uid, created_at) VALUES (?, ?, ?)",
            (from_uid, to_uid, datetime.now().isoformat()),
        )
        await db.execute(
            "UPDATE users SET likes = COALESCE(likes, 0) + 1 WHERE user_id = ?",
            (to_uid,),
        )
        await db.commit()
        _invalidate(to_uid)
        return True
    except Exception:
        return False


async def get_user_likes_count(user_id: int) -> int:
    db = await get_db()
    cur = await db.execute(
        "SELECT COUNT(*) FROM user_likes WHERE to_uid = ?", (user_id,),
    )
    return (await cur.fetchone())[0]


# ━━━━━━━━━━━━━━━━━━━ НФТ ━━━━━━━━━━━━━━━━━━━
async def count_user_nfts(user_id: int) -> int:
    db = await get_db()
    cur = await db.execute("SELECT COUNT(*) FROM user_nfts WHERE user_id = ?", (user_id,))
    return (await cur.fetchone())[0]


async def get_user_nfts(user_id: int):
    db = await get_db()
    cur = await db.execute(
        """SELECT un.id, t.name, t.income_per_hour, t.rarity_pct, t.rarity_name,
                  un.bought_price, un.created_at, t.collection_num
           FROM user_nfts un JOIN nft_templates t ON un.nft_id = t.id
           WHERE un.user_id = ?
           ORDER BY un.id""",
        (user_id,),
    )
    return await cur.fetchall()


async def get_user_nft_detail(user_nft_id: int):
    db = await get_db()
    cur = await db.execute(
        """SELECT un.id, un.user_id, un.nft_id, un.bought_price, un.created_at,
                  t.name, t.income_per_hour, t.rarity_pct, t.rarity_name,
                  t.price, t.collection_num
           FROM user_nfts un JOIN nft_templates t ON un.nft_id = t.id
           WHERE un.id = ?""",
        (user_nft_id,),
    )
    return await cur.fetchone()


async def buy_nft_template(user_id: int, template_id: int):
    from datetime import datetime
    db = await get_db()
    cur = await db.execute("SELECT * FROM nft_templates WHERE id = ? AND status = 'active'", (template_id,))
    tpl = await cur.fetchone()
    if not tpl:
        return None, "НФТ не найден"
    price = tpl[6] if isinstance(tpl, tuple) else tpl["price"]
    user = await get_user(user_id)
    if not user:
        return None, "Пользователь не найден"
    if float(user["clicks"]) < price:
        return None, "Недостаточно 💢"
    nft_count = await count_user_nfts(user_id)
    max_slots = await get_user_nft_slots(user_id)
    if nft_count >= max_slots:
        return None, "Нет свободных мест НФТ"
    await db.execute("UPDATE users SET clicks = clicks - ? WHERE user_id = ?", (price, user_id))
    await db.execute(
        "INSERT INTO user_nfts (user_id, nft_id, bought_price, created_at) VALUES (?, ?, ?, ?)",
        (user_id, template_id, price, datetime.now().isoformat()),
    )
    # Добавить доход
    income = tpl[5] if isinstance(tpl, tuple) else tpl["income_per_hour"]
    await db.execute(
        "UPDATE users SET passive_income = passive_income + ? WHERE user_id = ?",
        (income, user_id),
    )
    await db.commit()
    _invalidate(user_id)
    return template_id, "OK"


async def delete_user_nft(user_nft_id: int, user_id: int):
    """Удалить НФТ у пользователя. Стоит NFT_DELETE_COST."""
    from config import NFT_DELETE_COST
    db = await get_db()
    user = await get_user(user_id)
    if not user or float(user["clicks"]) < NFT_DELETE_COST:
        return False, "Недостаточно 💢"
    cur = await db.execute(
        """SELECT un.id, t.income_per_hour FROM user_nfts un
           JOIN nft_templates t ON un.nft_id = t.id
           WHERE un.id = ? AND un.user_id = ?""",
        (user_nft_id, user_id),
    )
    row = await cur.fetchone()
    if not row:
        return False, "НФТ не найден"
    income = row[1]
    await db.execute("DELETE FROM user_nfts WHERE id = ?", (user_nft_id,))
    await db.execute(
        "UPDATE users SET clicks = clicks - ?, passive_income = MAX(passive_income - ?, 0) WHERE user_id = ?",
        (NFT_DELETE_COST, income, user_id),
    )
    await db.commit()
    _invalidate(user_id)
    return True, "OK"


async def transfer_nft(user_nft_id: int, from_user: int, to_user: int):
    """Передать НФТ другому пользователю. Убирает доход у отправителя, добавляет получателю."""
    db = await get_db()
    cur = await db.execute(
        """SELECT un.id, t.income_per_hour FROM user_nfts un
           JOIN nft_templates t ON un.nft_id = t.id
           WHERE un.id = ? AND un.user_id = ?""",
        (user_nft_id, from_user),
    )
    row = await cur.fetchone()
    if not row:
        return False
    income = row[1]
    # Убираем доход у отправителя
    await db.execute(
        "UPDATE users SET passive_income = MAX(passive_income - ?, 0) WHERE user_id = ?",
        (income, from_user),
    )
    # Переносим НФТ
    await db.execute("UPDATE user_nfts SET user_id = ? WHERE id = ?", (to_user, user_nft_id))
    # Добавляем доход получателю
    await db.execute(
        "UPDATE users SET passive_income = passive_income + ? WHERE user_id = ?",
        (income, to_user),
    )
    await db.commit()
    _invalidate(from_user)
    _invalidate(to_user)
    return True


# ━━━━━━━━━━━━━━━━━━━ НФТ шаблоны ━━━━━━━━━━━━━━━━━━━
async def create_nft_template(name, rarity_name, rarity_pct, income, price, created_by, collection_num=0):
    from datetime import datetime
    db = await get_db()
    await db.execute(
        """INSERT INTO nft_templates
           (name, rarity_name, rarity_pct, income_per_hour, price, status, created_by, created_at, collection_num)
           VALUES (?, ?, ?, ?, ?, 'active', ?, ?, ?)""",
        (name, rarity_name, rarity_pct, income, price, created_by, datetime.now().isoformat(), collection_num),
    )
    await db.commit()
    cur = await db.execute("SELECT last_insert_rowid()")
    return (await cur.fetchone())[0]


async def get_nft_templates(status='active'):
    db = await get_db()
    cur = await db.execute(
        "SELECT * FROM nft_templates WHERE status = ? ORDER BY id", (status,)
    )
    return await cur.fetchall()


async def count_nft_templates(status='active') -> int:
    db = await get_db()
    cur = await db.execute(
        "SELECT COUNT(*) FROM nft_templates WHERE status = ?", (status,)
    )
    return (await cur.fetchone())[0]


async def get_nft_templates_page(page: int = 0, per_page: int = 5, status='active'):
    db = await get_db()
    offset = page * per_page
    cur = await db.execute(
        "SELECT * FROM nft_templates WHERE status = ? ORDER BY id LIMIT ? OFFSET ?",
        (status, per_page, offset),
    )
    return await cur.fetchall()


async def pin_nft(user_id: int, user_nft_id: int):
    db = await get_db()
    await db.execute("UPDATE users SET pinned_nft_id = ? WHERE user_id = ?", (user_nft_id, user_id))
    await db.commit()
    _invalidate(user_id)


async def unpin_nft(user_id: int):
    db = await get_db()
    await db.execute("UPDATE users SET pinned_nft_id = 0 WHERE user_id = ?", (user_id,))
    await db.commit()
    _invalidate(user_id)


async def get_user_pinned_nft(user_id: int):
    """Возвращает закреплённый НФТ (join) или None."""
    db = await get_db()
    user = await get_user(user_id)
    if not user:
        return None
    pid = user["pinned_nft_id"] if user["pinned_nft_id"] else 0
    if not pid:
        return None
    return await get_user_nft_detail(pid)


async def get_user_top_nfts(user_id: int, limit: int = 5):
    """Топ-5 НФТ пользователя по доходу."""
    db = await get_db()
    cur = await db.execute(
        """SELECT un.id, t.name, t.income_per_hour, t.rarity_pct, t.rarity_name,
                  un.bought_price, un.created_at, t.collection_num
           FROM user_nfts un JOIN nft_templates t ON un.nft_id = t.id
           WHERE un.user_id = ?
           ORDER BY t.income_per_hour DESC
           LIMIT ?""",
        (user_id, limit),
    )
    return await cur.fetchall()


async def get_nft_template(template_id: int):
    db = await get_db()
    db.row_factory = aiosqlite.Row
    cur = await db.execute("SELECT * FROM nft_templates WHERE id = ?", (template_id,))
    return await cur.fetchone()


async def delete_nft_template(template_id: int):
    db = await get_db()
    await db.execute("UPDATE nft_templates SET status = 'deleted' WHERE id = ?", (template_id,))
    await db.commit()


async def grant_nft_to_user(user_id: int, template_id: int, bought_price: float = 0):
    """Выдать НФТ пользователю напрямую (без проверки баланса/слотов)."""
    from datetime import datetime
    db = await get_db()
    await db.execute(
        "INSERT INTO user_nfts (user_id, nft_id, bought_price, created_at) VALUES (?, ?, ?, ?)",
        (user_id, template_id, bought_price, datetime.now().isoformat()),
    )
    await db.commit()
    cur = await db.execute("SELECT last_insert_rowid()")
    return (await cur.fetchone())[0]


# ━━━━━━━━━━━━━━━━━━━ НФТ маркет ━━━━━━━━━━━━━━━━━━━
async def create_market_listing(seller_id, user_nft_id, nft_id, price):
    from datetime import datetime
    db = await get_db()
    await db.execute(
        """INSERT INTO nft_market (seller_id, user_nft_id, nft_id, price, status, created_at)
           VALUES (?, ?, ?, ?, 'open', ?)""",
        (seller_id, user_nft_id, nft_id, price, datetime.now().isoformat()),
    )
    await db.commit()


async def get_market_listings(page=0, per_page=5):
    db = await get_db()
    offset = page * per_page
    cur = await db.execute(
        """SELECT m.id, m.seller_id, m.user_nft_id, m.nft_id, m.price,
                  t.name, t.rarity_name, t.rarity_pct, t.income_per_hour, t.collection_num
           FROM nft_market m JOIN nft_templates t ON m.nft_id = t.id
           WHERE m.status = 'open'
           ORDER BY m.created_at DESC LIMIT ? OFFSET ?""",
        (per_page, offset),
    )
    return await cur.fetchall()


async def count_market_listings() -> int:
    db = await get_db()
    cur = await db.execute("SELECT COUNT(*) FROM nft_market WHERE status = 'open'")
    return (await cur.fetchone())[0]


async def buy_market_listing(listing_id: int, buyer_id: int):
    db = await get_db()
    db.row_factory = aiosqlite.Row
    cur = await db.execute("SELECT * FROM nft_market WHERE id = ? AND status = 'open'", (listing_id,))
    listing = await cur.fetchone()
    if not listing:
        return False, "Листинг не найден"
    price = listing["price"]
    seller_id = listing["seller_id"]
    user_nft_id = listing["user_nft_id"]
    nft_id = listing["nft_id"]

    buyer = await get_user(buyer_id)
    if float(buyer["clicks"]) < price:
        return False, "Недостаточно 💢"

    nft_count = await count_user_nfts(buyer_id)
    max_slots = await get_user_nft_slots(buyer_id)
    if nft_count >= max_slots:
        return False, "Нет свободных мест НФТ"

    # Получить доход НФТ
    cur2 = await db.execute("SELECT income_per_hour FROM nft_templates WHERE id = ?", (nft_id,))
    tpl = await cur2.fetchone()
    income = tpl["income_per_hour"] if tpl else 0

    # Снять деньги у покупателя, дать продавцу
    await db.execute("UPDATE users SET clicks = clicks - ? WHERE user_id = ?", (price, buyer_id))
    await db.execute("UPDATE users SET clicks = clicks + ? WHERE user_id = ?", (price, seller_id))

    # Убрать доход у продавца, дать покупателю
    await db.execute(
        "UPDATE users SET passive_income = MAX(passive_income - ?, 0) WHERE user_id = ?",
        (income, seller_id),
    )
    await db.execute(
        "UPDATE users SET passive_income = passive_income + ? WHERE user_id = ?",
        (income, buyer_id),
    )

    # Перенести НФТ
    await db.execute("UPDATE user_nfts SET user_id = ? WHERE id = ?", (buyer_id, user_nft_id))
    await db.execute("UPDATE nft_market SET status = 'sold' WHERE id = ?", (listing_id,))
    await db.commit()
    _invalidate(buyer_id)
    _invalidate(seller_id)
    return True, "OK"


async def cancel_market_listing(listing_id: int, seller_id: int):
    db = await get_db()
    await db.execute(
        "UPDATE nft_market SET status = 'cancelled' WHERE id = ? AND seller_id = ?",
        (listing_id, seller_id),
    )
    await db.commit()


async def get_nft_on_sale(user_nft_id: int):
    db = await get_db()
    cur = await db.execute(
        "SELECT id FROM nft_market WHERE user_nft_id = ? AND status = 'open'",
        (user_nft_id,),
    )
    return await cur.fetchone()


# ━━━━━━━━━━━━━━━━━━━ Бан/Разбан ━━━━━━━━━━━━━━━━━━━
async def ban_user(user_id: int, duration: str = None):
    from datetime import datetime, timedelta
    db = await get_db()
    banned_until = None
    if duration and duration != "permanent":
        hours = int(duration)
        banned_until = (datetime.now() + timedelta(hours=hours)).isoformat()
    await db.execute(
        "UPDATE users SET is_banned = 1, banned_until = ? WHERE user_id = ?",
        (banned_until, user_id),
    )
    await db.commit()
    _invalidate(user_id)


async def unban_user(user_id: int):
    db = await get_db()
    await db.execute(
        "UPDATE users SET is_banned = 0, banned_until = NULL WHERE user_id = ?",
        (user_id,),
    )
    await db.commit()
    _invalidate(user_id)


async def get_banned_users(page=0, per_page=10):
    db = await get_db()
    offset = page * per_page
    cur = await db.execute(
        "SELECT user_id, username, banned_until FROM users WHERE is_banned = 1 LIMIT ? OFFSET ?",
        (per_page, offset),
    )
    return await cur.fetchall()


async def count_banned_users() -> int:
    db = await get_db()
    cur = await db.execute("SELECT COUNT(*) FROM users WHERE is_banned = 1")
    return (await cur.fetchone())[0]


# ━━━━━━━━━━━━━━━━━━━ Все пользователи (пагинация) ━━━━━━━━━━━━━━━━━━━
async def get_users_page(page=0, per_page=10):
    db = await get_db()
    offset = page * per_page
    cur = await db.execute(
        """SELECT user_id, username, clicks, rank, is_banned
           FROM users ORDER BY clicks DESC LIMIT ? OFFSET ?""",
        (per_page, offset),
    )
    return await cur.fetchall()


# ━━━━━━━━━━━━━━━━━━━ Сброс участника ━━━━━━━━━━━━━━━━━━━
async def reset_user_progress(user_id: int):
    db = await get_db()
    await db.execute(
        """UPDATE users SET clicks = 0, total_clicks = 0, bonus_click = 0,
           passive_income = 0, income_capacity = 150, rank = 1,
           last_income_claim = NULL WHERE user_id = ?""",
        (user_id,),
    )
    await db.execute("DELETE FROM user_nfts WHERE user_id = ?", (user_id,))
    await db.commit()
    _invalidate(user_id)


async def reset_user_clicks(user_id: int):
    db = await get_db()
    await db.execute("UPDATE users SET clicks = 0 WHERE user_id = ?", (user_id,))
    await db.commit()
    _invalidate(user_id)


async def reset_all_users():
    db = await get_db()
    # Сохраняем клики пользователей с одобренными заказами на покупку кликов
    cur = await db.execute(
        "SELECT DISTINCT user_id FROM payment_orders WHERE package_type = 'clicks' AND status = 'approved'"
    )
    paid_users = {row[0] for row in await cur.fetchall()}
    # Сбрасываем прогресс, НО сохраняем: VIP, рефералов
    await db.execute(
        """UPDATE users SET total_clicks = 0, bonus_click = 0,
           passive_income = 0, income_capacity = 150, rank = 1,
           nft_slots = 5, last_income_claim = NULL"""
    )
    # Обнуляем клики только тем, кто НЕ покупал
    if paid_users:
        placeholders = ",".join("?" for _ in paid_users)
        await db.execute(
            f"UPDATE users SET clicks = 0 WHERE user_id NOT IN ({placeholders})",
            tuple(paid_users),
        )
    else:
        await db.execute("UPDATE users SET clicks = 0")
    await db.execute("DELETE FROM user_nfts")
    await db.execute("DELETE FROM nft_market")
    await db.commit()
    _user_cache.clear()
    _cache_ts.clear()


# ━━━━━━━━━━━━━━━━━━━ Тикеты ━━━━━━━━━━━━━━━━━━━
async def create_ticket(user_id: int, ttype: str, message: str):
    from datetime import datetime
    db = await get_db()
    await db.execute(
        "INSERT INTO tickets (user_id, type, message, created_at) VALUES (?, ?, ?, ?)",
        (user_id, ttype, message, datetime.now().isoformat()),
    )
    await db.commit()


async def get_open_tickets(page=0, per_page=5):
    db = await get_db()
    offset = page * per_page
    cur = await db.execute(
        "SELECT id, user_id, type, message, created_at FROM tickets WHERE status = 'open' ORDER BY id DESC LIMIT ? OFFSET ?",
        (per_page, offset),
    )
    return await cur.fetchall()


async def count_open_tickets() -> int:
    db = await get_db()
    cur = await db.execute("SELECT COUNT(*) FROM tickets WHERE status = 'open'")
    return (await cur.fetchone())[0]


async def get_ticket(ticket_id: int):
    db = await get_db()
    db.row_factory = aiosqlite.Row
    cur = await db.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
    return await cur.fetchone()


async def close_ticket(ticket_id: int):
    db = await get_db()
    await db.execute("UPDATE tickets SET status = 'closed' WHERE id = ?", (ticket_id,))
    await db.commit()


async def add_ticket_reply(ticket_id: int, sender_id: int, message: str):
    from datetime import datetime
    db = await get_db()
    await db.execute(
        "INSERT INTO ticket_replies (ticket_id, sender_id, message, created_at) VALUES (?, ?, ?, ?)",
        (ticket_id, sender_id, message, datetime.now().isoformat()),
    )
    await db.commit()


async def get_ticket_replies(ticket_id: int):
    db = await get_db()
    cur = await db.execute(
        "SELECT sender_id, message, created_at FROM ticket_replies WHERE ticket_id = ? ORDER BY id",
        (ticket_id,),
    )
    return await cur.fetchall()


async def get_user_tickets(user_id: int):
    db = await get_db()
    cur = await db.execute(
        "SELECT id, type, message, status, created_at FROM tickets WHERE user_id = ? ORDER BY id DESC",
        (user_id,),
    )
    return await cur.fetchall()


# ━━━━━━━━━━━━━━━━━━━ Администраторы ━━━━━━━━━━━━━━━━━━━
async def is_admin(user_id: int) -> bool:
    db = await get_db()
    cur = await db.execute("SELECT user_id FROM admins WHERE user_id = ?", (user_id,))
    return (await cur.fetchone()) is not None


async def add_admin(user_id: int, username: str, added_by: int):
    from datetime import datetime
    db = await get_db()
    await db.execute(
        "INSERT OR REPLACE INTO admins (user_id, username, added_by, added_at) VALUES (?, ?, ?, ?)",
        (user_id, username, added_by, datetime.now().isoformat()),
    )
    await db.commit()


async def remove_admin(user_id: int):
    db = await get_db()
    await db.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
    await db.commit()


async def get_all_admins():
    db = await get_db()
    cur = await db.execute("SELECT user_id, username, added_at FROM admins ORDER BY added_at")
    return await cur.fetchall()


async def get_admin_permissions(user_id: int) -> dict:
    import json
    db = await get_db()
    cur = await db.execute("SELECT permissions FROM admins WHERE user_id = ?", (user_id,))
    row = await cur.fetchone()
    if not row or not row[0]:
        return {}
    try:
        return json.loads(row[0])
    except (json.JSONDecodeError, TypeError):
        return {}


async def set_admin_permissions(user_id: int, perms: dict):
    import json
    db = await get_db()
    await db.execute(
        "UPDATE admins SET permissions = ? WHERE user_id = ?",
        (json.dumps(perms), user_id),
    )
    await db.commit()


# ━━━━━━━━━━━━━━━━━━━ Ключи для админа ━━━━━━━━━━━━━━━━━━━
async def create_admin_key(key: str, created_by: int):
    from datetime import datetime
    db = await get_db()
    await db.execute(
        "INSERT INTO admin_keys (key, created_by, created_at) VALUES (?, ?, ?)",
        (key, created_by, datetime.now().isoformat()),
    )
    await db.commit()


async def use_admin_key(key: str, user_id: int):
    from datetime import datetime
    db = await get_db()
    cur = await db.execute(
        "SELECT id, created_by FROM admin_keys WHERE key = ? AND status = 'active'", (key,)
    )
    row = await cur.fetchone()
    if not row:
        return False
    await db.execute(
        "UPDATE admin_keys SET status = 'used', used_by = ?, used_at = ? WHERE id = ?",
        (user_id, datetime.now().isoformat(), row[0]),
    )
    await db.commit()
    return True


async def get_all_admin_keys():
    db = await get_db()
    cur = await db.execute("SELECT id, key, status, created_by, used_by, created_at FROM admin_keys ORDER BY id DESC")
    return await cur.fetchall()


# ━━━━━━━━━━━━━━━━━━━ Логи действий админов ━━━━━━━━━━━━━━━━━━━
async def log_admin_action(admin_id: int, action: str, target_id: int = None, details: str = None):
    from datetime import datetime
    db = await get_db()
    await db.execute(
        "INSERT INTO admin_actions (admin_id, action, target_id, details, created_at) VALUES (?, ?, ?, ?, ?)",
        (admin_id, action, target_id, details, datetime.now().isoformat()),
    )
    await db.commit()


async def get_admin_actions(admin_id: int = None, limit: int = 20):
    db = await get_db()
    if admin_id:
        cur = await db.execute(
            "SELECT * FROM admin_actions WHERE admin_id = ? ORDER BY id DESC LIMIT ?",
            (admin_id, limit),
        )
    else:
        cur = await db.execute(
            "SELECT * FROM admin_actions ORDER BY id DESC LIMIT ?", (limit,)
        )
    return await cur.fetchall()


# ━━━━━━━━━━━━━━━━━━━ Логи активности (для владельца — без кликов/доходов) ━━━━━━━━━━━━━━━━━━━
async def log_activity(user_id: int, action: str, details: str = ""):
    from datetime import datetime
    db = await get_db()
    await db.execute(
        "INSERT INTO activity_logs (user_id, action, details, created_at) VALUES (?, ?, ?, ?)",
        (user_id, action, details, datetime.now().isoformat()),
    )
    await db.commit()


async def get_activity_logs(user_id: int = None, action: str = None, page: int = 0, per_page: int = 10):
    db = await get_db()
    q = "SELECT * FROM activity_logs WHERE 1=1"
    params = []
    if user_id:
        q += " AND user_id = ?"
        params.append(user_id)
    if action:
        q += " AND action = ?"
        params.append(action)
    q += " ORDER BY id DESC LIMIT ? OFFSET ?"
    params.extend([per_page, page * per_page])
    cur = await db.execute(q, params)
    return await cur.fetchall()


async def count_activity_logs(user_id: int = None, action: str = None) -> int:
    db = await get_db()
    q = "SELECT COUNT(*) FROM activity_logs WHERE 1=1"
    params = []
    if user_id:
        q += " AND user_id = ?"
        params.append(user_id)
    if action:
        q += " AND action = ?"
        params.append(action)
    cur = await db.execute(q, params)
    return (await cur.fetchone())[0]


# ━━━━━━━━━━━━━━━━━━━ Чаты ━━━━━━━━━━━━━━━━━━━
async def chat_queue_add(user_id: int):
    db = await get_db()
    await db.execute("INSERT OR IGNORE INTO chat_queue (user_id) VALUES (?)", (user_id,))
    await db.commit()


async def chat_queue_remove(user_id: int):
    db = await get_db()
    await db.execute("DELETE FROM chat_queue WHERE user_id = ?", (user_id,))
    await db.commit()


async def chat_queue_find_partner(user_id: int):
    db = await get_db()
    cur = await db.execute("SELECT user_id FROM chat_queue WHERE user_id != ? LIMIT 1", (user_id,))
    row = await cur.fetchone()
    return row[0] if row else None


async def create_active_chat(u1: int, u2: int) -> int:
    from datetime import datetime
    db = await get_db()
    await db.execute(
        "INSERT INTO active_chats (u1, u2, created_at) VALUES (?, ?, ?)",
        (u1, u2, datetime.now().isoformat()),
    )
    await db.commit()
    cur = await db.execute("SELECT last_insert_rowid()")
    return (await cur.fetchone())[0]


async def get_active_chat(user_id: int):
    db = await get_db()
    cur = await db.execute(
        "SELECT id, u1, u2 FROM active_chats WHERE u1 = ? OR u2 = ?",
        (user_id, user_id),
    )
    return await cur.fetchone()


async def end_active_chat(chat_id: int):
    db = await get_db()
    await db.execute("DELETE FROM active_chats WHERE id = ?", (chat_id,))
    await db.commit()


async def get_all_active_chats():
    """Все активные чаты для владельца."""
    db = await get_db()
    cur = await db.execute(
        "SELECT id, u1, u2, created_at FROM active_chats ORDER BY id DESC"
    )
    return await cur.fetchall()


async def get_active_chat_by_id(chat_id: int):
    """Получить активный чат по ID."""
    db = await get_db()
    cur = await db.execute(
        "SELECT id, u1, u2, created_at FROM active_chats WHERE id = ?",
        (chat_id,),
    )
    return await cur.fetchone()


async def count_chat_messages(chat_id: int) -> int:
    db = await get_db()
    cur = await db.execute(
        "SELECT COUNT(*) FROM chat_logs WHERE chat_id = ?", (chat_id,)
    )
    return (await cur.fetchone())[0]


async def add_chat_log(chat_id: int, sender_id: int, message: str):
    from datetime import datetime
    db = await get_db()
    await db.execute(
        "INSERT INTO chat_logs (chat_id, sender_id, message, created_at) VALUES (?, ?, ?, ?)",
        (chat_id, sender_id, message, datetime.now().isoformat()),
    )
    await db.commit()


async def get_chat_logs_list(page=0, per_page=10):
    db = await get_db()
    offset = page * per_page
    cur = await db.execute(
        """SELECT DISTINCT chat_id, MIN(created_at) as started
           FROM chat_logs GROUP BY chat_id ORDER BY started DESC LIMIT ? OFFSET ?""",
        (per_page, offset),
    )
    return await cur.fetchall()


async def get_chat_messages(chat_id: int, page=0, per_page=20):
    db = await get_db()
    offset = page * per_page
    cur = await db.execute(
        "SELECT sender_id, message, created_at FROM chat_logs WHERE chat_id = ? ORDER BY id LIMIT ? OFFSET ?",
        (chat_id, per_page, offset),
    )
    return await cur.fetchall()


# ━━━━━━━━━━━━━━━━━━━ PvP ━━━━━━━━━━━━━━━━━━━
async def create_pvp_game(creator_id: int, bet: float, game_type: str, rounds: int = 1):
    from datetime import datetime
    db = await get_db()
    await db.execute(
        """INSERT INTO pvp_games (creator_id, bet, game_type, rounds, status, created_at)
           VALUES (?, ?, ?, ?, 'open', ?)""",
        (creator_id, bet, game_type, rounds, datetime.now().isoformat()),
    )
    await db.execute("UPDATE users SET clicks = clicks - ? WHERE user_id = ?", (bet, creator_id))
    await db.commit()
    _invalidate(creator_id)
    cur = await db.execute("SELECT last_insert_rowid()")
    return (await cur.fetchone())[0]


async def get_open_pvp_games():
    db = await get_db()
    cur = await db.execute(
        "SELECT id, creator_id, bet, game_type, rounds FROM pvp_games WHERE status = 'open' ORDER BY id DESC"
    )
    return await cur.fetchall()


async def get_pvp_game(game_id: int):
    db = await get_db()
    db.row_factory = aiosqlite.Row
    cur = await db.execute("SELECT * FROM pvp_games WHERE id = ?", (game_id,))
    return await cur.fetchone()


async def join_pvp_game(game_id: int, opponent_id: int):
    db = await get_db()
    game = await get_pvp_game(game_id)
    if not game or game["status"] != 'open':
        return False
    bet = game["bet"]
    user = await get_user(opponent_id)
    if float(user["clicks"]) < bet:
        return False
    await db.execute("UPDATE users SET clicks = clicks - ? WHERE user_id = ?", (bet, opponent_id))
    await db.execute(
        "UPDATE pvp_games SET opponent_id = ?, status = 'active' WHERE id = ?",
        (opponent_id, game_id),
    )
    await db.commit()
    _invalidate(opponent_id)
    return True


async def set_pvp_move(game_id: int, user_id: int, move: str):
    db = await get_db()
    game = await get_pvp_game(game_id)
    if not game:
        return
    if user_id == game["creator_id"]:
        await db.execute("UPDATE pvp_games SET creator_move = ? WHERE id = ?", (move, game_id))
    else:
        await db.execute("UPDATE pvp_games SET opponent_move = ? WHERE id = ?", (move, game_id))
    await db.commit()


async def finish_pvp_game(game_id: int, winner_id: int):
    db = await get_db()
    game = await get_pvp_game(game_id)
    if not game:
        return
    bet = game["bet"]
    prize = bet * 2
    await db.execute(
        "UPDATE pvp_games SET winner_id = ?, status = 'finished' WHERE id = ?",
        (winner_id, game_id),
    )
    await db.execute("UPDATE users SET clicks = clicks + ? WHERE user_id = ?", (prize, winner_id))
    await db.commit()
    _invalidate(winner_id)
    _invalidate(game["creator_id"])
    _invalidate(game["opponent_id"])


async def draw_pvp_game(game_id: int):
    db = await get_db()
    game = await get_pvp_game(game_id)
    if not game:
        return
    bet = game["bet"]
    await db.execute("UPDATE pvp_games SET status = 'draw' WHERE id = ?", (game_id,))
    await db.execute("UPDATE users SET clicks = clicks + ? WHERE user_id = ?", (bet, game["creator_id"]))
    await db.execute("UPDATE users SET clicks = clicks + ? WHERE user_id = ?", (bet, game["opponent_id"]))
    await db.commit()
    _invalidate(game["creator_id"])
    _invalidate(game["opponent_id"])


async def cancel_pvp_game(game_id: int):
    db = await get_db()
    game = await get_pvp_game(game_id)
    if not game:
        return
    await db.execute("UPDATE pvp_games SET status = 'cancelled' WHERE id = ?", (game_id,))
    await db.execute("UPDATE users SET clicks = clicks + ? WHERE user_id = ?", (game["bet"], game["creator_id"]))
    await db.commit()
    _invalidate(game["creator_id"])


async def update_pvp_round(game_id: int, creator_score: int, opponent_score: int, round_num: int):
    db = await get_db()
    await db.execute(
        """UPDATE pvp_games SET creator_score = ?, opponent_score = ?,
           round_num = ?, creator_move = NULL, opponent_move = NULL WHERE id = ?""",
        (creator_score, opponent_score, round_num, game_id),
    )
    await db.commit()


async def get_user_pvp_history(user_id: int, limit=10):
    db = await get_db()
    cur = await db.execute(
        """SELECT id, creator_id, opponent_id, bet, game_type, status, winner_id, rounds
           FROM pvp_games WHERE (creator_id = ? OR opponent_id = ?) AND status IN ('finished','draw')
           ORDER BY id DESC LIMIT ?""",
        (user_id, user_id, limit),
    )
    return await cur.fetchall()


# ━━━━━━━━━━━━━━━━━━━ Обмены НФТ ━━━━━━━━━━━━━━━━━━━
async def create_trade(sender_id: int, offer_nft_ids: list, want_clicks: float = 0):
    from datetime import datetime
    db = await get_db()
    await db.execute(
        """INSERT INTO nft_trades (sender_id, offer_clicks, want_clicks, status, created_at)
           VALUES (?, 0, ?, 'open', ?)""",
        (sender_id, want_clicks, datetime.now().isoformat()),
    )
    cur = await db.execute("SELECT last_insert_rowid()")
    trade_id = (await cur.fetchone())[0]
    for nft_id in offer_nft_ids:
        await db.execute(
            "INSERT INTO nft_trade_items (trade_id, side, user_nft_id) VALUES (?, 'offer', ?)",
            (trade_id, nft_id),
        )
    await db.commit()
    return trade_id


async def get_open_trades(page=0, per_page=5):
    db = await get_db()
    offset = page * per_page
    cur = await db.execute(
        """SELECT t.id, t.sender_id, t.want_clicks, t.created_at,
                  GROUP_CONCAT(ti.user_nft_id) as nft_ids
           FROM nft_trades t LEFT JOIN nft_trade_items ti ON t.id = ti.trade_id AND ti.side = 'offer'
           WHERE t.status = 'open'
           GROUP BY t.id ORDER BY t.id DESC LIMIT ? OFFSET ?""",
        (per_page, offset),
    )
    return await cur.fetchall()


async def count_open_trades() -> int:
    db = await get_db()
    cur = await db.execute("SELECT COUNT(*) FROM nft_trades WHERE status = 'open'")
    return (await cur.fetchone())[0]


async def get_trade(trade_id: int):
    db = await get_db()
    db.row_factory = aiosqlite.Row
    cur = await db.execute("SELECT * FROM nft_trades WHERE id = ?", (trade_id,))
    return await cur.fetchone()


async def get_trade_items(trade_id: int, side: str = 'offer'):
    db = await get_db()
    cur = await db.execute(
        """SELECT ti.user_nft_id, t.name, t.rarity_name, t.income_per_hour
           FROM nft_trade_items ti JOIN user_nfts un ON ti.user_nft_id = un.id
           JOIN nft_templates t ON un.nft_id = t.id
           WHERE ti.trade_id = ? AND ti.side = ?""",
        (trade_id, side),
    )
    return await cur.fetchall()


async def propose_trade(trade_id: int, buyer_id: int, offer_nft_ids: list):
    """Покупатель предлагает свои НФТ продавцу."""
    from datetime import datetime
    db = await get_db()
    await db.execute(
        "UPDATE nft_trades SET receiver_id = ?, status = 'proposed' WHERE id = ?",
        (buyer_id, trade_id),
    )
    for nft_id in offer_nft_ids:
        await db.execute(
            "INSERT INTO nft_trade_items (trade_id, side, user_nft_id) VALUES (?, 'propose', ?)",
            (trade_id, nft_id),
        )
    await db.commit()


async def accept_trade(trade_id: int):
    """Продавец принимает обмен. Все НФТ меняются местами."""
    db = await get_db()
    trade = await get_trade(trade_id)
    if not trade:
        return False
    sender_id = trade["sender_id"]
    receiver_id = trade["receiver_id"]

    # Получить offer НФТ (от продавца)
    offer_items = await get_trade_items(trade_id, 'offer')
    # Получить propose НФТ (от покупателя)
    propose_items = await get_trade_items(trade_id, 'propose')

    # Если есть клики
    want_clicks = float(trade["want_clicks"] or 0)
    if want_clicks > 0:
        buyer = await get_user(receiver_id)
        if float(buyer["clicks"]) < want_clicks:
            return False
        await db.execute("UPDATE users SET clicks = clicks - ? WHERE user_id = ?", (want_clicks, receiver_id))
        await db.execute("UPDATE users SET clicks = clicks + ? WHERE user_id = ?", (want_clicks, sender_id))

    # Переносим offer НФТ → покупателю
    for item in offer_items:
        await transfer_nft(item[0], sender_id, receiver_id)

    # Переносим propose НФТ → продавцу
    for item in propose_items:
        await transfer_nft(item[0], receiver_id, sender_id)

    await db.execute("UPDATE nft_trades SET status = 'completed' WHERE id = ?", (trade_id,))
    await db.commit()
    _invalidate(sender_id)
    _invalidate(receiver_id)
    return True


async def reject_trade(trade_id: int):
    db = await get_db()
    await db.execute("UPDATE nft_trades SET status = 'rejected' WHERE id = ?", (trade_id,))
    await db.commit()


async def cancel_trade(trade_id: int):
    db = await get_db()
    await db.execute("UPDATE nft_trades SET status = 'cancelled' WHERE id = ?", (trade_id,))
    await db.commit()


# ━━━━━━━━━━━━━━━━━━━ Входящие предложения обмена ━━━━━━━━━━━━━━━━━━━
async def get_incoming_trades(user_id: int):
    db = await get_db()
    cur = await db.execute(
        """SELECT id, sender_id, receiver_id, want_clicks, status, created_at
           FROM nft_trades WHERE sender_id = ? AND status = 'proposed'
           ORDER BY id DESC""",
        (user_id,),
    )
    return await cur.fetchall()


# ━━━━━━━━━━━━━━━━━━━ Ивенты ━━━━━━━━━━━━━━━━━━━
async def create_event(name, nft_name, nft_rarity, nft_income, bet, duration, max_part, created_by):
    from datetime import datetime, timedelta
    db = await get_db()
    now = datetime.now()
    ends = now + timedelta(minutes=duration)
    await db.execute(
        """INSERT INTO events (name, nft_prize_name, nft_rarity, nft_income, bet_amount,
           duration_min, max_participants, status, created_by, created_at, ends_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?)""",
        (name, nft_name, nft_rarity, nft_income, bet, duration, max_part,
         created_by, now.isoformat(), ends.isoformat()),
    )
    await db.commit()
    cur = await db.execute("SELECT last_insert_rowid()")
    return (await cur.fetchone())[0]


async def get_active_events():
    db = await get_db()
    db.row_factory = aiosqlite.Row
    cur = await db.execute("SELECT * FROM events WHERE status = 'active' ORDER BY id DESC")
    return await cur.fetchall()


async def get_event(event_id: int):
    db = await get_db()
    db.row_factory = aiosqlite.Row
    cur = await db.execute("SELECT * FROM events WHERE id = ?", (event_id,))
    return await cur.fetchone()


async def join_event(event_id: int, user_id: int, bid: float):
    from datetime import datetime
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO event_participants (event_id, user_id, bid_amount, joined_at) VALUES (?, ?, ?, ?)",
            (event_id, user_id, bid, datetime.now().isoformat()),
        )
        await db.execute("UPDATE users SET clicks = clicks - ? WHERE user_id = ?", (bid, user_id))
        await db.commit()
        _invalidate(user_id)
        return True
    except Exception:
        return False


async def update_event_bid(event_id: int, user_id: int, new_bid: float, additional: float):
    db = await get_db()
    await db.execute(
        "UPDATE event_participants SET bid_amount = ? WHERE event_id = ? AND user_id = ?",
        (new_bid, event_id, user_id),
    )
    await db.execute("UPDATE users SET clicks = clicks - ? WHERE user_id = ?", (additional, user_id))
    await db.commit()
    _invalidate(user_id)


async def get_event_participants(event_id: int):
    db = await get_db()
    cur = await db.execute(
        """SELECT ep.user_id, ep.bid_amount, u.username
           FROM event_participants ep JOIN users u ON ep.user_id = u.user_id
           WHERE ep.event_id = ? ORDER BY ep.bid_amount DESC""",
        (event_id,),
    )
    return await cur.fetchall()


async def count_event_participants(event_id: int) -> int:
    db = await get_db()
    cur = await db.execute("SELECT COUNT(*) FROM event_participants WHERE event_id = ?", (event_id,))
    return (await cur.fetchone())[0]


async def get_user_event_bid(event_id: int, user_id: int):
    db = await get_db()
    cur = await db.execute(
        "SELECT bid_amount FROM event_participants WHERE event_id = ? AND user_id = ?",
        (event_id, user_id),
    )
    row = await cur.fetchone()
    return row[0] if row else None


async def get_highest_bidder(event_id: int):
    db = await get_db()
    cur = await db.execute(
        "SELECT user_id, bid_amount FROM event_participants WHERE event_id = ? ORDER BY bid_amount DESC LIMIT 1",
        (event_id,),
    )
    return await cur.fetchone()


async def finish_event(event_id: int):
    db = await get_db()
    await db.execute("UPDATE events SET status = 'finished' WHERE id = ?", (event_id,))
    await db.commit()


async def cancel_event(event_id: int):
    db = await get_db()
    await db.execute("UPDATE events SET status = 'cancelled' WHERE id = ?", (event_id,))
    # Вернуть ставки
    cur = await db.execute("SELECT user_id, bid_amount FROM event_participants WHERE event_id = ?", (event_id,))
    rows = await cur.fetchall()
    for uid, bid in rows:
        await db.execute("UPDATE users SET clicks = clicks + ? WHERE user_id = ?", (bid, uid))
        _invalidate(uid)
    await db.commit()


async def save_auction_message(event_id: int, chat_id: int, message_id: int):
    db = await get_db()
    await db.execute(
        "INSERT INTO auction_messages (event_id, chat_id, message_id) VALUES (?, ?, ?)",
        (event_id, chat_id, message_id),
    )
    await db.commit()


async def get_auction_messages(event_id: int):
    db = await get_db()
    cur = await db.execute(
        "SELECT chat_id, message_id FROM auction_messages WHERE event_id = ?", (event_id,)
    )
    return await cur.fetchall()


async def delete_auction_messages(event_id: int):
    db = await get_db()
    await db.execute("DELETE FROM auction_messages WHERE event_id = ?", (event_id,))
    await db.commit()


# ━━━━━━━━━━━━━━━━━━━ Приз ━━━━━━━━━━━━━━━━━━━
async def get_prize_claim(user_id: int):
    db = await get_db()
    cur = await db.execute("SELECT id, user_id, claimed_at, active FROM prize_claims WHERE user_id = ?", (user_id,))
    return await cur.fetchone()


async def set_prize_claim(user_id: int):
    from datetime import datetime
    db = await get_db()
    await db.execute(
        "INSERT OR REPLACE INTO prize_claims (user_id, claimed_at, active) VALUES (?, ?, 1)",
        (user_id, datetime.now().isoformat()),
    )
    await db.commit()


async def deactivate_prize(user_id: int):
    db = await get_db()
    await db.execute("UPDATE prize_claims SET active = 0 WHERE user_id = ?", (user_id,))
    await db.commit()


# ━━━━━━━━━━━━━━━━━━━ Транзакции / Чеки ━━━━━━━━━━━━━━━━━━━
async def create_transaction(tx_type, user_id, user2_id=None, amount=0, details="", ref_id=None):
    from datetime import datetime
    db = await get_db()
    await db.execute(
        """INSERT INTO transactions (type, user_id, user2_id, amount, details, ref_id, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (tx_type, user_id, user2_id, amount, details, ref_id, datetime.now().isoformat()),
    )
    await db.commit()
    cur = await db.execute("SELECT last_insert_rowid()")
    return (await cur.fetchone())[0]


async def get_transaction(tx_id: int):
    db = await get_db()
    db.row_factory = aiosqlite.Row
    cur = await db.execute("SELECT * FROM transactions WHERE id = ?", (tx_id,))
    return await cur.fetchone()


async def get_user_transactions(user_id: int, tx_type=None, page=0, per_page=5):
    db = await get_db()
    if tx_type and tx_type != "all":
        cur = await db.execute(
            """SELECT id, type, user_id, user2_id, amount, details, created_at
               FROM transactions WHERE (user_id = ? OR user2_id = ?) AND type = ?
               ORDER BY id DESC LIMIT ? OFFSET ?""",
            (user_id, user_id, tx_type, per_page, page * per_page),
        )
    else:
        cur = await db.execute(
            """SELECT id, type, user_id, user2_id, amount, details, created_at
               FROM transactions WHERE user_id = ? OR user2_id = ?
               ORDER BY id DESC LIMIT ? OFFSET ?""",
            (user_id, user_id, per_page, page * per_page),
        )
    return await cur.fetchall()


async def count_user_transactions(user_id: int, tx_type=None) -> int:
    db = await get_db()
    if tx_type and tx_type != "all":
        cur = await db.execute(
            "SELECT COUNT(*) FROM transactions WHERE (user_id = ? OR user2_id = ?) AND type = ?",
            (user_id, user_id, tx_type),
        )
    else:
        cur = await db.execute(
            "SELECT COUNT(*) FROM transactions WHERE user_id = ? OR user2_id = ?",
            (user_id, user_id),
        )
    return (await cur.fetchone())[0]


# ━━━━━━━━━━━━━━━━━━━ Жалобы ━━━━━━━━━━━━━━━━━━━
async def create_complaint(tx_id: int, user_id: int, reason: str):
    from datetime import datetime
    db = await get_db()
    await db.execute(
        "INSERT INTO complaints (transaction_id, user_id, reason, created_at) VALUES (?, ?, ?, ?)",
        (tx_id, user_id, reason, datetime.now().isoformat()),
    )
    await db.commit()


async def get_pending_complaints(page=0, per_page=5):
    db = await get_db()
    offset = page * per_page
    cur = await db.execute(
        """SELECT c.id, c.transaction_id, c.user_id, c.reason, c.status, c.created_at,
                  t.type, t.amount, t.details
           FROM complaints c JOIN transactions t ON c.transaction_id = t.id
           WHERE c.status = 'pending'
           ORDER BY c.id DESC LIMIT ? OFFSET ?""",
        (per_page, offset),
    )
    return await cur.fetchall()


async def count_pending_complaints() -> int:
    db = await get_db()
    cur = await db.execute("SELECT COUNT(*) FROM complaints WHERE status = 'pending'")
    return (await cur.fetchone())[0]


async def resolve_complaint(complaint_id: int, admin_id: int, action: str, comment: str = ""):
    from datetime import datetime
    db = await get_db()
    await db.execute(
        """UPDATE complaints SET status = 'resolved', admin_id = ?, admin_action = ?,
           admin_comment = ?, resolved_at = ? WHERE id = ?""",
        (admin_id, action, comment, datetime.now().isoformat(), complaint_id),
    )
    await db.commit()


async def get_user_complaints(user_id: int, page=0, per_page=5):
    db = await get_db()
    cur = await db.execute(
        """SELECT c.id, c.transaction_id, c.reason, c.status, c.admin_action,
                  c.admin_comment, c.created_at
           FROM complaints c WHERE c.user_id = ?
           ORDER BY c.id DESC LIMIT ? OFFSET ?""",
        (user_id, per_page, page * per_page),
    )
    return await cur.fetchall()


async def get_complaint(complaint_id: int):
    db = await get_db()
    db.row_factory = aiosqlite.Row
    cur = await db.execute("SELECT * FROM complaints WHERE id = ?", (complaint_id,))
    return await cur.fetchone()


# ━━━━━━━━━━━━━━━━━━━ Настройки бота ━━━━━━━━━━━━━━━━━━━
async def get_setting(key: str, default: str = ""):
    db = await get_db()
    cur = await db.execute("SELECT value FROM bot_settings WHERE key = ?", (key,))
    row = await cur.fetchone()
    return row[0] if row else default


async def set_setting(key: str, value: str):
    db = await get_db()
    await db.execute(
        "INSERT OR REPLACE INTO bot_settings (key, value) VALUES (?, ?)", (key, value)
    )
    await db.commit()


async def get_all_settings():
    db = await get_db()
    cur = await db.execute("SELECT key, value FROM bot_settings ORDER BY key")
    return await cur.fetchall()


# ━━━━━━━━━━━━━━━━━━━ Подсчёт жалоб на пользователя ━━━━━━━━━━━━━━━━━━━
async def count_user_complaints_received(user_id: int) -> int:
    db = await get_db()
    cur = await db.execute(
        """SELECT COUNT(*) FROM complaints c
           JOIN transactions t ON c.transaction_id = t.id
           WHERE t.user2_id = ?""",
        (user_id,),
    )
    return (await cur.fetchone())[0]


# ━━━━━━━━━━━━━━━━━━━ Выдать НФТ игроку (админ/владелец) ━━━━━━━━━━━━━━━━━━━
async def give_nft_to_user(user_id: int, template_id: int):
    from datetime import datetime
    db = await get_db()
    cur = await db.execute("SELECT income_per_hour FROM nft_templates WHERE id = ?", (template_id,))
    row = await cur.fetchone()
    if not row:
        return False
    income = row[0]
    await db.execute(
        "INSERT INTO user_nfts (user_id, nft_id, bought_price, created_at) VALUES (?, ?, 0, ?)",
        (user_id, template_id, datetime.now().isoformat()),
    )
    await db.execute(
        "UPDATE users SET passive_income = passive_income + ? WHERE user_id = ?",
        (income, user_id),
    )
    await db.commit()
    _invalidate(user_id)
    return True


# ==========================================================
#  VIP / PREMIUM
# ==========================================================
async def set_user_vip(user_id: int, vip_type: str, mult_click: float,
                       mult_income: float, duration_days: int):
    from datetime import datetime, timedelta
    db = await get_db()
    if duration_days > 0:
        expires = (datetime.now() + timedelta(days=duration_days)).isoformat()
    else:
        expires = "permanent"
    await db.execute(
        """UPDATE users SET vip_type = ?, vip_multiplier_click = ?,
           vip_multiplier_income = ?, vip_expires = ? WHERE user_id = ?""",
        (vip_type, mult_click, mult_income, expires, user_id),
    )
    await db.commit()
    _invalidate(user_id)


async def remove_user_vip(user_id: int):
    db = await get_db()
    await db.execute(
        """UPDATE users SET vip_type = NULL, vip_multiplier_click = 1,
           vip_multiplier_income = 1, vip_expires = NULL WHERE user_id = ?""",
        (user_id,),
    )
    await db.commit()
    _invalidate(user_id)


async def check_vip_expired(user_id: int) -> bool:
    """Проверяет и снимает VIP если истёк. Возвращает True если VIP активен."""
    user = await get_user(user_id)
    if not user:
        return False
    vip = user["vip_type"]
    if not vip:
        return False
    expires = user["vip_expires"]
    if not expires or expires == "permanent":
        return True
    from datetime import datetime
    try:
        exp_dt = datetime.fromisoformat(expires)
        if datetime.now() > exp_dt:
            await remove_user_vip(user_id)
            return False
    except (ValueError, TypeError):
        return False
    return True


async def get_vip_multipliers(user_id: int) -> tuple:
    """Возвращает (mult_click, mult_income). Если VIP истёк — снимает его."""
    active = await check_vip_expired(user_id)
    if not active:
        return (1.0, 1.0)
    user = await get_user(user_id)
    mc = float(user["vip_multiplier_click"]) if user["vip_multiplier_click"] else 1.0
    mi = float(user["vip_multiplier_income"]) if user["vip_multiplier_income"] else 1.0
    return (mc, mi)


# ==========================================================
#  ЗАКАЗЫ НА ОПЛАТУ
# ==========================================================
async def create_payment_order(user_id: int, package_type: str, package_id: str,
                               pay_method: str, amount_rub: float) -> int:
    from datetime import datetime
    db = await get_db()
    await db.execute(
        """INSERT INTO payment_orders (user_id, package_type, package_id,
           pay_method, amount_rub, status, created_at)
           VALUES (?, ?, ?, ?, ?, 'pending', ?)""",
        (user_id, package_type, package_id, pay_method, amount_rub,
         datetime.now().isoformat()),
    )
    await db.commit()
    cur = await db.execute("SELECT last_insert_rowid()")
    return (await cur.fetchone())[0]


async def get_payment_order(order_id: int):
    db = await get_db()
    db.row_factory = aiosqlite.Row
    cur = await db.execute("SELECT * FROM payment_orders WHERE id = ?", (order_id,))
    return await cur.fetchone()


async def get_pending_orders(page=0, per_page=10):
    db = await get_db()
    offset = page * per_page
    cur = await db.execute(
        """SELECT id, user_id, package_type, package_id, pay_method,
                  amount_rub, status, created_at
           FROM payment_orders WHERE status = 'pending'
           ORDER BY id DESC LIMIT ? OFFSET ?""",
        (per_page, offset),
    )
    return await cur.fetchall()


async def count_pending_orders() -> int:
    db = await get_db()
    cur = await db.execute("SELECT COUNT(*) FROM payment_orders WHERE status = 'pending'")
    return (await cur.fetchone())[0]


async def resolve_payment_order(order_id: int, admin_id: int, status: str):
    from datetime import datetime
    db = await get_db()
    await db.execute(
        "UPDATE payment_orders SET status = ?, admin_id = ?, resolved_at = ? WHERE id = ?",
        (status, admin_id, datetime.now().isoformat(), order_id),
    )
    await db.commit()


async def get_user_orders(user_id: int, page=0, per_page=5):
    db = await get_db()
    cur = await db.execute(
        """SELECT id, package_type, package_id, pay_method, amount_rub, status, created_at
           FROM payment_orders WHERE user_id = ?
           ORDER BY id DESC LIMIT ? OFFSET ?""",
        (user_id, per_page, page * per_page),
    )
    return await cur.fetchall()


async def update_order_screenshot(order_id: int, file_id: str):
    db = await get_db()
    await db.execute(
        "UPDATE payment_orders SET screenshot_file_id = ? WHERE id = ?",
        (file_id, order_id),
    )
    await db.commit()


# ==========================================================
#  БАН ОПЛАТЫ
# ==========================================================

async def ban_payment(user_id: int):
    db = await get_db()
    await db.execute("UPDATE users SET payment_banned = 1 WHERE user_id = ?", (user_id,))
    await db.commit()
    _invalidate(user_id)


async def unban_payment(user_id: int):
    db = await get_db()
    await db.execute("UPDATE users SET payment_banned = 0 WHERE user_id = ?", (user_id,))
    await db.commit()
    _invalidate(user_id)


async def is_payment_banned(user_id: int) -> bool:
    user = await get_user(user_id)
    if not user:
        return False
    return bool(user["payment_banned"] if "payment_banned" in user.keys() else 0)


# ==========================================================
#  АУКЦИОН — дополнительные функции
# ==========================================================
async def get_expired_active_events():
    """Активные ивенты с истёкшим сроком."""
    from datetime import datetime
    db = await get_db()
    db.row_factory = aiosqlite.Row
    now = datetime.now().isoformat()
    cur = await db.execute(
        "SELECT * FROM events WHERE status = 'active' AND ends_at <= ?", (now,)
    )
    return await cur.fetchall()


async def finish_event_with_winner(event_id: int):
    """Завершить аукцион. Возвращает (winner_uid, winner_bid) или None."""
    db = await get_db()
    db.row_factory = aiosqlite.Row
    cur = await db.execute("SELECT * FROM events WHERE id = ? AND status = 'active'", (event_id,))
    event = await cur.fetchone()
    if not event:
        return None

    await db.execute("UPDATE events SET status = 'finished' WHERE id = ?", (event_id,))

    cur2 = await db.execute(
        "SELECT user_id, bid_amount FROM event_participants WHERE event_id = ? ORDER BY bid_amount DESC LIMIT 1",
        (event_id,),
    )
    winner = await cur2.fetchone()

    cur3 = await db.execute("SELECT user_id FROM event_participants WHERE event_id = ?", (event_id,))
    for row in await cur3.fetchall():
        _invalidate(row[0] if isinstance(row, tuple) else row["user_id"])

    await db.commit()
    return winner

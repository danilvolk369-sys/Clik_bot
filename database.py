# ======================================================
# РАБОТА С БАЗОЙ ДАННЫХ — КликТохн v1.0.0
# ======================================================

import time
import aiosqlite
from config import DB_NAME, RANK_THRESHOLDS

# ---------- Кэш ----------
_user_cache: dict = {}
_cache_ts: dict = {}
_CACHE_TTL = 30  # 30 сек — быстрый кэш

# ---------- Пул соединений ----------
_db_pool: aiosqlite.Connection | None = None


async def get_db() -> aiosqlite.Connection:
    """Получить персистентное соединение с БД (переиспользуется)."""
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
            user_id       INTEGER PRIMARY KEY,
            username      TEXT,
            clicks        REAL    DEFAULT 0,
            total_clicks  INTEGER DEFAULT 0,
            bonus_click   REAL    DEFAULT 0,
            passive_income REAL   DEFAULT 0,
            rank          INTEGER DEFAULT 1,
            referrals     INTEGER DEFAULT 0,
            referrer_id   INTEGER DEFAULT 0,
            nft_count     INTEGER DEFAULT 0,
            is_banned     INTEGER DEFAULT 0,
            created_at    TEXT
        )
    """)

    await db.execute("CREATE INDEX IF NOT EXISTS idx_clicks  ON users(clicks)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_banned  ON users(is_banned)")

    # Очередь поиска чатов
    await db.execute("""
        CREATE TABLE IF NOT EXISTS chat_queue (
            user_id INTEGER PRIMARY KEY
        )
    """)

    # Активные чаты
    await db.execute("""
        CREATE TABLE IF NOT EXISTS active_chats (
            id   INTEGER PRIMARY KEY AUTOINCREMENT,
            u1   INTEGER,
            u2   INTEGER,
            created_at TEXT
        )
    """)

    # Логи чатов
    await db.execute("""
        CREATE TABLE IF NOT EXISTS chat_logs (
            id   INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            sender_id INTEGER,
            message TEXT,
            created_at TEXT
        )
    """)

    # PvP игры
    await db.execute("""
        CREATE TABLE IF NOT EXISTS pvp_games (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            creator_id  INTEGER,
            opponent_id INTEGER DEFAULT NULL,
            bet         REAL,
            game_type   TEXT,
            status      TEXT DEFAULT 'open',
            creator_move  TEXT DEFAULT NULL,
            opponent_move TEXT DEFAULT NULL,
            winner_id   INTEGER DEFAULT NULL,
            created_at  TEXT
        )
    """)
    await db.execute("CREATE INDEX IF NOT EXISTS idx_pvp_status ON pvp_games(status)")

    # Дополнительные колонки PvP (Bo1/Bo3)
    for _col, _def in [("rounds","1"),("round_num","1"),
                       ("creator_score","0"),("opponent_score","0")]:
        try:
            await db.execute(
                f"ALTER TABLE pvp_games ADD COLUMN {_col} INTEGER DEFAULT {_def}"
            )
        except Exception:
            pass

    # Жалобы / проблемы
    await db.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER,
            type        TEXT,
            message     TEXT,
            status      TEXT DEFAULT 'open',
            created_at  TEXT
        )
    """)

    # ─── НФТ-шаблоны (создаёт владелец) ───
    await db.execute("""
        CREATE TABLE IF NOT EXISTS nft_templates (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            name            TEXT NOT NULL,
            income_per_hour REAL    DEFAULT 0,
            rarity          INTEGER DEFAULT 50,
            price           REAL    DEFAULT 0,
            status          TEXT    DEFAULT 'active',
            created_by      INTEGER,
            created_at      TEXT
        )
    """)

    # Миграция: добавить status если его нет
    try:
        await db.execute("ALTER TABLE nft_templates ADD COLUMN status TEXT DEFAULT 'active'")
    except Exception:
        pass

    # ─── НФТ, купленные пользователями ───
    await db.execute("""
        CREATE TABLE IF NOT EXISTS user_nfts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            nft_id      INTEGER NOT NULL,
            bought_price REAL   DEFAULT 0,
            created_at  TEXT,
            FOREIGN KEY (nft_id) REFERENCES nft_templates(id)
        )
    """)
    await db.execute("CREATE INDEX IF NOT EXISTS idx_user_nfts ON user_nfts(user_id)")

    # ─── Торговая площадка (листинги на продажу) ───
    await db.execute("""
        CREATE TABLE IF NOT EXISTS nft_market (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            seller_id   INTEGER NOT NULL,
            user_nft_id INTEGER NOT NULL,
            nft_id      INTEGER NOT NULL,
            price       REAL    NOT NULL,
            status      TEXT    DEFAULT 'open',
            created_at  TEXT,
            FOREIGN KEY (user_nft_id) REFERENCES user_nfts(id),
            FOREIGN KEY (nft_id) REFERENCES nft_templates(id)
        )
    """)
    await db.execute("CREATE INDEX IF NOT EXISTS idx_market_status ON nft_market(status)")

    # ─── Настройки бота (ключ-значение) ───
    await db.execute("""
        CREATE TABLE IF NOT EXISTS bot_settings (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)

    # ─── Администраторы ───
    await db.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            user_id    INTEGER PRIMARY KEY,
            username   TEXT,
            added_by   INTEGER,
            added_at   TEXT
        )
    """)

    # ─── Ключи администратора ───
    await db.execute("""
        CREATE TABLE IF NOT EXISTS admin_keys (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            key        TEXT UNIQUE NOT NULL,
            created_by INTEGER,
            used_by    INTEGER DEFAULT NULL,
            status     TEXT DEFAULT 'active',
            created_at TEXT,
            used_at    TEXT DEFAULT NULL
        )
    """)

    # ─── Лог действий администраторов ───
    await db.execute("""
        CREATE TABLE IF NOT EXISTS admin_actions (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id   INTEGER NOT NULL,
            action     TEXT NOT NULL,
            target_id  INTEGER DEFAULT NULL,
            details    TEXT DEFAULT NULL,
            created_at TEXT
        )
    """)

    # ─── Ответы на тикеты (диалог) ───
    await db.execute("""
        CREATE TABLE IF NOT EXISTS ticket_replies (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id  INTEGER NOT NULL,
            sender_id  INTEGER NOT NULL,
            message    TEXT NOT NULL,
            created_at TEXT,
            FOREIGN KEY (ticket_id) REFERENCES tickets(id)
        )
    """)

    # ─── Обмен НФТ (трейды) ───
    await db.execute("""
        CREATE TABLE IF NOT EXISTS nft_trades (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id      INTEGER NOT NULL,
            receiver_id    INTEGER NOT NULL,
            offer_clicks   REAL    DEFAULT 0,
            want_clicks    REAL    DEFAULT 0,
            status         TEXT    DEFAULT 'pending',
            created_at     TEXT
        )
    """)
    await db.execute("CREATE INDEX IF NOT EXISTS idx_trade_status ON nft_trades(status)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_trade_sender ON nft_trades(sender_id)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_trade_receiver ON nft_trades(receiver_id)")

    await db.execute("""
        CREATE TABLE IF NOT EXISTS nft_trade_items (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_id    INTEGER NOT NULL,
            side        TEXT    NOT NULL,
            user_nft_id INTEGER NOT NULL,
            FOREIGN KEY (trade_id) REFERENCES nft_trades(id),
            FOREIGN KEY (user_nft_id) REFERENCES user_nfts(id)
        )
    """)
    await db.execute("CREATE INDEX IF NOT EXISTS idx_trade_items ON nft_trade_items(trade_id)")

    # ─── Ивенты ───
    await db.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            name            TEXT NOT NULL,
            nft_prize_name  TEXT,
            bet_amount      REAL    DEFAULT 0,
            duration_min    INTEGER DEFAULT 5,
            status          TEXT    DEFAULT 'active',
            created_by      INTEGER,
            created_at      TEXT,
            ends_at         TEXT
        )
    """)
    await db.execute("CREATE INDEX IF NOT EXISTS idx_event_status ON events(status)")

    await db.execute("""
        CREATE TABLE IF NOT EXISTS event_participants (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id    INTEGER NOT NULL,
            user_id     INTEGER NOT NULL,
            bid_amount  REAL    DEFAULT 0,
            joined_at   TEXT,
            UNIQUE(event_id, user_id),
            FOREIGN KEY (event_id) REFERENCES events(id)
        )
    """)
    await db.execute("CREATE INDEX IF NOT EXISTS idx_ep_event ON event_participants(event_id)")

    # ─── Сообщения аукциона (для удаления после окончания) ───
    await db.execute("""
        CREATE TABLE IF NOT EXISTS auction_messages (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id  INTEGER NOT NULL,
            chat_id   INTEGER NOT NULL,
            message_id INTEGER NOT NULL,
            FOREIGN KEY (event_id) REFERENCES events(id)
        )
    """)
    await db.execute("CREATE INDEX IF NOT EXISTS idx_auc_msg_event ON auction_messages(event_id)")

    # ─── Приз (подписка на канал) ───
    await db.execute("""
        CREATE TABLE IF NOT EXISTS prize_claims (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL UNIQUE,
            claimed_at TEXT,
            active     INTEGER DEFAULT 1
        )
    """)
    await db.execute("CREATE INDEX IF NOT EXISTS idx_prize_user ON prize_claims(user_id)")

    # ─── Чеки / История транзакций ───
    await db.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            type        TEXT    NOT NULL,
            user_id     INTEGER NOT NULL,
            user2_id    INTEGER DEFAULT NULL,
            amount      REAL    DEFAULT 0,
            details     TEXT    DEFAULT '',
            ref_id      INTEGER DEFAULT NULL,
            status      TEXT    DEFAULT 'completed',
            created_at  TEXT
        )
    """)
    await db.execute("CREATE INDEX IF NOT EXISTS idx_tx_user ON transactions(user_id)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_tx_type ON transactions(type)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_tx_user2 ON transactions(user2_id)")

    # ─── Жалобы на транзакции ───
    await db.execute("""
        CREATE TABLE IF NOT EXISTS complaints (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            transaction_id  INTEGER NOT NULL,
            user_id         INTEGER NOT NULL,
            reason          TEXT    NOT NULL,
            status          TEXT    DEFAULT 'pending',
            admin_id        INTEGER DEFAULT NULL,
            admin_action    TEXT    DEFAULT NULL,
            admin_comment   TEXT    DEFAULT NULL,
            created_at      TEXT,
            resolved_at     TEXT    DEFAULT NULL,
            FOREIGN KEY (transaction_id) REFERENCES transactions(id)
        )
    """)
    await db.execute("CREATE INDEX IF NOT EXISTS idx_compl_status ON complaints(status)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_compl_user ON complaints(user_id)")

    # ─── Миграция: claimed_by в tickets ───
    try:
        await db.execute("ALTER TABLE tickets ADD COLUMN claimed_by INTEGER DEFAULT NULL")
    except Exception:
        pass

    # ─── Миграция: banned_until ───
    try:
        await db.execute("ALTER TABLE users ADD COLUMN banned_until TEXT DEFAULT NULL")
    except Exception:
        pass

    # ─── Миграция: last_income_claim ───
    try:
        await db.execute("ALTER TABLE users ADD COLUMN last_income_claim TEXT DEFAULT NULL")
    except Exception:
        pass

    # ─── Миграция: income_capacity (ёмкость накопления дохода) ───
    try:
        await db.execute("ALTER TABLE users ADD COLUMN income_capacity REAL DEFAULT 150")
    except Exception:
        pass

    # ─── Миграция: bid_amount в event_participants ───
    try:
        await db.execute("ALTER TABLE event_participants ADD COLUMN bid_amount REAL DEFAULT 0")
    except Exception:
        pass

    # ─── Миграция: want_nft_count в nft_trades (доска обменов) ───
    try:
        await db.execute("ALTER TABLE nft_trades ADD COLUMN want_nft_count INTEGER DEFAULT 0")
    except Exception:
        pass

    # ─── Миграция: nft_rarity / nft_income в events ───
    try:
        await db.execute("ALTER TABLE events ADD COLUMN nft_rarity INTEGER DEFAULT 3")
    except Exception:
        pass
    try:
        await db.execute("ALTER TABLE events ADD COLUMN nft_income REAL DEFAULT 0")
    except Exception:
        pass

    # ─── Миграция: anonymous (анонимность в рейтинге) ───
    try:
        await db.execute("ALTER TABLE users ADD COLUMN anonymous INTEGER DEFAULT 0")
    except Exception:
        pass

    # ─── Миграция: total_clicks INTEGER → REAL (SQLite не меняет тип,
    #     но REAL значения и так принимаются) ───

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
    """Количество ВСЕХ пользователей (включая забаненных)."""
    db = await get_db()
    cur = await db.execute("SELECT COUNT(*) FROM users")
    return (await cur.fetchone())[0]


async def is_user_banned(user_id: int) -> bool:
    u = await get_user(user_id)
    return bool(u and u["is_banned"])


# ---------- Клики ----------
async def update_clicks(user_id: int, amount: float):
    db = await get_db()
    await db.execute(
        "UPDATE users SET clicks = clicks + ?, total_clicks = total_clicks + ? WHERE user_id = ?",
        (amount, max(amount, 0), user_id),
    )
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


async def claim_passive_income(user_id: int) -> tuple[float, float]:
    """Собрать пассивный доход. Возвращает (начислено, часов_прошло).
    Если first_claim (last_income_claim is NULL) — ставим метку и возвращаем (-1, 0).
    """
    from datetime import datetime
    now = datetime.now()
    db = await get_db()
    db.row_factory = aiosqlite.Row
    cur = await db.execute(
        "SELECT passive_income, last_income_claim FROM users WHERE user_id = ?",
        (user_id,),
    )
    row = await cur.fetchone()
    if not row:
        return 0.0, 0.0

    income_per_hour = float(row["passive_income"] or 0)
    if income_per_hour <= 0:
        return 0.0, 0.0

    last_claim = row["last_income_claim"]
    if not last_claim:
        # Первый вызов — ставим метку, чтобы начать отсчёт
        await db.execute(
            "UPDATE users SET last_income_claim = ? WHERE user_id = ?",
            (now.isoformat(), user_id),
        )
        await db.commit()
        _invalidate(user_id)
        return -1.0, 0.0  # сигнал «таймер запущен»

    try:
        last_dt = datetime.fromisoformat(last_claim)
    except (ValueError, TypeError):
        last_dt = now

    diff = (now - last_dt).total_seconds()
    if diff < 60:  # минимум 1 минута
        remaining = 60 - diff
        return 0.0, remaining  # возвращаем оставшиеся секунды

    hours = diff / 3600.0
    if hours > 1.0:
        hours = 1.0  # максимум 1 час накопления
    earned = income_per_hour * hours

    # Ограничиваем накопление ёмкостью
    cur2 = await db.execute(
        "SELECT income_capacity FROM users WHERE user_id = ?", (user_id,)
    )
    cap_row = await cur2.fetchone()
    capacity = float(cap_row[0]) if cap_row and cap_row[0] else 150.0
    if earned > capacity:
        earned = capacity

    await db.execute(
        "UPDATE users SET clicks = clicks + ?, last_income_claim = ? WHERE user_id = ?",
        (earned, now.isoformat(), user_id),
    )
    await db.commit()
    _invalidate(user_id)
    return earned, hours


async def spend_clicks(user_id: int, amount: float) -> bool:
    """Списать клики атомарно. Возвращает True при успехе."""
    db = await get_db()
    cur = await db.execute(
        "UPDATE users SET clicks = clicks - ? WHERE user_id = ? AND clicks >= ? RETURNING user_id",
        (amount, user_id, amount),
    )
    row = await cur.fetchone()
    await db.commit()
    _invalidate(user_id)
    return row is not None


# ---------- Ранг ----------
def calc_rank(total_clicks: int) -> int:
    rank = 1
    for i, threshold in enumerate(RANK_THRESHOLDS, 1):
        if total_clicks >= threshold:
            rank = i
    return rank


async def update_rank(user_id: int):
    db = await get_db()
    cur = await db.execute("SELECT total_clicks FROM users WHERE user_id = ?", (user_id,))
    row = await cur.fetchone()
    if row:
        new_rank = calc_rank(row[0])
        await db.execute("UPDATE users SET rank = ? WHERE user_id = ?", (new_rank, user_id))
        await db.commit()
    _invalidate(user_id)


# ---------- Сброс данных ----------
async def reset_user_clicks(user_id: int):
    """Обнулить баланс кликов."""
    db = await get_db()
    await db.execute("UPDATE users SET clicks = 0 WHERE user_id = ?", (user_id,))
    await db.commit()
    _invalidate(user_id)


async def reset_user_progress(user_id: int):
    """Обнулить total_clicks и ранг до 1."""
    db = await get_db()
    await db.execute(
        "UPDATE users SET total_clicks = 0, rank = 1 WHERE user_id = ?",
        (user_id,),
    )
    await db.commit()
    _invalidate(user_id)


async def reset_user_all(user_id: int):
    """Полный сброс: клики, total_clicks, ранг, бонусы, пассив, доход."""
    db = await get_db()
    await db.execute(
        """UPDATE users SET
             clicks = 0, total_clicks = 0, rank = 1,
             bonus_click = 0, passive_income = 0,
             last_income_claim = NULL
           WHERE user_id = ?""",
        (user_id,),
    )
    await db.commit()
    _invalidate(user_id)


async def reset_all_players():
    """Полный сброс ВСЕХ игроков: клики, прогресс, пассив, ёмкость, НФТ."""
    db = await get_db()
    await db.execute(
        """UPDATE users SET
             clicks = 0, total_clicks = 0, rank = 1,
             bonus_click = 0, passive_income = 0,
             income_capacity = 150, nft_count = 0,
             last_income_claim = NULL"""
    )
    await db.execute("DELETE FROM user_nfts")
    await db.execute("DELETE FROM nft_market")
    await db.commit()
    _user_cache.clear()
    _cache_ts.clear()


# ---------- Рефералы ----------
async def add_referral(new_user_id: int, referrer_id: int):
    """Начислить реферальные бонусы обоим."""
    from config import REF_FIRST_CLICKS, REF_FIRST_POWER, REF_EACH_CLICKS, REF_EACH_POWER

    db = await get_db()
    # Помечаем реферера
    await db.execute(
        "UPDATE users SET referrer_id = ? WHERE user_id = ?",
        (referrer_id, new_user_id),
    )

    # Счётчик рефералов у пригласившего
    cur = await db.execute("SELECT referrals FROM users WHERE user_id = ?", (referrer_id,))
    row = await cur.fetchone()
    is_first = row and row[0] == 0

    await db.execute(
        "UPDATE users SET referrals = referrals + 1 WHERE user_id = ?",
        (referrer_id,),
    )

    if is_first:
        bonus_clicks = REF_FIRST_CLICKS
        bonus_power = REF_FIRST_POWER
    else:
        bonus_clicks = REF_EACH_CLICKS
        bonus_power = REF_EACH_POWER

    # Бонус пригласившему
    await db.execute(
        "UPDATE users SET clicks = clicks + ?, bonus_click = bonus_click + ? WHERE user_id = ?",
        (bonus_clicks, bonus_power, referrer_id),
    )
    # Бонус новому
    await db.execute(
        "UPDATE users SET clicks = clicks + ?, bonus_click = bonus_click + ? WHERE user_id = ?",
        (bonus_clicks, bonus_power, new_user_id),
    )
    await db.commit()

    _invalidate(referrer_id)
    _invalidate(new_user_id)


# ---------- Рейтинг ----------
async def get_top_players(limit: int = 50):
    db = await get_db()
    cur = await db.execute(
        """SELECT user_id, username, clicks, bonus_click, passive_income, rank, anonymous
           FROM users WHERE is_banned = 0
           ORDER BY clicks DESC LIMIT ?""",
        (limit,),
    )
    return await cur.fetchall()


async def get_user_anonymous(user_id: int) -> bool:
    db = await get_db()
    cur = await db.execute(
        "SELECT anonymous FROM users WHERE user_id = ?", (user_id,)
    )
    row = await cur.fetchone()
    return bool(row[0]) if row else False


async def set_user_anonymous(user_id: int, value: bool):
    db = await get_db()
    await db.execute(
        "UPDATE users SET anonymous = ? WHERE user_id = ?",
        (1 if value else 0, user_id),
    )
    await db.commit()
    _invalidate(user_id)


# ---------- Чат ----------
async def chat_queue_add(user_id: int):
    db = await get_db()
    await db.execute("INSERT OR IGNORE INTO chat_queue (user_id) VALUES (?)", (user_id,))
    await db.commit()


async def chat_queue_remove(user_id: int):
    db = await get_db()
    await db.execute("DELETE FROM chat_queue WHERE user_id = ?", (user_id,))
    await db.commit()


async def chat_queue_find_partner(user_id: int):
    """Найти партнёра в очереди (не себя). Возвращает user_id или None."""
    db = await get_db()
    cur = await db.execute(
        "SELECT user_id FROM chat_queue WHERE user_id != ? LIMIT 1", (user_id,)
    )
    row = await cur.fetchone()
    return row[0] if row else None


async def chat_create(u1: int, u2: int) -> int:
    from datetime import datetime
    db = await get_db()
    cur = await db.execute(
        "INSERT INTO active_chats (u1, u2, created_at) VALUES (?, ?, ?)",
        (u1, u2, datetime.now().isoformat()),
    )
    chat_id = cur.lastrowid
    await db.execute("DELETE FROM chat_queue WHERE user_id IN (?, ?)", (u1, u2))
    await db.commit()
    return chat_id


async def chat_get_active(user_id: int):
    db = await get_db()
    db.row_factory = aiosqlite.Row
    cur = await db.execute(
        "SELECT * FROM active_chats WHERE u1 = ? OR u2 = ?", (user_id, user_id)
    )
    return await cur.fetchone()


async def chat_end(chat_id: int):
    db = await get_db()
    await db.execute("DELETE FROM active_chats WHERE id = ?", (chat_id,))
    await db.commit()


async def chat_log(chat_id: int, sender_id: int, message: str):
    from datetime import datetime
    db = await get_db()
    await db.execute(
        "INSERT INTO chat_logs (chat_id, sender_id, message, created_at) VALUES (?, ?, ?, ?)",
        (chat_id, sender_id, message, datetime.now().isoformat()),
    )
    await db.commit()


async def chat_get_history(user_id: int, limit: int = 10):
    db = await get_db()
    cur = await db.execute(
        """SELECT ac.id, ac.u1, ac.u2, ac.created_at
           FROM active_chats ac
           WHERE ac.u1 = ? OR ac.u2 = ?
           ORDER BY ac.id DESC LIMIT ?""",
        (user_id, user_id, limit),
    )
    return await cur.fetchall()


async def chat_get_history_for_user(user_id: int, limit: int = 10):
    """Получить завершённые чаты (из логов) с количеством сообщений."""
    db = await get_db()
    cur = await db.execute(
        """SELECT cl.chat_id,
                  COUNT(*) as msg_count,
                  MIN(cl.created_at) as started
           FROM chat_logs cl
           WHERE cl.chat_id IN (
               SELECT DISTINCT chat_id FROM chat_logs WHERE sender_id = ?
           )
           GROUP BY cl.chat_id
           ORDER BY cl.chat_id DESC
           LIMIT ?""",
        (user_id, limit),
    )
    return await cur.fetchall()


async def chat_count_for_user(user_id: int) -> int:
    """Кол-во уникальных чатов, в которых участвовал."""
    db = await get_db()
    cur = await db.execute(
        """SELECT COUNT(DISTINCT chat_id)
           FROM chat_logs WHERE sender_id = ?""",
        (user_id,),
    )
    row = await cur.fetchone()
    return row[0] if row else 0


# ---------- Тикеты ----------
async def create_ticket(user_id: int, ticket_type: str, message: str):
    from datetime import datetime
    db = await get_db()
    await db.execute(
        "INSERT INTO tickets (user_id, type, message, created_at) VALUES (?, ?, ?, ?)",
        (user_id, ticket_type, message, datetime.now().isoformat()),
    )
    await db.commit()


# get_open_tickets и close_ticket перенесены ниже (единственные версии в конце файла)


# ---------- Бан / Разбан ----------
async def ban_user(user_id: int, days: int = 0):
    """Бан пользователя. days=0 — бессрочный, иначе на N дней."""
    from datetime import datetime, timedelta
    until = None
    if days > 0:
        until = (datetime.now() + timedelta(days=days)).isoformat()
    db = await get_db()
    await db.execute(
        "UPDATE users SET is_banned = 1, banned_until = ? WHERE user_id = ?",
        (until, user_id),
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


async def check_expired_bans():
    """Автоматически разбанить пользователей с истёкшим сроком."""
    from datetime import datetime
    now = datetime.now().isoformat()
    db = await get_db()
    cur = await db.execute(
        "SELECT user_id FROM users WHERE is_banned = 1 AND banned_until IS NOT NULL AND banned_until <= ?",
        (now,),
    )
    expired = [row[0] for row in await cur.fetchall()]
    if expired:
        await db.execute(
            f"UPDATE users SET is_banned = 0, banned_until = NULL "
            f"WHERE user_id IN ({','.join('?' * len(expired))})",
            expired,
        )
        await db.commit()
    for uid in expired:
        _invalidate(uid)
    return expired


async def get_ban_info(user_id: int) -> str | None:
    """Вернуть banned_until для пользователя (или None)."""
    db = await get_db()
    cur = await db.execute(
        "SELECT banned_until FROM users WHERE user_id = ?", (user_id,),
    )
    row = await cur.fetchone()
    return row[0] if row else None


# ---------- Чат-логи (просмотр для админов) ----------
async def get_chat_log_messages(chat_id: int, limit: int = 50):
    """Вернуть сообщения чата для просмотра."""
    db = await get_db()
    cur = await db.execute(
        "SELECT sender_id, message, created_at FROM chat_logs "
        "WHERE chat_id = ? ORDER BY id ASC LIMIT ?",
        (chat_id, limit),
    )
    return await cur.fetchall()


async def get_recent_chats(limit: int = 20):
    """Последние чаты (id, участники, кол-во сообщений)."""
    db = await get_db()
    cur = await db.execute(
        """SELECT chat_id,
                  GROUP_CONCAT(DISTINCT sender_id) as users,
                  COUNT(*) as msg_count,
                  MIN(created_at) as started
           FROM chat_logs
           GROUP BY chat_id
           ORDER BY chat_id DESC
           LIMIT ?""",
        (limit,),
    )
    return await cur.fetchall()


async def clear_all_chat_logs():
    """Очистить все чат-логи."""
    db = await get_db()
    await db.execute("DELETE FROM chat_logs")
    await db.execute("DELETE FROM active_chats")
    await db.commit()


async def clear_chat_log(chat_id: int):
    """Удалить логи конкретного чата."""
    db = await get_db()
    await db.execute("DELETE FROM chat_logs WHERE chat_id = ?", (chat_id,))
    await db.commit()


# ==========================================================
#  НФТ — ШАБЛОНЫ (владелец создаёт)
# ==========================================================
async def create_nft_template(name: str, income: float, rarity: int, price: float, created_by: int) -> int:
    from datetime import datetime
    db = await get_db()
    cur = await db.execute(
        """INSERT INTO nft_templates (name, income_per_hour, rarity, price, created_by, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (name, income, rarity, price, created_by, datetime.now().isoformat()),
    )
    await db.commit()
    return cur.lastrowid


async def get_all_nft_templates():
    db = await get_db()
    cur = await db.execute(
        "SELECT id, name, income_per_hour, rarity, price FROM nft_templates ORDER BY id"
    )
    return await cur.fetchall()


async def get_nft_template(nft_id: int):
    db = await get_db()
    db.row_factory = aiosqlite.Row
    cur = await db.execute(
        "SELECT * FROM nft_templates WHERE id = ?", (nft_id,)
    )
    return await cur.fetchone()


async def delete_nft_template(nft_id: int):
    db = await get_db()
    await db.execute("DELETE FROM nft_templates WHERE id = ?", (nft_id,))
    await db.commit()


# ==========================================================
#  НФТ — ВЛАДЕНИЕ (user_nfts)
# ==========================================================
async def buy_nft_from_shop(user_id: int, nft_id: int, price: float) -> bool:
    """Покупка НФТ из магазина (шаблон). Одноразовая — после покупки шаблон помечается sold."""
    from datetime import datetime
    u = await get_user(user_id)
    if not u or u["clicks"] < price:
        return False

    db = await get_db()
    # Проверяем, что шаблон ещё не куплен
    cur = await db.execute(
        "SELECT id FROM nft_templates WHERE id = ? AND status = 'active'", (nft_id,)
    )
    if not await cur.fetchone():
        return False

    await db.execute("UPDATE users SET clicks = clicks - ? WHERE user_id = ?", (price, user_id))
    await db.execute(
        "INSERT INTO user_nfts (user_id, nft_id, bought_price, created_at) VALUES (?, ?, ?, ?)",
        (user_id, nft_id, price, datetime.now().isoformat()),
    )
    # Помечаем шаблон как проданный (одноразовая покупка)
    await db.execute(
        "UPDATE nft_templates SET status = 'sold' WHERE id = ?", (nft_id,)
    )
    # Обновляем nft_count и passive_income
    tpl = await _get_nft_tpl_raw(db, nft_id)
    if tpl:
        income = tpl[2]  # income_per_hour
        await db.execute(
            "UPDATE users SET nft_count = nft_count + 1, passive_income = passive_income + ? WHERE user_id = ?",
            (income, user_id),
        )
    await db.commit()
    _invalidate(user_id)
    return True


async def _get_nft_tpl_raw(db, nft_id: int):
    cur = await db.execute(
        "SELECT id, name, income_per_hour, rarity, price FROM nft_templates WHERE id = ?", (nft_id,)
    )
    return await cur.fetchone()


async def get_user_nfts(user_id: int):
    """Все НФТ пользователя с информацией о шаблоне."""
    db = await get_db()
    cur = await db.execute(
        """SELECT un.id, nt.name, nt.income_per_hour, nt.rarity, un.bought_price, un.created_at
           FROM user_nfts un
           JOIN nft_templates nt ON un.nft_id = nt.id
           WHERE un.user_id = ?
           ORDER BY un.id""",
        (user_id,),
    )
    return await cur.fetchall()


async def count_user_nfts(user_id: int) -> int:
    db = await get_db()
    cur = await db.execute(
        "SELECT COUNT(*) FROM user_nfts WHERE user_id = ?", (user_id,)
    )
    return (await cur.fetchone())[0]


async def get_user_nft_by_id(user_nft_id: int):
    db = await get_db()
    cur = await db.execute(
        """SELECT un.id, un.user_id, un.nft_id, nt.name, nt.income_per_hour, nt.rarity, un.bought_price
           FROM user_nfts un
           JOIN nft_templates nt ON un.nft_id = nt.id
           WHERE un.id = ?""",
        (user_nft_id,),
    )
    return await cur.fetchone()


# ==========================================================
#  ТОРГОВАЯ ПЛОЩАДКА (nft_market)
# ==========================================================
async def list_nft_for_sale(seller_id: int, user_nft_id: int, nft_id: int, price: float) -> int:
    """Выставить НФТ на продажу. Возвращает ID листинга."""
    from datetime import datetime
    db = await get_db()
    cur = await db.execute(
        """INSERT INTO nft_market (seller_id, user_nft_id, nft_id, price, status, created_at)
           VALUES (?, ?, ?, ?, 'open', ?)""",
        (seller_id, user_nft_id, nft_id, price, datetime.now().isoformat()),
    )
    await db.commit()
    return cur.lastrowid


async def get_market_listings(limit: int = 20):
    """Все открытые листинги."""
    db = await get_db()
    cur = await db.execute(
        """SELECT m.id, m.seller_id, m.user_nft_id, m.price,
                  nt.name, nt.income_per_hour, nt.rarity
           FROM nft_market m
           JOIN user_nfts un ON m.user_nft_id = un.id
           JOIN nft_templates nt ON m.nft_id = nt.id
           WHERE m.status = 'open'
           ORDER BY m.id DESC
           LIMIT ?""",
        (limit,),
    )
    return await cur.fetchall()


async def get_market_listing(listing_id: int):
    db = await get_db()
    cur = await db.execute(
        """SELECT m.id, m.seller_id, m.user_nft_id, m.nft_id, m.price,
                  nt.name, nt.income_per_hour, nt.rarity
           FROM nft_market m
           JOIN nft_templates nt ON m.nft_id = nt.id
           WHERE m.id = ? AND m.status = 'open'""",
        (listing_id,),
    )
    return await cur.fetchone()


async def buy_nft_from_market(buyer_id: int, listing_id: int) -> bool:
    """Купить НФТ с торговой площадки. Переносит НФТ к покупателю, начисляет продавцу."""
    listing = await get_market_listing(listing_id)
    if not listing:
        return False

    lid, seller_id, user_nft_id, nft_id, price, name, income, rarity = listing
    if buyer_id == seller_id:
        return False

    u = await get_user(buyer_id)
    if not u or u["clicks"] < price:
        return False

    db = await get_db()
    # Списываем с покупателя
    await db.execute("UPDATE users SET clicks = clicks - ? WHERE user_id = ?", (price, buyer_id))
    # Начисляем продавцу
    await db.execute("UPDATE users SET clicks = clicks + ? WHERE user_id = ?", (price, seller_id))

    # Переносим NFT
    await db.execute("UPDATE user_nfts SET user_id = ? WHERE id = ?", (buyer_id, user_nft_id))

    # Обновляем счётчики: покупатель +1 nft, +income; продавец -1 nft, -income
    await db.execute(
        "UPDATE users SET nft_count = nft_count + 1, passive_income = passive_income + ? WHERE user_id = ?",
        (income, buyer_id),
    )
    await db.execute(
        "UPDATE users SET nft_count = MAX(0, nft_count - 1), passive_income = MAX(0, passive_income - ?) WHERE user_id = ?",
        (income, seller_id),
    )

    # Закрываем листинг
    await db.execute("UPDATE nft_market SET status = 'sold' WHERE id = ?", (listing_id,))
    await db.commit()

    _invalidate(buyer_id)
    _invalidate(seller_id)
    return True


async def cancel_market_listing(listing_id: int, seller_id: int) -> bool:
    """Снять с продажи."""
    db = await get_db()
    cur = await db.execute(
        "SELECT id FROM nft_market WHERE id = ? AND seller_id = ? AND status = 'open'",
        (listing_id, seller_id),
    )
    if not await cur.fetchone():
        return False
    await db.execute("UPDATE nft_market SET status = 'cancelled' WHERE id = ?", (listing_id,))
    await db.commit()
    return True


async def is_nft_on_sale(user_nft_id: int) -> bool:
    """Проверить, не выставлен ли НФТ на продажу."""
    db = await get_db()
    cur = await db.execute(
        "SELECT id FROM nft_market WHERE user_nft_id = ? AND status = 'open'", (user_nft_id,)
    )
    return bool(await cur.fetchone())


async def get_nft_listing_by_user_nft(user_nft_id: int):
    """Получить открытый листинг по user_nft_id."""
    db = await get_db()
    cur = await db.execute(
        "SELECT id FROM nft_market WHERE user_nft_id = ? AND status = 'open'",
        (user_nft_id,),
    )
    row = await cur.fetchone()
    return row[0] if row else None


# ==========================================================
#  КОМБИНИРОВАННАЯ ТОРГОВАЯ ПЛОЩАДКА (шаблоны + лоты)
# ==========================================================
async def get_combined_market_page(page: int, per_page: int = 5):
    """Комбинированный список: только active шаблоны + открытые лоты игроков."""
    offset = page * per_page
    db = await get_db()
    cur = await db.execute(
        """SELECT 'tpl' AS type, id, name, rarity, income_per_hour, price, 0 AS seller_id
           FROM nft_templates
           WHERE status = 'active'
           UNION ALL
           SELECT 'lot' AS type, m.id, nt.name, nt.rarity, nt.income_per_hour, m.price, m.seller_id
           FROM nft_market m
           JOIN nft_templates nt ON m.nft_id = nt.id
           WHERE m.status = 'open'
           ORDER BY price ASC
           LIMIT ? OFFSET ?""",
        (per_page, offset),
    )
    return await cur.fetchall()


async def count_combined_market() -> int:
    """Общее кол-во позиций на площадке (только active шаблоны + открытые лоты)."""
    db = await get_db()
    cur = await db.execute(
        """SELECT
             (SELECT COUNT(*) FROM nft_templates WHERE status = 'active') +
             (SELECT COUNT(*) FROM nft_market WHERE status = 'open')"""
    )
    return (await cur.fetchone())[0]


# ==========================================================
#  АДМИНИСТРАТОРЫ
# ==========================================================
async def is_admin(user_id: int) -> bool:
    db = await get_db()
    cur = await db.execute("SELECT user_id FROM admins WHERE user_id=?", (user_id,))
    return bool(await cur.fetchone())


async def add_admin(user_id: int, username: str, added_by: int):
    from datetime import datetime
    db = await get_db()
    await db.execute(
        "INSERT OR REPLACE INTO admins (user_id, username, added_by, added_at) VALUES (?,?,?,?)",
        (user_id, username, added_by, datetime.now().isoformat()),
    )
    await db.commit()


async def remove_admin(user_id: int):
    db = await get_db()
    await db.execute("DELETE FROM admins WHERE user_id=?", (user_id,))
    await db.commit()


async def get_all_admins():
    db = await get_db()
    cur = await db.execute("SELECT user_id, username, added_at FROM admins ORDER BY added_at")
    return await cur.fetchall()


async def create_admin_key(created_by: int) -> str:
    import secrets
    from datetime import datetime
    key = f"ADM-{secrets.token_hex(8).upper()}"
    db = await get_db()
    await db.execute(
        "INSERT INTO admin_keys (key, created_by, status, created_at) VALUES (?,?,'active',?)",
        (key, created_by, datetime.now().isoformat()),
    )
    await db.commit()
    return key


async def use_admin_key(key: str, user_id: int) -> bool:
    from datetime import datetime
    db = await get_db()
    cur = await db.execute(
        "SELECT id, created_by FROM admin_keys WHERE key=? AND status='active'", (key,)
    )
    row = await cur.fetchone()
    if not row:
        return False
    await db.execute(
        "UPDATE admin_keys SET status='used', used_by=?, used_at=? WHERE id=?",
        (user_id, datetime.now().isoformat(), row[0]),
    )
    await db.commit()
    return True


async def get_all_admin_keys():
    db = await get_db()
    cur = await db.execute(
        "SELECT id, key, created_by, used_by, status, created_at, used_at "
        "FROM admin_keys ORDER BY id DESC LIMIT 20"
    )
    return await cur.fetchall()


async def log_admin_action(admin_id: int, action: str,
                           target_id: int = None, details: str = None):
    from datetime import datetime
    db = await get_db()
    await db.execute(
        "INSERT INTO admin_actions (admin_id, action, target_id, details, created_at) "
        "VALUES (?,?,?,?,?)",
        (admin_id, action, target_id, details, datetime.now().isoformat()),
    )
    await db.commit()


async def get_admin_actions(admin_id: int = None, limit: int = 20):
    db = await get_db()
    if admin_id:
        cur = await db.execute(
            "SELECT id, admin_id, action, target_id, details, created_at "
            "FROM admin_actions WHERE admin_id=? ORDER BY id DESC LIMIT ?",
            (admin_id, limit),
        )
    else:
        cur = await db.execute(
            "SELECT id, admin_id, action, target_id, details, created_at "
            "FROM admin_actions ORDER BY id DESC LIMIT ?",
            (limit,),
        )
    return await cur.fetchall()


async def add_ticket_reply(ticket_id: int, sender_id: int, message: str):
    from datetime import datetime
    db = await get_db()
    await db.execute(
        "INSERT INTO ticket_replies (ticket_id, sender_id, message, created_at) VALUES (?,?,?,?)",
        (ticket_id, sender_id, message, datetime.now().isoformat()),
    )
    await db.commit()


async def get_ticket_replies(ticket_id: int):
    db = await get_db()
    cur = await db.execute(
        "SELECT id, sender_id, message, created_at "
        "FROM ticket_replies WHERE ticket_id=? ORDER BY id",
        (ticket_id,),
    )
    return await cur.fetchall()


async def get_ticket_by_id(ticket_id: int):
    db = await get_db()
    db.row_factory = aiosqlite.Row
    cur = await db.execute("SELECT * FROM tickets WHERE id=?", (ticket_id,))
    return await cur.fetchone()


async def get_open_tickets(limit: int = 20, viewer_id: int = None):
    """Open tickets. If viewer_id set — hide tickets claimed by others."""
    db = await get_db()
    if viewer_id:
        cur = await db.execute(
            "SELECT id, user_id, type, message, status, created_at "
            "FROM tickets WHERE status IN ('open','accepted') "
            "AND (claimed_by IS NULL OR claimed_by = ?) "
            "ORDER BY id DESC LIMIT ?",
            (viewer_id, limit),
        )
    else:
        cur = await db.execute(
            "SELECT id, user_id, type, message, status, created_at "
            "FROM tickets WHERE status IN ('open','accepted') ORDER BY id DESC LIMIT ?",
            (limit,),
        )
    return await cur.fetchall()


async def claim_ticket(ticket_id: int, admin_id: int):
    """Claim a ticket — other admins won't see it anymore."""
    db = await get_db()
    await db.execute(
        "UPDATE tickets SET claimed_by = ? WHERE id = ? AND (claimed_by IS NULL OR claimed_by = ?)",
        (admin_id, ticket_id, admin_id),
    )
    await db.commit()


async def update_ticket_status(ticket_id: int, status: str):
    db = await get_db()
    await db.execute("UPDATE tickets SET status=? WHERE id=?", (status, ticket_id))
    await db.commit()


# ---------- Список забаненных ----------
async def get_banned_users(limit: int = 30, offset: int = 0):
    """Вернуть список забаненных пользователей с пагинацией."""
    db = await get_db()
    cur = await db.execute(
        "SELECT user_id, username, clicks, rank FROM users "
        "WHERE is_banned = 1 ORDER BY user_id DESC LIMIT ? OFFSET ?",
        (limit, offset),
    )
    return await cur.fetchall()


async def count_banned_users() -> int:
    db = await get_db()
    cur = await db.execute("SELECT COUNT(*) FROM users WHERE is_banned = 1")
    return (await cur.fetchone())[0]


# ---------- Список участников (пагинация) ----------
async def get_users_page(limit: int = 4, offset: int = 0):
    """Вернуть страницу пользователей, отсортированных по кликам."""
    db = await get_db()
    cur = await db.execute(
        "SELECT user_id, username, clicks, rank, is_banned FROM users "
        "ORDER BY clicks DESC LIMIT ? OFFSET ?",
        (limit, offset),
    )
    return await cur.fetchall()


# ---------- Тикеты пользователя ----------
async def get_user_tickets(user_id: int, limit: int = 10):
    """Вернуть тикеты конкретного пользователя."""
    db = await get_db()
    cur = await db.execute(
        "SELECT id, type, message, status, created_at FROM tickets "
        "WHERE user_id = ? ORDER BY id DESC LIMIT ?",
        (user_id, limit),
    )
    return await cur.fetchall()


async def get_all_tickets(limit: int = 30):
    """Все тикеты (любого статуса)."""
    db = await get_db()
    cur = await db.execute(
        "SELECT id, user_id, type, message, status, created_at "
        "FROM tickets ORDER BY id DESC LIMIT ?",
        (limit,),
    )
    return await cur.fetchall()


# ==========================================================
#  ОБМЕН НФТ (TRADE) — Доска обменов
# ==========================================================

async def create_public_trade(sender_id: int, offer_nft_ids: list[int],
                              want_clicks: float = 0, want_nft_count: int = 0) -> int:
    """Создать публичное предложение обмена на доске. Возвращает trade_id."""
    from datetime import datetime
    db = await get_db()
    cur = await db.execute(
        "INSERT INTO nft_trades "
        "(sender_id, receiver_id, offer_clicks, want_clicks, want_nft_count, status, created_at) "
        "VALUES (?, 0, 0, ?, ?, 'open', ?)",
        (sender_id, want_clicks, want_nft_count, datetime.now().isoformat()),
    )
    trade_id = cur.lastrowid
    for nid in offer_nft_ids:
        await db.execute(
            "INSERT INTO nft_trade_items (trade_id, side, user_nft_id) VALUES (?, 'offer', ?)",
            (trade_id, nid),
        )
    await db.commit()
    return trade_id


async def get_trade_offer(trade_id: int):
    """Вернуть одно предложение обмена (8 полей).
    (id, sender_id, receiver_id, offer_clicks, want_clicks, status, created_at, want_nft_count)"""
    db = await get_db()
    cur = await db.execute(
        "SELECT id, sender_id, receiver_id, offer_clicks, want_clicks, "
        "       status, created_at, COALESCE(want_nft_count,0) "
        "FROM nft_trades WHERE id = ?",
        (trade_id,),
    )
    return await cur.fetchone()


async def get_trade_items(trade_id: int):
    """Вернуть список НФТ-предметов обмена с инфой о шаблоне."""
    db = await get_db()
    cur = await db.execute(
        "SELECT ti.id, ti.trade_id, ti.side, ti.user_nft_id, "
        "       nt.name, nt.rarity, nt.income_per_hour "
        "FROM nft_trade_items ti "
        "JOIN user_nfts un ON un.id = ti.user_nft_id "
        "JOIN nft_templates nt ON nt.id = un.nft_id "
        "WHERE ti.trade_id = ?",
        (trade_id,),
    )
    return await cur.fetchall()


async def count_open_trades(exclude_uid: int = 0) -> int:
    """Количество открытых предложений (исключая своих)."""
    db = await get_db()
    cur = await db.execute(
        "SELECT COUNT(*) FROM nft_trades WHERE status = 'open' AND sender_id != ?",
        (exclude_uid,),
    )
    return (await cur.fetchone())[0]


async def get_open_trades_page(page: int, per_page: int, exclude_uid: int = 0):
    """Страница открытых предложений для доски обменов.
    Каждая строка: (id, sender_id, offer_clicks, want_clicks, want_nft_count, created_at)"""
    db = await get_db()
    cur = await db.execute(
        "SELECT id, sender_id, offer_clicks, want_clicks, "
        "       COALESCE(want_nft_count,0), created_at "
        "FROM nft_trades WHERE status = 'open' AND sender_id != ? "
        "ORDER BY id DESC LIMIT ? OFFSET ?",
        (exclude_uid, per_page, page * per_page),
    )
    return await cur.fetchall()


async def get_my_open_trades(user_id: int, limit: int = 20):
    """Мои открытые / предложенные обмены (как создатель).
    (id, sender_id, receiver_id, offer_clicks, want_clicks, status, created_at, want_nft_count)"""
    db = await get_db()
    cur = await db.execute(
        "SELECT id, sender_id, receiver_id, offer_clicks, want_clicks, "
        "       status, created_at, COALESCE(want_nft_count,0) "
        "FROM nft_trades WHERE sender_id = ? AND status IN ('open','proposed') "
        "ORDER BY id DESC LIMIT ?",
        (user_id, limit),
    )
    return await cur.fetchall()


async def get_proposals_for_me(user_id: int, limit: int = 20):
    """Предложения на мои обмены (кто-то откликнулся, ждёт моего решения).
    (id, sender_id, receiver_id, offer_clicks, want_clicks, status, created_at, want_nft_count)"""
    db = await get_db()
    cur = await db.execute(
        "SELECT id, sender_id, receiver_id, offer_clicks, want_clicks, "
        "       status, created_at, COALESCE(want_nft_count,0) "
        "FROM nft_trades WHERE sender_id = ? AND status = 'proposed' "
        "ORDER BY id DESC LIMIT ?",
        (user_id, limit),
    )
    return await cur.fetchall()


async def propose_trade(trade_id: int, responder_id: int,
                        offer_nft_ids: list[int] | None = None,
                        offer_clicks: float = 0) -> str:
    """Откликнуться на публичный обмен.
    Возвращает 'ok', 'not_found', 'self', 'no_nfts', 'no_clicks', 'nft_limit', 'already'."""
    from config import MAX_NFT
    db = await get_db()
    trade = await get_trade_offer(trade_id)
    if not trade:
        return "not_found"
    t_id, sender_id, receiver_id, t_offer_clicks, want_clicks, status, dt, want_nft_count = trade

    if status != "open":
        return "already"
    if responder_id == sender_id:
        return "self"

    # Если обмен хочет клики — проверяем баланс
    if want_clicks and want_clicks > 0:
        cur = await db.execute("SELECT clicks FROM users WHERE user_id = ?", (responder_id,))
        row = await cur.fetchone()
        if not row or row[0] < want_clicks:
            return "no_clicks"

    # Если обмен хочет НФТ — проверяем наличие
    if offer_nft_ids:
        for nid in offer_nft_ids:
            cur2 = await db.execute(
                "SELECT id FROM user_nfts WHERE id = ? AND user_id = ?", (nid, responder_id))
            if not await cur2.fetchone():
                return "no_nfts"

    # Проверяем лимит НФТ у создателя после обмена
    items = await get_trade_items(trade_id)
    offer_items = [i for i in items if i[2] == "offer"]
    give_count = len(offer_nft_ids) if offer_nft_ids else 0
    receive_count = len(offer_items)

    cur_s = await db.execute("SELECT COUNT(*) FROM user_nfts WHERE user_id = ?", (sender_id,))
    cnt_s = (await cur_s.fetchone())[0]
    if cnt_s - receive_count + give_count > MAX_NFT:
        return "nft_limit"

    cur_r = await db.execute("SELECT COUNT(*) FROM user_nfts WHERE user_id = ?", (responder_id,))
    cnt_r = (await cur_r.fetchone())[0]
    if cnt_r - give_count + receive_count > MAX_NFT:
        return "nft_limit"

    # Записываем предложение
    if offer_nft_ids:
        for nid in offer_nft_ids:
            await db.execute(
                "INSERT INTO nft_trade_items (trade_id, side, user_nft_id) VALUES (?, 'want', ?)",
                (trade_id, nid),
            )

    await db.execute(
        "UPDATE nft_trades SET receiver_id = ?, want_clicks = ?, status = 'proposed' WHERE id = ?",
        (responder_id, want_clicks if not offer_nft_ids else 0, trade_id),
    )
    await db.commit()
    return "ok"


async def accept_trade(trade_id: int, acceptor_id: int) -> str:
    """Принять предложение. Создатель обмена принимает.
    Возвращает: 'ok', 'not_found', 'not_owner', 'no_clicks',
                'nft_unavailable', 'nft_limit'."""
    from config import MAX_NFT
    db = await get_db()
    trade = await get_trade_offer(trade_id)
    if not trade:
        return "not_found"
    t_id, sender_id, receiver_id, offer_clicks, want_clicks, status, dt, want_nft_count = trade

    if status != "proposed":
        return "not_found"
    if acceptor_id != sender_id:
        return "not_owner"

    items = await get_trade_items(trade_id)
    offer_items = [i for i in items if i[2] == "offer"]   # НФТ создателя
    want_items = [i for i in items if i[2] == "want"]     # НФТ откликнувшегося

    # Проверяем клики у откликнувшегося (он платит want_clicks)
    if want_clicks and want_clicks > 0:
        cur = await db.execute("SELECT clicks FROM users WHERE user_id = ?", (receiver_id,))
        row = await cur.fetchone()
        if not row or row[0] < want_clicks:
            return "no_clicks"

    # Проверяем НФТ создателя (offer)
    for i in offer_items:
        cur2 = await db.execute(
            "SELECT id FROM user_nfts WHERE id = ? AND user_id = ?", (i[3], sender_id))
        if not await cur2.fetchone():
            return "nft_unavailable"

    # Проверяем НФТ откликнувшегося (want)
    for i in want_items:
        cur2 = await db.execute(
            "SELECT id FROM user_nfts WHERE id = ? AND user_id = ?", (i[3], receiver_id))
        if not await cur2.fetchone():
            return "nft_unavailable"

    # Лимиты НФТ
    cur_s = await db.execute("SELECT COUNT(*) FROM user_nfts WHERE user_id = ?", (sender_id,))
    count_s = (await cur_s.fetchone())[0]
    cur_r = await db.execute("SELECT COUNT(*) FROM user_nfts WHERE user_id = ?", (receiver_id,))
    count_r = (await cur_r.fetchone())[0]
    net_s = count_s - len(offer_items) + len(want_items)
    net_r = count_r - len(want_items) + len(offer_items)
    if net_s > MAX_NFT or net_r > MAX_NFT:
        return "nft_limit"

    # === АТОМАРНЫЙ ОБМЕН ===
    for i in offer_items:
        await db.execute("UPDATE user_nfts SET user_id = ? WHERE id = ?", (receiver_id, i[3]))
    for i in want_items:
        await db.execute("UPDATE user_nfts SET user_id = ? WHERE id = ?", (sender_id, i[3]))

    # Клики: откликнувшийся отдаёт want_clicks → создателю
    if want_clicks and want_clicks > 0:
        await db.execute("UPDATE users SET clicks = clicks - ? WHERE user_id = ?",
                         (want_clicks, receiver_id))
        await db.execute("UPDATE users SET clicks = clicks + ? WHERE user_id = ?",
                         (want_clicks, sender_id))

    # Обновляем nft_count
    for uid in (sender_id, receiver_id):
        c = await db.execute("SELECT COUNT(*) FROM user_nfts WHERE user_id = ?", (uid,))
        cnt = (await c.fetchone())[0]
        await db.execute("UPDATE users SET nft_count = ? WHERE user_id = ?", (cnt, uid))

    await db.execute("UPDATE nft_trades SET status = 'accepted' WHERE id = ?", (trade_id,))
    await db.commit()
    _invalidate(sender_id)
    _invalidate(receiver_id)
    return "ok"


async def reject_proposal(trade_id: int, owner_id: int) -> bool:
    """Отклонить предложение. Обмен возвращается на доску (status='open')."""
    db = await get_db()
    trade = await get_trade_offer(trade_id)
    if not trade or trade[5] != "proposed":
        return False
    if owner_id != trade[1]:
        return False
    # Удаляем want-items откликнувшегося
    await db.execute("DELETE FROM nft_trade_items WHERE trade_id = ? AND side = 'want'", (trade_id,))
    # Возвращаем в open
    await db.execute(
        "UPDATE nft_trades SET receiver_id = 0, status = 'open' WHERE id = ?", (trade_id,))
    await db.commit()
    return True


async def cancel_trade(trade_id: int, sender_id: int) -> bool:
    """Отменить свой обмен (создатель)."""
    db = await get_db()
    trade = await get_trade_offer(trade_id)
    if not trade or trade[5] not in ("open", "proposed"):
        return False
    if sender_id != trade[1]:
        return False
    await db.execute("UPDATE nft_trades SET status = 'cancelled' WHERE id = ?", (trade_id,))
    await db.commit()
    return True


# ==========================================================
#  ИВЕНТЫ
# ==========================================================
async def create_event(name: str, nft_prize_name: str, bet_amount: float,
                       duration_min: int, created_by: int,
                       nft_rarity: int = 3, nft_income: float = 0) -> int:
    from datetime import datetime, timedelta
    db = await get_db()
    now = datetime.utcnow()
    ends = now + timedelta(minutes=duration_min)
    cur = await db.execute(
        "INSERT INTO events (name, nft_prize_name, bet_amount, duration_min, "
        "status, created_by, created_at, ends_at, nft_rarity, nft_income) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        (name, nft_prize_name, bet_amount, duration_min, "active",
         created_by, now.isoformat(), ends.isoformat(), nft_rarity, nft_income),
    )
    await db.commit()
    return cur.lastrowid


async def get_active_events():
    db = await get_db()
    cur = await db.execute(
        "SELECT id, name, nft_prize_name, bet_amount, duration_min, status, "
        "created_by, created_at, ends_at, "
        "COALESCE(nft_rarity, 3), COALESCE(nft_income, 0) "
        "FROM events WHERE status = 'active' ORDER BY id DESC",
    )
    return await cur.fetchall()


async def get_event(event_id: int):
    db = await get_db()
    cur = await db.execute(
        "SELECT id, name, nft_prize_name, bet_amount, duration_min, status, "
        "created_by, created_at, ends_at, "
        "COALESCE(nft_rarity, 3), COALESCE(nft_income, 0) "
        "FROM events WHERE id = ?",
        (event_id,),
    )
    return await cur.fetchone()


async def join_event(event_id: int, user_id: int, bid_amount: float = 0) -> bool:
    from datetime import datetime
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO event_participants (event_id, user_id, bid_amount, joined_at) VALUES (?,?,?,?)",
            (event_id, user_id, bid_amount, datetime.utcnow().isoformat()),
        )
        await db.commit()
        return True
    except Exception:
        return False


async def update_event_bid(event_id: int, user_id: int, new_bid: float):
    """Update bid amount for existing participant."""
    db = await get_db()
    await db.execute(
        "UPDATE event_participants SET bid_amount = ? WHERE event_id = ? AND user_id = ?",
        (new_bid, event_id, user_id),
    )
    await db.commit()


async def get_user_event_bid(event_id: int, user_id: int):
    """Return current bid for user in event, or None."""
    db = await get_db()
    cur = await db.execute(
        "SELECT bid_amount FROM event_participants WHERE event_id = ? AND user_id = ?",
        (event_id, user_id),
    )
    row = await cur.fetchone()
    return row[0] if row else None


async def get_event_participants(event_id: int):
    db = await get_db()
    cur = await db.execute(
        "SELECT ep.user_id, u.username, u.clicks, ep.bid_amount "
        "FROM event_participants ep "
        "JOIN users u ON u.user_id = ep.user_id "
        "WHERE ep.event_id = ?",
        (event_id,),
    )
    return await cur.fetchall()


async def get_highest_bidder(event_id: int):
    """Return (user_id, username, clicks, bid_amount) of highest bidder."""
    db = await get_db()
    cur = await db.execute(
        "SELECT ep.user_id, u.username, u.clicks, ep.bid_amount "
        "FROM event_participants ep "
        "JOIN users u ON u.user_id = ep.user_id "
        "WHERE ep.event_id = ? "
        "ORDER BY ep.bid_amount DESC LIMIT 1",
        (event_id,),
    )
    return await cur.fetchone()


async def count_event_participants(event_id: int) -> int:
    db = await get_db()
    cur = await db.execute(
        "SELECT COUNT(*) FROM event_participants WHERE event_id = ?",
        (event_id,),
    )
    return (await cur.fetchone())[0]


# ─── Аукцион: хранение сообщений ───
async def save_auction_message(event_id: int, chat_id: int, message_id: int):
    db = await get_db()
    await db.execute(
        "INSERT INTO auction_messages (event_id, chat_id, message_id) VALUES (?,?,?)",
        (event_id, chat_id, message_id),
    )
    await db.commit()


async def get_auction_messages(event_id: int):
    db = await get_db()
    cur = await db.execute(
        "SELECT chat_id, message_id FROM auction_messages WHERE event_id = ?",
        (event_id,),
    )
    return await cur.fetchall()


async def delete_auction_messages(event_id: int):
    db = await get_db()
    await db.execute("DELETE FROM auction_messages WHERE event_id = ?", (event_id,))
    await db.commit()


# ─── Приз: подписка ───
async def get_prize_claim(user_id: int):
    db = await get_db()
    cur = await db.execute(
        "SELECT id, user_id, claimed_at, active FROM prize_claims WHERE user_id = ?",
        (user_id,),
    )
    return await cur.fetchone()


async def set_prize_claim(user_id: int):
    from datetime import datetime
    db = await get_db()
    await db.execute(
        "INSERT OR REPLACE INTO prize_claims (user_id, claimed_at, active) VALUES (?,?,?)",
        (user_id, datetime.utcnow().isoformat(), 1),
    )
    await db.commit()


async def deactivate_prize(user_id: int):
    db = await get_db()
    await db.execute(
        "UPDATE prize_claims SET active = 0 WHERE user_id = ?",
        (user_id,),
    )
    await db.commit()


async def finish_event(event_id: int):
    db = await get_db()
    await db.execute(
        "UPDATE events SET status = 'finished' WHERE id = ?",
        (event_id,),
    )
    await db.commit()


async def cancel_event(event_id: int):
    db = await get_db()
    await db.execute(
        "UPDATE events SET status = 'cancelled' WHERE id = ?",
        (event_id,),
    )
    await db.commit()


# ==========================================================
#  ЧЕКИ / ИСТОРИЯ ТРАНЗАКЦИЙ
# ==========================================================
_TX_TYPES = ("pvp", "trade", "chat", "nft_buy", "nft_sell",
             "shop", "event", "gift", "market_buy", "market_sell")


async def create_transaction(
    tx_type: str,
    user_id: int,
    user2_id: int = None,
    amount: float = 0,
    details: str = "",
    ref_id: int = None,
    status: str = "completed",
) -> int:
    """Создать чек (запись транзакции). Возвращает ID чека."""
    from datetime import datetime
    db = await get_db()
    cur = await db.execute(
        "INSERT INTO transactions (type, user_id, user2_id, amount, details, "
        "ref_id, status, created_at) VALUES (?,?,?,?,?,?,?,?)",
        (tx_type, user_id, user2_id, amount, details,
         ref_id, status, datetime.now().isoformat()),
    )
    await db.commit()
    return cur.lastrowid


async def get_transaction(tx_id: int):
    """Получить транзакцию по ID."""
    db = await get_db()
    db.row_factory = aiosqlite.Row
    cur = await db.execute("SELECT * FROM transactions WHERE id = ?", (tx_id,))
    return await cur.fetchone()


async def get_user_transactions(user_id: int, tx_type: str = None,
                                 limit: int = 10, offset: int = 0):
    """Транзакции пользователя (как user_id или user2_id)."""
    db = await get_db()
    if tx_type:
        cur = await db.execute(
            "SELECT id, type, user_id, user2_id, amount, details, ref_id, "
            "status, created_at FROM transactions "
            "WHERE (user_id = ? OR user2_id = ?) AND type = ? "
            "ORDER BY id DESC LIMIT ? OFFSET ?",
            (user_id, user_id, tx_type, limit, offset),
        )
    else:
        cur = await db.execute(
            "SELECT id, type, user_id, user2_id, amount, details, ref_id, "
            "status, created_at FROM transactions "
            "WHERE user_id = ? OR user2_id = ? "
            "ORDER BY id DESC LIMIT ? OFFSET ?",
            (user_id, user_id, limit, offset),
        )
    return await cur.fetchall()


async def count_user_transactions(user_id: int, tx_type: str = None) -> int:
    """Количество транзакций пользователя."""
    db = await get_db()
    if tx_type:
        cur = await db.execute(
            "SELECT COUNT(*) FROM transactions "
            "WHERE (user_id = ? OR user2_id = ?) AND type = ?",
            (user_id, user_id, tx_type),
        )
    else:
        cur = await db.execute(
            "SELECT COUNT(*) FROM transactions WHERE user_id = ? OR user2_id = ?",
            (user_id, user_id),
        )
    return (await cur.fetchone())[0]


async def get_all_transactions(limit: int = 30, offset: int = 0):
    """Все транзакции (для админов)."""
    db = await get_db()
    cur = await db.execute(
        "SELECT id, type, user_id, user2_id, amount, details, ref_id, "
        "status, created_at FROM transactions "
        "ORDER BY id DESC LIMIT ? OFFSET ?",
        (limit, offset),
    )
    return await cur.fetchall()


async def count_all_transactions() -> int:
    db = await get_db()
    cur = await db.execute("SELECT COUNT(*) FROM transactions")
    return (await cur.fetchone())[0]


# ==========================================================
#  ЖАЛОБЫ НА ТРАНЗАКЦИИ
# ==========================================================
async def create_complaint(tx_id: int, user_id: int, reason: str) -> int:
    """Подать жалобу на транзакцию. Возвращает ID жалобы."""
    from datetime import datetime
    db = await get_db()
    cur = await db.execute(
        "INSERT INTO complaints (transaction_id, user_id, reason, status, created_at) "
        "VALUES (?,?,?,'pending',?)",
        (tx_id, user_id, reason, datetime.now().isoformat()),
    )
    await db.commit()
    return cur.lastrowid


async def get_complaint(complaint_id: int):
    """Получить жалобу по ID."""
    db = await get_db()
    db.row_factory = aiosqlite.Row
    cur = await db.execute("SELECT * FROM complaints WHERE id = ?", (complaint_id,))
    return await cur.fetchone()


async def get_pending_complaints(limit: int = 20):
    """Жалобы со статусом pending / reviewing."""
    db = await get_db()
    cur = await db.execute(
        "SELECT c.id, c.transaction_id, c.user_id, c.reason, c.status, "
        "c.created_at, t.type, t.amount, t.details "
        "FROM complaints c "
        "JOIN transactions t ON t.id = c.transaction_id "
        "WHERE c.status IN ('pending','reviewing') "
        "ORDER BY c.id DESC LIMIT ?",
        (limit,),
    )
    return await cur.fetchall()


async def count_pending_complaints() -> int:
    db = await get_db()
    cur = await db.execute(
        "SELECT COUNT(*) FROM complaints WHERE status IN ('pending','reviewing')"
    )
    return (await cur.fetchone())[0]


async def resolve_complaint(complaint_id: int, admin_id: int,
                            action: str, comment: str = ""):
    """Разрешить жалобу. action: refund / ban / warn / reject."""
    from datetime import datetime
    db = await get_db()
    await db.execute(
        "UPDATE complaints SET status = 'resolved', admin_id = ?, "
        "admin_action = ?, admin_comment = ?, resolved_at = ? WHERE id = ?",
        (admin_id, action, comment, datetime.now().isoformat(), complaint_id),
    )
    await db.commit()


async def get_user_complaints(user_id: int, limit: int = 10):
    """Жалобы пользователя."""
    db = await get_db()
    cur = await db.execute(
        "SELECT c.id, c.transaction_id, c.reason, c.status, "
        "c.admin_action, c.admin_comment, c.created_at "
        "FROM complaints c WHERE c.user_id = ? "
        "ORDER BY c.id DESC LIMIT ?",
        (user_id, limit),
    )
    return await cur.fetchall()


async def get_complaint_by_tx(tx_id: int, user_id: int):
    """Проверить, есть ли уже жалоба от пользователя на эту транзакцию."""
    db = await get_db()
    cur = await db.execute(
        "SELECT id FROM complaints WHERE transaction_id = ? AND user_id = ?",
        (tx_id, user_id),
    )
    return await cur.fetchone()


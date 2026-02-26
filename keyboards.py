# ======================================================
# КЛАВИАТУРЫ — КликТохн v1.0.0
# ======================================================

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


# ──────────── СТАРТ ────────────
def start_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Начать ⏺️", callback_data="open_menu")]
    ])


# ──────────── ГЛАВНОЕ МЕНЮ (2 страницы) ────────────
def main_menu_kb(page: int = 0):
    if page == 0:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💢 Начать клик", callback_data="click_menu")],
            [InlineKeyboardButton(text="💵 Взять доход", callback_data="claim_income")],
            [InlineKeyboardButton(text="🔗 Пригласить", callback_data="ref_menu")],
            [InlineKeyboardButton(text="💸 Магазин", callback_data="shop_menu")],
            [InlineKeyboardButton(text="🏆 Рейтинг", callback_data="rating_menu")],
            [InlineKeyboardButton(text="Далее ▶️", callback_data="menu_page:1")],
        ])
    else:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎨 Мои НФТ", callback_data="my_nft")],
            [InlineKeyboardButton(text="💬 Случайный CHAT", callback_data="chat_menu")],
            [InlineKeyboardButton(text="⚔️ PvP игроков", callback_data="pvp_menu")],
            [InlineKeyboardButton(text="📋 История / Чеки", callback_data="history_menu")],
            [InlineKeyboardButton(text="⚠️ Поддержка", callback_data="support_menu")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="menu_page:0")],
        ])


# ──────────── 1. КЛИК ТОХН ────────────
def click_zone_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💢 Тапнуть", callback_data="tap")],
        [InlineKeyboardButton(text="⬅️ В меню", callback_data="menu")],
    ])


# ──────────── 2. ПРИГЛАСИТЬ ────────────
def referral_kb(ref_link: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="📢 Пригласить",
            url=f"https://t.me/share/url?url={ref_link}&text=Присоединяйся к КликТохн!"
        )],
        [InlineKeyboardButton(text="🎁 Приз", callback_data="prize_menu")],
        [InlineKeyboardButton(text="⬅️ В меню", callback_data="menu")],
    ])


# ──────────── 3. МАГАЗИН ────────────
def shop_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔨 Улучшение клика", callback_data="shop_upg")],
        [InlineKeyboardButton(text="📈 Пассивный доход", callback_data="shop_pas")],
        [InlineKeyboardButton(text="📦 Ёмкость дохода", callback_data="shop_cap")],
        [InlineKeyboardButton(text="🏪 Торговая площадка", callback_data="market_menu")],
        [InlineKeyboardButton(text="⬅️ В меню", callback_data="menu")],
    ])


def shop_upg_kb():
    from config import SHOP_CLICK
    kb = []
    for i, (key, (bonus, price)) in enumerate(SHOP_CLICK.items(), 1):
        kb.append([InlineKeyboardButton(
            text=f"#{i} │ +{bonus} к клику │ {int(price)} 💢",
            callback_data=f"buy_c_{key}",
        )])
    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="shop_menu")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def shop_pas_kb():
    from config import SHOP_PASSIVE
    kb = []
    for i, (key, (bonus, price)) in enumerate(SHOP_PASSIVE.items(), 1):
        kb.append([InlineKeyboardButton(
            text=f"#{i} │ +{bonus}/час │ {int(price)} 💢",
            callback_data=f"buy_p_{key}",
        )])
    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="shop_menu")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def shop_cap_kb():
    from config import SHOP_CAPACITY
    kb = []
    for i, (key, (bonus, price)) in enumerate(SHOP_CAPACITY.items(), 1):
        kb.append([InlineKeyboardButton(
            text=f"#{i} │ +{bonus} ёмкость │ {int(price)} 💢",
            callback_data=f"buy_cap_{key}",
        )])
    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="shop_menu")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def income_kb():
    """Keyboard for income screen: Claim + Menu."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Взять", callback_data="do_claim_income")],
        [InlineKeyboardButton(text="⬅️ В меню", callback_data="menu")],
    ])


# ──────────── 4. РЕЙТИНГ ────────────
def rating_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏆 Топ - 50 Игроков", callback_data="top_50")],
        [InlineKeyboardButton(text="⬅️ В меню", callback_data="menu")],
    ])


# ──────────── 5. СЛУЧАЙНЫЙ CHAT ────────────
def chat_menu_kb():
    """Главное меню чата — НЕТ кнопки остановить."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Найти собеседника", callback_data="chat_search")],
        [InlineKeyboardButton(text="📋 Мои чаты", callback_data="chat_list")],
        [InlineKeyboardButton(text="📜 История", callback_data="chat_history")],
        [InlineKeyboardButton(text="⬅️ В меню", callback_data="menu")],
    ])


def chat_confirm_search_kb():
    """Подтверждение оплаты поиска собеседника."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, искать (-50 💢)", callback_data="chat_search_confirm")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="chat_menu")],
    ])


def chat_searching_kb():
    """Клавиатура во время поиска."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏹ Остановить поиск", callback_data="chat_stop_search")],
    ])


def chat_active_kb():
    """Клавиатура активного чата."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔇 Завершить чат", callback_data="chat_end")],
        [InlineKeyboardButton(text="🔍 Новый собеседник", callback_data="chat_next")],
    ])


def chat_ended_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Искать снова", callback_data="chat_search")],
        [InlineKeyboardButton(text="⬅️ В меню", callback_data="menu")],
    ])


# ──────────── 6. PvP ────────────
def pvp_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Найти бои", callback_data="pvp_find")],
        [InlineKeyboardButton(text="⚔️ Создать бой", callback_data="pvp_create")],
        [InlineKeyboardButton(text="📊 Мои бои", callback_data="pvp_history")],
        [InlineKeyboardButton(text="⬅️ В меню", callback_data="menu")],
    ])


def pvp_create_type_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✂️ КНБ", callback_data="pvp_type_rps"),
            InlineKeyboardButton(text="🎲 Кости", callback_data="pvp_type_dice"),
        ],
        [
            InlineKeyboardButton(text="🪙 Монетка", callback_data="pvp_type_flip"),
            InlineKeyboardButton(text="🎰 Слоты", callback_data="pvp_type_slots"),
        ],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="pvp_menu")],
    ])


def pvp_bet_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="100 💢", callback_data="pvp_bet_100"),
            InlineKeyboardButton(text="500 💢", callback_data="pvp_bet_500"),
        ],
        [
            InlineKeyboardButton(text="1000 💢", callback_data="pvp_bet_1000"),
            InlineKeyboardButton(text="5000 💢", callback_data="pvp_bet_5000"),
        ],
        [InlineKeyboardButton(text="✏️ Своя сумма", callback_data="pvp_bet_custom")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="pvp_create")],
    ])


def pvp_rps_kb(game_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🪨 Камень", callback_data=f"rps_{game_id}_rock"),
            InlineKeyboardButton(text="✂️ Ножницы", callback_data=f"rps_{game_id}_scissors"),
            InlineKeyboardButton(text="📄 Бумага", callback_data=f"rps_{game_id}_paper"),
        ],
    ])


def pvp_rounds_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="1️⃣ Bo1 (1 раунд)", callback_data="pvp_rounds_1"),
            InlineKeyboardButton(text="3️⃣ Bo3 (до 2 побед)", callback_data="pvp_rounds_3"),
        ],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="pvp_create")],
    ])


def pvp_dice_kb(game_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎲 Бросить кости", callback_data=f"dice_{game_id}_roll")],
    ])


def pvp_flip_kb(game_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🌕 Орёл", callback_data=f"flip_{game_id}_eagle"),
            InlineKeyboardButton(text="🌑 Решка", callback_data=f"flip_{game_id}_tails"),
        ],
    ])


def pvp_slots_kb(game_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎰 Крутить барабан", callback_data=f"slots_{game_id}_spin")],
    ])


# ──────────── 7. ПОДДЕРЖКА ────────────
def support_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚩 Жалоба", callback_data="support_complaint")],
        [InlineKeyboardButton(text="🐛 Проблема / Баг", callback_data="support_problem")],
        [InlineKeyboardButton(text="📨 Мои обращения", callback_data="support_my_tickets")],
        [InlineKeyboardButton(text="⬅️ В меню", callback_data="menu")],
    ])


def back_support_kb():
    """Назад в меню поддержки."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Поддержка", callback_data="support_menu")],
        [InlineKeyboardButton(text="🏠 В меню", callback_data="menu")],
    ])


def back_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ В меню", callback_data="menu")],
    ])


# ──────────── УТИЛИТЫ ────────────
def _rarity_emoji(rarity: int) -> str:
    """Текстовый уровень редкости (1-5)."""
    return {
        1: "🔴 Легендарный",
        2: "🟠 Эпический",
        3: "🟣 Редкий",
        4: "🔵 Необычный",
        5: "🟢 Обычный",
    }.get(rarity, "🟢 Обычный")


# ──────────── 8. МОИ НФТ ────────────
def my_nft_kb(user_nfts: list, max_nft: int = 5):
    """Клавиатура со списком НФТ пользователя + пустые слоты."""
    kb = []
    for idx, (un_id, name, income, rarity, bought, dt) in enumerate(user_nfts, 1):
        label = _rarity_emoji(rarity)
        kb.append([InlineKeyboardButton(
            text=f"#{idx} {label} ∙ {name}",
            callback_data=f"nft_info_{un_id}",
        )])
    # Пустые слоты
    for i in range(len(user_nfts) + 1, max_nft + 1):
        kb.append([InlineKeyboardButton(
            text=f"#{i} ── пусто ──",
            callback_data="noop",
        )])
    kb.append([InlineKeyboardButton(text="⬅️ В меню", callback_data="menu")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def nft_detail_kb(user_nft_id: int, on_sale: bool = False):
    """Детали конкретного НФТ — кнопки продать / обменять."""
    kb = []
    if on_sale:
        kb.append([InlineKeyboardButton(text="🚫 Снять с продажи", callback_data=f"nft_unsell_{user_nft_id}")])
    else:
        kb.append([
            InlineKeyboardButton(text="💰 Продать", callback_data=f"nft_sell_{user_nft_id}"),
            InlineKeyboardButton(text="🔄 Обменять", callback_data=f"nft_trade_{user_nft_id}"),
        ])
    kb.append([InlineKeyboardButton(text="⬅️ Назад к НФТ", callback_data="my_nft")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def nft_sell_confirm_kb(user_nft_id: int):
    """Подтверждение продажи."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, выставить", callback_data=f"nft_sell_yes_{user_nft_id}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="my_nft")],
    ])


# ──────────── 9. ТОРГОВАЯ ПЛОЩАДКА (НФТ ПРОДАЖИ) ────────────
def nft_marketplace_kb(items: list, page: int, total_pages: int):
    """Пагинированная клавиатура торговой площадки НФТ."""
    kb = []
    for item in items:
        item_type, item_id, name, rarity, income, price, seller_id = item
        label = _rarity_emoji(rarity)
        icon = "🛒" if item_type == 'tpl' else "👤"
        cb = f"nftv_{item_type}_{item_id}"
        kb.append([InlineKeyboardButton(
            text=f"{icon} {label} ∙ {name}",
            callback_data=cb,
        )])
    # Навигация
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀", callback_data=f"nftp_{page - 1}"))
    nav.append(InlineKeyboardButton(text=f"📄 {page + 1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="▶", callback_data=f"nftp_{page + 1}"))
    if total_pages > 0:
        kb.append(nav)
    kb.append([InlineKeyboardButton(text="⬅️ В магазин", callback_data="shop_menu")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def nft_buy_confirm_kb(item_type: str, item_id: int):
    """Кнопки подтверждения покупки НФТ."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, купить", callback_data=f"nftb_{item_type}_{item_id}")],
        [InlineKeyboardButton(text="❌ Нет", callback_data="nftp_0")],
    ])


def market_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛍 НФТ Продажи", callback_data="nftp_0")],
        [InlineKeyboardButton(text="🔄 Обмен НФТ", callback_data="trade_menu")],
        [InlineKeyboardButton(text="⬅️ В магазин", callback_data="shop_menu")],
    ])


# ──────────── 10. ПАНЕЛЬ ВЛАДЕЛЬЦА (2 страницы) ────────────
def owner_panel_kb(page: int = 0):
    """Панель владельца, разделённая на 2 страницы с навигацией ◀ ▶."""
    if page == 0:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📊 Статистика", callback_data="owner_stats")],
            [InlineKeyboardButton(text="👥 Участники", callback_data="owner_users")],
            [
                InlineKeyboardButton(text="🔨 Бан", callback_data="owner_ban"),
                InlineKeyboardButton(text="✅ Разбан", callback_data="owner_unban"),
            ],
            [InlineKeyboardButton(text="🚫 Список забаненных", callback_data="owner_banned_list")],
            [InlineKeyboardButton(text="👀 Переписки", callback_data="owner_chat_logs")],
            [InlineKeyboardButton(text="📋 Тикеты / Жалобы", callback_data="owner_tickets")],
            [InlineKeyboardButton(text="📨 Жалобы на чеки", callback_data="compl_pg:0")],
            [
                InlineKeyboardButton(text="▶️ Далее", callback_data="owner_panel_page:1"),
                InlineKeyboardButton(text="⬅️ Выход", callback_data="menu"),
            ],
        ])
    else:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💰 Выдать клики", callback_data="owner_give")],
            [InlineKeyboardButton(text="📢 Рассылка", callback_data="owner_broadcast")],
            [
                InlineKeyboardButton(text="🎨 Создать НФТ", callback_data="owner_nft_create"),
                InlineKeyboardButton(text="🗑 Удалить НФТ", callback_data="owner_nft_list"),
            ],
            [InlineKeyboardButton(text="👮 Администраторы", callback_data="owner_admins")],
            [InlineKeyboardButton(text="⚙️ Настройки", callback_data="owner_settings")],
            [
                InlineKeyboardButton(text="🗑 Сброс кликов", callback_data="owner_reset_clicks"),
                InlineKeyboardButton(text="🔄 Сброс прогресса", callback_data="owner_reset_progress"),
            ],
            [InlineKeyboardButton(text="💣 Сбросить всё", callback_data="owner_reset_all")],
            [InlineKeyboardButton(text="� Создать аукцион", callback_data="event_create")],
            [InlineKeyboardButton(text="☢️ Сбросить ВСЕХ игроков", callback_data="owner_wipe_all")],
            [
                InlineKeyboardButton(text="◀️ Назад", callback_data="owner_panel_page:0"),
                InlineKeyboardButton(text="⬅️ Выход", callback_data="menu"),
            ],
        ])
def owner_tickets_kb(tickets: list):
    """Список тикетов с кнопками принять/отклонить."""
    kb = []
    for tid, uid, ttype, msg, dt in tickets:
        short = msg[:30] + "..." if len(msg) > 30 else msg
        kb.append([
            InlineKeyboardButton(text=f"#{tid} {ttype}: {short}", callback_data=f"ticket_view_{tid}")
        ])
        kb.append([
            InlineKeyboardButton(text="✅ Принять", callback_data=f"ticket_accept_{tid}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"ticket_reject_{tid}"),
        ])
    kb.append([InlineKeyboardButton(text="⬅️ Панель", callback_data="owner_panel")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def owner_nft_list_kb(templates: list):
    """Список НФТ для удаления."""
    kb = []
    for tid, name, income, rarity, price in templates:
        kb.append([InlineKeyboardButton(
            text=f"🗑 #{tid} {name}",
            callback_data=f"owner_nft_del_{tid}",
        )])
    kb.append([InlineKeyboardButton(text="⬅️ Панель", callback_data="owner_panel")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def owner_nft_publish_kb():
    """Опубликовать / Отменить при создании НФТ."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Опубликовать", callback_data="owner_nft_publish")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="owner_nft_cancel")],
    ])


def owner_back_panel_kb():
    """Кнопка назад в панель."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Панель", callback_data="owner_panel")],
    ])


# ──────────── 10а. УПРАВЛЕНИЕ АДМИНИСТРАТОРАМИ (владелец) ────────────
def owner_admins_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👮 Список админов", callback_data="owner_admin_list")],
        [InlineKeyboardButton(text="🔑 Создать ключ", callback_data="owner_admin_genkey")],
        [InlineKeyboardButton(text="📋 Все ключи", callback_data="owner_admin_keys")],
        [InlineKeyboardButton(text="📊 Лог действий", callback_data="owner_admin_log")],
        [InlineKeyboardButton(text="❌ Снять админа", callback_data="owner_admin_remove")],
        [InlineKeyboardButton(text="⬅️ Панель", callback_data="owner_panel")],
    ])


# ──────────── 11. ПАНЕЛЬ АДМИНИСТРАТОРА (2 стр) ────────────
def admin_panel_kb(page: int = 0):
    if page == 0:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 Жалобы / Тикеты", callback_data="adm_tickets")],
            [InlineKeyboardButton(text="📨 Жалобы на чеки", callback_data="compl_pg:0")],
            [
                InlineKeyboardButton(text="🔨 Бан", callback_data="adm_ban"),
                InlineKeyboardButton(text="✅ Разбан", callback_data="adm_unban"),
            ],
            [InlineKeyboardButton(text="🚫 Забаненные", callback_data="adm_banned_list")],
            [InlineKeyboardButton(text="👀 Переписки", callback_data="adm_chat_logs")],
            [InlineKeyboardButton(text="📊 Мои действия", callback_data="adm_my_log")],
            [
                InlineKeyboardButton(text="▶️ Далее", callback_data="adm_panel_page:1"),
                InlineKeyboardButton(text="⬅️ В меню", callback_data="menu"),
            ],
        ])
    else:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎨 Создать НФТ", callback_data="adm_nft_create")],
            [InlineKeyboardButton(text="💰 Выдать клики", callback_data="adm_give")],
            [InlineKeyboardButton(text="📢 Рассылка", callback_data="adm_broadcast")],
            [
                InlineKeyboardButton(text="🗑 Сброс кликов", callback_data="adm_reset_clicks"),
                InlineKeyboardButton(text="🔄 Сброс прогресса", callback_data="adm_reset_progress"),
            ],
            [InlineKeyboardButton(text="� Создать аукцион", callback_data="event_create")],
            [
                InlineKeyboardButton(text="◀️ Назад", callback_data="adm_panel_page:0"),
                InlineKeyboardButton(text="⬅️ В меню", callback_data="menu"),
            ],
        ])


def admin_back_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Панель админа", callback_data="admin_panel")],
    ])


# ══════════════════════════════════════════════════════════
#  12. ИСТОРИЯ ТРАНЗАКЦИЙ (ЧЕКИ)
# ══════════════════════════════════════════════════════════

_TX_TYPE_LABELS = {
    "all":         "📋 Все",
    "pvp":         "⚔️ PvP",
    "trade":       "🔄 Обмены",
    "chat":        "💬 Чаты",
    "nft_buy":     "🛒 Покупки НФТ",
    "nft_sell":    "💰 Продажи НФТ",
    "market_buy":  "🏪 Покупки (площадка)",
    "market_sell": "🏪 Продажи (площадка)",
    "shop":        "🔧 Магазин",
    "event":       "🎉 Ивенты",
    "gift":        "🎁 Подарки",
}

_TX_ICON = {
    "pvp": "⚔️", "trade": "🔄", "chat": "💬",
    "nft_buy": "🛒", "nft_sell": "💰", "shop": "🔧",
    "event": "🎉", "gift": "🎁",
    "market_buy": "🏪", "market_sell": "🏪",
}


def history_menu_kb():
    """Главное меню истории — фильтры по типу."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Все чеки", callback_data="hist:all:0")],
        [
            InlineKeyboardButton(text="⚔️ PvP", callback_data="hist:pvp:0"),
            InlineKeyboardButton(text="🔄 Обмены", callback_data="hist:trade:0"),
        ],
        [
            InlineKeyboardButton(text="💬 Чаты", callback_data="hist:chat:0"),
            InlineKeyboardButton(text="🎉 Ивенты", callback_data="hist:event:0"),
        ],
        [
            InlineKeyboardButton(text="🛒 НФТ покупки", callback_data="hist:nft_buy:0"),
            InlineKeyboardButton(text="💰 НФТ продажи", callback_data="hist:nft_sell:0"),
        ],
        [
            InlineKeyboardButton(text="🔧 Магазин", callback_data="hist:shop:0"),
            InlineKeyboardButton(text="🎁 Подарки", callback_data="hist:gift:0"),
        ],
        [InlineKeyboardButton(text="📨 Мои жалобы", callback_data="my_complaints:0")],
        [InlineKeyboardButton(text="⬅️ В меню", callback_data="menu")],
    ])


def history_list_kb(items: list, page: int, total_pages: int,
                    tx_filter: str = "all"):
    """Пагинированный список чеков."""
    kb = []
    for item in items:
        tx_id, tx_type = item[0], item[1]
        amount = item[4]
        details = item[5] or ""
        icon = _TX_ICON.get(tx_type, "📋")
        short_det = details[:28] + ".." if len(details) > 30 else details
        amount_str = f" {int(amount)}💢" if amount else ""
        kb.append([InlineKeyboardButton(
            text=f"{icon} #{tx_id}{amount_str} ∙ {short_det}",
            callback_data=f"check:{tx_id}",
        )])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(
            text="◀", callback_data=f"hist:{tx_filter}:{page - 1}"))
    nav.append(InlineKeyboardButton(
        text=f"📄 {page + 1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(
            text="▶", callback_data=f"hist:{tx_filter}:{page + 1}"))
    if nav:
        kb.append(nav)
    kb.append([InlineKeyboardButton(
        text="🔍 Фильтры", callback_data="history_menu")])
    kb.append([InlineKeyboardButton(
        text="⬅️ В меню", callback_data="menu")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def check_detail_kb(tx_id: int, can_complain: bool = True, is_admin: bool = False):
    """Кнопки на детальном просмотре чека."""
    kb = []
    if can_complain:
        kb.append([InlineKeyboardButton(
            text="⚠️ Подать жалобу", callback_data=f"complain:{tx_id}")])
    if is_admin:
        kb.append([InlineKeyboardButton(
            text="🔨 Админ-действие", callback_data=f"adm_check:{tx_id}")])
    kb.append([InlineKeyboardButton(
        text="⬅️ К списку", callback_data="hist:all:0")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def complaints_list_kb(complaints: list, page: int = 0, total_pages: int = 1):
    """Список жалоб (для админов)."""
    kb = []
    for c in complaints:
        c_id, tx_id, uid, reason, status, dt, tx_type, amount, details = c
        icon = _TX_ICON.get(tx_type, "📋")
        short_r = reason[:25] + ".." if len(reason) > 27 else reason
        status_icon = "🟡" if status == "pending" else "🔵"
        kb.append([InlineKeyboardButton(
            text=f"{status_icon} #{c_id} {icon} Чек#{tx_id} ∙ {short_r}",
            callback_data=f"compl_view:{c_id}",
        )])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀", callback_data=f"compl_pg:{page-1}"))
    nav.append(InlineKeyboardButton(text=f"📄 {page+1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="▶", callback_data=f"compl_pg:{page+1}"))
    if nav:
        kb.append(nav)
    kb.append([InlineKeyboardButton(text="⬅️ Панель", callback_data="admin_panel")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def complaint_action_kb(complaint_id: int):
    """Действия админа по жалобе."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💸 Возврат", callback_data=f"compl_act:{complaint_id}:refund"),
            InlineKeyboardButton(text="⚠️ Предупреждение", callback_data=f"compl_act:{complaint_id}:warn"),
        ],
        [
            InlineKeyboardButton(text="🔨 Бан", callback_data=f"compl_act:{complaint_id}:ban"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"compl_act:{complaint_id}:reject"),
        ],
        [InlineKeyboardButton(text="📝 Чек доказательство", callback_data=f"compl_check:{complaint_id}")],
        [InlineKeyboardButton(text="⬅️ К жалобам", callback_data="compl_pg:0")],
    ])


def my_complaints_kb(complaints: list, page: int = 0, total_pages: int = 1):
    """Список жалоб пользователя."""
    kb = []
    for c in complaints:
        c_id, tx_id, reason, status, action, comment, dt = c
        s_icon = {"pending": "🟡", "reviewing": "🔵", "resolved": "✅"}.get(status, "⚪")
        short_r = reason[:25] + ".." if len(reason) > 27 else reason
        kb.append([InlineKeyboardButton(
            text=f"{s_icon} #{c_id} ∙ Чек #{tx_id} ∙ {short_r}",
            callback_data=f"my_compl:{c_id}",
        )])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀", callback_data=f"my_complaints:{page-1}"))
    nav.append(InlineKeyboardButton(text=f"📄 {page+1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="▶", callback_data=f"my_complaints:{page+1}"))
    if nav:
        kb.append(nav)
    kb.append([InlineKeyboardButton(text="⬅️ История", callback_data="history_menu")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def adm_check_action_kb(tx_id: int):
    """Админ-действия прямо из чека."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Инфо игрока 1", callback_data=f"adm_tx_u1:{tx_id}")],
        [InlineKeyboardButton(text="👤 Инфо игрока 2", callback_data=f"adm_tx_u2:{tx_id}")],
        [
            InlineKeyboardButton(text="🔨 Бан игрока", callback_data=f"adm_tx_ban:{tx_id}"),
            InlineKeyboardButton(text="💸 Возврат", callback_data=f"adm_tx_refund:{tx_id}"),
        ],
        [InlineKeyboardButton(text="⬅️ К чеку", callback_data=f"check:{tx_id}")],
    ])

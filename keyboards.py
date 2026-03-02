# ======================================================
# КЛАВИАТУРЫ — КликТохн v1.0.1  ·  Premium UI
# ======================================================
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import NFT_RARITY_EMOJI


def _rarity_emoji(rarity_name: str) -> str:
    return NFT_RARITY_EMOJI.get(rarity_name, "🟢")


# ━━━━━━━━━━━━  СТАРТ  ━━━━━━━━━━━━
def start_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Начать игру", callback_data="open_menu")],
    ])


# ━━━━━━━━━━━━  ГЛАВНОЕ МЕНЮ (2 стр.)  ━━━━━━━━━━━━
def main_menu_kb(page: int = 0):
    if page == 0:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💢 Клик", callback_data="click_menu")],
            [
                InlineKeyboardButton(text="🎨 Мои НФТ", callback_data="my_nft"),
                InlineKeyboardButton(text="💸 Магазин", callback_data="shop_menu"),
            ],
            [
                InlineKeyboardButton(text="🎮 Мини-игры", callback_data="minigames_menu"),
                InlineKeyboardButton(text="🔗 Пригласить", callback_data="ref_menu"),
            ],
            [InlineKeyboardButton(text="▶️ Ещё", callback_data="menu_page:1")],
        ])
    else:
        return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🏆 Рейтинг", callback_data="rating_menu"),
                InlineKeyboardButton(text="⚠️ Поддержка", callback_data="support_menu"),
            ],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="menu_page:0")],
        ])


# ━━━━━━━━━━━━  КЛИК / ДОХОД  ━━━━━━━━━━━━
def click_zone_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💢 Тапнуть", callback_data="tap")],
        [
            InlineKeyboardButton(text="💵 Доход", callback_data="claim_income"),
            InlineKeyboardButton(text="🏠 Меню", callback_data="menu"),
        ],
    ])


def income_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Собрать доход", callback_data="do_claim_income")],
        [
            InlineKeyboardButton(text="💢 К клику", callback_data="click_menu"),
            InlineKeyboardButton(text="🏠 Меню", callback_data="menu"),
        ],
    ])


# ━━━━━━━━━━━━  ПРИГЛАСИТЬ  ━━━━━━━━━━━━
def referral_kb(ref_link: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="📢 Поделиться ссылкой",
            url=f"https://t.me/share/url?url={ref_link}&text=Присоединяйся к КликТохн!"
        )],
        [InlineKeyboardButton(text="🎁 Получить приз", callback_data="prize_menu")],
        [InlineKeyboardButton(text="⬅️ Меню", callback_data="menu")],
    ])


# ━━━━━━━━━━━━  МАГАЗИН  ━━━━━━━━━━━━
def shop_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔨 Клик", callback_data="shop_upg"),
            InlineKeyboardButton(text="📈 Доход", callback_data="shop_pas"),
        ],
        [
            InlineKeyboardButton(text="📦 Ёмкость", callback_data="shop_cap"),
            InlineKeyboardButton(text="🔓 Слоты НФТ", callback_data="shop_nft_slot"),
        ],
        [InlineKeyboardButton(text="🏪 Торговая площадка", callback_data="market_menu")],
        [InlineKeyboardButton(text="💳 Оплата (Сбербанк)", callback_data="payment_menu")],
        [InlineKeyboardButton(text="⬅️ Меню", callback_data="menu")],
    ])


def shop_upg_kb(user_clicks: float = 0):
    from config import SHOP_CLICK
    kb = []
    for i, (key, (bonus, price)) in enumerate(SHOP_CLICK.items(), 1):
        mark = "✅" if user_clicks >= price else "❌"
        kb.append([InlineKeyboardButton(
            text=f"{mark} #{i}  ·  +{bonus} клик  ·  {int(price):,} 💢".replace(",", "."),
            callback_data=f"buy_c_{key}",
        )])
    kb.append([InlineKeyboardButton(text="⬅️ Магазин", callback_data="shop_menu")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def shop_pas_kb(user_clicks: float = 0):
    from config import SHOP_PASSIVE
    kb = []
    for i, (key, (bonus, price)) in enumerate(SHOP_PASSIVE.items(), 1):
        mark = "✅" if user_clicks >= price else "❌"
        kb.append([InlineKeyboardButton(
            text=f"{mark} #{i}  ·  +{bonus}/ч  ·  {int(price):,} 💢".replace(",", "."),
            callback_data=f"buy_p_{key}",
        )])
    kb.append([InlineKeyboardButton(text="⬅️ Магазин", callback_data="shop_menu")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def shop_cap_kb(user_clicks: float = 0):
    from config import SHOP_CAPACITY
    kb = []
    for i, (key, (bonus, price)) in enumerate(SHOP_CAPACITY.items(), 1):
        mark = "✅" if user_clicks >= price else "❌"
        kb.append([InlineKeyboardButton(
            text=f"{mark} #{i}  ·  +{bonus} ёмк.  ·  {int(price):,} 💢".replace(",", "."),
            callback_data=f"buy_cap_{key}",
        )])
    kb.append([InlineKeyboardButton(text="⬅️ Магазин", callback_data="shop_menu")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def shop_nft_slot_kb(user_clicks: float = 0):
    from config import SHOP_NFT_SLOT
    kb = []
    for i, (key, (bonus, price)) in enumerate(SHOP_NFT_SLOT.items(), 1):
        mark = "✅" if user_clicks >= price else "❌"
        kb.append([InlineKeyboardButton(
            text=f"{mark} #{i}  ·  +{bonus} слот  ·  {int(price):,} 💢".replace(",", "."),
            callback_data=f"buy_slot_{key}",
        )])
    kb.append([InlineKeyboardButton(text="⬅️ Магазин", callback_data="shop_menu")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


# ━━━━━━━━━━━━  ОПЛАТА  ━━━━━━━━━━━━
def payment_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💢 Купить Тохн", callback_data="pay_clicks_menu")],
        [InlineKeyboardButton(text="⭐ VIP / 💎 Premium", callback_data="pay_vip_menu")],
        [InlineKeyboardButton(text="📦 Мои заказы", callback_data="my_orders:0")],
        [InlineKeyboardButton(text="⬅️ Магазин", callback_data="shop_menu")],
    ])


def pay_clicks_packages_kb():
    from config import CLICK_PACKAGES
    kb = []
    for key, (clicks, price_rub, label) in CLICK_PACKAGES.items():
        kb.append([InlineKeyboardButton(text=label, callback_data=f"buy_pkg:{key}")])
    kb.append([InlineKeyboardButton(text="⬅️ Оплата", callback_data="payment_menu")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def pay_vip_packages_kb():
    from config import VIP_PACKAGES
    kb = []
    for key, (mc, mi, dur, price_rub, label) in VIP_PACKAGES.items():
        kb.append([InlineKeyboardButton(text=label, callback_data=f"buy_vip:{key}")])
    kb.append([InlineKeyboardButton(text="⬅️ Оплата", callback_data="payment_menu")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def pay_order_pending_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 Мои заказы", callback_data="my_orders:0")],
        [InlineKeyboardButton(text="⬅️ Магазин", callback_data="shop_menu")],
    ])


def owner_orders_kb(orders, page, total_pages, prefix="owner"):
    panel_cb = "owner_panel" if prefix == "owner" else "admin_panel"
    orders_cb = f"{prefix}_orders" if prefix != "owner" else "owner_orders"
    view_cb = f"{prefix}_order_view" if prefix != "owner" else "order_view"
    kb = []
    for o in orders:
        oid, uid, ptype, pid, method, rub, status, dt = o
        short_dt = dt[:10] if dt else ""
        st = "🟡" if status == "pending" else ("✅" if status == "approved" else "🔴")
        kb.append([InlineKeyboardButton(
            text=f"{st} #{oid} │ {uid} │ {rub}₽ │ {short_dt}",
            callback_data=f"{view_cb}:{oid}",
        )])
    nav = []
    if total_pages > 1:
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"{orders_cb}:{min(page + 1, total_pages - 1)}"))
        nav.append(InlineKeyboardButton(text="⏭️", callback_data=f"{orders_cb}:{total_pages - 1}"))
        nav.append(InlineKeyboardButton(text=f"📂 {page+1}/{total_pages}", callback_data="noop"))
        nav.append(InlineKeyboardButton(text="⏮️", callback_data=f"{orders_cb}:0"))
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"{orders_cb}:{max(page - 1, 0)}"))
    if nav:
        kb.append(nav)
    kb.append([InlineKeyboardButton(text="⬅️ Панель", callback_data=panel_cb)])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def order_action_kb(order_id: int, prefix="owner"):
    p = f"{prefix}_order" if prefix != "owner" else "order"
    orders_cb = f"{prefix}_orders" if prefix != "owner" else "owner_orders"
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Одобрить", callback_data=f"{p}_approve:{order_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"{p}_reject:{order_id}"),
        ],
        [
            InlineKeyboardButton(text="💬 Написать", callback_data=f"{p}_msg:{order_id}"),
            InlineKeyboardButton(text="🚫 Фейк", callback_data=f"{p}_fake:{order_id}"),
        ],
        [InlineKeyboardButton(text="⬅️ К заказам", callback_data=f"{orders_cb}:0")],
    ])


# ━━━━━━━━━━━━  МИНИ-ИГРЫ  ━━━━━━━━━━━━
def minigames_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⚔️ PvP", callback_data="pvp_menu"),
            InlineKeyboardButton(text="💬 Чат", callback_data="chat_menu"),
        ],
        [InlineKeyboardButton(text="⬅️ Меню", callback_data="menu")],
    ])


# ━━━━━━━━━━━━  РЕЙТИНГ  ━━━━━━━━━━━━
def rating_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🥇 Топ 1—3", callback_data="top_range:0")],
        [InlineKeyboardButton(text="🥈 Топ 4—6", callback_data="top_range:1")],
        [InlineKeyboardButton(text="🥉 Топ 7—9", callback_data="top_range:2")],
        [InlineKeyboardButton(text="🏅 Топ 10—12", callback_data="top_range:3")],
        [InlineKeyboardButton(text="⭐ Топ 13—15", callback_data="top_range:4")],
        [InlineKeyboardButton(text="🔥 Топ 16—18", callback_data="top_range:5")],
        [InlineKeyboardButton(text="💎 Топ 19—20", callback_data="top_range:6")],
        [InlineKeyboardButton(text="⬅️ Меню", callback_data="menu")],
    ])


# ━━━━━━━━━━━━  СЛУЧАЙНЫЙ ЧАТ  ━━━━━━━━━━━━
def chat_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Найти собеседника", callback_data="chat_search")],
        [InlineKeyboardButton(text="📋 Мои чаты", callback_data="chat_list")],
        [InlineKeyboardButton(text="⬅️ Мини-игры", callback_data="minigames_menu")],
    ])


def chat_confirm_search_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Искать (−50 💢)", callback_data="chat_search_confirm")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="chat_menu")],
    ])


def chat_searching_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏹ Остановить поиск", callback_data="chat_stop_search")],
    ])


def chat_active_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔇 Завершить", callback_data="chat_end"),
            InlineKeyboardButton(text="🔍 Следующий", callback_data="chat_next"),
        ],
    ])


def chat_ended_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Искать снова", callback_data="chat_search")],
        [InlineKeyboardButton(text="⬅️ Меню", callback_data="menu")],
    ])


# ━━━━━━━━━━━━  PvP  ━━━━━━━━━━━━
def pvp_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔍 Найти", callback_data="pvp_find"),
            InlineKeyboardButton(text="⚔️ Создать", callback_data="pvp_create"),
        ],
        [InlineKeyboardButton(text="📊 Мои бои", callback_data="pvp_history")],
        [InlineKeyboardButton(text="⬅️ Мини-игры", callback_data="minigames_menu")],
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
        [InlineKeyboardButton(text="❌⭕ Крестики-Нолики", callback_data="pvp_type_ttt")],
        [InlineKeyboardButton(text="⬅️ PvP", callback_data="pvp_menu")],
    ])


def pvp_rounds_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="1️⃣ 1 раунд", callback_data="pvp_rounds_1"),
            InlineKeyboardButton(text="2️⃣ 2 раунда", callback_data="pvp_rounds_2"),
        ],
        [
            InlineKeyboardButton(text="3️⃣ 3 раунда", callback_data="pvp_rounds_3"),
            InlineKeyboardButton(text="4️⃣ 4 раунда", callback_data="pvp_rounds_4"),
        ],
        [InlineKeyboardButton(text="⬅️ PvP", callback_data="pvp_create")],
    ])


def pvp_bet_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="100 💢", callback_data="pvp_bet_100"),
            InlineKeyboardButton(text="500 💢", callback_data="pvp_bet_500"),
        ],
        [
            InlineKeyboardButton(text="1 000 💢", callback_data="pvp_bet_1000"),
            InlineKeyboardButton(text="5 000 💢", callback_data="pvp_bet_5000"),
        ],
        [InlineKeyboardButton(text="✏️ Своя сумма", callback_data="pvp_bet_custom")],
        [InlineKeyboardButton(text="⬅️ PvP", callback_data="pvp_create")],
    ])


def pvp_rps_kb(game_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🪨 Камень", callback_data=f"rps_{game_id}_rock"),
            InlineKeyboardButton(text="✂️ Ножницы", callback_data=f"rps_{game_id}_scissors"),
            InlineKeyboardButton(text="📄 Бумага", callback_data=f"rps_{game_id}_paper"),
        ],
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
        [InlineKeyboardButton(text="🎰 Крутить", callback_data=f"slots_{game_id}_spin")],
    ])


def pvp_ttt_kb(game_id: int, board: str = "." * 9):
    """Клавиатура 3×3 для крестиков-ноликов. board — строка из 9 символов: '.', 'X', 'O'."""
    _sym = {"X": "❌", "O": "⭕", ".": "⬜"}
    rows = []
    for r in range(3):
        row = []
        for c in range(3):
            idx = r * 3 + c
            ch = board[idx]
            if ch == ".":
                row.append(InlineKeyboardButton(text="⬜", callback_data=f"ttt_{game_id}_{idx}"))
            else:
                row.append(InlineKeyboardButton(text=_sym[ch], callback_data="noop"))
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ━━━━━━━━━━━━  ПОДДЕРЖКА  ━━━━━━━━━━━━
def support_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🚩 Жалоба", callback_data="support_complaint"),
            InlineKeyboardButton(text="🐛 Баг", callback_data="support_problem"),
        ],
        [InlineKeyboardButton(text="📨 Мои обращения", callback_data="support_my_tickets")],
        [InlineKeyboardButton(text="📋 История / Чеки", callback_data="history_menu")],
        [InlineKeyboardButton(text="⬅️ Меню", callback_data="menu")],
    ])


def back_support_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⬅️ Поддержка", callback_data="support_menu"),
            InlineKeyboardButton(text="🏠 Меню", callback_data="menu"),
        ],
    ])


def back_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Меню", callback_data="menu")],
    ])


# ━━━━━━━━━━━━  МОИ НФТ  ━━━━━━━━━━━━
NFT_PER_PAGE = 5


def my_nft_kb(user_nfts: list, max_nft: int = 5, page: int = 0):
    import math
    total_nfts = len(user_nfts)
    total_pages = max(1, math.ceil(total_nfts / NFT_PER_PAGE)) if total_nfts > 0 else 1
    if page < 0:
        page = 0
    if page >= total_pages:
        page = total_pages - 1

    start = page * NFT_PER_PAGE
    end = start + NFT_PER_PAGE
    page_nfts = user_nfts[start:end]

    kb = []
    for idx, nft in enumerate(page_nfts, start + 1):
        un_id = nft[0]
        name = nft[1]
        rarity_name = nft[4] if len(nft) > 4 else "Обычный"
        emoji = _rarity_emoji(rarity_name)
        kb.append([InlineKeyboardButton(
            text=f"#{idx} {emoji} {rarity_name}  ·  {name}",
            callback_data=f"nft_info_{un_id}",
        )])
    # Пустые слоты на последней странице
    if page == total_pages - 1:
        shown = total_nfts
        for i in range(shown + 1, min(shown + (NFT_PER_PAGE - len(page_nfts)) + 1, max_nft + 1)):
            kb.append([InlineKeyboardButton(
                text=f"#{i}  ── пусто ──",
                callback_data="noop",
            )])

    # Пагинация: ▶️⏭️ 📂 1/N ⏮️◀️
    if total_pages > 1:
        nav = []
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"my_nft_pg:{min(page + 1, total_pages - 1)}"))
        nav.append(InlineKeyboardButton(text="⏭️", callback_data=f"my_nft_pg:{total_pages - 1}"))
        nav.append(InlineKeyboardButton(text=f"📂 {page + 1}/{total_pages}", callback_data="noop"))
        nav.append(InlineKeyboardButton(text="⏮️", callback_data="my_nft_pg:0"))
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"my_nft_pg:{max(page - 1, 0)}"))
        kb.append(nav)

    kb.append([InlineKeyboardButton(text="⬅️ Меню", callback_data="menu")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def nft_detail_kb(user_nft_id: int, on_sale: bool = False, is_pinned: bool = False):
    kb = []
    if on_sale:
        kb.append([InlineKeyboardButton(text="🚫 Снять с продажи", callback_data=f"nft_unsell_{user_nft_id}")])
    else:
        kb.append([
            InlineKeyboardButton(text="💰 Продать", callback_data=f"nft_sell_{user_nft_id}"),
            InlineKeyboardButton(text="🔄 Обменять", callback_data=f"nft_trade_{user_nft_id}"),
        ])
        kb.append([InlineKeyboardButton(text="🗑 Удалить (3.500 💢)", callback_data=f"nft_delete_{user_nft_id}")])
    # Pin / Unpin
    if is_pinned:
        kb.append([InlineKeyboardButton(text="📌 Открепить", callback_data=f"nft_unpin_{user_nft_id}")])
    else:
        kb.append([InlineKeyboardButton(text="📌 Закрепить в профиле", callback_data=f"nft_pin_{user_nft_id}")])
    kb.append([InlineKeyboardButton(text="⬅️ Мои НФТ", callback_data="my_nft")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def nft_sell_confirm_kb(user_nft_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Выставить", callback_data=f"nft_sell_yes_{user_nft_id}"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="my_nft"),
        ],
    ])


def nft_delete_confirm_kb(user_nft_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Удалить", callback_data=f"nft_del_yes_{user_nft_id}"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="my_nft"),
        ],
    ])


# ━━━━━━━━━━━━  ТОРГОВАЯ ПЛОЩАДКА  ━━━━━━━━━━━━
def market_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛍 НФТ Продажи", callback_data="nftp_0")],
        [InlineKeyboardButton(text="🔄 Обмен НФТ", callback_data="trade_menu")],
        [InlineKeyboardButton(text="⬅️ Магазин", callback_data="shop_menu")],
    ])


def nft_marketplace_kb(items: list, page: int, total_pages: int):
    kb = []
    for item in items:
        listing_id = item[0]
        name = item[5]
        rarity_name = item[6]
        rarity_pct = item[7]
        price = item[4]
        income = item[8]
        emoji = _rarity_emoji(rarity_name)
        kb.append([InlineKeyboardButton(
            text=f"{emoji} {name}  \u00b7  {rarity_name} ({rarity_pct}%)",
            callback_data=f"nftv_market_{listing_id}",
        )])
        kb.append([InlineKeyboardButton(
            text=f"   \ud83d\udcb0 {int(price):,} \ud83d\udca2  \u00b7  +{income}/\u0447".replace(",", "."),
            callback_data=f"nftv_market_{listing_id}",
        )])
    nav = []
    if total_pages > 1:
        if page > 0:
            nav.append(InlineKeyboardButton(text="⏮", callback_data="nftp_0"))
            nav.append(InlineKeyboardButton(text="◀️", callback_data=f"nftp_{page - 1}"))
        nav.append(InlineKeyboardButton(text=f"📂 {page + 1}/{total_pages}", callback_data="noop"))
        if page < total_pages - 1:
            nav.append(InlineKeyboardButton(text="▶️", callback_data=f"nftp_{page + 1}"))
            nav.append(InlineKeyboardButton(text="⏭", callback_data=f"nftp_{total_pages - 1}"))
        kb.append(nav)
    kb.append([InlineKeyboardButton(text="⬅️ Площадка", callback_data="market_menu")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def nft_buy_confirm_kb(listing_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Купить", callback_data=f"nftb_market_{listing_id}"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="nftp_0"),
        ],
    ])


# ━━━━━━━━━━━━  ОБМЕН НФТ  ━━━━━━━━━━━━
def trade_menu_kb(trades: list, page: int, total_pages: int):
    kb = []
    for trade in trades:
        trade_id = trade[0]
        sender_id = trade[1]
        want_clicks = trade[2]
        kb.append([InlineKeyboardButton(
            text=f"🔄 #{trade_id}  ·  Хочет: {int(want_clicks):,} 💢".replace(",", "."),
            callback_data=f"trade_view_{trade_id}",
        )])
    nav = []
    if total_pages > 1:
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"trades_pg_{min(page + 1, total_pages - 1)}"))
        nav.append(InlineKeyboardButton(text="⏭️", callback_data=f"trades_pg_{total_pages - 1}"))
        nav.append(InlineKeyboardButton(text=f"📂 {page + 1}/{total_pages}", callback_data="noop"))
        nav.append(InlineKeyboardButton(text="⏮️", callback_data="trades_pg_0"))
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"trades_pg_{max(page - 1, 0)}"))
        kb.append(nav)
    kb.append([
        InlineKeyboardButton(text="📥 Входящие", callback_data="trade_incoming"),
        InlineKeyboardButton(text="❌ Отменить мои", callback_data="trade_cancel_mine"),
    ])
    kb.append([InlineKeyboardButton(text="⬅️ Площадка", callback_data="market_menu")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  ПАНЕЛЬ ВЛАДЕЛЬЦА  (3 страницы)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def owner_panel_kb(page: int = 0):
    if page == 0:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📊 Статистика", callback_data="owner_stats")],
            [
                InlineKeyboardButton(text="👥 Участники", callback_data="owner_users"),
                InlineKeyboardButton(text="🚫 Забаненные", callback_data="owner_banned:0"),
            ],
            [
                InlineKeyboardButton(text="🔨 Бан", callback_data="owner_ban"),
                InlineKeyboardButton(text="✅ Разбан", callback_data="owner_unban"),
            ],
            [InlineKeyboardButton(text="💬 Переписки", callback_data="owner_chat_logs")],
            [
                InlineKeyboardButton(text="▶️ Далее", callback_data="owner_panel_page:1"),
                InlineKeyboardButton(text="🏠 Выход", callback_data="menu"),
            ],
        ])
    elif page == 1:
        return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="📋 Тикеты", callback_data="owner_tickets:0"),
                InlineKeyboardButton(text="📨 Жалобы", callback_data="compl_pg:0"),
            ],
            [InlineKeyboardButton(text="💳 Заказы оплаты", callback_data="owner_orders:0")],
            [
                InlineKeyboardButton(text="📢 Рассылка", callback_data="owner_broadcast"),
                InlineKeyboardButton(text="📝 Логи", callback_data="owner_logs"),
            ],
            [
                InlineKeyboardButton(text="◀️", callback_data="owner_panel_page:0"),
                InlineKeyboardButton(text="▶️", callback_data="owner_panel_page:2"),
            ],
        ])
    else:
        return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🎨 Создать НФТ", callback_data="owner_nft_create"),
                InlineKeyboardButton(text="⚡ Быстрое НФТ", callback_data="owner_quick_nft"),
            ],
            [
                InlineKeyboardButton(text="🗑 Удалить НФТ", callback_data="owner_nft_list"),
                InlineKeyboardButton(text="🎪 Аукцион", callback_data="event_create"),
            ],
            [InlineKeyboardButton(text="⚙️ Настройки", callback_data="owner_settings")],
            [InlineKeyboardButton(text="👮 Админы", callback_data="owner_admins")],
            [InlineKeyboardButton(text="☢️ Сброс ВСЕХ", callback_data="owner_wipe_all")],
            [
                InlineKeyboardButton(text="◀️", callback_data="owner_panel_page:1"),
                InlineKeyboardButton(text="🏠 Выход", callback_data="menu"),
            ],
        ])


def owner_admins_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👮 Список", callback_data="owner_admin_list"),
            InlineKeyboardButton(text="🔑 Ключ", callback_data="owner_admin_genkey"),
        ],
        [
            InlineKeyboardButton(text="📋 Все ключи", callback_data="owner_admin_keys"),
            InlineKeyboardButton(text="📊 Логи", callback_data="owner_admin_log"),
        ],
        [
            InlineKeyboardButton(text="❌ Снять", callback_data="owner_admin_remove"),
            InlineKeyboardButton(text="🔧 Права", callback_data="owner_admin_perms"),
        ],
        [InlineKeyboardButton(text="⬅️ Панель", callback_data="owner_panel")],
    ])


def owner_back_panel_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Панель", callback_data="owner_panel")],
    ])


def owner_tickets_kb(tickets: list, page: int = 0, total_pages: int = 1):
    kb = []
    for t in tickets:
        tid, uid, ttype, msg, dt = t
        short = msg[:28] + "…" if len(msg) > 28 else msg
        icon = "🚩" if ttype == "complaint" else "🐛"
        kb.append([InlineKeyboardButton(
            text=f"{icon} #{tid}  ·  {short}",
            callback_data=f"ticket_view_{tid}",
        )])
    nav = []
    if total_pages > 1:
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"owner_tickets:{min(page + 1, total_pages - 1)}"))
        nav.append(InlineKeyboardButton(text="⏭️", callback_data=f"owner_tickets:{total_pages - 1}"))
        nav.append(InlineKeyboardButton(text=f"📂 {page + 1}/{total_pages}", callback_data="noop"))
        nav.append(InlineKeyboardButton(text="⏮️", callback_data="owner_tickets:0"))
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"owner_tickets:{max(page - 1, 0)}"))
        kb.append(nav)
    kb.append([InlineKeyboardButton(text="⬅️ Панель", callback_data="owner_panel")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def owner_nft_list_kb(templates: list, page: int = 0, total_pages: int = 1, prefix="owner"):
    panel_cb = "owner_panel" if prefix == "owner" else "admin_panel"
    view_pref = f"{prefix}_nft_view_"
    pg_pref = f"{prefix}_nft_pg_"
    kb = []
    for t in templates:
        tid = t[0]
        name = t[1]
        rarity = t[3] if len(t) > 3 else "Обычный"
        emoji = _rarity_emoji(rarity)
        kb.append([InlineKeyboardButton(
            text=f"{emoji} #{tid}  ·  {name}",
            callback_data=f"{view_pref}{tid}",
        )])
    # Навигация
    nav = []
    if total_pages > 1:
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"{pg_pref}{min(page + 1, total_pages - 1)}"))
        nav.append(InlineKeyboardButton(text="⏭️", callback_data=f"{pg_pref}{total_pages - 1}"))
        nav.append(InlineKeyboardButton(text=f"📂 {page+1}/{total_pages}", callback_data="noop"))
        nav.append(InlineKeyboardButton(text="⏮️", callback_data=f"{pg_pref}0"))
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"{pg_pref}{max(page - 1, 0)}"))
        kb.append(nav)
    kb.append([InlineKeyboardButton(text="⬅️ Панель", callback_data=panel_cb)])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def owner_nft_detail_kb(tid: int, page: int = 0, prefix="owner"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑 Удалить НФТ", callback_data=f"{prefix}_nft_del_{tid}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"{prefix}_nft_pg_{page}")],
    ])


def user_nfts_view_kb(nfts: list, uid: int, prefix: str = "owner"):
    """Просмотр топ-5 НФТ пользователя из панели админа/владельца."""
    from config import NFT_RARITY_EMOJI
    kb = []
    for nft in nfts:
        un_id = nft[0]
        name = nft[1]
        income = nft[2]
        rarity_name = nft[4] if len(nft) > 4 else "Обычный"
        emoji = NFT_RARITY_EMOJI.get(rarity_name, "🟢")
        kb.append([InlineKeyboardButton(
            text=f"{emoji} {name} — {income}/ч",
            callback_data="noop",
        )])
    if not nfts:
        kb.append([InlineKeyboardButton(text="— нет НФТ —", callback_data="noop")])
    kb.append([InlineKeyboardButton(text="⬅️ Профиль", callback_data=f"{prefix}_user_view_{uid}")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def owner_nft_publish_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Опубликовать", callback_data="owner_nft_publish"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="owner_nft_cancel"),
        ],
    ])


# ━━━━━━━━━━━━  ЗАБАНЕННЫЕ (пагинация)  ━━━━━━━━━━━━
def banned_list_kb(users: list, page: int, total_pages: int, prefix: str = "owner"):
    kb = []
    for u in users:
        uid, uname, until = u
        name = f"@{uname}" if uname else f"ID:{uid}"
        kb.append([InlineKeyboardButton(
            text=f"🚫 {name}",
            callback_data=f"{prefix}_unban_quick_{uid}",
        )])
    nav = []
    if total_pages > 1:
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"{prefix}_banned:{min(page + 1, total_pages - 1)}"))
        nav.append(InlineKeyboardButton(text="⏭️", callback_data=f"{prefix}_banned:{total_pages - 1}"))
        nav.append(InlineKeyboardButton(text=f"📂 {page + 1}/{total_pages}", callback_data="noop"))
        nav.append(InlineKeyboardButton(text="⏮️", callback_data=f"{prefix}_banned:0"))
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"{prefix}_banned:{max(page - 1, 0)}"))
        kb.append(nav)
    back_cb = "admin_panel" if prefix == "adm" else "owner_panel"
    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=back_cb)])
    return InlineKeyboardMarkup(inline_keyboard=kb)


# ━━━━━━━━━━━━  УЧАСТНИКИ (пагинация)  ━━━━━━━━━━━━
def users_list_kb(users: list, page: int, total_pages: int, prefix: str = "owner"):
    kb = []
    for u in users:
        uid, uname, clicks, rank, banned = u
        name = f"@{uname}" if uname else f"ID:{uid}"
        status = "🚫" if banned else "✅"
        kb.append([InlineKeyboardButton(
            text=f"{status} {name}  ·  {int(clicks):,} 💢".replace(",", "."),
            callback_data=f"{prefix}_user_view_{uid}",
        )])
    if total_pages > 1:
        nav = []
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"{prefix}_users_pg:{min(page + 1, total_pages - 1)}"))
        nav.append(InlineKeyboardButton(text="⏭️", callback_data=f"{prefix}_users_pg:{total_pages - 1}"))
        nav.append(InlineKeyboardButton(text=f"📂 {page + 1}/{total_pages}", callback_data="noop"))
        nav.append(InlineKeyboardButton(text="⏮️", callback_data=f"{prefix}_users_pg:0"))
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"{prefix}_users_pg:{max(page - 1, 0)}"))
        kb.append(nav)
    back_cb = "admin_panel" if prefix == "adm" else "owner_panel"
    kb.append([InlineKeyboardButton(text="🔍 Поиск по ID", callback_data=f"{prefix}_user_search")])
    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=back_cb)])
    return InlineKeyboardMarkup(inline_keyboard=kb)


# ━━━━━━━━━━━━  ПРОФИЛЬ УЧАСТНИКА (админ)  ━━━━━━━━━━━━
def dialog_user_reply_kb(sender_type: str, sender_id: int):
    """Кнопка 'Ответить' для пользователя после сообщения от админа/владельца."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Ответить", callback_data=f"dialog_reply_{sender_type}_{sender_id}")],
    ])


def dialog_after_send_kb(prefix: str, uid: int):
    """Кнопки для админа/владельца после отправки сообщения."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💬 Продолжить", callback_data=f"{prefix}_dialog_cont_{uid}"),
            InlineKeyboardButton(text="🚪 Завершить", callback_data=f"{prefix}_dialog_end_{uid}"),
        ],
        [InlineKeyboardButton(text="⬅️ Назад к профилю", callback_data=f"{prefix}_profile_pg_{uid}_0")],
    ])


def dialog_incoming_reply_kb(prefix: str, uid: int):
    """Кнопки для админа/владельца когда пришёл ответ от пользователя."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💬 Ответить", callback_data=f"{prefix}_dialog_cont_{uid}"),
            InlineKeyboardButton(text="🚪 Завершить", callback_data=f"{prefix}_dialog_end_{uid}"),
        ],
    ])


def user_profile_admin_kb(uid: int, prefix: str = "owner", page: int = 0):
    p = prefix
    total_pages = 2
    nav = []
    nav.append(InlineKeyboardButton(text="▶️", callback_data=f"{p}_profile_pg_{uid}_{min(page + 1, total_pages - 1)}"))
    nav.append(InlineKeyboardButton(text="⏭️", callback_data=f"{p}_profile_pg_{uid}_{total_pages - 1}"))
    nav.append(InlineKeyboardButton(text=f"📂 {page+1}/{total_pages}", callback_data="noop"))
    nav.append(InlineKeyboardButton(text="⏮️", callback_data=f"{p}_profile_pg_{uid}_0"))
    nav.append(InlineKeyboardButton(text="◀️", callback_data=f"{p}_profile_pg_{uid}_{max(page - 1, 0)}"))

    if page == 0:
        rows = [
            [
                InlineKeyboardButton(text="💰 Выдать", callback_data=f"{p}_give_user_{uid}"),
                InlineKeyboardButton(text="💸 Снять", callback_data=f"{p}_take_user_{uid}"),
            ],
            [
                InlineKeyboardButton(text="🔨 Бан", callback_data=f"{p}_banmenu_{uid}"),
                InlineKeyboardButton(text="✅ Разбан", callback_data=f"{p}_unban_user_{uid}"),
            ],
            [
                InlineKeyboardButton(text="🎨 Выдать НФТ", callback_data=f"{p}_give_nft_{uid}"),
                InlineKeyboardButton(text="📝 История", callback_data=f"{p}_user_hist_{uid}"),
            ],
            [
                InlineKeyboardButton(text="🔄 Сброс", callback_data=f"{p}_reset_{uid}"),
                InlineKeyboardButton(text="💬 Написать", callback_data=f"{p}_msgusr_{uid}"),
            ],
            [
                InlineKeyboardButton(text="🎁 Донат", callback_data=f"{p}_donate_{uid}"),
            ],
        ]
    else:  # page == 1
        rows = [
            [
                InlineKeyboardButton(text="⚡ +Клик", callback_data=f"{p}_addval_{uid}_click"),
                InlineKeyboardButton(text="📈 +Доход", callback_data=f"{p}_addval_{uid}_income"),
            ],
            [
                InlineKeyboardButton(text="📦 +Ёмкость", callback_data=f"{p}_addval_{uid}_cap"),
                InlineKeyboardButton(text="🎯 +Слот", callback_data=f"{p}_addval_{uid}_slot"),
            ],
            [
                InlineKeyboardButton(text="🏷️ Ранг", callback_data=f"{p}_setrank_{uid}"),
                InlineKeyboardButton(text="📛 Ник", callback_data=f"{p}_setname_{uid}"),
            ],
            [
                InlineKeyboardButton(text="📊 Логи", callback_data=f"{p}_actlog_{uid}"),
                InlineKeyboardButton(text="🔗 Рефералы", callback_data=f"{p}_resetref_{uid}"),
            ],
            [
                InlineKeyboardButton(text="🎨 НФТ юзера", callback_data=f"{p}_usernfts_{uid}"),
            ],
        ]

    rows.append(nav)
    rows.append([InlineKeyboardButton(text="⬅️ Участники", callback_data=f"{p}_users")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def donate_submenu_kb(uid: int, prefix: str = "owner", vip_type: str | None = None, pay_banned: bool = False):
    """Подменю Донат — VIP/Premium выдача + пакеты кликов + оплата."""
    p = prefix
    rows = [
        [
            InlineKeyboardButton(text="⭐ VIP 7д", callback_data=f"{p}_setvip_{uid}_vip7"),
            InlineKeyboardButton(text="👑 Prem 7д", callback_data=f"{p}_setvip_{uid}_prem7"),
        ],
        [
            InlineKeyboardButton(text="⭐ VIP 30д", callback_data=f"{p}_setvip_{uid}_vip30"),
            InlineKeyboardButton(text="👑 Prem 30д", callback_data=f"{p}_setvip_{uid}_prem30"),
        ],
        [
            InlineKeyboardButton(text="⭐ VIP ∞", callback_data=f"{p}_setvip_{uid}_vip0"),
            InlineKeyboardButton(text="👑 Prem ∞", callback_data=f"{p}_setvip_{uid}_prem0"),
        ],
    ]
    rows.append([
        InlineKeyboardButton(text="❌ Снять VIP", callback_data=f"{p}_setvip_{uid}_rmvip"),
        InlineKeyboardButton(text="❌ Снять Prem", callback_data=f"{p}_setvip_{uid}_rmprem"),
    ])
    rows.append([InlineKeyboardButton(
        text="💢 Выдать кликов", callback_data=f"{p}_givedon_{uid}",
    )])
    rows.append([InlineKeyboardButton(
        text="✅ Разбан оплаты" if pay_banned else "💳 Бан оплаты",
        callback_data=f"{p}_payunban_{uid}" if pay_banned else f"{p}_payban_{uid}",
    )])
    rows.append([InlineKeyboardButton(
        text="⬅️ Профиль", callback_data=f"{p}_user_view_{uid}",
    )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def ban_duration_kb(uid: int, prefix: str = "owner"):
    p = prefix
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🕐 1 час", callback_data=f"{p}_doban_{uid}_1"),
            InlineKeyboardButton(text="🕒 3 часа", callback_data=f"{p}_doban_{uid}_3"),
        ],
        [
            InlineKeyboardButton(text="🕕 6 часов", callback_data=f"{p}_doban_{uid}_6"),
            InlineKeyboardButton(text="🕛 12 часов", callback_data=f"{p}_doban_{uid}_12"),
        ],
        [
            InlineKeyboardButton(text="🕐 24 часа", callback_data=f"{p}_doban_{uid}_24"),
            InlineKeyboardButton(text="♾ Навсегда", callback_data=f"{p}_doban_{uid}_permanent"),
        ],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"{p}_user_view_{uid}")],
    ])


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  ПАНЕЛЬ АДМИНИСТРАТОРА  (3 стр.)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def admin_panel_kb(page: int = 0):
    if page == 0:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📊 Статистика", callback_data="adm_stats")],
            [
                InlineKeyboardButton(text="👥 Участники", callback_data="adm_users"),
                InlineKeyboardButton(text="🚫 Забаненные", callback_data="adm_banned:0"),
            ],
            [
                InlineKeyboardButton(text="🔨 Бан", callback_data="adm_ban"),
                InlineKeyboardButton(text="✅ Разбан", callback_data="adm_unban"),
            ],
            [InlineKeyboardButton(text="💬 Переписки", callback_data="adm_chat_logs")],
            [
                InlineKeyboardButton(text="▶️ Далее", callback_data="adm_panel_page:1"),
                InlineKeyboardButton(text="🏠 Меню", callback_data="menu"),
            ],
        ])
    elif page == 1:
        return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="📋 Тикеты", callback_data="adm_tickets:0"),
                InlineKeyboardButton(text="📨 Жалобы", callback_data="compl_pg:0"),
            ],
            [InlineKeyboardButton(text="💳 Заказы оплаты", callback_data="adm_orders:0")],
            [
                InlineKeyboardButton(text="📢 Рассылка", callback_data="adm_broadcast"),
                InlineKeyboardButton(text="📝 Логи", callback_data="adm_logs"),
            ],
            [InlineKeyboardButton(text="📊 Мои действия", callback_data="adm_my_log")],
            [
                InlineKeyboardButton(text="⏮️◀️", callback_data="adm_panel_page:0"),
                InlineKeyboardButton(text="📂 2/3", callback_data="noop"),
                InlineKeyboardButton(text="▶️⏭️", callback_data="adm_panel_page:2"),
            ],
        ])
    else:  # page == 2
        return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🎨 Создать НФТ", callback_data="adm_nft_create"),
                InlineKeyboardButton(text="⚡ Быстрое НФТ", callback_data="adm_quick_nft"),
            ],
            [
                InlineKeyboardButton(text="🗑 Удалить НФТ", callback_data="adm_nft_list"),
                InlineKeyboardButton(text="🎪 Аукцион", callback_data="event_create"),
            ],
            [InlineKeyboardButton(text="💰 Выдача кликов", callback_data="adm_give")],
            [InlineKeyboardButton(text="⚙️ Настройки", callback_data="adm_settings")],
            [InlineKeyboardButton(text="🚪 Разжаловаться", callback_data="adm_demote_self")],
            [
                InlineKeyboardButton(text="⏮️◀️", callback_data="adm_panel_page:1"),
                InlineKeyboardButton(text="📂 3/3", callback_data="noop"),
                InlineKeyboardButton(text="⬅️ Назад", callback_data="adm_panel_page:0"),
            ],
        ])


def admin_back_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Панель админа", callback_data="admin_panel")],
    ])


# ━━━━━━━━━━━━  ИСТОРИЯ / ЧЕКИ  ━━━━━━━━━━━━
_TX_ICON = {
    "pvp": "⚔️", "trade": "🔄", "chat": "💬",
    "nft_buy": "🛒", "nft_sell": "💰", "shop": "🔧",
    "event": "🎉", "gift": "🎁",
    "market_buy": "🏪", "market_sell": "🏪",
}


def history_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Все чеки", callback_data="hist:all:0")],
        [
            InlineKeyboardButton(text="⚔️ PvP", callback_data="hist:pvp:0"),
            InlineKeyboardButton(text="🔄 Обмены", callback_data="hist:trade:0"),
        ],
        [
            InlineKeyboardButton(text="🛒 Покупки", callback_data="hist:nft_buy:0"),
            InlineKeyboardButton(text="💰 Продажи", callback_data="hist:nft_sell:0"),
        ],
        [
            InlineKeyboardButton(text="🔧 Магазин", callback_data="hist:shop:0"),
            InlineKeyboardButton(text="🎉 Ивенты", callback_data="hist:event:0"),
        ],
        [InlineKeyboardButton(text="📨 Мои жалобы", callback_data="my_complaints:0")],
        [InlineKeyboardButton(text="⬅️ Поддержка", callback_data="support_menu")],
    ])


def history_list_kb(items: list, page: int, total_pages: int, tx_filter: str = "all"):
    kb = []
    for item in items:
        tx_id, tx_type = item[0], item[1]
        amount = item[4]
        details = item[5] or ""
        icon = _TX_ICON.get(tx_type, "📋")
        short = details[:26] + "…" if len(details) > 26 else details
        amt = f" {int(amount)}💢" if amount else ""
        kb.append([InlineKeyboardButton(
            text=f"{icon} #{tx_id}{amt}  ·  {short}",
            callback_data=f"check:{tx_id}",
        )])
    nav = []
    if total_pages > 1:
        if page > 0:
            nav.append(InlineKeyboardButton(text="◀️", callback_data=f"hist:{tx_filter}:{page - 1}"))
        nav.append(InlineKeyboardButton(text=f"📂 {page + 1}/{total_pages}", callback_data="noop"))
        if page < total_pages - 1:
            nav.append(InlineKeyboardButton(text="▶️", callback_data=f"hist:{tx_filter}:{page + 1}"))
        kb.append(nav)
    kb.append([
        InlineKeyboardButton(text="🔍 Фильтры", callback_data="history_menu"),
        InlineKeyboardButton(text="⬅️ Поддержка", callback_data="support_menu"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def check_detail_kb(tx_id: int, can_complain: bool = True):
    kb = []
    if can_complain:
        kb.append([InlineKeyboardButton(text="⚠️ Подать жалобу", callback_data=f"complain:{tx_id}")])
    kb.append([InlineKeyboardButton(text="⬅️ К списку", callback_data="hist:all:0")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def complaints_list_kb(complaints: list, page: int = 0, total_pages: int = 1):
    kb = []
    for c in complaints:
        c_id = c[0]
        tx_id = c[1]
        reason = c[3]
        status = c[4]
        tx_type = c[6] if len(c) > 6 else ""
        icon = _TX_ICON.get(tx_type, "📋")
        short = reason[:23] + "…" if len(reason) > 23 else reason
        s_icon = "🟡" if status == "pending" else "🔵"
        kb.append([InlineKeyboardButton(
            text=f"{s_icon} #{c_id} {icon} Чек#{tx_id}  ·  {short}",
            callback_data=f"compl_view:{c_id}",
        )])
    nav = []
    if total_pages > 1:
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"compl_pg:{min(page + 1, total_pages - 1)}"))
        nav.append(InlineKeyboardButton(text="⏭️", callback_data=f"compl_pg:{total_pages - 1}"))
        nav.append(InlineKeyboardButton(text=f"📂 {page + 1}/{total_pages}", callback_data="noop"))
        nav.append(InlineKeyboardButton(text="⏮️", callback_data="compl_pg:0"))
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"compl_pg:{max(page - 1, 0)}"))
        kb.append(nav)
    kb.append([InlineKeyboardButton(text="⬅️ Панель", callback_data="admin_panel")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def complaint_action_kb(complaint_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💸 Возврат", callback_data=f"compl_act:{complaint_id}:refund"),
            InlineKeyboardButton(text="⚠️ Пред.", callback_data=f"compl_act:{complaint_id}:warn"),
        ],
        [
            InlineKeyboardButton(text="🔨 Бан", callback_data=f"compl_act:{complaint_id}:ban"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"compl_act:{complaint_id}:reject"),
        ],
        [InlineKeyboardButton(text="⬅️ Жалобы", callback_data="compl_pg:0")],
    ])


def my_complaints_kb(complaints: list, page: int = 0, total_pages: int = 1):
    kb = []
    for c in complaints:
        c_id = c[0]
        tx_id = c[1]
        reason = c[2]
        status = c[3]
        s_icon = {"pending": "🟡", "reviewing": "🔵", "resolved": "✅"}.get(status, "⚪")
        short = reason[:23] + "…" if len(reason) > 23 else reason
        kb.append([InlineKeyboardButton(
            text=f"{s_icon} #{c_id}  ·  Чек #{tx_id}  ·  {short}",
            callback_data=f"my_compl:{c_id}",
        )])
    nav = []
    if total_pages > 1:
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"my_complaints:{min(page + 1, total_pages - 1)}"))
        nav.append(InlineKeyboardButton(text="⏭️", callback_data=f"my_complaints:{total_pages - 1}"))
        nav.append(InlineKeyboardButton(text=f"📂 {page + 1}/{total_pages}", callback_data="noop"))
        nav.append(InlineKeyboardButton(text="⏮️", callback_data="my_complaints:0"))
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"my_complaints:{max(page - 1, 0)}"))
        kb.append(nav)
    kb.append([InlineKeyboardButton(text="⬅️ Поддержка", callback_data="support_menu")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


# ━━━━━━━━━━━━  ЛОГИ ВЛАДЕЛЬЦА  ━━━━━━━━━━━━
def owner_logs_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⚔️ PvP", callback_data="olog:pvp:0"),
            InlineKeyboardButton(text="🔄 Обмены", callback_data="olog:trade:0"),
        ],
        [
            InlineKeyboardButton(text="💰 Продажи", callback_data="olog:sale:0"),
            InlineKeyboardButton(text="🛒 Покупки", callback_data="olog:buy:0"),
        ],
        [InlineKeyboardButton(text="🔍 По ID участника", callback_data="olog:search")],
        [InlineKeyboardButton(text="⬅️ Панель", callback_data="owner_panel")],
    ])


def admin_logs_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⚔️ PvP", callback_data="alog:pvp:0"),
            InlineKeyboardButton(text="🔄 Обмены", callback_data="alog:trade:0"),
        ],
        [
            InlineKeyboardButton(text="💰 Продажи", callback_data="alog:sale:0"),
            InlineKeyboardButton(text="🛒 Покупки", callback_data="alog:buy:0"),
        ],
        [InlineKeyboardButton(text="🔍 По ID участника", callback_data="alog:search")],
        [InlineKeyboardButton(text="⬅️ Панель", callback_data="adm_panel")],
    ])


# ━━━━━━━━━━━━  АУКЦИОНЫ (broadcast)  ━━━━━━━━━━━━
def auction_broadcast_kb(event_id: int):
    """Клавиатура рассылки: пользователь ещё НЕ участвует."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Участвовать", callback_data=f"auc_join:{event_id}"),
            InlineKeyboardButton(text="❌ Игнорировать", callback_data=f"auc_ignore:{event_id}"),
        ],
    ])


def auction_joined_kb(event_id: int):
    """Клавиатура для участника: добавить сумму / обновить."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Добавить сумму", callback_data=f"auc_raise:{event_id}")],
        [InlineKeyboardButton(text="🔄 Обновить", callback_data=f"auc_view:{event_id}")],
    ])

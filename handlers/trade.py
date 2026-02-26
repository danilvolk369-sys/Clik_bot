# ======================================================
# TRADE — Доска обменов НФТ (полностью кнопочный)
# ======================================================

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from config import MAX_NFT
from handlers.common import fnum
from states import TradeStates
from database import (
    get_user, get_user_nfts, count_user_nfts, get_user_nft_by_id,
    is_nft_on_sale,
    create_public_trade, get_trade_offer, get_trade_items,
    count_open_trades, get_open_trades_page,
    get_my_open_trades, get_proposals_for_me,
    propose_trade, accept_trade, reject_proposal, cancel_trade,
    create_transaction,
)

router = Router()


# ─── Утилиты ───
def _rarity_emoji(rarity: int) -> str:
    return {
        1: "📦", 2: "🧩", 3: "💎", 4: "🔮", 5: "👑",
        6: "🐉", 7: "⚡", 8: "🌌", 9: "♾️", 10: "🏆",
    }.get(rarity, "📦")


def _rarity_label(rarity: int) -> str:
    return {
        1: "📦 Обычный", 2: "🧩 Необычный", 3: "💎 Редкий",
        4: "🔮 Эпический", 5: "👑 Легендарный", 6: "🐉 Мифический",
        7: "⚡ Божественный", 8: "🌌 Космический", 9: "♾️ Вечный",
        10: "🏆 Запредельный",
    }.get(rarity, "📦 Обычный")


def _want_label(want_clicks: float, want_nft_count: int) -> str:
    """Краткое описание того, что хочет получить создатель."""
    if want_clicks and want_clicks > 0:
        return f"💢 {fnum(want_clicks)} кликов"
    if want_nft_count > 0:
        return f"🎨 {want_nft_count} НФТ"
    return "—"


# ══════════════════════════════════════════════
#  🔄 ОБМЕН НФТ — главное меню
# ══════════════════════════════════════════════
@router.callback_query(F.data == "trade_menu")
async def show_trade_menu(call: CallbackQuery, state: FSMContext):
    await state.clear()
    uid = call.from_user.id
    user = await get_user(uid)
    if not user:
        return await call.answer("❌ /start", show_alert=True)

    open_count = await count_open_trades(uid)
    my_trades = await get_my_open_trades(uid)
    proposals = [t for t in my_trades if t[5] == "proposed"]

    text = (
        "🔄 ОБМЕН НФТ\n"
        "══════════════════════\n\n"
        "📦 Обменивайте НФТ с другими игроками!\n\n"
        "• НФТ за клики 💢\n"
        "• НФТ на НФТ (1:1, 1:2, 1:3)\n\n"
        f"📋 Предложений на доске: {open_count}\n"
        f"📥 Ожидают решения: {len(proposals)}\n\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        "Выберите действие:"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Доска обменов", callback_data="trd_board_0")],
        [InlineKeyboardButton(text="➕ Создать обмен", callback_data="trd_create")],
        [InlineKeyboardButton(text=f"📥 Предложения ({len(proposals)})", callback_data="trd_proposals")],
        [InlineKeyboardButton(text="📤 Мои обмены", callback_data="trd_my_trades")],
        [InlineKeyboardButton(text="⬅️ Площадка", callback_data="market_menu")],
    ])
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


# ══════════════════════════════════════════════
#  📋 ДОСКА ОБМЕНОВ — пагинация
# ══════════════════════════════════════════════
@router.callback_query(F.data.regexp(r"^trd_board_\d+$"))
async def show_trade_board(call: CallbackQuery, state: FSMContext):
    await state.clear()
    uid = call.from_user.id
    page = int(call.data.split("_")[-1])
    per_page = 5

    total = await count_open_trades(uid)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(0, min(page, total_pages - 1))

    trades = await get_open_trades_page(page, per_page, uid)

    if not trades:
        text = (
            "📋 ДОСКА ОБМЕНОВ\n"
            "══════════════════════\n\n"
            "😔 Пока нет предложений.\n\n"
            "══════════════════════"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить", callback_data="trd_board_0")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="trade_menu")],
        ])
        await call.message.edit_text(text, reply_markup=kb)
        return await call.answer()

    text = (
        "📋 ДОСКА ОБМЕНОВ\n"
        "══════════════════════\n\n"
    )

    kb_rows = []
    for t_id, sender_id, offer_clicks, want_clicks, want_nft_count, dt in trades:
        sender = await get_user(sender_id)
        sname = f"@{sender['username']}" if sender and sender['username'] else f"ID:{sender_id}"
        items = await get_trade_items(t_id)
        offer_items = [i for i in items if i[2] == "offer"]
        nft_name = offer_items[0][4] if offer_items else "НФТ"
        nft_rarity = offer_items[0][5] if offer_items else 1
        emoji = _rarity_emoji(nft_rarity)
        want = _want_label(want_clicks, want_nft_count)

        text += f"{emoji} {nft_name} → {want}\n👤 {sname}\n\n"
        kb_rows.append([InlineKeyboardButton(
            text=f"{emoji} {nft_name} — {sname}",
            callback_data=f"trd_view_{t_id}",
        )])

    text += f"══════════════════════\n📄 Стр. {page + 1} / {total_pages}"

    # Навигация
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"trd_board_{page - 1}"))
    nav.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"trd_board_{page + 1}"))
    kb_rows.append(nav)
    kb_rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="trade_menu")])

    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))
    await call.answer()


# ══════════════════════════════════════════════
#  👁 ПРОСМОТР ОБМЕНА (для всех)
# ══════════════════════════════════════════════
@router.callback_query(F.data.regexp(r"^trd_view_\d+$"))
async def trade_view(call: CallbackQuery, state: FSMContext = None):
    uid = call.from_user.id
    trade_id = int(call.data.split("_")[-1])
    trade = await get_trade_offer(trade_id)

    if not trade:
        return await call.answer("❌ Обмен не найден", show_alert=True)

    t_id, sender_id, receiver_id, offer_clicks, want_clicks, status, dt, want_nft_count = trade

    items = await get_trade_items(trade_id)
    offer_items = [i for i in items if i[2] == "offer"]
    want_items = [i for i in items if i[2] == "want"]

    sender = await get_user(sender_id)
    sname = f"@{sender['username']}" if sender and sender['username'] else f"ID:{sender_id}"

    _status_map = {
        "open": "🟢 Открыт",
        "proposed": "🟡 Есть предложение",
        "accepted": "✅ Завершён",
        "cancelled": "🚫 Отменён",
    }

    text = (
        f"🔄 ОБМЕН #{t_id}\n"
        f"══════════════════════\n\n"
        f"👤 Создатель: {sname}\n"
        f"📌 Статус: {_status_map.get(status, status)}\n\n"
    )

    text += "📤 ПРЕДЛАГАЕТ:\n┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
    for _, _, side, user_nft_id, nft_name, nft_rarity, nft_income in offer_items:
        text += f"  {_rarity_emoji(nft_rarity)} {nft_name} (+{fnum(nft_income)}/ч)\n"

    text += "\n📥 ХОЧЕТ ПОЛУЧИТЬ:\n┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
    if want_clicks and want_clicks > 0:
        text += f"  💢 {fnum(want_clicks)} кликов\n"
    elif want_nft_count > 0:
        text += f"  🎨 {want_nft_count} НФТ\n"
    else:
        text += "  —\n"

    # Если статус proposed — показываем что предложил откликнувшийся
    if status == "proposed" and receiver_id:
        responder = await get_user(receiver_id)
        rname = f"@{responder['username']}" if responder and responder['username'] else f"ID:{receiver_id}"
        text += f"\n🤝 ПРЕДЛОЖЕНИЕ ОТ {rname}:\n┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        if want_items:
            for _, _, side, user_nft_id, nft_name, nft_rarity, nft_income in want_items:
                text += f"  {_rarity_emoji(nft_rarity)} {nft_name} (+{fnum(nft_income)}/ч)\n"
        elif want_clicks and want_clicks > 0:
            text += f"  💢 {fnum(want_clicks)} кликов\n"

    text += "\n══════════════════════"

    kb = []
    if status == "open":
        if uid == sender_id:
            # Создатель может отменить
            kb.append([InlineKeyboardButton(text="🚫 Отменить обмен", callback_data=f"trd_cancel_{t_id}")])
        else:
            # Другой игрок может предложить
            if want_clicks and want_clicks > 0:
                kb.append([InlineKeyboardButton(
                    text=f"💢 Предложить {fnum(want_clicks)} кликов",
                    callback_data=f"trd_propose_clicks_{t_id}",
                )])
            elif want_nft_count > 0:
                kb.append([InlineKeyboardButton(
                    text=f"🎨 Предложить {want_nft_count} НФТ",
                    callback_data=f"trd_propose_nfts_{t_id}",
                )])
    elif status == "proposed" and uid == sender_id:
        # Создатель решает
        kb.append([
            InlineKeyboardButton(text="✅ Принять", callback_data=f"trd_accept_{t_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"trd_reject_{t_id}"),
        ])
        kb.append([InlineKeyboardButton(text="🚫 Отменить обмен", callback_data=f"trd_cancel_{t_id}")])

    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="trade_menu")])
    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await call.answer()


# ══════════════════════════════════════════════
#  ➕ СОЗДАТЬ ОБМЕН — шаг 1: выбор НФТ
# ══════════════════════════════════════════════
@router.callback_query(F.data == "trd_create")
async def trade_create_start(call: CallbackQuery, state: FSMContext):
    uid = call.from_user.id
    nfts = await get_user_nfts(uid)
    if not nfts:
        return await call.answer("❌ У вас нет НФТ для обмена!", show_alert=True)

    available = []
    for un_id, name, income, rarity, bought, dt in nfts:
        if not await is_nft_on_sale(un_id):
            available.append((un_id, name, income, rarity))

    if not available:
        return await call.answer("❌ Все НФТ на продаже!", show_alert=True)

    await state.set_state(TradeStates.select_my_nft)

    text = (
        "➕ НОВЫЙ ОБМЕН\n"
        "══════════════════════\n\n"
        "🎁 Выберите НФТ, который\n"
        "хотите обменять:\n\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈"
    )
    kb = []
    for un_id, name, income, rarity in available:
        emoji = _rarity_emoji(rarity)
        kb.append([InlineKeyboardButton(
            text=f"{emoji} {name} (+{fnum(income)}/ч)",
            callback_data=f"trd_sel_nft_{un_id}",
        )])
    kb.append([InlineKeyboardButton(text="⬅️ Отмена", callback_data="trade_menu")])

    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await call.answer()


# Также обрабатываем «Обменять» из детали НФТ
@router.callback_query(F.data.startswith("nft_trade_"))
async def nft_trade_shortcut(call: CallbackQuery, state: FSMContext):
    """Из карточки НФТ → сразу к шагу 2 (что хотите получить)."""
    user_nft_id = int(call.data.replace("nft_trade_", ""))
    uid = call.from_user.id

    nft = await get_user_nft_by_id(user_nft_id)
    if not nft or nft[1] != uid:
        return await call.answer("❌ НФТ не найден", show_alert=True)
    if await is_nft_on_sale(user_nft_id):
        return await call.answer("❌ Снимите НФТ с продажи!", show_alert=True)

    un_id, owner_id, nft_id, name, income, rarity, bought = nft
    await state.set_state(TradeStates.choose_want_type)
    await state.update_data(trd_nft_id=user_nft_id, trd_nft_name=name,
                            trd_nft_income=income, trd_nft_rarity=rarity)

    emoji = _rarity_emoji(rarity)
    text = (
        "➕ НОВЫЙ ОБМЕН\n"
        "══════════════════════\n\n"
        f"📤 Вы обмениваете:\n"
        f"  {emoji} {name} (+{fnum(income)}/ч)\n\n"
        "🎯 Что хотите получить?\n\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💢 Клики", callback_data="trd_want_clicks")],
        [InlineKeyboardButton(text="🎨 1 НФТ", callback_data="trd_want_1nft")],
        [InlineKeyboardButton(text="🎨 2 НФТ", callback_data="trd_want_2nft")],
        [InlineKeyboardButton(text="🎨 3 НФТ", callback_data="trd_want_3nft")],
        [InlineKeyboardButton(text="⬅️ Отмена", callback_data="trade_menu")],
    ])
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


# ─── Шаг 1 → 2: выбрали НФТ → тип обмена ───
@router.callback_query(F.data.startswith("trd_sel_nft_"), TradeStates.select_my_nft)
async def trade_select_nft(call: CallbackQuery, state: FSMContext):
    user_nft_id = int(call.data.replace("trd_sel_nft_", ""))
    uid = call.from_user.id

    nft = await get_user_nft_by_id(user_nft_id)
    if not nft or nft[1] != uid:
        return await call.answer("❌ НФТ не найден", show_alert=True)

    un_id, owner_id, nft_id, name, income, rarity, bought = nft
    await state.set_state(TradeStates.choose_want_type)
    await state.update_data(trd_nft_id=user_nft_id, trd_nft_name=name,
                            trd_nft_income=income, trd_nft_rarity=rarity)

    emoji = _rarity_emoji(rarity)
    text = (
        "➕ НОВЫЙ ОБМЕН\n"
        "══════════════════════\n\n"
        f"📤 Вы обмениваете:\n"
        f"  {emoji} {name} (+{fnum(income)}/ч)\n\n"
        "🎯 Что хотите получить?\n\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💢 Клики", callback_data="trd_want_clicks")],
        [InlineKeyboardButton(text="🎨 1 НФТ", callback_data="trd_want_1nft")],
        [InlineKeyboardButton(text="🎨 2 НФТ", callback_data="trd_want_2nft")],
        [InlineKeyboardButton(text="🎨 3 НФТ", callback_data="trd_want_3nft")],
        [InlineKeyboardButton(text="⬅️ Отмена", callback_data="trade_menu")],
    ])
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


# ─── Шаг 2a: хочу клики → ввод суммы ───
@router.callback_query(F.data == "trd_want_clicks", TradeStates.choose_want_type)
async def trade_want_clicks(call: CallbackQuery, state: FSMContext):
    await state.set_state(TradeStates.enter_click_price)

    text = (
        "💢 УКАЖИТЕ ЦЕНУ\n"
        "══════════════════════\n\n"
        "Выберите или введите количество\n"
        "кликов, которое хотите получить:\n\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="1 000 💢", callback_data="trd_price_1000"),
            InlineKeyboardButton(text="5 000 💢", callback_data="trd_price_5000"),
        ],
        [
            InlineKeyboardButton(text="10 000 💢", callback_data="trd_price_10000"),
            InlineKeyboardButton(text="50 000 💢", callback_data="trd_price_50000"),
        ],
        [
            InlineKeyboardButton(text="100 000 💢", callback_data="trd_price_100000"),
            InlineKeyboardButton(text="500 000 💢", callback_data="trd_price_500000"),
        ],
        [InlineKeyboardButton(text="⬅️ Отмена", callback_data="trade_menu")],
    ])
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


@router.callback_query(F.data.startswith("trd_price_"), TradeStates.enter_click_price)
async def trade_price_preset(call: CallbackQuery, state: FSMContext):
    price = int(call.data.replace("trd_price_", ""))
    await state.update_data(trd_want_clicks=price, trd_want_nft_count=0)
    await state.set_state(TradeStates.confirm_create)
    await _show_create_preview(call, state)


@router.message(TradeStates.enter_click_price)
async def trade_price_manual(message: Message, state: FSMContext):
    try:
        price = int(message.text.strip().replace(" ", ""))
        assert price > 0
    except (ValueError, AssertionError, AttributeError):
        return await message.answer("❌ Введите положительное число.")

    await state.update_data(trd_want_clicks=price, trd_want_nft_count=0)
    await state.set_state(TradeStates.confirm_create)

    data = await state.get_data()
    nft_name = data.get("trd_nft_name", "НФТ")
    nft_rarity = data.get("trd_nft_rarity", 1)
    emoji = _rarity_emoji(nft_rarity)

    text = (
        "📋 ПОДТВЕРЖДЕНИЕ\n"
        "══════════════════════\n\n"
        f"📤 Вы отдаёте:\n"
        f"  {emoji} {nft_name}\n\n"
        f"📥 Вы хотите:\n"
        f"  💢 {fnum(price)} кликов\n\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        "Опубликовать на доске обменов?"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Опубликовать", callback_data="trd_publish")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="trade_menu")],
    ])
    await message.answer(text, reply_markup=kb)


# ─── Шаг 2b: хочу НФТ ───
@router.callback_query(F.data.regexp(r"^trd_want_[123]nft$"), TradeStates.choose_want_type)
async def trade_want_nfts(call: CallbackQuery, state: FSMContext):
    count = int(call.data.replace("trd_want_", "").replace("nft", ""))
    await state.update_data(trd_want_clicks=0, trd_want_nft_count=count)
    await state.set_state(TradeStates.confirm_create)
    await _show_create_preview(call, state)


# ─── Превью создания ───
async def _show_create_preview(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    nft_name = data.get("trd_nft_name", "НФТ")
    nft_rarity = data.get("trd_nft_rarity", 1)
    want_clicks = data.get("trd_want_clicks", 0)
    want_nft = data.get("trd_want_nft_count", 0)
    emoji = _rarity_emoji(nft_rarity)

    want_text = _want_label(want_clicks, want_nft)

    text = (
        "📋 ПОДТВЕРЖДЕНИЕ\n"
        "══════════════════════\n\n"
        f"📤 Вы отдаёте:\n"
        f"  {emoji} {nft_name}\n\n"
        f"📥 Вы хотите:\n"
        f"  {want_text}\n\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        "Опубликовать на доске обменов?"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Опубликовать", callback_data="trd_publish")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="trade_menu")],
    ])
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


# ─── Публикация обмена ───
@router.callback_query(F.data == "trd_publish", TradeStates.confirm_create)
async def trade_publish(call: CallbackQuery, state: FSMContext):
    uid = call.from_user.id
    data = await state.get_data()
    nft_id = data.get("trd_nft_id")
    want_clicks = data.get("trd_want_clicks", 0)
    want_nft = data.get("trd_want_nft_count", 0)
    await state.clear()

    # Проверяем НФТ
    nft = await get_user_nft_by_id(nft_id)
    if not nft or nft[1] != uid:
        return await call.answer("❌ НФТ недоступен!", show_alert=True)
    if await is_nft_on_sale(nft_id):
        return await call.answer("❌ НФТ на продаже!", show_alert=True)

    trade_id = await create_public_trade(
        sender_id=uid,
        offer_nft_ids=[nft_id],
        want_clicks=want_clicks,
        want_nft_count=want_nft,
    )

    nft_name = data.get("trd_nft_name", "НФТ")
    want_text = _want_label(want_clicks, want_nft)

    text = (
        "✅ ОБМЕН ОПУБЛИКОВАН!\n"
        "══════════════════════\n\n"
        f"📤 Обмен #{trade_id}\n"
        f"🎨 {nft_name} → {want_text}\n\n"
        "⏳ Ожидайте предложений от\n"
        "других игроков на доске.\n\n"
        "══════════════════════"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 Мои обмены", callback_data="trd_my_trades")],
        [InlineKeyboardButton(text="⬅️ Обмен НФТ", callback_data="trade_menu")],
    ])
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer("✅ Опубликовано!", show_alert=True)


# ══════════════════════════════════════════════
#  🤝 ПРЕДЛОЖИТЬ — клики
# ══════════════════════════════════════════════
@router.callback_query(F.data.regexp(r"^trd_propose_clicks_\d+$"))
async def propose_clicks(call: CallbackQuery, state: FSMContext):
    uid = call.from_user.id
    trade_id = int(call.data.split("_")[-1])
    trade = await get_trade_offer(trade_id)
    if not trade or trade[5] != "open":
        return await call.answer("❌ Обмен недоступен", show_alert=True)

    t_id, sender_id, _, _, want_clicks, status, dt, want_nft_count = trade
    if uid == sender_id:
        return await call.answer("❌ Это ваш обмен!", show_alert=True)

    user = await get_user(uid)
    if user["clicks"] < want_clicks:
        return await call.answer(
            f"❌ Нужно {fnum(want_clicks)} 💢, у вас {fnum(user['clicks'])} 💢",
            show_alert=True)

    items = await get_trade_items(trade_id)
    offer_items = [i for i in items if i[2] == "offer"]
    nft_name = offer_items[0][4] if offer_items else "НФТ"
    nft_rarity = offer_items[0][5] if offer_items else 1
    emoji = _rarity_emoji(nft_rarity)

    sender = await get_user(sender_id)
    sname = f"@{sender['username']}" if sender and sender['username'] else f"ID:{sender_id}"

    text = (
        "🤝 ПОДТВЕРЖДЕНИЕ\n"
        "══════════════════════\n\n"
        f"👤 Обмен с {sname}\n\n"
        f"📥 Вы получите:\n"
        f"  {emoji} {nft_name}\n\n"
        f"📤 Вы отдадите:\n"
        f"  💢 {fnum(want_clicks)} кликов\n\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        "Подтвердить?"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"trd_do_propose_c_{trade_id}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"trd_view_{trade_id}")],
    ])
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


@router.callback_query(F.data.regexp(r"^trd_do_propose_c_\d+$"))
async def do_propose_clicks(call: CallbackQuery):
    uid = call.from_user.id
    trade_id = int(call.data.split("_")[-1])

    result = await propose_trade(trade_id, uid)
    if result == "no_clicks":
        return await call.answer("❌ Недостаточно кликов!", show_alert=True)
    if result == "self":
        return await call.answer("❌ Это ваш обмен!", show_alert=True)
    if result == "already":
        return await call.answer("❌ Обмен уже занят!", show_alert=True)
    if result == "nft_limit":
        return await call.answer(f"❌ Лимит {MAX_NFT} НФТ!", show_alert=True)
    if result != "ok":
        return await call.answer("❌ Ошибка", show_alert=True)

    # Уведомляем создателя
    trade = await get_trade_offer(trade_id)
    if trade:
        sender_id = trade[1]
        uname = call.from_user.username
        rname = f"@{uname}" if uname else f"ID:{uid}"
        try:
            notify_kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📥 Посмотреть", callback_data=f"trd_view_{trade_id}")],
            ])
            await call.bot.send_message(
                sender_id,
                f"🔔 НОВОЕ ПРЕДЛОЖЕНИЕ!\n"
                f"══════════════════════\n\n"
                f"👤 {rname} хочет обменяться!\n"
                f"📤 Обмен #{trade_id}\n\n"
                f"Проверьте предложения!",
                reply_markup=notify_kb,
            )
        except Exception:
            pass

    text = (
        "✅ ПРЕДЛОЖЕНИЕ ОТПРАВЛЕНО!\n"
        "══════════════════════\n\n"
        f"📤 Обмен #{trade_id}\n\n"
        "⏳ Ожидайте решения создателя.\n\n"
        "══════════════════════"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Обмен НФТ", callback_data="trade_menu")],
    ])
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer("✅ Отправлено!", show_alert=True)


# ══════════════════════════════════════════════
#  🤝 ПРЕДЛОЖИТЬ — НФТ (выбор кнопками)
# ══════════════════════════════════════════════
@router.callback_query(F.data.regexp(r"^trd_propose_nfts_\d+$"))
async def propose_nfts_start(call: CallbackQuery, state: FSMContext):
    uid = call.from_user.id
    trade_id = int(call.data.split("_")[-1])
    trade = await get_trade_offer(trade_id)
    if not trade or trade[5] != "open":
        return await call.answer("❌ Обмен недоступен", show_alert=True)

    t_id, sender_id, _, _, want_clicks, status, dt, want_nft_count = trade
    if uid == sender_id:
        return await call.answer("❌ Это ваш обмен!", show_alert=True)

    nfts = await get_user_nfts(uid)
    available = []
    for un_id, name, income, rarity, bought, nft_dt in nfts:
        if not await is_nft_on_sale(un_id):
            available.append((un_id, name, income, rarity))

    if len(available) < want_nft_count:
        return await call.answer(
            f"❌ Нужно {want_nft_count} НФТ, у вас доступно {len(available)}!",
            show_alert=True)

    await state.set_state(TradeStates.propose_select_nfts)
    await state.update_data(
        trd_propose_trade_id=trade_id,
        trd_propose_need=want_nft_count,
        trd_propose_selected=[],
    )

    text = (
        f"🎨 ВЫБЕРИТЕ {want_nft_count} НФТ\n"
        "══════════════════════\n\n"
        f"Выберите {want_nft_count} НФТ для обмена:\n"
        f"Выбрано: 0 / {want_nft_count}\n\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈"
    )
    kb = []
    for un_id, name, income, rarity in available:
        emoji = _rarity_emoji(rarity)
        kb.append([InlineKeyboardButton(
            text=f"{emoji} {name} (+{fnum(income)}/ч)",
            callback_data=f"trd_pnft_{un_id}",
        )])
    kb.append([InlineKeyboardButton(text="⬅️ Отмена", callback_data=f"trd_view_{trade_id}")])

    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await call.answer()


@router.callback_query(F.data.startswith("trd_pnft_"), TradeStates.propose_select_nfts)
async def propose_nft_toggle(call: CallbackQuery, state: FSMContext):
    un_id = int(call.data.replace("trd_pnft_", ""))
    data = await state.get_data()
    selected = data.get("trd_propose_selected", [])
    need = data.get("trd_propose_need", 1)
    trade_id = data.get("trd_propose_trade_id")

    if un_id in selected:
        selected.remove(un_id)
        await state.update_data(trd_propose_selected=selected)
        await call.answer(f"➖ Убрано ({len(selected)}/{need})")
        return

    if len(selected) >= need:
        return await call.answer(f"❌ Максимум {need} НФТ!", show_alert=True)

    nft = await get_user_nft_by_id(un_id)
    if not nft or nft[1] != call.from_user.id:
        return await call.answer("❌ НФТ не найден", show_alert=True)

    selected.append(un_id)
    await state.update_data(trd_propose_selected=selected)

    if len(selected) == need:
        # Все выбраны — показываем подтверждение
        await state.set_state(TradeStates.confirm_propose)

        trade = await get_trade_offer(trade_id)
        items = await get_trade_items(trade_id)
        offer_items = [i for i in items if i[2] == "offer"]
        get_nft_name = offer_items[0][4] if offer_items else "НФТ"
        get_nft_rarity = offer_items[0][5] if offer_items else 1

        sender = await get_user(trade[1])
        sname = f"@{sender['username']}" if sender and sender['username'] else f"ID:{trade[1]}"

        text = (
            "🤝 ПОДТВЕРЖДЕНИЕ\n"
            "══════════════════════\n\n"
            f"👤 Обмен с {sname}\n\n"
            f"📥 Вы получите:\n"
            f"  {_rarity_emoji(get_nft_rarity)} {get_nft_name}\n\n"
            f"📤 Вы отдадите:\n"
        )
        for nid in selected:
            n = await get_user_nft_by_id(nid)
            if n:
                text += f"  {_rarity_emoji(n[5])} {n[3]} (+{fnum(n[4])}/ч)\n"
        text += (
            "\n┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            "Подтвердить?"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Подтвердить", callback_data="trd_do_propose_nfts")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data=f"trd_view_{trade_id}")],
        ])
        await call.message.edit_text(text, reply_markup=kb)
        await call.answer()
    else:
        await call.answer(f"✅ Выбрано {len(selected)}/{need}")


@router.callback_query(F.data == "trd_do_propose_nfts", TradeStates.confirm_propose)
async def do_propose_nfts(call: CallbackQuery, state: FSMContext):
    uid = call.from_user.id
    data = await state.get_data()
    trade_id = data.get("trd_propose_trade_id")
    selected = data.get("trd_propose_selected", [])
    await state.clear()

    result = await propose_trade(trade_id, uid, offer_nft_ids=selected)
    if result == "no_nfts":
        return await call.answer("❌ НФТ недоступны!", show_alert=True)
    if result == "self":
        return await call.answer("❌ Это ваш обмен!", show_alert=True)
    if result == "already":
        return await call.answer("❌ Обмен уже занят!", show_alert=True)
    if result == "nft_limit":
        return await call.answer(f"❌ Лимит {MAX_NFT} НФТ!", show_alert=True)
    if result != "ok":
        return await call.answer("❌ Ошибка", show_alert=True)

    # Уведомляем создателя
    trade = await get_trade_offer(trade_id)
    if trade:
        sender_id = trade[1]
        uname = call.from_user.username
        rname = f"@{uname}" if uname else f"ID:{uid}"
        try:
            notify_kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📥 Посмотреть", callback_data=f"trd_view_{trade_id}")],
            ])
            await call.bot.send_message(
                sender_id,
                f"🔔 НОВОЕ ПРЕДЛОЖЕНИЕ!\n"
                f"══════════════════════\n\n"
                f"👤 {rname} предлагает НФТ!\n"
                f"📤 Обмен #{trade_id}\n\n"
                f"Проверьте предложения!",
                reply_markup=notify_kb,
            )
        except Exception:
            pass

    text = (
        "✅ ПРЕДЛОЖЕНИЕ ОТПРАВЛЕНО!\n"
        "══════════════════════\n\n"
        f"📤 Обмен #{trade_id}\n\n"
        "⏳ Ожидайте решения создателя.\n\n"
        "══════════════════════"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Обмен НФТ", callback_data="trade_menu")],
    ])
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer("✅ Отправлено!", show_alert=True)


# ══════════════════════════════════════════════
#  ✅ ПРИНЯТЬ / ❌ ОТКЛОНИТЬ предложение
# ══════════════════════════════════════════════
@router.callback_query(F.data.regexp(r"^trd_accept_\d+$"))
async def trade_accept_handler(call: CallbackQuery):
    uid = call.from_user.id
    trade_id = int(call.data.split("_")[-1])

    result = await accept_trade(trade_id, uid)
    if result == "not_found":
        return await call.answer("❌ Предложение не найдено", show_alert=True)
    if result == "not_owner":
        return await call.answer("❌ Вы не создатель этого обмена", show_alert=True)
    if result == "no_clicks":
        return await call.answer("❌ У откликнувшегося недостаточно кликов!", show_alert=True)
    if result == "nft_unavailable":
        return await call.answer("❌ Некоторые НФТ недоступны!", show_alert=True)
    if result == "nft_limit":
        return await call.answer(f"❌ Превышен лимит {MAX_NFT} НФТ!", show_alert=True)

    # Уведомляем откликнувшегося
    trade = await get_trade_offer(trade_id)
    if trade:
        receiver_id = trade[2]
        try:
            await call.bot.send_message(
                receiver_id,
                f"✅ Ваше предложение на обмен #{trade_id} принято!\n"
                f"НФТ и клики обменяны. 🎉",
            )
        except Exception:
            pass

        total_val = float(trade[3] or 0) + float(trade[4] or 0)
        await create_transaction(
            "trade", uid, receiver_id, total_val,
            f"Обмен #{trade_id} ∙ принят", ref_id=trade_id,
        )

    text = (
        "✅ ОБМЕН ЗАВЕРШЁН!\n"
        "══════════════════════\n\n"
        f"📤 Обмен #{trade_id} успешно выполнен!\n"
        "НФТ и клики переведены. 🎉\n\n"
        "══════════════════════"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎨 Мои НФТ", callback_data="my_nft")],
        [InlineKeyboardButton(text="⬅️ Обмен НФТ", callback_data="trade_menu")],
    ])
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer("✅ Обмен завершён!", show_alert=True)


@router.callback_query(F.data.regexp(r"^trd_reject_\d+$"))
async def trade_reject_handler(call: CallbackQuery):
    uid = call.from_user.id
    trade_id = int(call.data.split("_")[-1])

    ok = await reject_proposal(trade_id, uid)
    if not ok:
        return await call.answer("❌ Ошибка", show_alert=True)

    # Уведомляем откликнувшегося что отклонено
    trade = await get_trade_offer(trade_id)
    # After rejection, receiver_id was reset to 0, but we can notify if we had it
    # Since it's reset, we skip notification for simplicity
    await call.answer("❌ Предложение отклонено, обмен вернулся на доску", show_alert=True)

    # Показать обмен заново
    await trade_view(call)


# ─── Отменить обмен (создатель) ───
@router.callback_query(F.data.regexp(r"^trd_cancel_\d+$"))
async def trade_cancel_handler(call: CallbackQuery):
    uid = call.from_user.id
    trade_id = int(call.data.split("_")[-1])

    ok = await cancel_trade(trade_id, uid)
    if not ok:
        return await call.answer("❌ Ошибка", show_alert=True)

    await call.answer("🚫 Обмен отменён", show_alert=True)

    text = (
        "🚫 ОБМЕН ОТМЕНЁН\n"
        "══════════════════════\n\n"
        f"Обмен #{trade_id} отменён.\n\n"
        "══════════════════════"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Обмен НФТ", callback_data="trade_menu")],
    ])
    await call.message.edit_text(text, reply_markup=kb)


# ══════════════════════════════════════════════
#  📥 ПРЕДЛОЖЕНИЯ (входящие отклики на мои обмены)
# ══════════════════════════════════════════════
@router.callback_query(F.data == "trd_proposals")
async def show_proposals(call: CallbackQuery, state: FSMContext):
    if state:
        await state.clear()
    uid = call.from_user.id
    proposals = await get_proposals_for_me(uid)

    if not proposals:
        text = (
            "📥 ПРЕДЛОЖЕНИЯ\n"
            "══════════════════════\n\n"
            "📭 Нет предложений.\n\n"
            "══════════════════════"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить", callback_data="trd_proposals")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="trade_menu")],
        ])
        await call.message.edit_text(text, reply_markup=kb)
        return await call.answer()

    text = "📥 ПРЕДЛОЖЕНИЯ\n══════════════════════\n\n"
    kb = []
    for t in proposals:
        t_id = t[0]
        receiver_id = t[2]
        responder = await get_user(receiver_id)
        rname = f"@{responder['username']}" if responder and responder['username'] else f"ID:{receiver_id}"
        text += f"🤝 #{t_id} от {rname}\n"
        kb.append([InlineKeyboardButton(
            text=f"🤝 #{t_id} — {rname}",
            callback_data=f"trd_view_{t_id}",
        )])

    text += "\n┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\nВыберите предложение:"
    kb.append([InlineKeyboardButton(text="🔄 Обновить", callback_data="trd_proposals")])
    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="trade_menu")])
    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await call.answer()


# ══════════════════════════════════════════════
#  📤 МОИ ОБМЕНЫ
# ══════════════════════════════════════════════
@router.callback_query(F.data == "trd_my_trades")
async def show_my_trades(call: CallbackQuery, state: FSMContext):
    if state:
        await state.clear()
    uid = call.from_user.id
    trades = await get_my_open_trades(uid)

    if not trades:
        text = (
            "📤 МОИ ОБМЕНЫ\n"
            "══════════════════════\n\n"
            "📭 Нет активных обменов.\n\n"
            "══════════════════════"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Создать обмен", callback_data="trd_create")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="trade_menu")],
        ])
        await call.message.edit_text(text, reply_markup=kb)
        return await call.answer()

    _status_icon = {"open": "🟢", "proposed": "🟡"}

    text = "📤 МОИ ОБМЕНЫ\n══════════════════════\n\n"
    kb = []
    for t in trades:
        t_id, sender_id, receiver_id, offer_clicks, want_clicks, status, dt, want_nft_count = t
        icon = _status_icon.get(status, "⚪")
        items = await get_trade_items(t_id)
        offer_items = [i for i in items if i[2] == "offer"]
        nft_name = offer_items[0][4] if offer_items else "НФТ"
        want_text = _want_label(want_clicks, want_nft_count)
        st_text = "ожидает" if status == "open" else "есть отклик!"
        text += f"{icon} #{t_id} ∙ {nft_name} → {want_text} ({st_text})\n"
        kb.append([InlineKeyboardButton(
            text=f"{icon} #{t_id} ∙ {nft_name}",
            callback_data=f"trd_view_{t_id}",
        )])

    text += "\n┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈"
    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="trade_menu")])
    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await call.answer()

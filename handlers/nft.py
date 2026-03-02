# ======================================================
# НФТ — Мои НФТ, продажа, удаление, маркет
# ======================================================
import math

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from config import NFT_RARITY_EMOJI, NFT_DELETE_COST
from states import SellNFTStates
from database import (
    get_user, get_user_nfts, get_user_nft_detail, count_user_nfts,
    get_user_nft_slots, delete_user_nft, get_nft_on_sale,
    create_market_listing, cancel_market_listing,
    get_market_listings, count_market_listings, buy_market_listing,
    create_transaction, log_activity, set_user_online,
    pin_nft, unpin_nft, get_user_pinned_nft,
)
from keyboards import (
    my_nft_kb, nft_detail_kb, nft_delete_confirm_kb,
    nft_sell_confirm_kb, back_menu_kb, market_menu_kb,
)
from handlers.common import fnum
from banners_util import send_msg, safe_edit

router = Router()


def _rarity_emoji(rn: str) -> str:
    return NFT_RARITY_EMOJI.get(rn, "🟢")


# ── Мои НФТ ──
@router.callback_query(F.data == "my_nft")
async def my_nft(call: CallbackQuery, state: FSMContext):
    await _show_my_nft_page(call, state, 0)


@router.callback_query(F.data.startswith("my_nft_pg:"))
async def my_nft_page(call: CallbackQuery, state: FSMContext):
    page = int(call.data.split(":")[1])
    await _show_my_nft_page(call, state, page)


async def _show_my_nft_page(call: CallbackQuery, state: FSMContext, page: int):
    uid = call.from_user.id
    await state.clear()
    await set_user_online(uid)
    user = await get_user(uid)
    if not user:
        return await call.answer("❌ /start", show_alert=True)

    nfts = await get_user_nfts(uid)
    max_slots = await get_user_nft_slots(uid)
    count = len(nfts)

    total_income = sum(float(n[2] or 0) for n in nfts)

    text = (
        "<b>🎨 Мои НФТ</b>\n"
        "━━━━━━━━━━━━━━━━━━━\n\n"
        f"📦 Слотов: <b>{count}/{max_slots}</b>\n"
        f"📈 Доход НФТ: <b>{fnum(total_income)}</b>/ч\n\n"
        "━━━━━━━━━━━━━━━━━━━"
    )

    await send_msg(call, text, reply_markup=my_nft_kb(nfts, max_slots, page))


# ── Детали НФТ ──
@router.callback_query(F.data.startswith("nft_info_"))
async def nft_info(call: CallbackQuery):
    un_id = int(call.data.replace("nft_info_", ""))
    nft = await get_user_nft_detail(un_id)
    if not nft:
        return await call.answer("❌ НФТ не найден", show_alert=True)

    # un.id, un.user_id, un.nft_id, un.bought_price, un.created_at,
    # t.name, t.income_per_hour, t.rarity_pct, t.rarity_name, t.price, t.collection_num
    name = nft[5]
    income = nft[6]
    rarity_pct = nft[7]
    rarity_name = nft[8]
    price = nft[9]
    collection_num = nft[10]
    bought_price = nft[3]
    created_at = nft[4]
    emoji = _rarity_emoji(rarity_name)

    on_sale = await get_nft_on_sale(un_id)

    # Check if pinned
    pinned = await get_user_pinned_nft(call.from_user.id)
    is_pinned = pinned is not None and int(pinned[0]) == un_id

    text = (
        f"<b>📋 НФТ</b>\n"
        "━━━━━━━━━━━━━━━━━━━\n\n"
        f"📛 Название: <b>{name}</b>\n"
        f"📂 Коллекция: <b>#{collection_num}</b>\n"
        f"✨ Редкость: {emoji} {rarity_name} ({rarity_pct}%)\n"
        f"💰 Доход: <b>{fnum(income)}</b>/ч\n\n\n"
        f"🏷 Цена: {fnum(bought_price)} 💢\n"
    )
    if is_pinned:
        text += "\n📌 <b>ЗАКРЕПЛЁН В ПРОФИЛЕ</b>\n"
    if on_sale:
        text += "\n📢 <b>ВЫСТАВЛЕН НА ПРОДАЖУ</b>\n"
    text += "\n━━━━━━━━━━━━━━━━━━━"

    await call.message.edit_text(
        text,
        reply_markup=nft_detail_kb(un_id, on_sale=bool(on_sale), is_pinned=is_pinned),
    )
    await call.answer()


# ── Удаление НФТ ──
@router.callback_query(F.data.startswith("nft_delete_"))
async def nft_delete_ask(call: CallbackQuery):
    un_id = int(call.data.replace("nft_delete_", ""))
    text = (
        f"<b>🗑 Удаление НФТ</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"Стоимость: <b>{fnum(NFT_DELETE_COST)}</b> 💢\n\n"
        f"⚠️ Вы уверены?"
    )
    await safe_edit(call.message, text, reply_markup=nft_delete_confirm_kb(un_id))
    await call.answer()


@router.callback_query(F.data.startswith("nft_del_yes_"))
async def nft_del_confirm(call: CallbackQuery):
    un_id = int(call.data.replace("nft_del_yes_", ""))
    uid = call.from_user.id
    ok, msg = await delete_user_nft(un_id, uid)
    if not ok:
        return await call.answer(f"❌ {msg}", show_alert=True)
    await log_activity(uid, "nft", f"Удалил НФТ #{un_id} за {NFT_DELETE_COST}")
    await create_transaction("nft_sell", uid, amount=NFT_DELETE_COST, details=f"Удаление НФТ #{un_id}")
    await call.answer("✅ НФТ удалён!", show_alert=True)
    # Вернуться к списку
    nfts = await get_user_nfts(uid)
    max_slots = await get_user_nft_slots(uid)
    count = len(nfts)
    total_income = sum(float(n[2] or 0) for n in nfts)
    text = (
        "<b>🎨 Мои НФТ</b>\n"
        "━━━━━━━━━━━━━━━━━━━\n\n"
        f"📦 Слотов: <b>{count}/{max_slots}</b>\n"
        f"📈 Доход НФТ: <b>{fnum(total_income)}</b>/ч\n\n"
        "━━━━━━━━━━━━━━━━━━━"
    )
    await send_msg(call, text, reply_markup=my_nft_kb(nfts, max_slots, 0))


# ── Продажа ──
@router.callback_query(F.data.startswith("nft_sell_"))
async def nft_sell_start(call: CallbackQuery, state: FSMContext):
    un_id = int(call.data.replace("nft_sell_", ""))
    nft = await get_user_nft_detail(un_id)
    if not nft:
        return await call.answer("❌ Не найден", show_alert=True)
    await state.set_state(SellNFTStates.waiting_price)
    await state.set_data({"user_nft_id": un_id, "nft_id": nft[2]})

    name = nft[5]
    income = nft[6]
    rarity_pct = nft[7]
    rarity_name = nft[8]
    emoji = _rarity_emoji(rarity_name)

    text = (
        f"<b>💰 Продажа НФТ</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"📛 Название: <b>{name}</b>\n"
        f"✨ Редкость: {emoji} {rarity_name} ({rarity_pct}%)\n"
        f"💰 Доход: <b>{fnum(income)}</b>/ч\n\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"✏️ Введите цену продажи (число):"
    )
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="my_nft")]
    ]))
    await call.answer()


@router.message(SellNFTStates.waiting_price)
async def nft_sell_price(message: Message, state: FSMContext):
    try:
        price = float(message.text.strip())
        if price < 1:
            return await message.answer("❌ Минимум 1 💢")
    except (ValueError, TypeError):
        return await message.answer("❌ Введите число")

    data = await state.get_data()
    un_id = data["user_nft_id"]
    nft_id = data["nft_id"]
    uid = message.from_user.id
    await state.clear()

    await create_market_listing(uid, un_id, nft_id, price)
    await log_activity(uid, "sale", f"Выставил НФТ #{un_id} за {price}")
    await create_transaction("nft_sell", uid, amount=price, details=f"Выставлен НФТ #{un_id}")
    await message.answer(
        f"✅ НФТ выставлен на продажу за {fnum(price)} 💢!",
        reply_markup=back_menu_kb(),
    )


# ── Снять с продажи ──
@router.callback_query(F.data.startswith("nft_unsell_"))
async def nft_unsell(call: CallbackQuery):
    un_id = int(call.data.replace("nft_unsell_", ""))
    sale = await get_nft_on_sale(un_id)
    if sale:
        await cancel_market_listing(sale[0], call.from_user.id)
        await call.answer("✅ Снято с продажи!", show_alert=True)
    else:
        await call.answer("❌ Не найдено", show_alert=True)
    # Показываем детали НФТ (нельзя вызвать nft_info напрямую — call.data != nft_info_*)
    nft = await get_user_nft_detail(un_id)
    if not nft:
        return
    name = nft[5]
    income = nft[6]
    rarity_pct = nft[7]
    rarity_name = nft[8]
    bought_price = nft[9]
    collection_num = nft[10]
    created_at = nft[4]
    on_sale = await get_nft_on_sale(un_id)
    emoji = _rarity_emoji(rarity_name)
    text = (
        f"<b>📋 НФТ</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"📛 Название: <b>{name}</b>\n"
        f"📂 Коллекция: <b>#{collection_num}</b>\n"
        f"✨ Редкость: {emoji} {rarity_name} ({rarity_pct}%)\n"
        f"💰 Доход: <b>{fnum(income)}</b>/ч\n\n\n"
        f"🏷 Цена: {fnum(bought_price)} 💢\n"
    )
    if on_sale:
        text += "\n📢 <b>ВЫСТАВЛЕН НА ПРОДАЖУ</b>\n"
    text += "\n━━━━━━━━━━━━━━━━━━━"
    await safe_edit(call.message, text, reply_markup=nft_detail_kb(un_id, on_sale=bool(on_sale)))


# ── Закрепить / Открепить НФТ ──
@router.callback_query(F.data.startswith("nft_pin_"))
async def nft_pin(call: CallbackQuery):
    un_id = int(call.data.replace("nft_pin_", ""))
    uid = call.from_user.id
    nft = await get_user_nft_detail(un_id)
    if not nft or nft[1] != uid:
        return await call.answer("❌ НФТ не найден", show_alert=True)
    await pin_nft(uid, un_id)
    await call.answer("📌 НФТ закреплён в профиле!", show_alert=True)
    # Refresh detail view
    name = nft[5]
    income = nft[6]
    rarity_pct = nft[7]
    rarity_name = nft[8]
    bought_price = nft[3]
    collection_num = nft[10]
    emoji = _rarity_emoji(rarity_name)
    on_sale = await get_nft_on_sale(un_id)
    text = (
        f"<b>📋 НФТ</b>\n"
        "━━━━━━━━━━━━━━━━━━━\n\n"
        f"📛 Название: <b>{name}</b>\n"
        f"📂 Коллекция: <b>#{collection_num}</b>\n"
        f"✨ Редкость: {emoji} {rarity_name} ({rarity_pct}%)\n"
        f"💰 Доход: <b>{fnum(income)}</b>/ч\n\n\n"
        f"🏷 Цена: {fnum(bought_price)} 💢\n"
        "\n📌 <b>ЗАКРЕПЛЁН В ПРОФИЛЕ</b>\n"
    )
    if on_sale:
        text += "\n📢 <b>ВЫСТАВЛЕН НА ПРОДАЖУ</b>\n"
    text += "\n━━━━━━━━━━━━━━━━━━━"
    await safe_edit(call.message, text, reply_markup=nft_detail_kb(un_id, on_sale=bool(on_sale), is_pinned=True))


@router.callback_query(F.data.startswith("nft_unpin_"))
async def nft_unpin(call: CallbackQuery):
    un_id = int(call.data.replace("nft_unpin_", ""))
    uid = call.from_user.id
    await unpin_nft(uid)
    await call.answer("📌 НФТ откреплён!", show_alert=True)
    nft = await get_user_nft_detail(un_id)
    if not nft:
        return
    name = nft[5]
    income = nft[6]
    rarity_pct = nft[7]
    rarity_name = nft[8]
    bought_price = nft[3]
    collection_num = nft[10]
    emoji = _rarity_emoji(rarity_name)
    on_sale = await get_nft_on_sale(un_id)
    text = (
        f"<b>📋 НФТ</b>\n"
        "━━━━━━━━━━━━━━━━━━━\n\n"
        f"📛 Название: <b>{name}</b>\n"
        f"📂 Коллекция: <b>#{collection_num}</b>\n"
        f"✨ Редкость: {emoji} {rarity_name} ({rarity_pct}%)\n"
        f"💰 Доход: <b>{fnum(income)}</b>/ч\n\n\n"
        f"🏷 Цена: {fnum(bought_price)} 💢\n"
    )
    if on_sale:
        text += "\n📢 <b>ВЫСТАВЛЕН НА ПРОДАЖУ</b>\n"
    text += "\n━━━━━━━━━━━━━━━━━━━"
    await safe_edit(call.message, text, reply_markup=nft_detail_kb(un_id, on_sale=bool(on_sale), is_pinned=False))


# ══════════════════════════════════════════
#  ТОРГОВАЯ ПЛОЩАДКА (маркет)
# ══════════════════════════════════════════
@router.callback_query(F.data == "market_menu")
async def market_menu(call: CallbackQuery):
    await set_user_online(call.from_user.id)
    text = (
        "<b>🏠 Торговая площадка</b>\n"
        "━━━━━━━━━━━━━━━━━━━\n\n"
        "Покупайте и продавайте НФТ\n"
        "другим игрокам!\n\n"
        "━━━━━━━━━━━━━━━━━━━"
    )
    await send_msg(call, text, reply_markup=market_menu_kb())


@router.callback_query(F.data.startswith("nftp_"))
async def nft_market_page(call: CallbackQuery):
    page = int(call.data.replace("nftp_", ""))
    total = await count_market_listings()
    per_page = 5
    total_pages = max(1, math.ceil(total / per_page))
    if page < 0:
        page = 0
    if page >= total_pages:
        page = total_pages - 1
    items = await get_market_listings(page, per_page)

    if not items:
        text = "<b>🏠 Площадка пуста</b>\n\nВыставьте свои НФТ на продажу!"
        try:
            await call.message.edit_text(text, reply_markup=market_menu_kb())
        except Exception:
            pass
        return await call.answer()

    text = f"<b>🛒 НФТ НА ПРОДАЖЕ</b> ({total} шт.)\n━━━━━━━━━━━━━━━━━━━\n"

    kb = []
    for item in items:
        listing_id = item[0]
        name = item[5]
        rarity_name = item[6]
        rarity_pct = item[7]
        income = item[8]
        price = item[4]
        collection_num = item[9]
        emoji = _rarity_emoji(rarity_name)

        text += (
            f"\n📛 Название: <b>{name}</b>\n"
            f"📂 Коллекция: <b>#{collection_num}</b>\n"
            f"✨ Редкость: {emoji} {rarity_name} ({rarity_pct}%)\n"
            f"💰 Доход: <b>{fnum(income)}</b>/ч\n\n"
            f"🏷 Цена: <b>{fnum(price)}</b> 💢\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
        )
        kb.append([InlineKeyboardButton(
            text=f"🛍 Купить «{name}» — {fnum(price)} 💢",
            callback_data=f"nft_buy_ask_{listing_id}"
        )])

    # Пагинация
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️ Назад", callback_data=f"nftp_{page - 1}"))
    nav.append(InlineKeyboardButton(text=f"📂 {page + 1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="Вперёд ▶️", callback_data=f"nftp_{page + 1}"))
    kb.append(nav)
    kb.append([InlineKeyboardButton(text="⬅️ Площадка", callback_data="market_menu")])

    try:
        await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="HTML")
    except Exception:
        pass
    await call.answer()


# ── Просмотр листинга (купить) ──
@router.callback_query(F.data.startswith("nftv_market_"))
async def nft_market_view(call: CallbackQuery):
    listing_id = int(call.data.replace("nftv_market_", ""))
    from database import get_db
    import aiosqlite
    db = await get_db()
    db.row_factory = aiosqlite.Row
    cur = await db.execute(
        """SELECT m.id, m.seller_id, m.price, t.name, t.rarity_name, t.rarity_pct,
                  t.income_per_hour, t.collection_num
           FROM nft_market m JOIN nft_templates t ON m.nft_id = t.id
           WHERE m.id = ? AND m.status = 'open'""",
        (listing_id,),
    )
    row = await cur.fetchone()
    if not row:
        return await call.answer("❌ Не найден", show_alert=True)

    emoji = _rarity_emoji(row["rarity_name"])
    text = (
        f"<b>📋 НФТ на площадке</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"📛 Название: <b>{row['name']}</b>\n"
        f"📂 Коллекция: <b>#{row['collection_num']}</b>\n"
        f"✨ Редкость: {emoji} {row['rarity_name']} ({row['rarity_pct']}%)\n"
        f"💰 Доход: <b>{fnum(row['income_per_hour'])}</b>/ч\n\n\n"
        f"🏷 Цена: <b>{fnum(row['price'])}</b> 💢\n\n"
        f"━━━━━━━━━━━━━━━━━━━"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛍 Купить", callback_data=f"nft_buy_ask_{listing_id}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="nftp_0")],
    ])
    await safe_edit(call.message, text, reply_markup=kb)
    await call.answer()


# ── Подтверждение покупки ──
@router.callback_query(F.data.startswith("nft_buy_ask_"))
async def nft_buy_ask(call: CallbackQuery):
    listing_id = int(call.data.replace("nft_buy_ask_", ""))
    from database import get_db
    import aiosqlite
    db = await get_db()
    db.row_factory = aiosqlite.Row
    cur = await db.execute(
        """SELECT m.id, m.price, t.name
           FROM nft_market m JOIN nft_templates t ON m.nft_id = t.id
           WHERE m.id = ? AND m.status = 'open'""",
        (listing_id,),
    )
    row = await cur.fetchone()
    if not row:
        return await call.answer("❌ Не найден", show_alert=True)

    text = (
        f"❓ <b>Подтвердите покупку</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"📛 <b>{row['name']}</b>\n"
        f"🏷 Цена: <b>{fnum(row['price'])}</b> 💢\n\n"
        f"Вы уверены?\n\n"
        f"━━━━━━━━━━━━━━━━━━━"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да", callback_data=f"nftb_market_{listing_id}"),
            InlineKeyboardButton(text="❌ Нет", callback_data="nftp_0"),
        ],
    ])
    await safe_edit(call.message, text, reply_markup=kb)
    await call.answer()


# ── Покупка с маркета ──
@router.callback_query(F.data.startswith("nftb_market_"))
async def nft_market_buy(call: CallbackQuery):
    listing_id = int(call.data.replace("nftb_market_", ""))
    uid = call.from_user.id
    ok, msg = await buy_market_listing(listing_id, uid)
    if not ok:
        return await call.answer(f"❌ {msg}", show_alert=True)
    await log_activity(uid, "buy", f"Купил НФТ с маркета #{listing_id}")
    await create_transaction("market_buy", uid, amount=0, details=f"Покупка с маркета #{listing_id}")
    await call.answer("✅ НФТ куплен!", show_alert=True)
    # Перейти к маркету (page=0)
    call.data = "nftp_0"
    await nft_market_page(call)

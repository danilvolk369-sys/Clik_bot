# ======================================================
# ОБМЕН НФТ — предложить 1-5 НФТ, принять/отклонить
# ======================================================
import math

from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from database import (
    get_user, get_user_nfts, get_user_nft_detail,
    create_trade, get_open_trades, count_open_trades,
    get_trade, get_trade_items, propose_trade, accept_trade,
    reject_trade, cancel_trade, get_incoming_trades,
    transfer_nft, create_transaction, log_activity, set_user_online,
)
from keyboards import trade_menu_kb, back_menu_kb
from config import NFT_RARITY_EMOJI
from handlers.common import fnum
from banners_util import send_msg, safe_edit

router = Router()

# Контекст для сборки обмена
_trade_ctx: dict = {}  # uid -> {"step": ..., "nft_ids": [...], "trade_id": ..., ...}


def _rarity_emoji(rn: str) -> str:
    return NFT_RARITY_EMOJI.get(rn, "🟢")


# ── Меню обменов ──
@router.callback_query(F.data == "trade_menu")
async def show_trade_menu(call: CallbackQuery, state: FSMContext | None = None):
    uid = call.from_user.id
    if state:
        await state.clear()
    await set_user_online(uid)
    _trade_ctx.pop(uid, None)

    total = await count_open_trades()
    per_page = 5
    total_pages = max(1, math.ceil(total / per_page))
    trades = await get_open_trades(0, per_page)

    if not trades:
        text = "🔄 ОБМЕН НФТ\n══════════════════════\n\nНет открытых обменов."
    else:
        text = f"🔄 ОБМЕН НФТ ({total} шт.)\n══════════════════════\n"

    await send_msg(call, text, reply_markup=trade_menu_kb(trades, 0, total_pages))


@router.callback_query(F.data.startswith("trades_pg_"))
async def trades_page(call: CallbackQuery):
    page = int(call.data.replace("trades_pg_", ""))
    total = await count_open_trades()
    per_page = 5
    total_pages = max(1, math.ceil(total / per_page))
    trades = await get_open_trades(page, per_page)
    text = f"🔄 ОБМЕН НФТ ({total} шт.)\n══════════════════════\n"
    await call.message.edit_text(text, reply_markup=trade_menu_kb(trades, page, total_pages))
    await call.answer()


# ── Создать обмен (из НФТ-детали) ──
@router.callback_query(F.data.startswith("nft_trade_"))
async def start_trade(call: CallbackQuery):
    un_id = int(call.data.replace("nft_trade_", ""))
    uid = call.from_user.id
    nft = await get_user_nft_detail(un_id)
    if not nft or nft[1] != uid:
        return await call.answer("❌ НФТ не ваш", show_alert=True)

    _trade_ctx[uid] = {"step": "select", "nft_ids": [un_id]}

    text = (
        "🔄 СОЗДАНИЕ ОБМЕНА\n"
        "══════════════════════\n\n"
        f"Выбрано: 1 НФТ (макс 5)\n\n"
        "Добавьте ещё или создайте обмен."
    )
    nfts = await get_user_nfts(uid)
    kb = _select_nfts_kb(nfts, _trade_ctx[uid]["nft_ids"])
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


def _select_nfts_kb(user_nfts: list, selected_ids: list):
    kb = []
    for nft in user_nfts:
        un_id = nft[0]
        name = nft[1]
        rarity_name = nft[4] if len(nft) > 4 else "Обычный"
        emoji = _rarity_emoji(rarity_name)
        check = "✅" if un_id in selected_ids else "☐"
        kb.append([InlineKeyboardButton(
            text=f"{check} {emoji} {name}",
            callback_data=f"trade_toggle_{un_id}",
        )])
    kb.append([InlineKeyboardButton(text="✅ Создать обмен (0 💢)", callback_data="trade_create_0")])
    kb.append([InlineKeyboardButton(text="✅ С ценой (введите)", callback_data="trade_create_price")])
    kb.append([InlineKeyboardButton(text="❌ Отмена", callback_data="my_nft")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


@router.callback_query(F.data.startswith("trade_toggle_"))
async def trade_toggle(call: CallbackQuery):
    un_id = int(call.data.replace("trade_toggle_", ""))
    uid = call.from_user.id
    ctx = _trade_ctx.get(uid)
    if not ctx:
        return await call.answer("❌ Начните заново", show_alert=True)

    ids = ctx["nft_ids"]
    if un_id in ids:
        ids.remove(un_id)
    else:
        if len(ids) >= 5:
            return await call.answer("❌ Максимум 5 НФТ", show_alert=True)
        ids.append(un_id)

    _trade_ctx[uid]["nft_ids"] = ids
    nfts = await get_user_nfts(uid)
    text = (
        "🔄 СОЗДАНИЕ ОБМЕНА\n"
        "══════════════════════\n\n"
        f"Выбрано: {len(ids)} НФТ (макс 5)\n\n"
        "Добавьте ещё или создайте обмен."
    )
    await call.message.edit_text(text, reply_markup=_select_nfts_kb(nfts, ids))
    await call.answer()


@router.callback_query(F.data == "trade_create_0")
async def trade_create_free(call: CallbackQuery):
    uid = call.from_user.id
    ctx = _trade_ctx.get(uid)
    if not ctx or not ctx["nft_ids"]:
        return await call.answer("❌ Выберите хотя бы 1 НФТ", show_alert=True)

    trade_id = await create_trade(uid, ctx["nft_ids"], want_clicks=0)
    _trade_ctx.pop(uid, None)
    await log_activity(uid, "trade", f"Создал обмен #{trade_id}, {len(ctx['nft_ids'])} НФТ")
    await call.answer("✅ Обмен создан!", show_alert=True)
    await show_trade_menu(call)


@router.callback_query(F.data == "trade_create_price")
async def trade_create_price_ask(call: CallbackQuery, state: FSMContext):
    uid = call.from_user.id
    ctx = _trade_ctx.get(uid)
    if not ctx or not ctx["nft_ids"]:
        return await call.answer("❌ Выберите хотя бы 1 НФТ", show_alert=True)

    from states import TradeStates
    _trade_ctx[uid]["step"] = "price"
    await state.set_state(TradeStates.enter_click_price)
    text = "Введите требуемую цену в 💢 (или 0):"
    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="trade_menu")]
    ]))
    await call.answer()


from states import TradeStates as _TS


@router.message(_TS.enter_click_price)
async def trade_price_input(message: Message, state: FSMContext):
    uid = message.from_user.id
    ctx = _trade_ctx.get(uid)
    if not ctx or ctx.get("step") != "price":
        await state.clear()
        return await message.answer("❌ Ошибка контекста. Начните заново.", reply_markup=back_menu_kb())

    try:
        price = float(message.text.strip())
        if price < 0:
            return await message.answer("❌ Цена не может быть отрицательной")
    except (ValueError, TypeError):
        return await message.answer("❌ Введите число")

    await state.clear()
    nft_ids = ctx["nft_ids"]
    trade_id = await create_trade(uid, nft_ids, want_clicks=price)
    _trade_ctx.pop(uid, None)
    await log_activity(uid, "trade", f"Создал обмен #{trade_id}, {len(nft_ids)} НФТ, цена {price}")
    await message.answer(
        f"✅ Обмен создан! Цена: {fnum(price)} 💢",
        reply_markup=back_menu_kb(),
    )


# ── Просмотр обмена ──
@router.callback_query(F.data.startswith("trade_view_"))
async def trade_view(call: CallbackQuery):
    trade_id = int(call.data.replace("trade_view_", ""))
    uid = call.from_user.id
    trade = await get_trade(trade_id)
    if not trade:
        return await call.answer("❌ Не найден", show_alert=True)

    offer_items = await get_trade_items(trade_id, 'offer')
    lines = ["🔄 ОБМЕН ПРЕДЛОЖЕНИЕ\n══════════════════════\n"]
    lines.append(f"📤 Предлагает (ID: {trade['sender_id']}):\n")
    for item in offer_items:
        un_id, name, rn, income = item
        emoji = _rarity_emoji(rn)
        lines.append(f"  {emoji} {name} — {fnum(income)} Тохн/ч")

    want_clicks = float(trade['want_clicks'] or 0)
    if want_clicks > 0:
        lines.append(f"\n💰 Хочет: {fnum(want_clicks)} 💢")

    lines.append("\n══════════════════════")

    kb = []
    if trade["sender_id"] == uid:
        kb.append([InlineKeyboardButton(text="❌ Отменить обмен", callback_data=f"trade_cancel_{trade_id}")])
    else:
        kb.append([InlineKeyboardButton(text="📤 Предложить свои НФТ", callback_data=f"trade_propose_{trade_id}")])
        if want_clicks > 0:
            kb.append([InlineKeyboardButton(text=f"💰 Купить за {fnum(want_clicks)} 💢", callback_data=f"trade_buy_{trade_id}")])
    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="trade_menu")])

    await call.message.edit_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await call.answer()


# ── Отменить свой обмен ──
@router.callback_query(F.data.startswith("trade_cancel_"))
async def trade_cancel_handler(call: CallbackQuery):
    trade_id = int(call.data.replace("trade_cancel_", ""))
    trade = await get_trade(trade_id)
    if not trade or trade["sender_id"] != call.from_user.id:
        return await call.answer("❌ Ошибка", show_alert=True)
    await cancel_trade(trade_id)
    await call.answer("✅ Обмен отменён", show_alert=True)
    await show_trade_menu(call)


# ── Отменить все мои обмены ──
@router.callback_query(F.data == "trade_cancel_mine")
async def trade_cancel_mine(call: CallbackQuery):
    uid = call.from_user.id
    from database import get_db
    db = await get_db()
    await db.execute("UPDATE nft_trades SET status = 'cancelled' WHERE sender_id = ? AND status = 'open'", (uid,))
    await db.commit()
    await call.answer("✅ Все ваши обмены отменены", show_alert=True)
    await show_trade_menu(call)


# ── Купить за клики ──
@router.callback_query(F.data.startswith("trade_buy_"))
async def trade_buy(call: CallbackQuery):
    trade_id = int(call.data.replace("trade_buy_", ""))
    uid = call.from_user.id
    trade = await get_trade(trade_id)
    if not trade or trade["status"] != "open":
        return await call.answer("❌ Не доступен", show_alert=True)
    if trade["sender_id"] == uid:
        return await call.answer("❌ Нельзя купить у себя", show_alert=True)

    want = float(trade["want_clicks"] or 0)
    user = await get_user(uid)
    if float(user["clicks"]) < want:
        return await call.answer("❌ Недостаточно 💢", show_alert=True)

    # Применить обмен напрямую
    await propose_trade(trade_id, uid, [])
    ok = await accept_trade(trade_id)
    if ok:
        await log_activity(uid, "trade", f"Купил обмен #{trade_id} за {want}")
        await create_transaction("trade", uid, user2_id=trade["sender_id"], amount=want,
                                 details=f"Обмен #{trade_id}")
        await call.answer("✅ Обмен завершён!", show_alert=True)
    else:
        await call.answer("❌ Ошибка обмена", show_alert=True)
    await show_trade_menu(call)


# ── Предложить свои НФТ ──
@router.callback_query(F.data.startswith("trade_propose_"))
async def trade_propose_start(call: CallbackQuery):
    trade_id = int(call.data.replace("trade_propose_", ""))
    uid = call.from_user.id
    trade = await get_trade(trade_id)
    if not trade or trade["status"] != "open":
        return await call.answer("❌ Не доступен", show_alert=True)

    _trade_ctx[uid] = {"step": "propose", "nft_ids": [], "trade_id": trade_id}
    nfts = await get_user_nfts(uid)
    if not nfts:
        return await call.answer("❌ У вас нет НФТ", show_alert=True)

    text = (
        "📤 ПРЕДЛОЖИТЬ НФТ В ОБМЕН\n"
        "══════════════════════\n\n"
        "Выберите НФТ для предложения (макс 5):"
    )
    kb = _propose_nfts_kb(nfts, [], trade_id)
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


def _propose_nfts_kb(user_nfts, selected_ids, trade_id):
    kb = []
    for nft in user_nfts:
        un_id = nft[0]
        name = nft[1]
        rarity_name = nft[4] if len(nft) > 4 else "Обычный"
        emoji = _rarity_emoji(rarity_name)
        check = "✅" if un_id in selected_ids else "☐"
        kb.append([InlineKeyboardButton(
            text=f"{check} {emoji} {name}",
            callback_data=f"prop_toggle_{un_id}",
        )])
    kb.append([InlineKeyboardButton(text="📤 Отправить предложение", callback_data=f"prop_send_{trade_id}")])
    kb.append([InlineKeyboardButton(text="❌ Отмена", callback_data="trade_menu")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


@router.callback_query(F.data.startswith("prop_toggle_"))
async def prop_toggle(call: CallbackQuery):
    un_id = int(call.data.replace("prop_toggle_", ""))
    uid = call.from_user.id
    ctx = _trade_ctx.get(uid)
    if not ctx or ctx["step"] != "propose":
        return await call.answer("❌", show_alert=True)

    ids = ctx["nft_ids"]
    if un_id in ids:
        ids.remove(un_id)
    else:
        if len(ids) >= 5:
            return await call.answer("❌ Максимум 5", show_alert=True)
        ids.append(un_id)

    nfts = await get_user_nfts(uid)
    text = (
        "📤 ПРЕДЛОЖИТЬ НФТ В ОБМЕН\n"
        "══════════════════════\n\n"
        f"Выбрано: {len(ids)}/5"
    )
    await call.message.edit_text(text, reply_markup=_propose_nfts_kb(nfts, ids, ctx["trade_id"]))
    await call.answer()


@router.callback_query(F.data.startswith("prop_send_"))
async def prop_send(call: CallbackQuery):
    trade_id = int(call.data.replace("prop_send_", ""))
    uid = call.from_user.id
    ctx = _trade_ctx.get(uid)
    if not ctx or not ctx["nft_ids"]:
        return await call.answer("❌ Выберите НФТ", show_alert=True)

    await propose_trade(trade_id, uid, ctx["nft_ids"])
    _trade_ctx.pop(uid, None)
    await log_activity(uid, "trade", f"Предложил обмен #{trade_id}, {len(ctx['nft_ids'])} НФТ")

    # Уведомить продавца
    trade = await get_trade(trade_id)
    if trade:
        try:
            await call.bot.send_message(
                trade["sender_id"],
                f"📥 Новое предложение обмена #{trade_id}!\nОткройте входящие предложения для просмотра.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📥 Входящие", callback_data="trade_incoming")]
                ]),
            )
        except Exception:
            pass

    await call.answer("✅ Предложение отправлено!", show_alert=True)
    await show_trade_menu(call)


# ── Входящие предложения ──
@router.callback_query(F.data == "trade_incoming")
async def incoming_trades(call: CallbackQuery):
    uid = call.from_user.id
    await set_user_online(uid)
    trades = await get_incoming_trades(uid)
    if not trades:
        text = "📥 ВХОДЯЩИЕ ПРЕДЛОЖЕНИЯ\n══════════════════════\n\nНет входящих предложений."
        await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="trade_menu")]
        ]))
        return await call.answer()

    kb = []
    for t in trades[:10]:
        tid = t[0]
        receiver_id = t[2]
        kb.append([InlineKeyboardButton(
            text=f"📥 #{tid} от ID:{receiver_id}",
            callback_data=f"trade_inc_view_{tid}",
        )])
    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="trade_menu")])
    await call.message.edit_text(
        "📥 ВХОДЯЩИЕ ПРЕДЛОЖЕНИЯ\n══════════════════════\n",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
    )
    await call.answer()


@router.callback_query(F.data.startswith("trade_inc_view_"))
async def trade_inc_view(call: CallbackQuery):
    trade_id = int(call.data.replace("trade_inc_view_", ""))
    trade = await get_trade(trade_id)
    if not trade:
        return await call.answer("❌ Не найден", show_alert=True)

    offer = await get_trade_items(trade_id, 'offer')
    propose = await get_trade_items(trade_id, 'propose')

    lines = ["📥 ПРЕДЛОЖЕНИЕ ОБМЕНА\n══════════════════════\n"]
    lines.append("📤 Ваши НФТ (отдаёте):")
    for item in offer:
        un_id, name, rn, income = item
        emoji = _rarity_emoji(rn)
        lines.append(f"  {emoji} {name}")

    lines.append("\n📥 Получаете:")
    if propose:
        for item in propose:
            un_id, name, rn, income = item
            emoji = _rarity_emoji(rn)
            lines.append(f"  {emoji} {name}")
    want = float(trade["want_clicks"] or 0)
    if want > 0:
        lines.append(f"  💰 {fnum(want)} 💢")

    lines.append("\n══════════════════════")

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Принять", callback_data=f"trade_accept_{trade_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"trade_reject_{trade_id}"),
        ],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="trade_incoming")],
    ])
    await call.message.edit_text("\n".join(lines), reply_markup=kb)
    await call.answer()


@router.callback_query(F.data.startswith("trade_accept_"))
async def trade_accept_handler(call: CallbackQuery):
    trade_id = int(call.data.replace("trade_accept_", ""))
    ok = await accept_trade(trade_id)
    if ok:
        trade = await get_trade(trade_id)
        await log_activity(call.from_user.id, "trade", f"Принял обмен #{trade_id}")
        await create_transaction("trade", call.from_user.id,
                                 user2_id=trade["receiver_id"] if trade else None,
                                 amount=0, details=f"Принят обмен #{trade_id}")
        await call.answer("✅ Обмен принят!", show_alert=True)
        # Уведомить предлагавшего
        if trade and trade["receiver_id"]:
            try:
                await call.bot.send_message(trade["receiver_id"], f"✅ Ваш обмен #{trade_id} принят!")
            except Exception:
                pass
    else:
        await call.answer("❌ Ошибка обмена", show_alert=True)
    await incoming_trades(call)


@router.callback_query(F.data.startswith("trade_reject_"))
async def trade_reject_handler(call: CallbackQuery):
    trade_id = int(call.data.replace("trade_reject_", ""))
    await reject_trade(trade_id)
    await log_activity(call.from_user.id, "trade", f"Отклонил обмен #{trade_id}")
    await call.answer("✅ Обмен отклонён", show_alert=True)
    await incoming_trades(call)

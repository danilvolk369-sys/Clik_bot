# ======================================================
# HISTORY — Поддержка, История транзакций (чеки) + Жалобы
# ======================================================
import math

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from states import ComplaintStates, SupportStates
from database import (
    get_user_transactions, count_user_transactions,
    get_transaction,
    create_complaint, get_user_complaints,
    get_complaint,
    count_pending_complaints, get_pending_complaints,
    resolve_complaint,
    set_user_online,
    create_ticket, get_user_tickets,
)
from keyboards import (
    history_menu_kb, history_list_kb, check_detail_kb,
    my_complaints_kb, support_menu_kb, back_support_kb,
)
from handlers.common import fnum
from banners_util import send_msg, safe_edit

router = Router()

PER_PAGE = 5


# ══════════════════════════════════════════
#  ПОДДЕРЖКА — главное меню
# ══════════════════════════════════════════

@router.callback_query(F.data == "support_menu")
async def support_menu(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await set_user_online(call.from_user.id)
    await send_msg(
        call,
        "⚠️ ПОДДЕРЖКА\n══════════════════════\n\n"
        "Здесь вы можете:\n"
        "• 🚩 Подать жалобу\n"
        "• 🐛 Сообщить о проблеме/баге\n"
        "• 📨 Посмотреть свои обращения\n"
        "• 📋 Просмотреть историю / чеки\n"
        "══════════════════════",
        reply_markup=support_menu_kb(),
    )
    await call.answer()


# ── Жалоба (тикет) ──
@router.callback_query(F.data == "support_complaint")
async def support_complaint_start(call: CallbackQuery, state: FSMContext):
    await state.set_state(SupportStates.waiting_complaint)
    await call.message.edit_text(
        "🚩 ЖАЛОБА\n══════════════════════\n\n"
        "Опишите вашу жалобу (максимум 500 символов).\n"
        "Укажите ID игрока или ситуацию:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="support_menu")]
        ]),
    )
    await call.answer()


@router.message(SupportStates.waiting_complaint)
async def support_complaint_msg(message: Message, state: FSMContext):
    text = message.text
    if not text or len(text.strip()) < 5:
        return await message.answer(
            "❌ Слишком короткое сообщение. Минимум 5 символов.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отмена", callback_data="support_menu")]
            ]),
        )
    await state.clear()
    await create_ticket(message.from_user.id, "complaint", text.strip()[:500])
    await message.answer(
        "✅ Жалоба отправлена!\n\n"
        "Администрация рассмотрит её в ближайшее время.",
        reply_markup=back_support_kb(),
    )


# ── Проблема / Баг (тикет) ──
@router.callback_query(F.data == "support_problem")
async def support_problem_start(call: CallbackQuery, state: FSMContext):
    await state.set_state(SupportStates.waiting_problem)
    await call.message.edit_text(
        "🐛 ПРОБЛЕМА / БАГ\n══════════════════════\n\n"
        "Опишите проблему или баг (максимум 500 символов).\n"
        "Укажите что именно не работает:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="support_menu")]
        ]),
    )
    await call.answer()


@router.message(SupportStates.waiting_problem)
async def support_problem_msg(message: Message, state: FSMContext):
    text = message.text
    if not text or len(text.strip()) < 5:
        return await message.answer(
            "❌ Слишком короткое сообщение. Минимум 5 символов.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отмена", callback_data="support_menu")]
            ]),
        )
    await state.clear()
    await create_ticket(message.from_user.id, "problem", text.strip()[:500])
    await message.answer(
        "✅ Обращение отправлено!\n\n"
        "Администрация ответит вам в ближайшее время.",
        reply_markup=back_support_kb(),
    )


# ── Мои обращения (тикеты пользователя) ──
@router.callback_query(F.data == "support_my_tickets")
async def support_my_tickets(call: CallbackQuery, state: FSMContext):
    await state.clear()
    uid = call.from_user.id
    tickets = await get_user_tickets(uid)

    if not tickets:
        text = (
            "📨 МОИ ОБРАЩЕНИЯ\n══════════════════════\n\n"
            "У вас нет обращений."
        )
        await call.message.edit_text(text, reply_markup=back_support_kb())
        return await call.answer()

    text = f"📨 МОИ ОБРАЩЕНИЯ ({len(tickets)})\n══════════════════════\n\n"
    status_map = {"open": "🟡 Открыт", "closed": "✅ Закрыт"}
    type_map = {"complaint": "🚩 Жалоба", "problem": "🐛 Проблема"}
    for t in tickets[:20]:  # max 20
        tid = t[0]
        ttype = type_map.get(t[1], t[1])
        status = status_map.get(t[3], t[3])
        date = t[4][:10] if t[4] else "—"
        text += f"#{tid} {ttype} — {status} ({date})\n"

    text += "\n══════════════════════"
    await call.message.edit_text(text, reply_markup=back_support_kb())
    await call.answer()


# ══════════════════════════════════════════
#  ИСТОРИЯ ТРАНЗАКЦИЙ
# ══════════════════════════════════════════

_TX_LABELS = {
    "pvp": "⚔️ PvP",
    "trade": "🔄 Обмен",
    "nft_buy": "🛒 Покупка НФТ",
    "nft_sell": "💰 Продажа НФТ",
    "shop": "🔧 Магазин",
    "event": "🎉 Ивент",
    "gift": "🎁 Подарок",
    "market_buy": "🏪 Рынок (покупка)",
    "market_sell": "🏪 Рынок (продажа)",
    "chat": "💬 Чат",
}


# ── Меню истории ──
@router.callback_query(F.data == "history_menu")
async def history_menu(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await set_user_online(call.from_user.id)
    await call.message.edit_text(
        "📋 ИСТОРИЯ / ЧЕКИ\n══════════════════════\n\n"
        "Выберите категорию транзакций:",
        reply_markup=history_menu_kb(),
    )
    await call.answer()


# ── Список транзакций ──
@router.callback_query(F.data.startswith("hist:"))
async def history_list(call: CallbackQuery):
    parts = call.data.split(":")
    if len(parts) < 3:
        return await call.answer()
    tx_filter = parts[1]  # all, pvp, trade, nft_buy, nft_sell, shop, event
    page = int(parts[2])
    uid = call.from_user.id

    total = await count_user_transactions(uid, tx_filter if tx_filter != "all" else None)
    total_pages = max(1, math.ceil(total / PER_PAGE))
    items = await get_user_transactions(uid, tx_filter if tx_filter != "all" else None, page, PER_PAGE)

    if not items:
        text = "📋 Транзакций не найдено."
    else:
        text = f"📋 ЧЕКИ — {tx_filter.upper()}\n══════════════════════\n"

    await call.message.edit_text(text, reply_markup=history_list_kb(items, page, total_pages, tx_filter))
    await call.answer()


# ── Деталь чека ──
@router.callback_query(F.data.startswith("check:"))
async def check_detail(call: CallbackQuery):
    tx_id = int(call.data.split(":")[1])
    tx = await get_transaction(tx_id)
    if not tx:
        return await call.answer("❌ Не найден", show_alert=True)

    tx_type = tx["type"]
    label = _TX_LABELS.get(tx_type, f"📋 {tx_type}")
    user2 = tx["user2_id"]
    amount = tx["amount"]
    details = tx["details"] or "—"
    created = tx["created_at"][:16] if tx["created_at"] else "—"

    text = (
        f"📋 ЧЕК #{tx_id}\n══════════════════════\n\n"
        f"Тип: {label}\n"
        f"Сумма: {fnum(amount)} 💢\n"
    )
    if user2:
        text += f"Участник 2: {user2}\n"
    text += (
        f"Детали: {details}\n"
        f"Дата: {created}\n"
        f"══════════════════════"
    )

    # Можно пожаловаться если это PvP, trade, nft_buy, market операция
    can_complain = tx_type in ("pvp", "trade", "nft_buy", "market_buy", "event")
    await call.message.edit_text(text, reply_markup=check_detail_kb(tx_id, can_complain))
    await call.answer()


# ══════════════════════════════════════════
#  ЖАЛОБЫ (пользователь)
# ══════════════════════════════════════════

# ── Подать жалобу на чек ──
@router.callback_query(F.data.startswith("complain:"))
async def complain_start(call: CallbackQuery, state: FSMContext):
    tx_id = int(call.data.split(":")[1])
    tx = await get_transaction(tx_id)
    if not tx:
        return await call.answer("❌", show_alert=True)

    await state.set_state(ComplaintStates.waiting_reason)
    await state.update_data(complaint_tx_id=tx_id)
    await call.message.edit_text(
        f"⚠️ ЖАЛОБА на чек #{tx_id}\n══════════════════════\n\n"
        "Опишите причину жалобы (максимум 500 символов):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data=f"check:{tx_id}")]
        ]),
    )
    await call.answer()


@router.message(ComplaintStates.waiting_reason)
async def complain_reason(message: Message, state: FSMContext):
    data = await state.get_data()
    tx_id = data.get("complaint_tx_id")
    if not tx_id:
        await state.clear()
        return

    reason = message.text.strip()[:500]
    await state.clear()

    await create_complaint(tx_id, message.from_user.id, reason)

    await message.answer(
        f"✅ Жалоба на чек #{tx_id} подана!\n\n"
        "Администрация рассмотрит вашу жалобу.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 К чекам", callback_data="hist:all:0")],
            [InlineKeyboardButton(text="📨 Мои жалобы", callback_data="my_complaints:0")],
            [InlineKeyboardButton(text="⬅️ Поддержка", callback_data="support_menu")],
        ]),
    )


# ── Мои жалобы ──
@router.callback_query(F.data.startswith("my_complaints:"))
async def my_complaints_list(call: CallbackQuery):
    page = int(call.data.split(":")[1])
    uid = call.from_user.id

    complaints = await get_user_complaints(uid, page, PER_PAGE)
    # Для подсчёта total нам нужна отдельная функция; прикинем
    from database import get_db
    db = await get_db()
    cur = await db.execute("SELECT COUNT(*) FROM complaints WHERE user_id = ?", (uid,))
    total = (await cur.fetchone())[0]
    total_pages = max(1, math.ceil(total / PER_PAGE))

    text = f"📨 МОИ ЖАЛОБЫ ({total})\n══════════════════════\n"
    if not complaints:
        text += "\nНет жалоб."

    await call.message.edit_text(text, reply_markup=my_complaints_kb(complaints, page, total_pages))
    await call.answer()


@router.callback_query(F.data.startswith("my_compl:"))
async def my_complaint_detail(call: CallbackQuery):
    c_id = int(call.data.split(":")[1])
    c = await get_complaint(c_id)
    if not c:
        return await call.answer("❌", show_alert=True)

    status_labels = {
        "pending": "🟡 На рассмотрении",
        "reviewing": "🔵 Рассматривается",
        "resolved": "✅ Решена",
    }
    status = status_labels.get(c["status"], c["status"])
    action_labels = {
        "refund": "💸 Возврат средств",
        "warn": "⚠️ Предупреждение",
        "ban": "🔨 Бан нарушителя",
        "reject": "❌ Отклонена",
    }
    admin_action = action_labels.get(c["admin_action"], c["admin_action"] or "—")
    admin_comment = c["admin_comment"] or "—"

    text = (
        f"📨 ЖАЛОБА #{c_id}\n══════════════════════\n\n"
        f"Чек: #{c['transaction_id']}\n"
        f"Причина: {c['reason']}\n\n"
        f"Статус: {status}\n"
    )
    if c["status"] == "resolved":
        text += (
            f"Решение: {admin_action}\n"
            f"Комментарий: {admin_comment}\n"
        )
    text += f"\nДата: {c['created_at'][:16]}\n══════════════════════"

    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ К жалобам", callback_data="my_complaints:0")],
        [InlineKeyboardButton(text="⬅️ Поддержка", callback_data="support_menu")],
    ]))
    await call.answer()

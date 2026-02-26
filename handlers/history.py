# ======================================================
# HISTORY — Чеки, история транзакций, жалобы
# ======================================================

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from config import OWNER_ID
from states import ComplaintStates
from handlers.common import fnum
from database import (
    get_user, is_admin,
    get_user_transactions, count_user_transactions,
    get_transaction, get_all_transactions, count_all_transactions,
    create_complaint, get_complaint, get_pending_complaints,
    count_pending_complaints, resolve_complaint,
    get_user_complaints, get_complaint_by_tx,
    ban_user, update_clicks, log_admin_action,
)
from keyboards import (
    history_menu_kb, history_list_kb, check_detail_kb,
    complaints_list_kb, complaint_action_kb,
    my_complaints_kb, adm_check_action_kb,
    back_menu_kb,
)

router = Router()

# ─── Константы оформления ──────────────────────────────
_TX_LABELS = {
    "pvp":         "⚔️ PvP Бой",
    "trade":       "🔄 Обмен НФТ",
    "chat":        "💬 Анонимный чат",
    "nft_buy":     "🛒 Покупка НФТ",
    "nft_sell":    "💰 Продажа НФТ",
    "market_buy":  "🏪 Покупка (площадка)",
    "market_sell": "🏪 Продажа (площадка)",
    "shop":        "🔧 Магазин",
    "event":       "🎉 Ивент",
    "gift":        "🎁 Подарок",
}

_TX_ICON = {
    "pvp": "⚔️", "trade": "🔄", "chat": "💬",
    "nft_buy": "🛒", "nft_sell": "💰", "shop": "🔧",
    "event": "🎉", "gift": "🎁",
    "market_buy": "🏪", "market_sell": "🏪",
}

_COMPL_ACTION_LABELS = {
    "refund": "💸 Возврат средств",
    "ban":    "🔨 Бан нарушителя",
    "warn":   "⚠️ Предупреждение",
    "reject": "❌ Отклонено",
}


# ═══════════════════════════════════════════════════════
#  📋 ИСТОРИЯ — ГЛАВНОЕ МЕНЮ
# ═══════════════════════════════════════════════════════
@router.callback_query(F.data == "history_menu")
async def show_history_menu(call: CallbackQuery, state: FSMContext):
    if state:
        await state.clear()
    uid = call.from_user.id
    total = await count_user_transactions(uid)
    text = (
        "📋 ИСТОРИЯ ТРАНЗАКЦИЙ\n"
        "══════════════════════\n\n"
        "🧾 Каждая ваша операция записывается\n"
        "в виде чека с уникальным номером.\n\n"
        f"📊 Всего чеков: {total}\n\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        "Выберите категорию:"
    )
    try:
        await call.message.edit_text(text, reply_markup=history_menu_kb())
    except Exception:
        await call.message.answer(text, reply_markup=history_menu_kb())
    await call.answer()


# ═══════════════════════════════════════════════════════
#  📋 СПИСОК ЧЕКОВ (с фильтрацией и пагинацией)
# ═══════════════════════════════════════════════════════
@router.callback_query(F.data.startswith("hist:"))
async def show_history_list(call: CallbackQuery):
    uid = call.from_user.id
    parts = call.data.split(":")
    tx_filter = parts[1]
    page = int(parts[2]) if len(parts) > 2 else 0
    per_page = 6

    f_type = None if tx_filter == "all" else tx_filter
    total = await count_user_transactions(uid, f_type)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(0, min(page, total_pages - 1))

    items = await get_user_transactions(uid, f_type, limit=per_page, offset=page * per_page)

    filter_name = _TX_LABELS.get(tx_filter, "📋 Все")
    if tx_filter == "all":
        filter_name = "📋 Все"

    if not items:
        text = (
            f"📋 ИСТОРИЯ — {filter_name}\n"
            "══════════════════════\n\n"
            "😔 Нет записей в этой категории.\n\n"
            "══════════════════════"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔍 Фильтры", callback_data="history_menu")],
            [InlineKeyboardButton(text="⬅️ В меню", callback_data="menu")],
        ])
        await call.message.edit_text(text, reply_markup=kb)
        return await call.answer()

    text = (
        f"📋 ИСТОРИЯ — {filter_name}\n"
        "══════════════════════\n\n"
        f"📊 Записей: {total} ∙ Стр. {page + 1}/{total_pages}\n\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        "🧾 Нажмите на чек для подробностей:\n"
    )
    await call.message.edit_text(
        text,
        reply_markup=history_list_kb(items, page, total_pages, tx_filter),
    )
    await call.answer()


# ═══════════════════════════════════════════════════════
#  🧾 ДЕТАЛИ ЧЕКА
# ═══════════════════════════════════════════════════════
def _format_check(tx, is_adm: bool = False) -> str:
    """Красивый формат чека."""
    tx_id = tx["id"]
    tx_type = tx["type"]
    user_id = tx["user_id"]
    user2_id = tx["user2_id"]
    amount = tx["amount"]
    details = tx["details"] or "—"
    ref_id = tx["ref_id"]
    status = tx["status"]
    dt = tx["created_at"] or ""

    icon = _TX_ICON.get(tx_type, "📋")
    label = _TX_LABELS.get(tx_type, tx_type)
    status_icon = {"completed": "✅", "pending": "🟡", "failed": "❌"}.get(status, "⚪")

    # Форматируем дату
    date_str = dt[:16].replace("T", " ") if dt else "—"

    lines = [
        "┏━━━━━━━━━━━━━━━━━━━━━━━━┓",
        f"┃  {icon} ЧЕК #{tx_id}",
        "┣━━━━━━━━━━━━━━━━━━━━━━━━┫",
        f"┃ 📂 Тип: {label}",
        f"┃ {status_icon} Статус: {status}",
        f"┃ 📅 Дата: {date_str}",
    ]

    if amount:
        lines.append(f"┃ 💰 Сумма: {fnum(amount)} 💢")

    lines.append(f"┃ 👤 Игрок 1: {user_id}")

    if user2_id:
        lines.append(f"┃ 👥 Игрок 2: {user2_id}")

    if ref_id:
        ref_label = {
            "pvp": "🎮 Игра", "trade": "🔄 Обмен", "chat": "💬 Чат",
            "event": "🎉 Ивент",
        }.get(tx_type, "🔗 Ссылка")
        lines.append(f"┃ {ref_label}: #{ref_id}")

    lines.append("┣━━━━━━━━━━━━━━━━━━━━━━━━┫")
    lines.append(f"┃ 📝 {details}")
    lines.append("┗━━━━━━━━━━━━━━━━━━━━━━━━┛")

    return "\n".join(lines)


@router.callback_query(F.data.startswith("check:"))
async def show_check_detail(call: CallbackQuery):
    tx_id = int(call.data.split(":")[1])
    tx = await get_transaction(tx_id)
    if not tx:
        return await call.answer("❌ Чек не найден!", show_alert=True)

    uid = call.from_user.id
    is_adm = uid == OWNER_ID or await is_admin(uid)

    # Проверяем, может ли жаловаться (свой чек + нет жалобы)
    can_complain = (tx["user_id"] == uid or tx["user2_id"] == uid)
    if can_complain:
        existing = await get_complaint_by_tx(tx_id, uid)
        if existing:
            can_complain = False

    text = _format_check(tx, is_adm)

    await call.message.edit_text(
        text,
        reply_markup=check_detail_kb(tx_id, can_complain, is_adm),
    )
    await call.answer()


# ═══════════════════════════════════════════════════════
#  ⚠️ ПОДАТЬ ЖАЛОБУ
# ═══════════════════════════════════════════════════════
@router.callback_query(F.data.startswith("complain:"))
async def start_complaint(call: CallbackQuery, state: FSMContext):
    tx_id = int(call.data.split(":")[1])
    tx = await get_transaction(tx_id)
    if not tx:
        return await call.answer("❌ Чек не найден!", show_alert=True)

    uid = call.from_user.id
    if tx["user_id"] != uid and tx["user2_id"] != uid:
        return await call.answer("❌ Это не ваш чек!", show_alert=True)

    existing = await get_complaint_by_tx(tx_id, uid)
    if existing:
        return await call.answer("❌ Вы уже подавали жалобу на этот чек!", show_alert=True)

    await state.set_state(ComplaintStates.waiting_reason)
    await state.update_data(complaint_tx_id=tx_id)

    icon = _TX_ICON.get(tx["type"], "📋")
    text = (
        f"⚠️ ЖАЛОБА НА ЧЕК #{tx_id}\n"
        "══════════════════════\n\n"
        f"{icon} Тип: {_TX_LABELS.get(tx['type'], tx['type'])}\n"
        f"💰 Сумма: {fnum(tx['amount'])} 💢\n\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        "📝 Опишите проблему:\n\n"
        "• Что произошло?\n"
        "• Что не так?\n"
        "• Требуется возврат?\n\n"
        "✏️ Напишите причину жалобы:"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"check:{tx_id}")],
    ])
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


@router.message(ComplaintStates.waiting_reason)
async def process_complaint_reason(message: Message, state: FSMContext):
    reason = (message.text or "").strip()
    if not reason or len(reason) < 5:
        return await message.answer(
            "❌ Опишите причину подробнее (минимум 5 символов):"
        )

    data = await state.get_data()
    tx_id = data.get("complaint_tx_id")
    if not tx_id:
        await state.clear()
        return await message.answer("❌ Ошибка. Попробуйте заново.")

    uid = message.from_user.id
    c_id = await create_complaint(tx_id, uid, reason)
    await state.clear()

    text = (
        "✅ ЖАЛОБА ОТПРАВЛЕНА\n"
        "══════════════════════\n\n"
        f"📋 Жалоба #{c_id}\n"
        f"🧾 На чек #{tx_id}\n\n"
        f"📝 Причина:\n{reason}\n\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        "🟡 Статус: На рассмотрении\n\n"
        "Администрация рассмотрит вашу\n"
        "жалобу и примет решение."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Мои жалобы", callback_data="my_complaints:0")],
        [InlineKeyboardButton(text="⬅️ В меню", callback_data="menu")],
    ])
    await message.answer(text, reply_markup=kb)

    # Уведомляем админов через бот
    try:
        tx = await get_transaction(tx_id)
        notify_text = (
            "🚨 НОВАЯ ЖАЛОБА\n"
            "══════════════════════\n\n"
            f"📋 Жалоба #{c_id}\n"
            f"👤 От: {uid}\n"
            f"🧾 Чек #{tx_id} ({_TX_LABELS.get(tx['type'], tx['type'])})\n"
            f"📝 {reason[:100]}\n\n"
            "Откройте панель → Жалобы на чеки"
        )
        await message.bot.send_message(OWNER_ID, notify_text)
    except Exception:
        pass


# ═══════════════════════════════════════════════════════
#  📨 МОИ ЖАЛОБЫ (пользователь)
# ═══════════════════════════════════════════════════════
@router.callback_query(F.data.startswith("my_complaints:"))
async def show_my_complaints(call: CallbackQuery):
    uid = call.from_user.id
    page = int(call.data.split(":")[1])
    per_page = 5

    complaints = await get_user_complaints(uid, limit=50)
    total = len(complaints)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(0, min(page, total_pages - 1))
    page_items = complaints[page * per_page:(page + 1) * per_page]

    if not complaints:
        text = (
            "📨 МОИ ЖАЛОБЫ\n"
            "══════════════════════\n\n"
            "😊 У вас нет поданных жалоб.\n\n"
            "══════════════════════"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 История", callback_data="history_menu")],
            [InlineKeyboardButton(text="⬅️ В меню", callback_data="menu")],
        ])
        await call.message.edit_text(text, reply_markup=kb)
        return await call.answer()

    text = (
        "📨 МОИ ЖАЛОБЫ\n"
        "══════════════════════\n\n"
        f"📊 Всего: {total}\n\n"
        "Нажмите на жалобу для подробностей:\n"
    )
    await call.message.edit_text(
        text,
        reply_markup=my_complaints_kb(page_items, page, total_pages),
    )
    await call.answer()


@router.callback_query(F.data.startswith("my_compl:"))
async def show_my_complaint_detail(call: CallbackQuery):
    c_id = int(call.data.split(":")[1])
    c = await get_complaint(c_id)
    if not c:
        return await call.answer("❌ Жалоба не найдена!", show_alert=True)

    uid = call.from_user.id
    if c["user_id"] != uid:
        return await call.answer("❌ Это не ваша жалоба!", show_alert=True)

    tx = await get_transaction(c["transaction_id"])

    status_map = {
        "pending": "🟡 На рассмотрении",
        "reviewing": "🔵 Рассматривается",
        "resolved": "✅ Решено",
    }
    status_text = status_map.get(c["status"], c["status"])

    action_text = ""
    if c["admin_action"]:
        action_text = f"\n🛡 Решение: {_COMPL_ACTION_LABELS.get(c['admin_action'], c['admin_action'])}"
    if c["admin_comment"]:
        action_text += f"\n💬 Комментарий: {c['admin_comment']}"

    tx_info = ""
    if tx:
        icon = _TX_ICON.get(tx["type"], "📋")
        tx_info = (
            f"\n\n{icon} Чек #{tx['id']}: {_TX_LABELS.get(tx['type'], tx['type'])}\n"
            f"💰 Сумма: {fnum(tx['amount'])} 💢"
        )

    text = (
        f"📨 ЖАЛОБА #{c_id}\n"
        "══════════════════════\n\n"
        f"{status_text}\n"
        f"📅 Подана: {str(c['created_at'])[:16].replace('T', ' ')}\n"
        f"\n📝 Причина:\n{c['reason']}"
        f"{action_text}"
        f"{tx_info}\n\n"
        "══════════════════════"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧾 Открыть чек", callback_data=f"check:{c['transaction_id']}")],
        [InlineKeyboardButton(text="⬅️ Мои жалобы", callback_data="my_complaints:0")],
    ])
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


# ═══════════════════════════════════════════════════════
#  🛡 АДМИН — СПИСОК ЖАЛОБ
# ═══════════════════════════════════════════════════════
async def _check_is_admin(uid: int) -> bool:
    return uid == OWNER_ID or await is_admin(uid)


@router.callback_query(F.data.startswith("compl_pg:"))
async def admin_complaints_list(call: CallbackQuery):
    uid = call.from_user.id
    if not await _check_is_admin(uid):
        return await call.answer("❌ Нет доступа!", show_alert=True)

    page = int(call.data.split(":")[1])
    per_page = 6

    complaints = await get_pending_complaints(limit=50)
    total = len(complaints)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(0, min(page, total_pages - 1))
    page_items = complaints[page * per_page:(page + 1) * per_page]

    pending_cnt = await count_pending_complaints()

    if not complaints:
        text = (
            "📨 ЖАЛОБЫ НА ЧЕКИ\n"
            "══════════════════════\n\n"
            "✅ Нет активных жалоб!\n\n"
            "══════════════════════"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Панель", callback_data="admin_panel")],
        ])
        await call.message.edit_text(text, reply_markup=kb)
        return await call.answer()

    text = (
        "📨 ЖАЛОБЫ НА ЧЕКИ\n"
        "══════════════════════\n\n"
        f"🟡 Ожидают: {pending_cnt}\n"
        f"📊 Всего: {total} ∙ Стр {page + 1}/{total_pages}\n\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
    )
    await call.message.edit_text(
        text,
        reply_markup=complaints_list_kb(page_items, page, total_pages),
    )
    await call.answer()


# ═══════════════════════════════════════════════════════
#  🛡 АДМИН — ПРОСМОТР ЖАЛОБЫ
# ═══════════════════════════════════════════════════════
@router.callback_query(F.data.startswith("compl_view:"))
async def admin_complaint_view(call: CallbackQuery):
    uid = call.from_user.id
    if not await _check_is_admin(uid):
        return await call.answer("❌ Нет доступа!", show_alert=True)

    c_id = int(call.data.split(":")[1])
    c = await get_complaint(c_id)
    if not c:
        return await call.answer("❌ Жалоба не найдена!", show_alert=True)

    tx = await get_transaction(c["transaction_id"])

    # Формируем детальный вид
    tx_block = ""
    if tx:
        tx_block = _format_check(tx, is_adm=True)

    status_m = {
        "pending": "🟡 Ожидает", "reviewing": "🔵 В процессе", "resolved": "✅ Решено",
    }

    text = (
        f"🔍 ЖАЛОБА #{c_id}\n"
        "══════════════════════\n\n"
        f"👤 Автор: {c['user_id']}\n"
        f"📅 Подана: {str(c['created_at'])[:16].replace('T', ' ')}\n"
        f"🔖 Статус: {status_m.get(c['status'], c['status'])}\n\n"
        f"📝 Причина:\n{c['reason']}\n\n"
        "┈┈┈ ДОКАЗАТЕЛЬСТВО (ЧЕК) ┈┈┈\n\n"
        f"{tx_block}\n\n"
        "══════════════════════\n"
        "Выберите действие:"
    )
    await call.message.edit_text(
        text,
        reply_markup=complaint_action_kb(c_id),
    )
    await call.answer()


# ═══════════════════════════════════════════════════════
#  🛡 АДМИН — ПРОСМОТР ЧЕКА (доказательство из жалобы)
# ═══════════════════════════════════════════════════════
@router.callback_query(F.data.startswith("compl_check:"))
async def admin_complaint_check_evidence(call: CallbackQuery):
    uid = call.from_user.id
    if not await _check_is_admin(uid):
        return await call.answer("❌ Нет доступа!", show_alert=True)

    c_id = int(call.data.split(":")[1])
    c = await get_complaint(c_id)
    if not c:
        return await call.answer("❌ Жалоба не найдена!", show_alert=True)

    tx = await get_transaction(c["transaction_id"])
    if not tx:
        return await call.answer("❌ Чек не найден!", show_alert=True)

    text = _format_check(tx, is_adm=True)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ К жалобе", callback_data=f"compl_view:{c_id}")],
    ])
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


# ═══════════════════════════════════════════════════════
#  🛡 АДМИН — ДЕЙСТВИЕ ПО ЖАЛОБЕ
# ═══════════════════════════════════════════════════════
@router.callback_query(F.data.startswith("compl_act:"))
async def admin_complaint_action(call: CallbackQuery, state: FSMContext):
    uid = call.from_user.id
    if not await _check_is_admin(uid):
        return await call.answer("❌ Нет доступа!", show_alert=True)

    parts = call.data.split(":")
    c_id = int(parts[1])
    action = parts[2]

    c = await get_complaint(c_id)
    if not c:
        return await call.answer("❌ Жалоба не найдена!", show_alert=True)

    tx = await get_transaction(c["transaction_id"])

    action_labels = {
        "refund": "💸 ВОЗВРАТ", "ban": "🔨 БАН",
        "warn": "⚠️ ПРЕДУПРЕЖДЕНИЕ", "reject": "❌ ОТКЛОНЕНИЕ",
    }
    action_label = action_labels.get(action, action)

    # Выполняем действие
    if action == "refund" and tx:
        # Возвращаем сумму пострадавшему
        victim_id = c["user_id"]
        amount = float(tx["amount"] or 0)
        if amount > 0:
            await update_clicks(victim_id, amount)

    elif action == "ban" and tx:
        # Баним второго участника (нарушителя)
        victim_id = c["user_id"]
        offender_id = tx["user2_id"] if tx["user_id"] == victim_id else tx["user_id"]
        if offender_id:
            await ban_user(offender_id, days=7)

    # Разрешаем жалобу
    await resolve_complaint(c_id, uid, action, f"Действие: {action_label}")
    await log_admin_action(uid, f"complaint_{action}", c["user_id"],
                           f"Жалоба #{c_id}, Чек #{c['transaction_id']}")

    # Уведомляем пользователя
    try:
        notify = (
            f"📨 Ваша жалоба #{c_id} рассмотрена!\n\n"
            f"🛡 Решение: {action_label}\n"
            f"🧾 Чек #{c['transaction_id']}\n\n"
        )
        if action == "refund":
            notify += f"💸 Вам возвращено: {fnum(tx['amount'])} 💢"
        elif action == "ban":
            notify += "🔨 Нарушитель забанен на 7 дней"
        elif action == "warn":
            notify += "⚠️ Нарушитель предупреждён"
        elif action == "reject":
            notify += "Жалоба не подтверждена"

        await call.bot.send_message(c["user_id"], notify)
    except Exception:
        pass

    text = (
        f"✅ ЖАЛОБА #{c_id} — РЕШЕНО\n"
        "══════════════════════\n\n"
        f"🛡 Действие: {action_label}\n"
        f"👤 Автор жалобы: {c['user_id']}\n"
        f"🧾 Чек: #{c['transaction_id']}\n\n"
        "══════════════════════"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📨 К жалобам", callback_data="compl_pg:0")],
        [InlineKeyboardButton(text="⬅️ Панель", callback_data="admin_panel")],
    ])
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


# ═══════════════════════════════════════════════════════
#  🛡 АДМИН — ДЕЙСТВИЯ ИЗ ЧЕКА
# ═══════════════════════════════════════════════════════
@router.callback_query(F.data.startswith("adm_check:"))
async def admin_check_actions(call: CallbackQuery):
    uid = call.from_user.id
    if not await _check_is_admin(uid):
        return await call.answer("❌ Нет доступа!", show_alert=True)

    tx_id = int(call.data.split(":")[1])
    tx = await get_transaction(tx_id)
    if not tx:
        return await call.answer("❌ Чек не найден!", show_alert=True)

    text = (
        f"🛡 АДМИН-ДЕЙСТВИЯ — ЧЕК #{tx_id}\n"
        "══════════════════════\n\n"
        f"👤 Игрок 1: {tx['user_id']}\n"
        f"👥 Игрок 2: {tx['user2_id'] or '—'}\n"
        f"💰 Сумма: {fnum(tx['amount'])} 💢\n\n"
        "Выберите действие:"
    )
    await call.message.edit_text(text, reply_markup=adm_check_action_kb(tx_id))
    await call.answer()


@router.callback_query(F.data.startswith("adm_tx_u1:"))
async def admin_tx_user1_info(call: CallbackQuery):
    uid = call.from_user.id
    if not await _check_is_admin(uid):
        return await call.answer("❌ Нет доступа!", show_alert=True)

    tx_id = int(call.data.split(":")[1])
    tx = await get_transaction(tx_id)
    if not tx:
        return await call.answer("❌ Чек не найден!", show_alert=True)

    u = await get_user(tx["user_id"])
    text = _format_user_info(u, tx["user_id"]) if u else f"❌ Пользователь {tx['user_id']} не найден"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ К действиям", callback_data=f"adm_check:{tx_id}")],
    ])
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


@router.callback_query(F.data.startswith("adm_tx_u2:"))
async def admin_tx_user2_info(call: CallbackQuery):
    uid = call.from_user.id
    if not await _check_is_admin(uid):
        return await call.answer("❌ Нет доступа!", show_alert=True)

    tx_id = int(call.data.split(":")[1])
    tx = await get_transaction(tx_id)
    if not tx or not tx["user2_id"]:
        return await call.answer("❌ Второй игрок не указан!", show_alert=True)

    u = await get_user(tx["user2_id"])
    text = _format_user_info(u, tx["user2_id"]) if u else f"❌ Пользователь {tx['user2_id']} не найден"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ К действиям", callback_data=f"adm_check:{tx_id}")],
    ])
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


def _format_user_info(u, uid) -> str:
    """Форматирование информации о пользователе для админа."""
    return (
        f"👤 ИНФО ИГРОКА\n"
        "══════════════════════\n\n"
        f"🆔 ID: {uid}\n"
        f"📛 Имя: @{u['username'] or '—'}\n"
        f"💰 Клики: {fnum(u['clicks'])}\n"
        f"📊 Всего: {fnum(u['total_clicks'])}\n"
        f"🏅 Ранг: {u['rank']}\n"
        f"🔨 Бан: {'Да' if u['is_banned'] else 'Нет'}\n\n"
        "══════════════════════"
    )


@router.callback_query(F.data.startswith("adm_tx_ban:"))
async def admin_tx_ban(call: CallbackQuery):
    uid = call.from_user.id
    if not await _check_is_admin(uid):
        return await call.answer("❌ Нет доступа!", show_alert=True)

    tx_id = int(call.data.split(":")[1])
    tx = await get_transaction(tx_id)
    if not tx:
        return await call.answer("❌ Чек не найден!", show_alert=True)

    # Баним обоих участников — выбор кого банить
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    rows = []
    rows.append([InlineKeyboardButton(
        text=f"🔨 Бан {tx['user_id']}", callback_data=f"adm_tx_doban:{tx['user_id']}:{tx_id}")])
    if tx["user2_id"]:
        rows.append([InlineKeyboardButton(
            text=f"🔨 Бан {tx['user2_id']}", callback_data=f"adm_tx_doban:{tx['user2_id']}:{tx_id}")])
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=f"adm_check:{tx_id}")])

    text = f"🔨 Кого забанить?\n(по чеку #{tx_id})"
    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await call.answer()


@router.callback_query(F.data.startswith("adm_tx_doban:"))
async def admin_tx_do_ban(call: CallbackQuery):
    uid = call.from_user.id
    if not await _check_is_admin(uid):
        return await call.answer("❌ Нет доступа!", show_alert=True)

    parts = call.data.split(":")
    target_id = int(parts[1])
    tx_id = int(parts[2])

    await ban_user(target_id, days=7)
    await log_admin_action(uid, "ban_from_check", target_id, f"Бан из чека #{tx_id}")

    text = f"✅ Пользователь {target_id} забанен на 7 дней!\n🧾 Основание: Чек #{tx_id}"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ К чеку", callback_data=f"check:{tx_id}")],
    ])
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


@router.callback_query(F.data.startswith("adm_tx_refund:"))
async def admin_tx_refund(call: CallbackQuery):
    uid = call.from_user.id
    if not await _check_is_admin(uid):
        return await call.answer("❌ Нет доступа!", show_alert=True)

    tx_id = int(call.data.split(":")[1])
    tx = await get_transaction(tx_id)
    if not tx:
        return await call.answer("❌ Чек не найден!", show_alert=True)

    amount = float(tx["amount"] or 0)
    if amount <= 0:
        return await call.answer("❌ Нет суммы для возврата!", show_alert=True)

    # Возврат обоим участникам
    await update_clicks(tx["user_id"], amount)
    if tx["user2_id"]:
        await update_clicks(tx["user2_id"], amount)

    await log_admin_action(uid, "refund_from_check", tx["user_id"],
                           f"Возврат {amount} по чеку #{tx_id}")

    text = (
        f"✅ ВОЗВРАТ ВЫПОЛНЕН\n"
        "══════════════════════\n\n"
        f"🧾 Чек #{tx_id}\n"
        f"💰 Возвращено: {fnum(amount)} 💢\n"
        f"👤 Игрок 1: {tx['user_id']} ← {fnum(amount)} 💢\n"
    )
    if tx["user2_id"]:
        text += f"👥 Игрок 2: {tx['user2_id']} ← {fnum(amount)} 💢\n"
    text += "\n══════════════════════"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ К чеку", callback_data=f"check:{tx_id}")],
    ])
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()

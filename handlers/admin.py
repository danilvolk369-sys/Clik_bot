# ======================================================
# ADMIN — Панель администратора (кнопочный)
# ======================================================

import aiosqlite
import asyncio
import random

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from config import OWNER_ID, DB_NAME
from states import AdminStates, EventStates, EventBidStates
from database import (
    get_user, is_admin, add_admin, use_admin_key,
    ban_user, unban_user, log_admin_action,
    get_open_tickets, get_ticket_by_id, get_ticket_replies,
    add_ticket_reply, update_ticket_status, get_admin_actions,
    claim_ticket,
    invalidate_cache, get_banned_users, count_banned_users,
    get_chat_log_messages, get_recent_chats,
    update_clicks, create_nft_template,
    reset_user_clicks, reset_user_progress,
    create_event, get_active_events, get_event,
    join_event, get_event_participants, count_event_participants,
    finish_event, cancel_event, count_users_all,
    count_user_nfts, buy_nft_from_shop,
    update_event_bid, get_user_event_bid, get_highest_bidder,
    save_auction_message, get_auction_messages, delete_auction_messages,
)
from handlers.common import fnum
from keyboards import admin_panel_kb, admin_back_kb, back_menu_kb

router = Router()


# ═══════════════════════════════════════════════════════
#  УТИЛИТЫ
# ═══════════════════════════════════════════════════════
async def _check_admin(uid: int) -> bool:
    return uid == OWNER_ID or await is_admin(uid)


# ═══════════════════════════════════════════════════════
#  /admin — ВХОД + АКТИВАЦИЯ КЛЮЧА
# ═══════════════════════════════════════════════════════
@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    uid = message.from_user.id
    if uid == OWNER_ID:
        return await message.answer(
            "👑 Вы владелец. Используйте /owner",
        )
    if await is_admin(uid):
        await state.clear()
        text = (
            "🛡 ПАНЕЛЬ АДМИНИСТРАТОРА\n"
            "══════════════════════\n\n"
            f"┠👤 ID: {uid}\n"
            f"┗🛡 Роль: Администратор\n\n"
            "Выберите действие:\n\n"
            "══════════════════════"
        )
        return await message.answer(text, reply_markup=admin_panel_kb())

    # Не админ — предложить ввести ключ
    await state.set_state(AdminStates.waiting_key)
    await message.answer(
        "🔑 АКТИВАЦИЯ КЛЮЧА\n"
        "══════════════════════\n\n"
        "Введите ключ администратора,\n"
        "полученный от владельца:\n\n"
        "══════════════════════",
        reply_markup=back_menu_kb(),
    )


@router.message(AdminStates.waiting_key)
async def admin_activate_key(message: Message, state: FSMContext):
    key = (message.text or "").strip()
    if not key:
        return await message.answer("❌ Введите ключ:")

    uid = message.from_user.id
    uname = message.from_user.username or ""

    ok = await use_admin_key(key, uid)
    if not ok:
        return await message.answer(
            "❌ Неверный или уже использованный ключ.\n"
            "Попробуйте ещё раз или обратитесь к владельцу.",
        )

    await add_admin(uid, uname, OWNER_ID)
    await state.clear()

    try:
        await message.bot.send_message(
            OWNER_ID,
            f"🛡 Новый администратор!\n"
            f"┠👤 @{uname} (ID: {uid})\n"
            f"┗🔑 Активировал ключ",
        )
    except Exception:
        pass

    text = (
        "✅ КЛЮЧ АКТИВИРОВАН!\n"
        "══════════════════════\n\n"
        "🛡 Вы назначены администратором!\n\n"
        "Используйте /admin для доступа\n"
        "к панели управления.\n\n"
        "══════════════════════"
    )
    await message.answer(text, reply_markup=admin_panel_kb())


# ═══════════════════════════════════════════════════════
#  ПАНЕЛЬ АДМИНА (callback)
# ═══════════════════════════════════════════════════════
@router.callback_query(F.data == "admin_panel")
async def cb_admin_panel(call: CallbackQuery, state: FSMContext):
    if not await _check_admin(call.from_user.id):
        return await call.answer("❌ Нет доступа", show_alert=True)
    await state.clear()
    text = (
        "🛡 ПАНЕЛЬ АДМИНИСТРАТОРА\n"
        "══════════════════════\n\n"
        "┠📋 Жалобы — рассмотреть тикеты\n"
        "┠🔨 Бан / ✅ Разбан — модерация\n"
        "┠🎨 НФТ / 💰 Клики / 📢 Рассылка\n"
        "┗🎉 Ивенты — создать соревнование\n\n"
        "══════════════════════"
    )
    await call.message.edit_text(text, reply_markup=admin_panel_kb(0))
    await call.answer()


@router.callback_query(F.data.startswith("adm_panel_page:"))
async def adm_panel_page(call: CallbackQuery, state: FSMContext):
    if not await _check_admin(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    await state.clear()
    page = int(call.data.split(":")[1])
    text = (
        "🛡 ПАНЕЛЬ АДМИНИСТРАТОРА\n"
        "══════════════════════\n\n"
        "┠📋 Жалобы — рассмотреть тикеты\n"
        "┠🔨 Бан / ✅ Разбан — модерация\n"
        "┠🎨 НФТ / 💰 Клики / 📢 Рассылка\n"
        "┗🎉 Ивенты — создать соревнование\n\n"
        "══════════════════════"
    )
    await call.message.edit_text(text, reply_markup=admin_panel_kb(page))
    await call.answer()


# ═══════════════════════════════════════════════════════
#  📋 ЖАЛОБЫ / ТИКЕТЫ
# ═══════════════════════════════════════════════════════
@router.callback_query(F.data == "adm_tickets")
async def adm_tickets_list(call: CallbackQuery, state: FSMContext = None):
    if not await _check_admin(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    if state:
        await state.clear()

    rows = await get_open_tickets(20, viewer_id=call.from_user.id)

    if not rows:
        text = (
            "📋 ТИКЕТЫ / ЖАЛОБЫ\n"
            "══════════════════════\n\n"
            "✨ Нет доступных обращений.\n\n"
            "══════════════════════"
        )
        await call.message.edit_text(text, reply_markup=admin_back_kb())
        return await call.answer()

    _type_icon = {"complaint": "🚩", "problem": "🐛"}
    _st_icon = {"open": "🟡", "accepted": "🟢"}
    text = "📋 ТИКЕТЫ / ЖАЛОБЫ\n══════════════════════\n\n"
    for tid, uid, ttype, msg, st, dt in rows:
        icon = _type_icon.get(ttype, "📋")
        si = _st_icon.get(st, "⚪")
        text += f"{si} {icon} #{tid}  │  от {uid}\n   {msg[:50]}\n\n"
    text += "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\nВыберите тикет:"

    kb = []
    for tid, uid, ttype, msg, st, dt in rows:
        icon = _type_icon.get(ttype, "📋")
        claimed = " 🟢" if st == "accepted" else ""
        kb.append([InlineKeyboardButton(
            text=f"{icon} #{tid} — Открыть{claimed}",
            callback_data=f"admt_view_{tid}",
        )])
    kb.append([InlineKeyboardButton(text="⬅️ Панель", callback_data="admin_panel")])
    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await call.answer()


@router.callback_query(F.data.regexp(r"^admt_view_\d+$"))
async def adm_ticket_view(call: CallbackQuery):
    if not await _check_admin(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    tid = int(call.data.split("_")[-1])
    ticket = await get_ticket_by_id(tid)
    if not ticket:
        return await call.answer("❌ Тикет не найден", show_alert=True)

    # Claim ticket for this admin
    await claim_ticket(tid, call.from_user.id)

    replies = await get_ticket_replies(tid)
    user = await get_user(ticket["user_id"])
    uname = f"@{user['username']}" if user and user["username"] else f"ID:{ticket['user_id']}"
    _type_name = {"complaint": "🚩 Жалоба", "problem": "🐛 Проблема"}
    _status_name = {
        "open": "🟡 Открыт", "accepted": "🟢 В работе",
        "rejected": "🔴 Отклонён", "closed": "🔒 Закрыт",
    }

    text = (
        f"📋 ТИКЕТ #{tid}\n"
        f"══════════════════════\n\n"
        f"┠👤 От: {uname} ({ticket['user_id']})\n"
        f"┠📝 Тип: {_type_name.get(ticket['type'], ticket['type'])}\n"
        f"┠📅 Дата: {(ticket['created_at'] or '')[:16]}\n"
        f"┗📌 Статус: {_status_name.get(ticket['status'], ticket['status'])}\n\n"
        f"💬 ТЕКСТ ОБРАЩЕНИЯ:\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"{ticket['message']}\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n\n"
    )

    if replies:
        text += "═══ ДИАЛОГ ═══\n\n"
        for rid, sid, msg, dt in replies:
            who = "🛡 Админ" if (sid == OWNER_ID or await is_admin(sid)) else "👤 Игрок"
            text += f"  {who}  │  {(dt or '')[:16]}\n  {msg}\n\n"

    text += "══════════════════════"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Принять", callback_data=f"admt_accept_{tid}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"admt_reject_{tid}"),
        ],
        [InlineKeyboardButton(text="💬 Ответить", callback_data=f"admt_reply_{tid}")],
        [InlineKeyboardButton(text="👀 Переписки отправителя", callback_data=f"admt_chats_{ticket['user_id']}")],
        [InlineKeyboardButton(text="🔒 Закрыть", callback_data=f"admt_close_{tid}")],
        [InlineKeyboardButton(text="⬅️ Все тикеты", callback_data="adm_tickets")],
    ])
    try:
        await call.message.edit_text(text, reply_markup=kb)
    except Exception:
        await call.message.answer(text, reply_markup=kb)
    await call.answer()

# ─── Ответ на тикет ───
@router.callback_query(F.data.regexp(r"^admt_reply_\d+$"))
async def adm_ticket_reply_start(call: CallbackQuery, state: FSMContext):
    if not await _check_admin(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    tid = int(call.data.split("_")[-1])
    await state.set_state(AdminStates.waiting_ticket_reply)
    await state.update_data(ticket_reply_id=tid)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Отмена", callback_data=f"admt_view_{tid}")],
    ])
    await call.message.edit_text(
        f"💬 ОТВЕТ НА ТИКЕТ #{tid}\n"
        "══════════════════════\n\n"
        "Введите ваш ответ игроку:",
        reply_markup=kb,
    )
    await call.answer()


@router.message(AdminStates.waiting_ticket_reply)
async def adm_ticket_reply_save(message: Message, state: FSMContext):
    if not await _check_admin(message.from_user.id):
        return
    data = await state.get_data()
    tid = data.get("ticket_reply_id")
    txt = (message.text or "").strip()
    if not txt:
        return await message.answer("❌ Введите текст ответа:")

    await state.clear()
    ticket = await get_ticket_by_id(tid)
    if not ticket:
        return await message.answer("❌ Тикет не найден.", reply_markup=admin_panel_kb())

    await add_ticket_reply(tid, message.from_user.id, txt)
    await log_admin_action(message.from_user.id, "ticket_reply", ticket["user_id"],
                           f"Тикет #{tid}")

    # Отправляем игроку
    try:
        await message.bot.send_message(
            ticket["user_id"],
            f"💬 ОТВЕТ ПО ТИКЕТУ #{tid}\n"
            f"══════════════════════\n\n"
            f"🛡 Администратор:\n{txt}\n\n"
            f"══════════════════════",
        )
    except Exception:
        pass

    await message.answer(
        f"✅ Ответ отправлен по тикету #{tid}!",
        reply_markup=admin_panel_kb(),
    )


# ─── Принять тикет ───
@router.callback_query(F.data.regexp(r"^admt_accept_\d+$"))
async def adm_ticket_accept(call: CallbackQuery):
    if not await _check_admin(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    tid = int(call.data.split("_")[-1])
    ticket = await get_ticket_by_id(tid)
    if not ticket:
        return await call.answer("❌", show_alert=True)

    await update_ticket_status(tid, "accepted")
    await claim_ticket(tid, call.from_user.id)
    await log_admin_action(call.from_user.id, "ticket_accept", ticket["user_id"],
                           f"Тикет #{tid}")
    try:
        await call.bot.send_message(
            ticket["user_id"],
            f"✅ Ваш тикет #{tid} принят администрацией!\n"
            "Мы рассмотрим вашу проблему.",
        )
    except Exception:
        pass

    # После принятия — предложить забанить
    text = (
        f"✅ Тикет #{tid} принят!\n"
        f"══════════════════════\n\n"
        f"Хотите забанить нарушителя?"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🔨 Забанить отправителя",
            callback_data=f"admt_ban_author_{tid}",
        )],
        [InlineKeyboardButton(
            text="🔨 Забанить другого (по ID)",
            callback_data=f"admt_ban_other_{tid}",
        )],
        [InlineKeyboardButton(text="📋 Назад к тикету", callback_data=f"admt_view_{tid}")],
        [InlineKeyboardButton(text="⬅️ Все тикеты", callback_data="adm_tickets")],
    ])
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


# ═══════════════════════════════════════════════════════
#  🔨 БАН ИЗ ТИКЕТА (автор / другой)
# ═══════════════════════════════════════════════════════
@router.callback_query(F.data.regexp(r"^admt_ban_author_\d+$"))
async def adm_ticket_ban_author(call: CallbackQuery):
    """Забанить автора тикета (отправитель жалобы — нет, нарушителя из сообщения)."""
    if not await _check_admin(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    tid = int(call.data.split("_")[-1])
    ticket = await get_ticket_by_id(tid)
    if not ticket:
        return await call.answer("❌ Тикет не найден", show_alert=True)

    uid = ticket["user_id"]
    u = await get_user(uid)
    name = f"@{u['username']}" if u and u["username"] else "Аноним"

    text = (
        f"🔨 ЗАБАНИТЬ ОТПРАВИТЕЛЯ\n"
        f"══════════════════════\n\n"
        f"┠👤 {name} (ID: {uid})\n"
        f"┗📋 Тикет #{tid}\n\n"
        f"Выберите срок бана:"
    )
    kb = _ban_duration_kb(uid, back_cb=f"admt_view_{tid}")
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


@router.callback_query(F.data.regexp(r"^admt_ban_other_\d+$"))
async def adm_ticket_ban_other(call: CallbackQuery, state: FSMContext):
    """Забанить другого пользователя (по ID)."""
    if not await _check_admin(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    tid = int(call.data.split("_")[-1])
    await state.set_state(AdminStates.waiting_ban_id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Отмена", callback_data=f"admt_view_{tid}")],
    ])
    await call.message.edit_text(
        f"🔨 ЗАБАНИТЬ НАРУШИТЕЛЯ\n"
        f"══════════════════════\n\n"
        f"Из тикета #{tid}\n"
        f"Введите ID нарушителя:",
        reply_markup=kb,
    )
    await call.answer()


# ═══════════════════════════════════════════════════════
#  👀 ПРОСМОТР ПЕРЕПИСОК
# ═══════════════════════════════════════════════════════
@router.callback_query(F.data == "adm_chat_logs")
async def adm_chat_logs_list(call: CallbackQuery):
    """Список последних чатов для просмотра."""
    if not await _check_admin(call.from_user.id):
        return await call.answer("❌", show_alert=True)

    chats = await get_recent_chats(20)
    if not chats:
        text = "👀 ПЕРЕПИСКИ\n══════════════════════\n\n📭 Нет чат-логов."
        await call.message.edit_text(text, reply_markup=admin_back_kb())
        return await call.answer()

    text = "👀 ПОСЛЕДНИЕ ПЕРЕПИСКИ\n══════════════════════\n\n"
    kb = []
    for chat_id, users_str, msg_count, started in chats:
        text += f"💬 Чат #{chat_id} │ 👥 {users_str} │ ✉️ {msg_count} сообщ.\n"
        text += f"   📅 {(started or '')[:16]}\n\n"
        kb.append([InlineKeyboardButton(
            text=f"👀 Чат #{chat_id} ({msg_count} сообщ.)",
            callback_data=f"adm_chatlog:{chat_id}",
        )])
    text += "══════════════════════"
    kb.append([InlineKeyboardButton(text="⬅️ Панель админа", callback_data="admin_panel")])

    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await call.answer()


@router.callback_query(F.data.startswith("adm_chatlog:"))
async def adm_chat_log_view(call: CallbackQuery):
    """Просмотр конкретного чата."""
    if not await _check_admin(call.from_user.id):
        return await call.answer("❌", show_alert=True)

    chat_id = int(call.data.split(":")[1])
    messages = await get_chat_log_messages(chat_id, limit=50)

    if not messages:
        text = f"👀 ЧАТ #{chat_id}\n══════════════════════\n\n📭 Нет сообщений."
    else:
        text = f"👀 ЧАТ #{chat_id}\n══════════════════════\n\n"
        for sender_id, msg, dt in messages:
            time_str = (dt or "")[-8:-3] if dt else ""  # HH:MM
            short_msg = msg[:100] if msg else ""
            text += f"👤 {sender_id} [{time_str}]:\n   {short_msg}\n\n"

        # Обрезаем если слишком длинный
        if len(text) > 4000:
            text = text[:3950] + "\n\n... (обрезано)"

        text += "══════════════════════"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Все переписки", callback_data="adm_chat_logs")],
        [InlineKeyboardButton(text="⬅️ Панель админа", callback_data="admin_panel")],
    ])
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


@router.callback_query(F.data.regexp(r"^admt_chats_\d+$"))
async def adm_ticket_user_chats(call: CallbackQuery):
    """Переписки конкретного пользователя (из тикета)."""
    if not await _check_admin(call.from_user.id):
        return await call.answer("❌", show_alert=True)

    from database import chat_get_history_for_user
    uid = int(call.data.split("_")[-1])
    chats = await chat_get_history_for_user(uid, limit=15)

    if not chats:
        text = f"👀 ПЕРЕПИСКИ ID:{uid}\n══════════════════════\n\n📭 Нет чат-логов."
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Панель", callback_data="admin_panel")],
        ])
        await call.message.edit_text(text, reply_markup=kb)
        return await call.answer()

    text = f"👀 ПЕРЕПИСКИ ID:{uid}\n══════════════════════\n\n"
    kb_rows = []
    for chat_id, msg_count, started in chats:
        text += f"💬 Чат #{chat_id} │ ✉️ {msg_count} сообщ. │ 📅 {(started or '')[:16]}\n\n"
        kb_rows.append([InlineKeyboardButton(
            text=f"👀 Чат #{chat_id}",
            callback_data=f"adm_chatlog:{chat_id}",
        )])
    text += "══════════════════════"
    kb_rows.append([InlineKeyboardButton(text="⬅️ Панель", callback_data="admin_panel")])

    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))
    await call.answer()
# ─── Отклонить тикет ───
@router.callback_query(F.data.regexp(r"^admt_reject_\d+$"))
async def adm_ticket_reject(call: CallbackQuery):
    if not await _check_admin(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    tid = int(call.data.split("_")[-1])
    ticket = await get_ticket_by_id(tid)
    if not ticket:
        return await call.answer("❌", show_alert=True)

    await update_ticket_status(tid, "rejected")
    await log_admin_action(call.from_user.id, "ticket_reject", ticket["user_id"],
                           f"Тикет #{tid}")
    try:
        await call.bot.send_message(
            ticket["user_id"],
            f"❌ Ваш тикет #{tid} отклонён.",
        )
    except Exception:
        pass
    await call.answer(f"❌ Тикет #{tid} отклонён!", show_alert=True)
    await adm_tickets_list(call)


# ─── Закрыть тикет ───
@router.callback_query(F.data.regexp(r"^admt_close_\d+$"))
async def adm_ticket_close(call: CallbackQuery):
    if not await _check_admin(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    tid = int(call.data.split("_")[-1])
    await update_ticket_status(tid, "closed")
    await log_admin_action(call.from_user.id, "ticket_close", None, f"Тикет #{tid}")
    await call.answer(f"🔒 Тикет #{tid} закрыт!", show_alert=True)
    await adm_tickets_list(call)


# ═══════════════════════════════════════════════════════
#  🔨 БАН (админ) — с выбором срока
# ═══════════════════════════════════════════════════════
BAN_DURATIONS = {
    "7":  "1 неделя",
    "14": "2 недели",
    "30": "1 месяц",
    "90": "3 месяца",
    "0":  "♾ Навсегда",
}


def _ban_duration_kb(uid: int, back_cb: str = "admin_panel"):
    """Клавиатура выбора срока бана."""
    kb = []
    for days, label in BAN_DURATIONS.items():
        kb.append([InlineKeyboardButton(
            text=f"🔨 {label}",
            callback_data=f"adm_ban_do:{uid}:{days}",
        )])
    kb.append([InlineKeyboardButton(text="⬅️ Отмена", callback_data=back_cb)])
    return InlineKeyboardMarkup(inline_keyboard=kb)


@router.callback_query(F.data == "adm_ban")
async def adm_ban_start(call: CallbackQuery, state: FSMContext):
    if not await _check_admin(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    await state.set_state(AdminStates.waiting_ban_id)
    await call.message.edit_text(
        "🔨 БАН ПОЛЬЗОВАТЕЛЯ\n"
        "══════════════════════\n\n"
        "Введите ID пользователя для бана:",
        reply_markup=admin_back_kb(),
    )
    await call.answer()


@router.message(AdminStates.waiting_ban_id)
async def adm_ban_choose_duration(message: Message, state: FSMContext):
    if not await _check_admin(message.from_user.id):
        return
    try:
        uid = int(message.text.strip())
    except (ValueError, AttributeError):
        return await message.answer("❌ Введите числовой ID:")

    if uid == OWNER_ID:
        return await message.answer("❌ Нельзя забанить владельца!")
    if await is_admin(uid):
        return await message.answer("❌ Нельзя забанить другого админа!")

    u = await get_user(uid)
    if not u:
        return await message.answer("❌ Пользователь не найден.")

    await state.clear()
    name = f"@{u['username']}" if u["username"] else "Аноним"
    await message.answer(
        f"🔨 БАН: {name} (ID: {uid})\n"
        "══════════════════════\n\n"
        "Выберите срок бана:",
        reply_markup=_ban_duration_kb(uid),
    )


@router.callback_query(F.data.startswith("adm_ban_do:"))
async def adm_ban_execute(call: CallbackQuery):
    if not await _check_admin(call.from_user.id):
        return await call.answer("❌", show_alert=True)

    parts = call.data.split(":")
    uid = int(parts[1])
    days = int(parts[2])

    u = await get_user(uid)
    if not u:
        return await call.answer("❌ Пользователь не найден", show_alert=True)

    await ban_user(uid, days=days)
    await log_admin_action(call.from_user.id, "ban", uid,
                           f"Срок: {BAN_DURATIONS.get(str(days), str(days) + 'д')}")

    try:
        dur_text = BAN_DURATIONS.get(str(days), f"{days} дн.")
        await call.bot.send_message(
            uid,
            f"🔴 Вы заблокированы администрацией.\n"
            f"Срок: {dur_text}",
        )
    except Exception:
        pass

    name = f"@{u['username']}" if u["username"] else "Аноним"
    dur_text = BAN_DURATIONS.get(str(days), f"{days} дн.")
    await call.message.edit_text(
        f"✅ Забанен!\n\n┠🪪 ID: {uid}\n┠👤 {name}\n┗⏱ Срок: {dur_text}",
        reply_markup=admin_back_kb(),
    )
    await call.answer()


# ═══════════════════════════════════════════════════════
#  ✅ РАЗБАН (админ)
# ═══════════════════════════════════════════════════════
@router.callback_query(F.data == "adm_unban")
async def adm_unban_start(call: CallbackQuery, state: FSMContext):
    if not await _check_admin(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    await state.set_state(AdminStates.waiting_unban_id)
    await call.message.edit_text(
        "✅ РАЗБАН ПОЛЬЗОВАТЕЛЯ\n"
        "══════════════════════\n\n"
        "Введите ID пользователя для разбана:",
        reply_markup=admin_back_kb(),
    )
    await call.answer()


@router.message(AdminStates.waiting_unban_id)
async def adm_unban_process(message: Message, state: FSMContext):
    if not await _check_admin(message.from_user.id):
        return
    try:
        uid = int(message.text.strip())
    except (ValueError, AttributeError):
        return await message.answer("❌ Введите числовой ID:")

    u = await get_user(uid)
    if not u:
        return await message.answer("❌ Пользователь не найден.")

    await unban_user(uid)
    await log_admin_action(message.from_user.id, "unban", uid)
    await state.clear()

    try:
        await message.bot.send_message(uid, "🟢 Вы разблокированы! Добро пожаловать.")
    except Exception:
        pass

    name = f"@{u['username']}" if u["username"] else "Аноним"
    await message.answer(
        f"✅ Разбанен!\n\n┠🪪 ID: {uid}\n┗👤 {name}",
        reply_markup=admin_panel_kb(),
    )


# ═══════════════════════════════════════════════════════
#  📊 МОИ ДЕЙСТВИЯ
# ═══════════════════════════════════════════════════════
@router.callback_query(F.data == "adm_my_log")
async def adm_my_log(call: CallbackQuery):
    if not await _check_admin(call.from_user.id):
        return await call.answer("❌", show_alert=True)

    actions = await get_admin_actions(admin_id=call.from_user.id, limit=15)
    if not actions:
        text = "📊 МОИ ДЕЙСТВИЯ\n══════════════════════\n\n😔 Нет записей."
    else:
        text = "📊 МОИ ДЕЙСТВИЯ\n══════════════════════\n\n"
        for aid, admin_id, action, target, details, dt in actions:
            act_icon = {
                "ban": "🔨 Бан",
                "unban": "✅ Разбан",
                "ticket_reply": "💬 Ответ",
                "ticket_accept": "📗 Принял",
                "ticket_reject": "📕 Отклонил",
                "ticket_close": "🔒 Закрыл",
            }.get(action, f"📝 {action}")
            target_s = f" → ID:{target}" if target else ""
            text += f"┠{act_icon}{target_s}\n   {(dt or '')[:16]}\n"
            if details:
                text += f"   {details[:50]}\n"
            text += "\n"
        text += "══════════════════════"

    await call.message.edit_text(text, reply_markup=admin_back_kb())
    await call.answer()


# ═══════════════════════════════════════════════════════
#  🚫 СПИСОК ЗАБАНЕННЫХ (админ, пагинация по 4)
# ═══════════════════════════════════════════════════════
ADM_PAGE_SIZE_BANNED = 4


@router.callback_query(F.data.startswith("adm_banned_list"))
async def adm_banned_list(call: CallbackQuery):
    if not await _check_admin(call.from_user.id):
        return await call.answer("❌", show_alert=True)

    parts = call.data.split(":")
    page = int(parts[1]) if len(parts) > 1 else 0
    if page < 0:
        page = 0

    total = await count_banned_users()
    total_pages = max(1, (total + ADM_PAGE_SIZE_BANNED - 1) // ADM_PAGE_SIZE_BANNED)
    if page >= total_pages:
        page = total_pages - 1

    offset = page * ADM_PAGE_SIZE_BANNED
    rows = await get_banned_users(limit=ADM_PAGE_SIZE_BANNED, offset=offset)

    if not rows:
        text = (
            "🚫 СПИСОК ЗАБАНЕННЫХ\n"
            "══════════════════════\n\n"
            "😊 Нет забаненных пользователей."
        )
    else:
        text = (
            f"🚫 СПИСОК ЗАБАНЕННЫХ ({total})  ({page + 1}/{total_pages})\n"
            "══════════════════════\n\n"
        )
        for i, (uid, uname, clicks, rank) in enumerate(rows, offset + 1):
            name = f"@{uname}" if uname else "Аноним"
            text += (
                f"🔴 #{i} {name}\n"
                f"   ID: {uid} │ 💢 {fnum(clicks)} │ ⭐ {rank}\n\n"
            )
        text += "══════════════════════"

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️ Назад", callback_data=f"adm_banned_list:{page - 1}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="Далее ▶️", callback_data=f"adm_banned_list:{page + 1}"))

    kb_rows = []
    if nav:
        kb_rows.append(nav)
    kb_rows.append([InlineKeyboardButton(text="⬅️ Панель админа", callback_data="admin_panel")])
    kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)

    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


# ═══════════════════════════════════════════════════════
#  🎨 СОЗДАНИЕ НФТ (админ)
# ═══════════════════════════════════════════════════════

_RARITY_LABELS = {
    1:  "📦 Обычный",     2:  "🧩 Необычный",  3:  "💎 Редкий",
    4:  "🔮 Эпический",   5:  "👑 Легендарный", 6:  "🐉 Мифический",
    7:  "⚡ Божественный", 8:  "🌌 Космический", 9:  "♾️ Вечный",
    10: "🏆 Запредельный",
}


@router.callback_query(F.data == "adm_nft_create")
async def adm_nft_create(call: CallbackQuery, state: FSMContext):
    if not await _check_admin(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    await state.set_state(AdminStates.nft_name)
    await call.message.edit_text(
        "🎨 СОЗДАНИЕ НФТ\n══════════════════════\n\n"
        "Шаг 1/4 — Введите название НФТ:",
        reply_markup=admin_back_kb(),
    )
    await call.answer()


@router.message(AdminStates.nft_name)
async def adm_nft_step_name(message: Message, state: FSMContext):
    if not await _check_admin(message.from_user.id):
        return
    name = (message.text or "").strip()
    if not name or len(name) > 64:
        return await message.answer("❌ 1-64 символа:")
    await state.update_data(nft_name=name)
    await state.set_state(AdminStates.nft_rarity)
    await message.answer(
        f"✅ Название: {name}\n\n"
        "Шаг 2/4 — Редкость (1-10):\n\n"
        " 1 — 📦 Обычный\n"
        " 2 — 🧩 Необычный\n"
        " 3 — 💎 Редкий\n"
        " 4 — 🔮 Эпический\n"
        " 5 — 👑 Легендарный\n"
        " 6 — 🐉 Мифический\n"
        " 7 — ⚡ Божественный\n"
        " 8 — 🌌 Космический\n"
        " 9 — ♾️ Вечный\n"
        "10 — 🏆 Запредельный",
    )


@router.message(AdminStates.nft_rarity)
async def adm_nft_step_rarity(message: Message, state: FSMContext):
    if not await _check_admin(message.from_user.id):
        return
    try:
        rarity = int(message.text.strip())
        assert 1 <= rarity <= 10
    except (ValueError, AssertionError, AttributeError):
        return await message.answer("❌ Число от 1 до 10:")
    await state.update_data(nft_rarity=rarity)
    await state.set_state(AdminStates.nft_income)
    await message.answer(
        f"✅ Редкость: {_RARITY_LABELS.get(rarity, str(rarity))}\n\n"
        "Шаг 3/4 — Доход в час (💢/ч):",
    )


@router.message(AdminStates.nft_income)
async def adm_nft_step_income(message: Message, state: FSMContext):
    if not await _check_admin(message.from_user.id):
        return
    try:
        income = float(message.text.strip().replace(",", "."))
        assert income > 0
    except (ValueError, AssertionError, AttributeError):
        return await message.answer("❌ Положительное число:")
    await state.update_data(nft_income=income)
    await state.set_state(AdminStates.nft_price)
    await message.answer(f"✅ Доход: +{fnum(income)} 💢/ч\n\nШаг 4/4 — Цена (💢):")


@router.message(AdminStates.nft_price)
async def adm_nft_step_price(message: Message, state: FSMContext):
    if not await _check_admin(message.from_user.id):
        return
    try:
        price = float(message.text.strip().replace(",", "."))
        assert price > 0
    except (ValueError, AssertionError, AttributeError):
        return await message.answer("❌ Положительное число:")
    await state.update_data(nft_price=price)
    await state.set_state(AdminStates.nft_confirm)

    data = await state.get_data()
    name, rarity, income = data["nft_name"], data["nft_rarity"], data["nft_income"]

    preview = (
        "🎨 ПРЕВЬЮ НФТ\n══════════════════════\n\n"
        f"┠📛 Название: {name}\n"
        f"┠🏷 Редкость: {_RARITY_LABELS.get(rarity, str(rarity))}\n"
        f"┠📈 Доход: +{fnum(income)} 💢/ч\n"
        f"┗💰 Цена: {int(price):,} 💢\n\n"
        "══════════════════════\nОпубликовать?"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Опубликовать", callback_data="adm_nft_publish")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="admin_panel")],
    ])
    await message.answer(preview, reply_markup=kb)


@router.callback_query(F.data == "adm_nft_publish", AdminStates.nft_confirm)
async def adm_nft_publish(call: CallbackQuery, state: FSMContext):
    if not await _check_admin(call.from_user.id):
        return await call.answer("❌", show_alert=True)

    data = await state.get_data()
    name = data.get("nft_name")
    rarity = data.get("nft_rarity")
    income = data.get("nft_income")
    price = data.get("nft_price")

    if not all([name, rarity is not None, income is not None, price is not None]):
        await state.clear()
        return await call.message.edit_text(
            "❌ Данные утеряны.", reply_markup=admin_panel_kb(),
        )

    nft_id = await create_nft_template(name, income, rarity, price, call.from_user.id)
    await log_admin_action(call.from_user.id, "nft_create", None,
                           f"НФТ #{nft_id} {name}")
    await state.clear()

    text = (
        "✅ НФТ ОПУБЛИКОВАН!\n══════════════════════\n\n"
        f"┠📛 {name}\n"
        f"┠🏷 {_RARITY_LABELS.get(rarity, str(rarity))}\n"
        f"┠📈 +{fnum(income)} 💢/ч\n"
        f"┠💰 {int(price):,} 💢\n"
        f"┗🆔 #{nft_id}\n\n"
        "Доступен в 🏪 Торговой площадке!"
    )
    await call.message.edit_text(text, reply_markup=admin_panel_kb(1))
    await call.answer("✅ Опубликовано!", show_alert=True)


# ═══════════════════════════════════════════════════════
#  💰 ВЫДАТЬ КЛИКИ (админ)
# ═══════════════════════════════════════════════════════
@router.callback_query(F.data == "adm_give")
async def adm_give_start(call: CallbackQuery, state: FSMContext):
    if not await _check_admin(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    await state.set_state(AdminStates.waiting_give)
    await call.message.edit_text(
        "💰 ВЫДАТЬ КЛИКИ\n"
        "══════════════════════\n\n"
        "Введите в формате:\n"
        "ID  количество\n\n"
        "Пример: 123456789 5000",
        reply_markup=admin_back_kb(),
    )
    await call.answer()


@router.message(AdminStates.waiting_give)
async def adm_give_process(message: Message, state: FSMContext):
    if not await _check_admin(message.from_user.id):
        return
    parts = (message.text or "").split()
    if len(parts) < 2:
        return await message.answer("❌ Формат: ID количество\nПример: 123456789 5000")

    try:
        uid = int(parts[0])
        amount = float(parts[1])
        assert amount > 0
    except (ValueError, AssertionError):
        return await message.answer("❌ ID — число, кол-во — > 0.")

    u = await get_user(uid)
    if not u:
        return await message.answer("❌ Пользователь не найден.")

    await update_clicks(uid, amount)
    await log_admin_action(message.from_user.id, "give_clicks", uid,
                           f"+{fnum(amount)} 💢")
    await state.clear()

    try:
        await message.bot.send_message(
            uid,
            f"🎁 ПОДАРОК ОТ АДМИНИСТРАЦИИ\n"
            f"══════════════════════\n\n"
            f"┠💰 Начислено: +{fnum(amount)} 💢\n"
            f"┗📋 Выдача от админа\n\n"
            f"Приятной игры! 🎉",
        )
    except Exception:
        pass

    name = f"@{u['username']}" if u["username"] else "Аноним"
    await message.answer(
        f"✅ Выдано!\n\n┠👤 {name} (ID: {uid})\n┗💰 +{fnum(amount)} 💢",
        reply_markup=admin_panel_kb(1),
    )


# ═══════════════════════════════════════════════════════
#  📢 РАССЫЛКА (админ)
# ═══════════════════════════════════════════════════════
@router.callback_query(F.data == "adm_broadcast")
async def adm_broadcast_start(call: CallbackQuery, state: FSMContext):
    if not await _check_admin(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    await state.set_state(AdminStates.waiting_broadcast)
    await call.message.edit_text(
        "📢 РАССЫЛКА\n"
        "══════════════════════\n\n"
        "Введите текст рассылки всем игрокам:",
        reply_markup=admin_back_kb(),
    )
    await call.answer()


@router.message(AdminStates.waiting_broadcast)
async def adm_broadcast_process(message: Message, state: FSMContext):
    if not await _check_admin(message.from_user.id):
        return
    text = (message.text or "").strip()
    if not text:
        return await message.answer("❌ Введите текст:")

    await state.clear()
    await message.answer("⏳ Рассылка запущена...")

    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("SELECT user_id FROM users WHERE is_banned = 0")
        users = await cur.fetchall()

    sent, fail = 0, 0
    for (uid,) in users:
        try:
            await message.bot.send_message(uid, f"📢 {text}")
            sent += 1
        except Exception:
            fail += 1

    await log_admin_action(message.from_user.id, "broadcast", None,
                           f"Отправлено: {sent}, Ошибок: {fail}")
    await message.answer(
        f"✅ РАССЫЛКА ЗАВЕРШЕНА\n══════════════════════\n\n"
        f"┠📨 Отправлено: {sent}\n┗❌ Ошибок: {fail}",
        reply_markup=admin_panel_kb(1),
    )


# ═══════════════════════════════════════════════════════
#  🗑 СБРОС КЛИКОВ / 🔄 СБРОС ПРОГРЕССА (админ)
# ═══════════════════════════════════════════════════════
_ADM_RESET_MODES = {
    "adm_reset_clicks":   ("clicks",   "🗑 СБРОС КЛИКОВ",   "Баланс кликов обнулён."),
    "adm_reset_progress": ("progress", "🔄 СБРОС ПРОГРЕССА", "total_clicks и ранг сброшены."),
}


@router.callback_query(F.data.in_(set(_ADM_RESET_MODES.keys())))
async def adm_reset_start(call: CallbackQuery, state: FSMContext):
    if not await _check_admin(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    mode, title, desc = _ADM_RESET_MODES[call.data]
    await state.set_state(AdminStates.waiting_reset_user_id)
    await state.update_data(reset_mode=mode)
    await call.message.edit_text(
        f"{title}\n══════════════════════\n\n"
        f"{desc}\n\n"
        "Введите ID пользователя:",
        reply_markup=admin_back_kb(),
    )
    await call.answer()


@router.message(AdminStates.waiting_reset_user_id)
async def adm_reset_process(message: Message, state: FSMContext):
    if not await _check_admin(message.from_user.id):
        return
    try:
        uid = int(message.text.strip())
    except (ValueError, AttributeError):
        return await message.answer("❌ Введите числовой ID.")

    u = await get_user(uid)
    if not u:
        return await message.answer("❌ Пользователь не найден.")

    data = await state.get_data()
    mode = data.get("reset_mode", "clicks")
    name = f"@{u['username']}" if u["username"] else "Аноним"

    if mode == "clicks":
        await reset_user_clicks(uid)
        label = "🗑 Баланс кликов обнулён"
    else:
        await reset_user_progress(uid)
        label = "🔄 Прогресс сброшен (total_clicks → 0, ранг → 1)"

    await log_admin_action(message.from_user.id, f"reset_{mode}", uid)
    await state.clear()
    await message.answer(
        f"✅ Сброс выполнен!\n\n"
        f"┠👤 {name} (ID: {uid})\n"
        f"┗{label}",
        reply_markup=admin_panel_kb(1),
    )


# ═══════════════════════════════════════════════════════
#  🎉 АУКЦИОН (создание — owner + admin)
#  Шаги: 1.Название, 2.НФТ, 3.Редкость, 4.Доход/ч,
#         5.Мин.ставка, 6.Длительность → Подтверждение →
#         Рассылка (Подтвердить/Игнорировать) →
#         Макс 10 участников, реальное обновление,
#         после окончания — удаление рассылки + Победитель
# ═══════════════════════════════════════════════════════

def _rarity_label(rarity: int) -> str:
    return {
        1: "📦 Обычный", 2: "🧩 Необычный", 3: "💎 Редкий",
        4: "🔮 Эпический", 5: "👑 Легендарный", 6: "🐉 Мифический",
        7: "⚡ Божественный", 8: "🌌 Космический", 9: "♾️ Вечный",
        10: "🏆 Запредельный",
    }.get(rarity, "📦 Обычный")


def _rarity_emoji(rarity: int) -> str:
    return {
        1: "📦", 2: "🧩", 3: "💎", 4: "🔮", 5: "👑",
        6: "🐉", 7: "⚡", 8: "🌌", 9: "♾️", 10: "🏆",
    }.get(rarity, "📦")


MAX_AUCTION_PARTICIPANTS = 2


@router.callback_query(F.data == "event_create")
async def event_create_start(call: CallbackQuery, state: FSMContext):
    uid = call.from_user.id
    if uid != OWNER_ID and not await is_admin(uid):
        return await call.answer("❌ Нет доступа", show_alert=True)
    await state.set_state(EventStates.waiting_name)
    back_cb = "owner_panel" if uid == OWNER_ID else "admin_panel"
    await call.message.edit_text(
        "🏷 СОЗДАНИЕ АУКЦИОНА\n"
        "══════════════════════\n\n"
        "Шаг 1/6 — Название аукциона:\n\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        "✏️ Введите название:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Отмена", callback_data=back_cb)],
        ]),
    )
    await call.answer()


@router.message(EventStates.waiting_name)
async def event_step_name(message: Message, state: FSMContext):
    uid = message.from_user.id
    if uid != OWNER_ID and not await is_admin(uid):
        return
    name = (message.text or "").strip()
    if not name or len(name) > 64:
        return await message.answer("❌ Название 1-64 символа:")
    await state.update_data(event_name=name)
    await state.set_state(EventStates.waiting_nft_name)
    await message.answer(
        f"✅ Название: {name}\n\n"
        "Шаг 2/6 — Название НФТ-приза\n"
        "(победитель получит этот НФТ):\n\n"
        "✏️ Введите название НФТ:",
    )


@router.message(EventStates.waiting_nft_name)
async def event_step_nft(message: Message, state: FSMContext):
    uid = message.from_user.id
    if uid != OWNER_ID and not await is_admin(uid):
        return
    nft_name = (message.text or "").strip()
    if not nft_name or len(nft_name) > 64:
        return await message.answer("❌ Название 1-64 символа:")
    await state.update_data(event_nft_name=nft_name)
    await state.set_state(EventStates.waiting_rarity)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📦 1", callback_data="evt_rar_1"),
            InlineKeyboardButton(text="🧩 2", callback_data="evt_rar_2"),
            InlineKeyboardButton(text="💎 3", callback_data="evt_rar_3"),
        ],
        [
            InlineKeyboardButton(text="🔮 4", callback_data="evt_rar_4"),
            InlineKeyboardButton(text="👑 5", callback_data="evt_rar_5"),
            InlineKeyboardButton(text="🐉 6", callback_data="evt_rar_6"),
        ],
        [
            InlineKeyboardButton(text="⚡ 7", callback_data="evt_rar_7"),
            InlineKeyboardButton(text="🌌 8", callback_data="evt_rar_8"),
            InlineKeyboardButton(text="♾️ 9", callback_data="evt_rar_9"),
        ],
        [InlineKeyboardButton(text="🏆 10", callback_data="evt_rar_10")],
    ])
    await message.answer(
        f"✅ НФТ-приз: {nft_name}\n\n"
        "Шаг 3/6 — Редкость НФТ (1-10):",
        reply_markup=kb,
    )


@router.callback_query(F.data.regexp(r"^evt_rar_\d+$"), EventStates.waiting_rarity)
async def event_step_rarity(call: CallbackQuery, state: FSMContext):
    rarity = int(call.data.replace("evt_rar_", ""))
    await state.update_data(event_rarity=rarity)
    await state.set_state(EventStates.waiting_income)
    await call.message.edit_text(
        f"✅ Редкость: {_rarity_label(rarity)}\n\n"
        "Шаг 4/6 — Доход НФТ в час (💢/ч):\n\n"
        "✏️ Введите число:",
    )
    await call.answer()


@router.message(EventStates.waiting_income)
async def event_step_income(message: Message, state: FSMContext):
    uid = message.from_user.id
    if uid != OWNER_ID and not await is_admin(uid):
        return
    try:
        income = float(message.text.strip().replace(",", "."))
        assert income > 0
    except (ValueError, AssertionError, AttributeError):
        return await message.answer("❌ Положительное число:")
    await state.update_data(event_income=income)
    await state.set_state(EventStates.waiting_bet)
    await message.answer(
        f"✅ Доход: +{fnum(income)} 💢/ч\n\n"
        "Шаг 5/6 — Минимальная ставка (💢):\n\n"
        "✏️ Введите число:",
    )


@router.message(EventStates.waiting_bet)
async def event_step_bet(message: Message, state: FSMContext):
    uid = message.from_user.id
    if uid != OWNER_ID and not await is_admin(uid):
        return
    try:
        bet = float(message.text.strip().replace(",", "."))
        assert bet > 0
    except (ValueError, AssertionError, AttributeError):
        return await message.answer("❌ Положительное число:")
    await state.update_data(event_bet=bet)
    await state.set_state(EventStates.waiting_duration)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="1 мин", callback_data="evt_dur_1"),
            InlineKeyboardButton(text="3 мин", callback_data="evt_dur_3"),
            InlineKeyboardButton(text="5 мин", callback_data="evt_dur_5"),
        ],
        [
            InlineKeyboardButton(text="10 мин", callback_data="evt_dur_10"),
            InlineKeyboardButton(text="15 мин", callback_data="evt_dur_15"),
            InlineKeyboardButton(text="30 мин", callback_data="evt_dur_30"),
        ],
    ])
    await message.answer(
        f"✅ Мин. ставка: {fnum(bet)} 💢\n\n"
        "Шаг 6/6 — Длительность аукциона:",
        reply_markup=kb,
    )


@router.callback_query(F.data.startswith("evt_dur_"), EventStates.waiting_duration)
async def event_step_duration(call: CallbackQuery, state: FSMContext):
    duration = int(call.data.replace("evt_dur_", ""))
    await state.update_data(event_duration=duration)
    await state.set_state(EventStates.confirm)

    data = await state.get_data()
    name = data["event_name"]
    nft_name = data["event_nft_name"]
    rarity = data["event_rarity"]
    income = data["event_income"]
    bet = data["event_bet"]
    emoji = _rarity_emoji(rarity)

    text = (
        "📋 ПРЕВЬЮ АУКЦИОНА\n"
        "══════════════════════\n\n"
        f"┠🏷 Название: {name}\n"
        f"┠🎨 НФТ-приз: {nft_name}\n"
        f"┠{emoji} Редкость: {_rarity_label(rarity)}\n"
        f"┠📈 Доход: +{fnum(income)} 💢/ч\n"
        f"┠💢 Мин. ставка: {fnum(bet)} 💢\n"
        f"┗⏱ Длительность: {duration} мин\n\n"
        "══════════════════════\n"
        "🏷 Кто поставит больше кликов —\n"
        "тот получит НФТ!\n\n"
        "Запустить аукцион?"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Запустить", callback_data="evt_confirm_yes")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_panel")],
    ])
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


@router.callback_query(F.data == "evt_confirm_yes", EventStates.confirm)
async def event_confirm(call: CallbackQuery, state: FSMContext):
    uid = call.from_user.id
    data = await state.get_data()
    await state.clear()

    name = data["event_name"]
    nft_name = data["event_nft_name"]
    rarity = data["event_rarity"]
    income = data["event_income"]
    bet = data["event_bet"]
    duration = data["event_duration"]
    emoji = _rarity_emoji(rarity)

    event_id = await create_event(
        name, nft_name, bet, duration, uid,
        nft_rarity=rarity, nft_income=income,
    )
    await log_admin_action(uid, "event_create", None,
                           f"Аукцион #{event_id} {name}")

    text = (
        "🏷 АУКЦИОН ЗАПУЩЕН!\n"
        "══════════════════════\n\n"
        f"┠🎯 {name}\n"
        f"┠🎨 Приз: {emoji} {nft_name}\n"
        f"┠📈 Доход: +{fnum(income)} 💢/ч\n"
        f"┠💢 Мин. ставка: {fnum(bet)} 💢\n"
        f"┠⏱ Время: {duration} мин\n"
        f"┗🆔 #{event_id}\n\n"
        "📢 Рассылка запущена..."
    )
    back_cb = "owner_panel" if uid == OWNER_ID else "admin_panel"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Панель", callback_data=back_cb)],
    ])
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer("🏷 Запущено!", show_alert=True)

    # ═══ Рассылка всем: «Подтвердить / Игнорировать» ═══
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("SELECT user_id FROM users WHERE is_banned = 0")
        users = await cur.fetchall()

    notify_text = (
        f"🏷 НОВЫЙ АУКЦИОН!\n"
        f"══════════════════════\n\n"
        f"🎯 {name}\n"
        f"🎨 Приз: {emoji} {nft_name}\n"
        f"✨ Редкость: {_rarity_label(rarity)}\n"
        f"📈 Доход: +{fnum(income)} 💢/ч\n"
        f"💢 Мин. ставка: {fnum(bet)} 💢\n"
        f"⏱ Время: {duration} мин\n\n"
        f"🏷 Кто поставит больше — тот победит!\n"
        f"👥 Макс. участников: {MAX_AUCTION_PARTICIPANTS}\n\n"
        f"══════════════════════"
    )
    notify_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"evt_join_{event_id}"),
            InlineKeyboardButton(text="❌ Игнорировать", callback_data=f"evt_ignore_{event_id}"),
        ],
    ])

    for (u_id,) in users:
        if u_id == uid:
            continue
        try:
            sent = await call.bot.send_message(u_id, notify_text, reply_markup=notify_kb)
            await save_auction_message(event_id, u_id, sent.message_id)
        except Exception:
            pass

    # Запуск таймера завершения
    asyncio.create_task(_event_timer(call.bot, event_id, duration, nft_name, rarity, income, bet, name))


async def _build_auction_status(event_id: int, event_name: str, nft_name: str,
                                rarity: int, income: float, min_bet: float,
                                duration: int) -> str:
    """Формирует текст текущего состояния аукциона."""
    emoji = _rarity_emoji(rarity)
    participants = await get_event_participants(event_id)
    top_bids = sorted(participants, key=lambda x: x[3], reverse=True)
    count = len(participants)

    text = (
        f"🏷 АУКЦИОН: {event_name}\n"
        f"══════════════════════\n\n"
        f"🎨 Приз: {emoji} {nft_name}\n"
        f"✨ {_rarity_label(rarity)}\n"
        f"📈 Доход: +{fnum(income)} 💢/ч\n"
        f"💢 Мин. ставка: {fnum(min_bet)} 💢\n"
        f"⏱ Длительность: {duration} мин\n\n"
        f"👥 Участников: {count}/{MAX_AUCTION_PARTICIPANTS}\n\n"
    )

    if top_bids:
        text += "📊 ТОП СТАВОК:\n┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        for i, (p_uid, p_uname, _, p_bid) in enumerate(top_bids[:10], 1):
            pn = f"@{p_uname}" if p_uname else f"ID:{p_uid}"
            medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"#{i}")
            text += f"  {medal} {pn}: {fnum(p_bid)} 💢\n"
        text += "\n"

    text += "══════════════════════"
    return text


async def _update_all_auction_messages(bot, event_id: int, text: str, kb=None):
    """Обновить текст рассылки у всех получивших сообщение."""
    messages = await get_auction_messages(event_id)
    for chat_id, message_id in messages:
        try:
            if kb:
                await bot.edit_message_text(
                    text, chat_id=chat_id, message_id=message_id,
                    reply_markup=kb,
                )
            else:
                await bot.edit_message_text(
                    text, chat_id=chat_id, message_id=message_id,
                )
        except Exception:
            pass


async def _delete_all_auction_messages(bot, event_id: int):
    """Удалить все сообщения рассылки аукциона."""
    messages = await get_auction_messages(event_id)
    for chat_id, message_id in messages:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=message_id)
        except Exception:
            pass
    await delete_auction_messages(event_id)


async def _event_timer(bot, event_id: int, duration: int, nft_name: str,
                       rarity: int, income: float, min_bet: float, event_name: str):
    """Таймер аукциона: обновляет текст каждые 15 сек, по завершению удаляет рассылку."""
    import time
    end_time = time.time() + duration * 60
    emoji = _rarity_emoji(rarity)

    # Периодическое обновление текста (каждые 15 сек)
    while time.time() < end_time:
        await asyncio.sleep(15)

        event = await get_event(event_id)
        if not event or event[5] != "active":
            return

        remaining = int(end_time - time.time())
        if remaining < 0:
            remaining = 0
        mins_left = remaining // 60
        secs_left = remaining % 60

        status_text = await _build_auction_status(
            event_id, event_name, nft_name, rarity, income, min_bet, duration,
        )
        status_text += f"\n⏳ Осталось: {mins_left}:{secs_left:02d}"

        count = await count_event_participants(event_id)
        if count < MAX_AUCTION_PARTICIPANTS:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🏷 Сделать ставку!", callback_data=f"evt_join_{event_id}")],
            ])
        else:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📊 Обновить", callback_data=f"evt_join_{event_id}")],
            ])

        await _update_all_auction_messages(bot, event_id, status_text, kb)

    # ═══ Завершение аукциона ═══
    event = await get_event(event_id)
    if not event or event[5] != "active":
        return

    participants = await get_event_participants(event_id)
    await finish_event(event_id)

    # Получаем всех пользователей, кому была отправлена рассылка (до удаления)
    broadcast_msgs = await get_auction_messages(event_id)
    broadcast_user_ids = {chat_id for chat_id, _ in broadcast_msgs}

    # Удаляем все сообщения рассылки
    await _delete_all_auction_messages(bot, event_id)

    if not participants or len(participants) < 2:
        # 0 или 1 участник — аукцион отменён, возврат ставки
        cancel_text = (
            f"🏁 АУКЦИОН ОТМЕНЁН!\n"
            f"══════════════════════\n\n"
            f"🏷 {event_name}\n\n"
            f"😔 Недостаточно участников\n"
            f"(нужно минимум 2).\n"
            f"Аукцион отменён.\n\n"
            f"══════════════════════"
        )
        # Возвращаем ставку единственному участнику
        for p_uid, p_uname, _, p_bid in participants:
            await update_clicks(p_uid, p_bid)
            try:
                await bot.send_message(
                    p_uid,
                    cancel_text + f"\n\n💰 Ваша ставка ({fnum(p_bid)} 💢) возвращена.",
                )
            except Exception:
                pass
        # Уведомляем остальных
        participant_ids = {p[0] for p in participants}
        for b_uid in broadcast_user_ids:
            if b_uid not in participant_ids:
                try:
                    await bot.send_message(b_uid, cancel_text)
                except Exception:
                    pass
        return

    # Победитель — максимальная ставка
    winner_row = await get_highest_bidder(event_id)
    if not winner_row:
        return

    winner_id, winner_name, _, winner_bid = winner_row
    wname = f"@{winner_name}" if winner_name else f"ID:{winner_id}"

    # Создаём НФТ с заданными rarity и income
    from config import MAX_NFT
    nft_id = await create_nft_template(nft_name, income, rarity, min_bet * 2, 0)

    nft_count = await count_user_nfts(winner_id)
    nft_given = False
    if nft_count < MAX_NFT:
        await buy_nft_from_shop(winner_id, nft_id, 0)
        nft_given = True

    # ─── Формируем итоговый текст для ВСЕХ ───
    top_bids = sorted(participants, key=lambda x: x[3], reverse=True)
    result_text = (
        f"🏁 АУКЦИОН ЗАВЕРШЁН!\n"
        f"══════════════════════\n\n"
        f"🏷 {event_name}\n"
        f"🎨 Приз: {emoji} {nft_name}\n"
        f"✨ {_rarity_label(rarity)}\n"
        f"📈 +{fnum(income)} 💢/ч\n\n"
        f"🏆 ПОБЕДИТЕЛЬ: {wname}\n"
        f"💢 Ставка: {fnum(winner_bid)} 💢\n\n"
    )
    if len(top_bids) > 1:
        result_text += "📊 ИТОГИ:\n┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        for i, (p_uid, p_uname, _, p_bid) in enumerate(top_bids, 1):
            pn = f"@{p_uname}" if p_uname else f"ID:{p_uid}"
            medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"#{i}")
            mark = " 🏆" if p_uid == winner_id else " ❌"
            result_text += f"  {medal} {pn}: {fnum(p_bid)} 💢{mark}\n"
        result_text += "\n"
    result_text += "══════════════════════"

    # ─── Рассылка итогов ВСЕМ пользователям ───
    participant_ids = {p[0] for p in participants}
    all_notify_ids = broadcast_user_ids | participant_ids

    for b_uid in all_notify_ids:
        if b_uid == winner_id:
            continue  # победителю отдельно
        # Проигравшему — персональное с инфо о потере ставки
        if b_uid in participant_ids:
            p_bid = next((p[3] for p in participants if p[0] == b_uid), 0)
            try:
                await bot.send_message(
                    b_uid,
                    result_text + f"\n\n❌ Вы проиграли!\n💢 Ваша ставка ({fnum(p_bid)} 💢) сгорела.",
                )
            except Exception:
                pass
        else:
            # Не участвовал — просто итоги
            try:
                await bot.send_message(b_uid, result_text)
            except Exception:
                pass

    # Уведомляем победителя
    prize_text = f"🎨 Вы получили {emoji} {nft_name}!" if nft_given else f"❌ НФТ не выдан (лимит {MAX_NFT}), но вы победили!"
    try:
        await bot.send_message(
            winner_id,
            result_text + f"\n\n🎉 ВЫ ПОБЕДИЛИ!\n{prize_text}",
        )
    except Exception:
        pass


# ═══════════════════════════════════════════════════════
#  ❌ Игнорировать аукцион
# ═══════════════════════════════════════════════════════
@router.callback_query(F.data.regexp(r"^evt_ignore_\d+$"))
async def event_ignore(call: CallbackQuery):
    """Пользователь игнорирует аукцион — удаляем его сообщение."""
    try:
        await call.message.delete()
    except Exception:
        await call.answer("ОК", show_alert=False)
    # Удаляем из tracked messages
    event_id = int(call.data.split("_")[-1])
    from database import get_db
    db = await get_db()
    await db.execute(
        "DELETE FROM auction_messages WHERE event_id = ? AND chat_id = ? AND message_id = ?",
        (event_id, call.from_user.id, call.message.message_id),
    )
    await db.commit()


# ═══════════════════════════════════════════════════════
#  🏷 СТАВКА В АУКЦИОНЕ (юзеры)
# ═══════════════════════════════════════════════════════
@router.callback_query(F.data.regexp(r"^evt_join_\d+$"))
async def event_join_start(call: CallbackQuery, state: FSMContext):
    """Показать окно ввода ставки для аукциона."""
    uid = call.from_user.id
    event_id = int(call.data.split("_")[-1])

    event = await get_event(event_id)
    if not event:
        return await call.answer("❌ Аукцион не найден", show_alert=True)
    if event[5] != "active":
        return await call.answer("❌ Аукцион уже завершён!", show_alert=True)

    min_bet = event[3]
    nft_name = event[2]
    rarity = event[9]
    income_val = event[10]
    emoji = _rarity_emoji(rarity)

    user = await get_user(uid)
    if not user:
        return await call.answer("❌ /start", show_alert=True)

    count = await count_event_participants(event_id)
    current_bid = await get_user_event_bid(event_id, uid)

    # Проверка лимита участников
    if current_bid is None and count >= MAX_AUCTION_PARTICIPANTS:
        return await call.answer(
            f"❌ Все {MAX_AUCTION_PARTICIPANTS} мест заняты!",
            show_alert=True,
        )

    participants = await get_event_participants(event_id)
    top_bids = sorted(participants, key=lambda x: x[3], reverse=True)[:10]

    text = (
        f"🏷 АУКЦИОН: {event[1]}\n"
        f"══════════════════════\n\n"
        f"┠🎨 Приз: {emoji} {nft_name}\n"
        f"┠✨ {_rarity_label(rarity)}\n"
        f"┠📈 Доход: +{fnum(income_val)} 💢/ч\n"
        f"┠💢 Мин. ставка: {fnum(min_bet)} 💢\n"
        f"┠⏱ Длительность: {event[4]} мин\n"
        f"┗👥 Участников: {count}/{MAX_AUCTION_PARTICIPANTS}\n\n"
    )

    if top_bids:
        text += "📊 ТОП СТАВОК:\n┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        for i, (p_uid, p_uname, _, p_bid) in enumerate(top_bids, 1):
            pn = f"@{p_uname}" if p_uname else f"ID:{p_uid}"
            medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"#{i}")
            you = " ← ВЫ" if p_uid == uid else ""
            text += f"  {medal} {pn}: {fnum(p_bid)} 💢{you}\n"
        text += "\n"

    if current_bid is not None:
        text += (
            f"📌 Ваша ставка: {fnum(current_bid)} 💢\n"
            f"💳 Баланс: {fnum(user['clicks'])} 💢\n\n"
            f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            f"💡 Повысить ставку!\n"
            f"Введите НОВУЮ сумму (> {fnum(current_bid)} 💢):"
        )
    else:
        text += (
            f"💳 Баланс: {fnum(user['clicks'])} 💢\n\n"
            f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            f"Введите сумму ставки (мин. {fnum(min_bet)} 💢):"
        )

    await state.set_state(EventBidStates.waiting_bid)
    await state.update_data(bid_event_id=event_id)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data=f"evt_join_{event_id}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="events_list")],
    ])
    try:
        await call.message.edit_text(text, reply_markup=kb)
    except Exception:
        await call.message.answer(text, reply_markup=kb)
    await call.answer()


@router.message(EventBidStates.waiting_bid)
async def event_place_bid(message: Message, state: FSMContext):
    """Обработка ввода суммы ставки."""
    uid = message.from_user.id
    data = await state.get_data()
    event_id = data.get("bid_event_id")

    if not event_id:
        await state.clear()
        return await message.answer("❌ Ошибка. Попробуйте снова.")

    event = await get_event(event_id)
    if not event or event[5] != "active":
        await state.clear()
        return await message.answer("❌ Аукцион завершён или не найден.")

    try:
        bid = float(message.text.strip().replace(",", ".").replace(" ", ""))
        assert bid > 0
    except (ValueError, AssertionError, AttributeError):
        return await message.answer("❌ Введите положительное число:")

    min_bet = event[3]
    user = await get_user(uid)
    if not user:
        await state.clear()
        return await message.answer("❌ /start")

    current_bid = await get_user_event_bid(event_id, uid)

    if current_bid is not None:
        # Повышение ставки
        if bid <= current_bid:
            return await message.answer(
                f"❌ Новая ставка должна быть > {fnum(current_bid)} 💢!"
            )
        extra = bid - current_bid
        if user["clicks"] < extra:
            return await message.answer(
                f"❌ Нужно ещё {fnum(extra)} 💢! (баланс: {fnum(user['clicks'])} 💢)"
            )
        await update_clicks(uid, -extra)
        await update_event_bid(event_id, uid, bid)
        await state.clear()

        count = await count_event_participants(event_id)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📊 Обновить ставки", callback_data=f"evt_join_{event_id}")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="events_list")],
        ])
        await message.answer(
            f"✅ СТАВКА ПОВЫШЕНА!\n"
            f"══════════════════════\n\n"
            f"┠🎯 {event[1]}\n"
            f"┠💢 Ваша ставка: {fnum(bid)} 💢\n"
            f"┠💰 Списано доп.: {fnum(extra)} 💢\n"
            f"┗👥 Участников: {count}/{MAX_AUCTION_PARTICIPANTS}\n\n"
            f"══════════════════════",
            reply_markup=kb,
        )
    else:
        # Первая ставка — проверяем лимит
        count = await count_event_participants(event_id)
        if count >= MAX_AUCTION_PARTICIPANTS:
            await state.clear()
            return await message.answer(
                f"❌ Все {MAX_AUCTION_PARTICIPANTS} мест заняты!"
            )

        if bid < min_bet:
            return await message.answer(
                f"❌ Минимальная ставка: {fnum(min_bet)} 💢!"
            )
        if user["clicks"] < bid:
            return await message.answer(
                f"❌ Недостаточно кликов! (баланс: {fnum(user['clicks'])} 💢)"
            )
        await update_clicks(uid, -bid)
        ok = await join_event(event_id, uid, bid)
        if not ok:
            await update_event_bid(event_id, uid, bid)
        await state.clear()

        count = await count_event_participants(event_id)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📊 Обновить ставки", callback_data=f"evt_join_{event_id}")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="events_list")],
        ])
        await message.answer(
            f"✅ СТАВКА ПРИНЯТА!\n"
            f"══════════════════════\n\n"
            f"┠🎯 {event[1]}\n"
            f"┠💢 Ваша ставка: {fnum(bid)} 💢\n"
            f"┗👥 Участников: {count}/{MAX_AUCTION_PARTICIPANTS}\n\n"
            f"══════════════════════\n"
            f"🏷 Ждите завершения аукциона!",
            reply_markup=kb,
        )

    # Обновить все сообщения рассылки после новой ставки
    nft_name = event[2]
    rarity_v = event[9]
    income_v = event[10]
    status_text = await _build_auction_status(
        event_id, event[1], nft_name, rarity_v, income_v, min_bet, event[4],
    )
    new_count = await count_event_participants(event_id)
    if new_count < MAX_AUCTION_PARTICIPANTS:
        upd_kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🏷 Сделать ставку!", callback_data=f"evt_join_{event_id}"),
                InlineKeyboardButton(text="❌ Игнорировать", callback_data=f"evt_ignore_{event_id}"),
            ],
        ])
    else:
        upd_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📊 Смотреть", callback_data=f"evt_join_{event_id}")],
        ])
    await _update_all_auction_messages(message.bot, event_id, status_text, upd_kb)


# ═══════════════════════════════════════════════════════
#  🏷 СПИСОК АКТИВНЫХ АУКЦИОНОВ
# ═══════════════════════════════════════════════════════
@router.callback_query(F.data == "events_list")
async def events_list(call: CallbackQuery):
    events = await get_active_events()
    if not events:
        text = (
            "🏷 АУКЦИОНЫ\n"
            "══════════════════════\n\n"
            "📭 Нет активных аукционов.\n\n"
            "══════════════════════"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_page:1")],
        ])
        await call.message.edit_text(text, reply_markup=kb)
        return await call.answer()

    text = "🏷 АКТИВНЫЕ АУКЦИОНЫ\n══════════════════════\n\n"
    kb_rows = []
    for ev in events:
        eid = ev[0]
        ename = ev[1]
        nft_n = ev[2]
        ebet = ev[3]
        rar = ev[9]
        inc = ev[10]
        emoji = _rarity_emoji(rar)
        cnt = await count_event_participants(eid)
        top = await get_highest_bidder(eid)
        top_bid = fnum(top[3]) if top else "0"
        text += (
            f"🎯 {ename}\n"
            f"  {emoji} {nft_n} │ 📈 +{fnum(inc)}/ч\n"
            f"  💢 мин.{fnum(ebet)} │ 🏷 макс.{top_bid} │ 👥 {cnt}/{MAX_AUCTION_PARTICIPANTS}\n\n"
        )
        kb_rows.append([InlineKeyboardButton(
            text=f"🏷 {ename} ({cnt} уч.)",
            callback_data=f"evt_join_{eid}",
        )])
    text += "══════════════════════"
    kb_rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_page:1")])
    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))
    await call.answer()
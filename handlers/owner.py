# ======================================================
# OWNER — Поддержка + Панель владельца (кнопочный)
# ======================================================

import aiosqlite
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from config import DB_NAME, OWNER_ID
from states import SupportStates, OwnerStates
from database import (
    get_user, create_ticket, update_clicks, count_users,
    create_nft_template, get_all_nft_templates, delete_nft_template,
    ban_user, unban_user,
    is_admin, add_admin, remove_admin, get_all_admins,
    create_admin_key, get_all_admin_keys, get_admin_actions,
    log_admin_action,
    get_open_tickets, get_ticket_by_id, get_ticket_replies,
    add_ticket_reply, update_ticket_status,
    get_banned_users, count_banned_users, get_user_tickets,
    get_users_page, count_users_all,
    get_chat_log_messages, get_recent_chats, chat_get_history_for_user,
    reset_user_clicks, reset_user_progress, reset_user_all,
    claim_ticket,
    clear_all_chat_logs, clear_chat_log,
)
from handlers.common import fnum
from keyboards import (
    support_menu_kb, back_support_kb, back_menu_kb, owner_panel_kb,
    owner_nft_publish_kb, owner_back_panel_kb, owner_nft_list_kb,
    owner_admins_kb,
)

router = Router()


# ════════════════════════════════════════════════════════
#  УТИЛИТЫ
# ════════════════════════════════════════════════════════
def _is_owner(uid: int) -> bool:
    return uid == OWNER_ID


# ---- Настройки (key-value в БД) ----
_SETTINGS_DEFAULTS = {
    "base_click_power": "0.05",
    "chat_search_cost": "50",
    "max_nft":          "5",
    "ref_first_clicks": "200",
    "ref_first_power":  "0.5",
    "ref_each_clicks":  "100",
    "ref_each_power":   "0.5",
    "crit_chance":      "5",
    "crit_multiplier":  "5",
}

_SETTINGS_LABELS = {
    "base_click_power": "⚡ Базовая сила клика",
    "chat_search_cost": "💬 Цена поиска чата",
    "max_nft":          "🎨 Макс НФТ у игрока",
    "ref_first_clicks": "🔗 Реф 1-й бонус (💢)",
    "ref_first_power":  "🔗 Реф 1-й бонус (сила)",
    "ref_each_clicks":  "🔗 Реф каждый (💢)",
    "ref_each_power":   "🔗 Реф каждый (сила)",
    "crit_chance":      "🎯 Шанс крита (%)",
    "crit_multiplier":  "💥 Множитель крита",
}


async def get_setting(key: str) -> str:
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("SELECT value FROM bot_settings WHERE key = ?", (key,))
        row = await cur.fetchone()
    return row[0] if row else _SETTINGS_DEFAULTS.get(key, "0")


async def set_setting(key: str, value: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT OR REPLACE INTO bot_settings (key, value) VALUES (?, ?)",
            (key, value),
        )
        await db.commit()


async def get_all_settings() -> dict:
    result = dict(_SETTINGS_DEFAULTS)
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("SELECT key, value FROM bot_settings")
        for k, v in await cur.fetchall():
            result[k] = v
    return result


def _apply_setting_runtime(key: str, value: str):
    import config
    v = float(value)
    mapping = {
        "base_click_power": ("BASE_CLICK_POWER", v),
        "chat_search_cost": ("CHAT_SEARCH_COST", v),
        "max_nft":          ("MAX_NFT", int(v)),
        "ref_first_clicks": ("REF_FIRST_CLICKS", v),
        "ref_first_power":  ("REF_FIRST_POWER", v),
        "ref_each_clicks":  ("REF_EACH_CLICKS", v),
        "ref_each_power":   ("REF_EACH_POWER", v),
    }
    if key in mapping:
        attr, val = mapping[key]
        setattr(config, attr, val)


# ══════════ 7. ПОДДЕРЖКА (для всех) ══════════
@router.callback_query(F.data == "support_menu")
async def show_support(call: CallbackQuery, state: FSMContext = None):
    if state:
        await state.clear()
    text = (
        "📞 ЦЕНТР ПОДДЕРЖКИ\n"
        "══════════════════════\n\n"
        "🚩 Жалоба — сообщить о нарушении\n"
        "🐛 Проблема — баг или ошибка\n"
        "📨 Мои обращения — история тикетов\n\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        "Выберите тип обращения ниже:"
    )
    await call.message.edit_text(text, reply_markup=support_menu_kb())
    await call.answer()



@router.callback_query(F.data == "support_complaint")
async def ask_complaint(call: CallbackQuery, state: FSMContext):
    await state.set_state(SupportStates.waiting_complaint)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="support_menu")],
    ])
    await call.message.edit_text(
        "🚩 ЖАЛОБА\n"
        "══════════════════════\n\n"
        "📝 Опишите нарушение подробно:\n"
        "• Что произошло?\n"
        "• Укажите ID нарушителя (если знаете)\n\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        "✏️ Введите текст жалобы:",
        reply_markup=kb,
    )
    await call.answer()


@router.message(SupportStates.waiting_complaint)
async def save_complaint(message: Message, state: FSMContext):
    txt = (message.text or "").strip()
    if not txt:
        return await message.answer("❌ Введите текст жалобы.")
    await create_ticket(message.from_user.id, "complaint", txt)
    await state.clear()
    try:
        uname = message.from_user.username
        name = f"@{uname}" if uname else f"ID:{message.from_user.id}"
        await message.bot.send_message(
            OWNER_ID,
            f"🔔 НОВАЯ ЖАЛОБА\n"
            f"══════════════════════\n\n"
            f"👤 От: {name} ({message.from_user.id})\n"
            f"💬 Текст: {txt[:200]}\n\n"
            f"══════════════════════",
        )
    except Exception:
        pass
    await message.answer(
        "✅ ЖАЛОБА ОТПРАВЛЕНА\n"
        "══════════════════════\n\n"
        "📋 Ваше обращение зарегистрировано.\n"
        "⏳ Ожидайте ответа администрации.\n\n"
        "Вы можете отслеживать статус в\n"
        "\"📨 Мои обращения\"",
        reply_markup=back_support_kb(),
    )


@router.callback_query(F.data == "support_problem")
async def ask_problem(call: CallbackQuery, state: FSMContext):
    await state.set_state(SupportStates.waiting_problem)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="support_menu")],
    ])
    await call.message.edit_text(
        "🐛 ПРОБЛЕМА / БАГ\n"
        "══════════════════════\n\n"
        "📝 Опишите проблему подробно:\n"
        "• Что не работает?\n"
        "• Когда это случилось?\n"
        "• Шаги для воспроизведения\n\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        "✏️ Введите описание:",
        reply_markup=kb,
    )
    await call.answer()


@router.message(SupportStates.waiting_problem)
async def save_problem(message: Message, state: FSMContext):
    txt = (message.text or "").strip()
    if not txt:
        return await message.answer("❌ Введите описание проблемы.")
    await create_ticket(message.from_user.id, "problem", txt)
    await state.clear()
    try:
        uname = message.from_user.username
        name = f"@{uname}" if uname else f"ID:{message.from_user.id}"
        await message.bot.send_message(
            OWNER_ID,
            f"🔔 НОВАЯ ПРОБЛЕМА\n"
            f"══════════════════════\n\n"
            f"👤 От: {name} ({message.from_user.id})\n"
            f"🐛 Текст: {txt[:200]}\n\n"
            f"══════════════════════",
        )
    except Exception:
        pass
    await message.answer(
        "✅ ОБРАЩЕНИЕ ОТПРАВЛЕНО\n"
        "══════════════════════\n\n"
        "🐛 Ваша проблема зарегистрирована.\n"
        "⏳ Ожидайте ответа администрации.\n\n"
        "Отслеживайте статус в\n"
        "\"📨 Мои обращения\"",
        reply_markup=back_support_kb(),
    )


# ══════════ МОИ ОБРАЩЕНИЯ (для пользователей) ══════════
@router.callback_query(F.data == "support_my_tickets")
async def support_my_tickets(call: CallbackQuery):
    uid = call.from_user.id
    rows = await get_user_tickets(uid, 10)

    if not rows:
        text = (
            "📨 МОИ ОБРАЩЕНИЯ\n"
            "══════════════════════\n\n"
            "📭 У вас пока нет обращений.\n\n"
            "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            "Создайте новое обращение через\n"
            "меню поддержки."
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Поддержка", callback_data="support_menu")],
        ])
        await call.message.edit_text(text, reply_markup=kb)
        return await call.answer()

    _status_icon = {
        "open":     "🟡 Открыт",
        "accepted": "🟢 В работе",
        "rejected": "🔴 Отклонён",
        "closed":   "🔒 Закрыт",
    }
    _type_icon = {"complaint": "🚩", "problem": "🐛"}

    text = "📨 МОИ ОБРАЩЕНИЯ\n══════════════════════\n\n"
    for tid, ttype, msg, status, dt in rows:
        icon = _type_icon.get(ttype, "📋")
        st = _status_icon.get(status, status)
        short = msg[:40] + "…" if len(msg) > 40 else msg
        dt_str = (dt or "")[:10]
        text += (
            f"{icon} Тикет #{tid}\n"
            f"   📌 {st}  │  📅 {dt_str}\n"
            f"   💬 {short}\n\n"
        )
    text += "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\nНажмите на тикет для подробностей:"

    kb = []
    for tid, ttype, msg, status, dt in rows:
        icon = _type_icon.get(ttype, "📋")
        kb.append([InlineKeyboardButton(
            text=f"{icon} #{tid} — Подробнее",
            callback_data=f"uticket_view_{tid}",
        )])
    kb.append([InlineKeyboardButton(text="🔄 Обновить", callback_data="support_my_tickets")])
    kb.append([InlineKeyboardButton(text="⬅️ Поддержка", callback_data="support_menu")])
    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await call.answer()


@router.callback_query(F.data.regexp(r"^uticket_view_\d+$"))
async def user_ticket_view(call: CallbackQuery):
    """Подробный просмотр тикета пользователем + диалог."""
    uid = call.from_user.id
    tid = int(call.data.split("_")[-1])
    ticket = await get_ticket_by_id(tid)
    if not ticket or ticket["user_id"] != uid:
        return await call.answer("❌ Тикет не найден", show_alert=True)

    replies = await get_ticket_replies(tid)

    _status_icon = {
        "open":     "🟡 Ожидает рассмотрения",
        "accepted": "🟢 Принят — в работе",
        "rejected": "🔴 Отклонён",
        "closed":   "🔒 Закрыт",
    }
    _type_name = {"complaint": "🚩 Жалоба", "problem": "🐛 Проблема"}

    text = (
        f"📋 ТИКЕТ #{tid}\n"
        f"══════════════════════\n\n"
        f"┠📝 Тип: {_type_name.get(ticket['type'], ticket['type'])}\n"
        f"┠📅 Создан: {(ticket['created_at'] or '')[:16]}\n"
        f"┗📌 Статус: {_status_icon.get(ticket['status'], ticket['status'])}\n\n"
        f"💬 Ваше сообщение:\n{ticket['message']}\n\n"
    )

    if replies:
        text += "═══ ДИАЛОГ ═══\n\n"
        for rid, sid, msg, dt in replies:
            if sid == uid:
                who = "👤 Вы"
            else:
                who = "👑 Администрация"
            text += f"  {who}  │  {(dt or '')[:16]}\n  {msg}\n\n"

    text += "══════════════════════"

    kb_rows = []
    # Можно ответить, только если тикет не закрыт
    if ticket["status"] not in ("closed", "rejected"):
        kb_rows.append([InlineKeyboardButton(
            text="💬 Ответить", callback_data=f"uticket_reply_{tid}",
        )])
    kb_rows.append([InlineKeyboardButton(text="⬅️ Мои обращения", callback_data="support_my_tickets")])
    kb_rows.append([InlineKeyboardButton(text="🏠 В меню", callback_data="menu")])

    try:
        await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))
    except Exception:
        await call.message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))
    await call.answer()


@router.callback_query(F.data.regexp(r"^uticket_reply_\d+$"))
async def user_ticket_reply_start(call: CallbackQuery, state: FSMContext):
    """Пользователь начинает отвечать на свой тикет."""
    tid = int(call.data.split("_")[-1])
    ticket = await get_ticket_by_id(tid)
    if not ticket or ticket["user_id"] != call.from_user.id:
        return await call.answer("❌", show_alert=True)

    await state.set_state(SupportStates.waiting_reply)
    await state.update_data(reply_ticket_id=tid)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Отмена", callback_data=f"uticket_view_{tid}")],
    ])
    await call.message.edit_text(
        f"💬 ОТВЕТ НА ТИКЕТ #{tid}\n"
        "══════════════════════\n\n"
        "✏️ Введите ваше сообщение:",
        reply_markup=kb,
    )
    await call.answer()


@router.message(SupportStates.waiting_reply)
async def user_ticket_reply_save(message: Message, state: FSMContext):
    """Сохранить ответ пользователя и уведомить админов."""
    data = await state.get_data()
    tid = data.get("reply_ticket_id")
    txt = (message.text or "").strip()
    if not txt:
        return await message.answer("❌ Введите текст сообщения.")

    await state.clear()
    ticket = await get_ticket_by_id(tid)
    if not ticket:
        return await message.answer("❌ Тикет не найден.", reply_markup=back_support_kb())

    await add_ticket_reply(tid, message.from_user.id, txt)

    # Уведомляем владельца + клеймнувшего админа
    uname = message.from_user.username
    name = f"@{uname}" if uname else f"ID:{message.from_user.id}"
    notify_text = (
        f"💬 ОТВЕТ ИГРОКА ПО ТИКЕТУ #{tid}\n"
        f"══════════════════════\n\n"
        f"👤 От: {name}\n"
        f"💬 {txt[:300]}\n\n"
        f"══════════════════════"
    )
    notified = set()
    claimed = ticket["claimed_by"] if ticket["claimed_by"] else None
    for target in [OWNER_ID, claimed]:
        if target and target not in notified:
            notified.add(target)
            try:
                await message.bot.send_message(target, notify_text)
            except Exception:
                pass

    await message.answer(
        f"✅ Сообщение отправлено!\n\n"
        f"💬 Ваш ответ по тикету #{tid} доставлен\n"
        f"администрации.",
        reply_markup=back_support_kb(),
    )


# ════════════════════════════════════════════════════════
#  ПАНЕЛЬ ВЛАДЕЛЬЦА
# ════════════════════════════════════════════════════════
@router.message(Command("owner"))
async def cmd_owner(message: Message, state: FSMContext):
    if not _is_owner(message.from_user.id):
        return await message.answer("❌ Нет доступа.")
    await state.clear()
    await message.answer(
        "👑 ПАНЕЛЬ ВЛАДЕЛЬЦА (1/2)\n══════════════════════\nВыберите действие:",
        reply_markup=owner_panel_kb(0),
    )


@router.callback_query(F.data == "owner_panel")
async def cb_owner_panel(call: CallbackQuery, state: FSMContext):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    await state.clear()
    await call.message.edit_text(
        "👑 ПАНЕЛЬ ВЛАДЕЛЬЦА (1/2)\n══════════════════════\nВыберите действие:",
        reply_markup=owner_panel_kb(0),
    )
    await call.answer()


@router.callback_query(F.data.startswith("owner_panel_page:"))
async def cb_owner_panel_page(call: CallbackQuery, state: FSMContext):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    await state.clear()
    page = int(call.data.split(":")[1])
    label = f"({page + 1}/2)"
    await call.message.edit_text(
        f"👑 ПАНЕЛЬ ВЛАДЕЛЬЦА {label}\n══════════════════════\nВыберите действие:",
        reply_markup=owner_panel_kb(page),
    )
    await call.answer()


# ════════════════════════════════════════════════════════
#  📊 СТАТИСТИКА
# ════════════════════════════════════════════════════════
@router.callback_query(F.data == "owner_stats")
async def owner_stats(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)

    async with aiosqlite.connect(DB_NAME) as db:
        total = (await (await db.execute("SELECT COUNT(*) FROM users")).fetchone())[0]
        active = (await (await db.execute("SELECT COUNT(*) FROM users WHERE clicks > 0")).fetchone())[0]
        banned = (await (await db.execute("SELECT COUNT(*) FROM users WHERE is_banned = 1")).fetchone())[0]
        total_clicks = (await (await db.execute("SELECT COALESCE(SUM(total_clicks),0) FROM users")).fetchone())[0]
        tickets_open = (await (await db.execute("SELECT COUNT(*) FROM tickets WHERE status='open'")).fetchone())[0]
        nft_active = (await (await db.execute("SELECT COUNT(*) FROM nft_templates WHERE status='active'")).fetchone())[0]
        nft_sold = (await (await db.execute("SELECT COUNT(*) FROM nft_templates WHERE status='sold'")).fetchone())[0]
        market_lots = (await (await db.execute("SELECT COUNT(*) FROM nft_market WHERE status='open'")).fetchone())[0]

    text = (
        "📊 СТАТИСТИКА\n"
        "══════════════════════\n\n"
        f"┠👥 Всего игроков: {total}\n"
        f"┠🟢 Активных: {active}\n"
        f"┠🔴 Забанено: {banned}\n"
        f"┠💢 Кликов всего: {int(total_clicks):,}\n"
        f"┠📋 Тикетов: {tickets_open}\n"
        f"┠🎨 НФТ актив: {nft_active}\n"
        f"┠✅ НФТ продано: {nft_sold}\n"
        f"┗🏪 Лотов: {market_lots}\n\n"
        "══════════════════════"
    )
    await call.message.edit_text(text, reply_markup=owner_back_panel_kb())
    await call.answer()


# ════════════════════════════════════════════════════════
#  👥 УЧАСТНИКИ (пагинация по 5 с кнопками по каждому)
# ════════════════════════════════════════════════════════
PAGE_SIZE_USERS = 5


@router.callback_query(F.data.startswith("owner_users"))
async def owner_users(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)

    # owner_users / owner_users:3
    parts = call.data.split(":")
    page = int(parts[1]) if len(parts) > 1 else 0
    if page < 0:
        page = 0

    total = await count_users_all()
    total_pages = max(1, (total + PAGE_SIZE_USERS - 1) // PAGE_SIZE_USERS)
    if page >= total_pages:
        page = total_pages - 1

    offset = page * PAGE_SIZE_USERS
    rows = await get_users_page(limit=PAGE_SIZE_USERS, offset=offset)

    if not rows:
        text = "👥 УЧАСТНИКИ\n══════════════════════\n\nНет пользователей."
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Панель", callback_data="owner_panel")],
        ])
        await call.message.edit_text(text, reply_markup=kb)
        return await call.answer()

    text = f"👥 УЧАСТНИКИ  ({page + 1}/{total_pages})  Всего: {total}\n══════════════════════\n\n"
    kb_rows = []
    for i, (uid, uname, clicks, rank, is_banned) in enumerate(rows, offset + 1):
        name = f"@{uname}" if uname else "Аноним"
        s = "🔴" if is_banned else "🟢"
        text += f"{s} #{i} {name}\n   ID: {uid} │ 💢 {fnum(clicks)} │ ⭐ {rank}\n\n"

        # Строка 1: Бан/Разбан + Чаты
        row1 = []
        if is_banned:
            row1.append(InlineKeyboardButton(
                text=f"✅ Разбан",
                callback_data=f"owner_quick_unban:{uid}:{page}",
            ))
        else:
            row1.append(InlineKeyboardButton(
                text=f"🔨 Бан",
                callback_data=f"owner_quick_ban:{uid}:{page}",
            ))
        row1.append(InlineKeyboardButton(
            text=f"👀 Чаты",
            callback_data=f"oticket_chats_{uid}",
        ))
        kb_rows.append(row1)

        # Строка 2: Сброс кликов + Сброс прогресса + Сброс всё
        kb_rows.append([
            InlineKeyboardButton(text="🗑 Клики", callback_data=f"ou_rst_clk:{uid}:{page}"),
            InlineKeyboardButton(text="🔄 Прогресс", callback_data=f"ou_rst_prg:{uid}:{page}"),
            InlineKeyboardButton(text="💣 Всё", callback_data=f"ou_rst_all:{uid}:{page}"),
        ])

    text += "══════════════════════"

    # Навигация
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️ Назад", callback_data=f"owner_users:{page - 1}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="Далее ▶️", callback_data=f"owner_users:{page + 1}"))
    if nav:
        kb_rows.append(nav)
    kb_rows.append([InlineKeyboardButton(text="⬅️ Панель", callback_data="owner_panel")])
    kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)

    try:
        await call.message.edit_text(text, reply_markup=kb)
    except Exception:
        await call.message.answer(text, reply_markup=kb)
    await call.answer()


@router.callback_query(F.data.startswith("owner_quick_ban:"))
async def owner_quick_ban(call: CallbackQuery):
    """Quick ban from user list — show duration picker."""
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    parts = call.data.split(":")
    uid = int(parts[1])
    page = int(parts[2]) if len(parts) > 2 else 0

    u = await get_user(uid)
    name = f"@{u['username']}" if u and u["username"] else "Аноним"

    text = (
        f"🔨 БАН: {name} (ID: {uid})\n"
        "══════════════════════\n\n"
        "Выберите срок бана:"
    )
    kb = _owner_ban_duration_kb(uid, back_cb=f"owner_users:{page}")
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


@router.callback_query(F.data.startswith("owner_quick_unban:"))
async def owner_quick_unban(call: CallbackQuery):
    """Quick unban from user list."""
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    parts = call.data.split(":")
    uid = int(parts[1])

    await unban_user(uid)
    try:
        await call.bot.send_message(uid, "🟢 Вы разблокированы! Добро пожаловать.")
    except Exception:
        pass
    await call.answer(f"✅ Пользователь {uid} разбанен!", show_alert=True)
    # Обновляем список
    call.data = f"owner_users:{parts[2]}" if len(parts) > 2 else "owner_users"
    await owner_users(call)


# ─── Быстрый сброс из списка участников ───
@router.callback_query(F.data.startswith("ou_rst_clk:"))
async def ou_rst_clicks(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    parts = call.data.split(":")
    uid = int(parts[1])
    await reset_user_clicks(uid)
    await call.answer(f"🗑 Клики {uid} обнулены!", show_alert=True)
    call.data = f"owner_users:{parts[2]}" if len(parts) > 2 else "owner_users"
    await owner_users(call)


@router.callback_query(F.data.startswith("ou_rst_prg:"))
async def ou_rst_progress(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    parts = call.data.split(":")
    uid = int(parts[1])
    await reset_user_progress(uid)
    await call.answer(f"🔄 Прогресс {uid} сброшен!", show_alert=True)
    call.data = f"owner_users:{parts[2]}" if len(parts) > 2 else "owner_users"
    await owner_users(call)


@router.callback_query(F.data.startswith("ou_rst_all:"))
async def ou_rst_all(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    parts = call.data.split(":")
    uid = int(parts[1])
    await reset_user_all(uid)
    await call.answer(f"💣 Все данные {uid} сброшены!", show_alert=True)
    call.data = f"owner_users:{parts[2]}" if len(parts) > 2 else "owner_users"
    await owner_users(call)


# ════════════════════════════════════════════════════════
#  🔨 БАН (кнопочный) — с выбором срока
# ════════════════════════════════════════════════════════
BAN_DURATIONS = {
    "7":  "1 неделя",
    "14": "2 недели",
    "30": "1 месяц",
    "90": "3 месяца",
    "0":  "♾ Навсегда",
}


def _owner_ban_duration_kb(uid: int, back_cb: str = "owner_panel"):
    """Клавиатура выбора срока бана."""
    kb = []
    for days, label in BAN_DURATIONS.items():
        kb.append([InlineKeyboardButton(
            text=f"🔨 {label}",
            callback_data=f"owner_ban_do:{uid}:{days}",
        )])
    kb.append([InlineKeyboardButton(text="⬅️ Отмена", callback_data=back_cb)])
    return InlineKeyboardMarkup(inline_keyboard=kb)


@router.callback_query(F.data == "owner_ban")
async def owner_ban_start(call: CallbackQuery, state: FSMContext):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    await state.set_state(OwnerStates.waiting_ban_id)
    await call.message.edit_text(
        "🔨 БАН ПОЛЬЗОВАТЕЛЯ\n"
        "══════════════════════\n\n"
        "Введите ID пользователя для бана:",
        reply_markup=owner_back_panel_kb(),
    )
    await call.answer()


@router.message(OwnerStates.waiting_ban_id)
async def owner_ban_choose_duration(message: Message, state: FSMContext):
    if not _is_owner(message.from_user.id):
        return
    try:
        uid = int(message.text.strip())
    except (ValueError, AttributeError):
        return await message.answer("❌ Введите числовой ID:")

    u = await get_user(uid)
    if not u:
        return await message.answer("❌ Пользователь не найден.")

    if uid == OWNER_ID:
        return await message.answer("❌ Нельзя забанить себя!")

    await state.clear()
    name = f"@{u['username']}" if u["username"] else "Аноним"
    await message.answer(
        f"🔨 БАН: {name} (ID: {uid})\n"
        "══════════════════════\n\n"
        "Выберите срок бана:",
        reply_markup=_owner_ban_duration_kb(uid),
    )


@router.callback_query(F.data.startswith("owner_ban_do:"))
async def owner_ban_execute(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)

    parts = call.data.split(":")
    uid = int(parts[1])
    days = int(parts[2])

    u = await get_user(uid)
    if not u:
        return await call.answer("❌ Пользователь не найден", show_alert=True)

    await ban_user(uid, days=days)

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
        reply_markup=owner_back_panel_kb(),
    )
    await call.answer()


# ════════════════════════════════════════════════════════
#  ✅ РАЗБАН (кнопочный)
# ════════════════════════════════════════════════════════
@router.callback_query(F.data == "owner_unban")
async def owner_unban_start(call: CallbackQuery, state: FSMContext):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    await state.set_state(OwnerStates.waiting_unban_id)
    await call.message.edit_text(
        "✅ РАЗБАН ПОЛЬЗОВАТЕЛЯ\n"
        "══════════════════════\n\n"
        "Введите ID пользователя для разбана:",
        reply_markup=owner_back_panel_kb(),
    )
    await call.answer()


@router.message(OwnerStates.waiting_unban_id)
async def owner_unban_process(message: Message, state: FSMContext):
    if not _is_owner(message.from_user.id):
        return
    try:
        uid = int(message.text.strip())
    except (ValueError, AttributeError):
        return await message.answer("❌ Введите числовой ID:")

    u = await get_user(uid)
    if not u:
        return await message.answer("❌ Пользователь не найден.")

    await unban_user(uid)
    await state.clear()

    try:
        await message.bot.send_message(uid, "🟢 Вы разблокированы! Добро пожаловать.")
    except Exception:
        pass

    name = f"@{u['username']}" if u["username"] else "Аноним"
    await message.answer(
        f"✅ Разбанен!\n\n┠🪪 ID: {uid}\n┗👤 {name}",
        reply_markup=owner_panel_kb(),
    )


# ════════════════════════════════════════════════════════
#  � СПИСОК ЗАБАНЕННЫХ (владелец)
# ════════════════════════════════════════════════════════
PAGE_SIZE_BANNED = 4


@router.callback_query(F.data.startswith("owner_banned_list"))
async def owner_banned_list(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)

    parts = call.data.split(":")
    page = int(parts[1]) if len(parts) > 1 else 0
    if page < 0:
        page = 0

    total = await count_banned_users()
    total_pages = max(1, (total + PAGE_SIZE_BANNED - 1) // PAGE_SIZE_BANNED)
    if page >= total_pages:
        page = total_pages - 1

    offset = page * PAGE_SIZE_BANNED
    rows = await get_banned_users(limit=PAGE_SIZE_BANNED, offset=offset)

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
        nav.append(InlineKeyboardButton(text="◀️ Назад", callback_data=f"owner_banned_list:{page - 1}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="Далее ▶️", callback_data=f"owner_banned_list:{page + 1}"))

    kb_rows = []
    if nav:
        kb_rows.append(nav)
    kb_rows.append([InlineKeyboardButton(text="⬅️ Панель", callback_data="owner_panel")])
    kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)

    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


# ════════════════════════════════════════════════════════
#  �💰 ВЫДАТЬ КЛИКИ (кнопочный)
# ════════════════════════════════════════════════════════
@router.callback_query(F.data == "owner_give")
async def owner_give_start(call: CallbackQuery, state: FSMContext):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    await state.set_state(OwnerStates.waiting_give)
    await call.message.edit_text(
        "💰 ВЫДАТЬ КЛИКИ\n"
        "══════════════════════\n\n"
        "Введите в формате:\n"
        "ID  количество\n\n"
        "Пример: 123456789 5000",
        reply_markup=owner_back_panel_kb(),
    )
    await call.answer()


@router.message(OwnerStates.waiting_give)
async def owner_give_process(message: Message, state: FSMContext):
    if not _is_owner(message.from_user.id):
        return
    parts = (message.text or "").split()
    if len(parts) < 2:
        return await message.answer("❌ Формат: ID количество\nПример: 123456789 5000")

    try:
        uid = int(parts[0])
        amount = float(parts[1])
        assert amount > 0
    except (ValueError, AssertionError):
        return await message.answer("❌ ID — число, кол-во — положительное число.")

    u = await get_user(uid)
    if not u:
        return await message.answer("❌ Пользователь не найден.")

    await update_clicks(uid, amount)
    await state.clear()

    try:
        gift_text = (
            "🎁 ПОДАРОК ОТ АДМИНИСТРАЦИИ\n"
            "══════════════════════\n\n"
            f"┠💰 Начислено: +{int(amount):,} 💢\n"
            f"┗📋 Причина: выдача от владельца\n\n"
            "Приятной игры! 🎉\n\n"
            "══════════════════════"
        )
        await message.bot.send_message(uid, gift_text)
    except Exception:
        pass

    name = f"@{u['username']}" if u["username"] else "Аноним"
    await message.answer(
        f"✅ Выдано!\n\n┠👤 {name} (ID: {uid})\n┗💰 +{fnum(amount)} 💢",
        reply_markup=owner_panel_kb(),
    )


# ════════════════════════════════════════════════════════
#  � СБРОС ДАННЫХ УЧАСТНИКА
# ════════════════════════════════════════════════════════
_RESET_MODES = {
    "owner_reset_clicks":   ("clicks",   "🗑 СБРОС КЛИКОВ",   "Баланс кликов будет обнулён."),
    "owner_reset_progress": ("progress", "🔄 СБРОС ПРОГРЕССА", "total_clicks и ранг будут сброшены."),
    "owner_reset_all":      ("all",      "💣 ПОЛНЫЙ СБРОС",    "Клики, прогресс, бонусы, доход — всё обнулится."),
}


@router.callback_query(F.data.in_(set(_RESET_MODES.keys())))
async def owner_reset_start(call: CallbackQuery, state: FSMContext):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    mode, title, desc = _RESET_MODES[call.data]
    await state.set_state(OwnerStates.waiting_reset_user_id)
    await state.update_data(reset_mode=mode)
    await call.message.edit_text(
        f"{title}\n══════════════════════\n\n"
        f"{desc}\n\n"
        "Введите ID пользователя:",
        reply_markup=owner_back_panel_kb(),
    )
    await call.answer()


@router.message(OwnerStates.waiting_reset_user_id)
async def owner_reset_process(message: Message, state: FSMContext):
    if not _is_owner(message.from_user.id):
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
    elif mode == "progress":
        await reset_user_progress(uid)
        label = "🔄 Прогресс сброшен (total_clicks → 0, ранг → 1)"
    else:
        await reset_user_all(uid)
        label = "💣 Все данные сброшены"

    await state.clear()
    await message.answer(
        f"✅ Сброс выполнен!\n\n"
        f"┠👤 {name} (ID: {uid})\n"
        f"┗{label}",
        reply_markup=owner_panel_kb(1),
    )


# ════════════════════════════════════════════════════════
#  �📢 РАССЫЛКА (кнопочный)

# ════════════════════════════════════════════════════════
#  ☢️ СБРОС ВСЕХ ИГРОКОВ
# ════════════════════════════════════════════════════════
@router.callback_query(F.data == "owner_wipe_all")
async def owner_wipe_all_confirm(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    await call.message.edit_text(
        "☢️ СБРОС ВСЕХ ИГРОКОВ\n"
        "══════════════════════\n\n"
        "⚠️ ЭТО УДАЛИТ У ВСЕХ:\n"
        "• Клики и прогресс\n"
        "• Ранги и бонусы\n"
        "• Пассивный доход и ёмкость\n"
        "• Все НФТ и маркетплейс\n\n"
        "❗ Действие необратимо!\n"
        "Вы уверены?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="☢️ ДА, СБРОСИТЬ ВСЕХ", callback_data="owner_wipe_all_yes"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="owner_panel_page:1"),
            ],
        ]),
    )
    await call.answer()


@router.callback_query(F.data == "owner_wipe_all_yes")
async def owner_wipe_all_execute(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    from database import reset_all_players
    await reset_all_players()
    await call.message.edit_text(
        "☢️ СБРОС ВЫПОЛНЕН!\n"
        "══════════════════════\n\n"
        "✅ Все игроки начинают заново.\n"
        "Клики, прогресс, НФТ, доход — обнулены.",
        reply_markup=owner_panel_kb(1),
    )
    await call.answer("✅ Все игроки сброшены!", show_alert=True)


# ════════════════════════════════════════════════════════
@router.callback_query(F.data == "owner_broadcast")
async def owner_broadcast_start(call: CallbackQuery, state: FSMContext):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    await state.set_state(OwnerStates.waiting_broadcast)
    await call.message.edit_text(
        "📢 РАССЫЛКА\n"
        "══════════════════════\n\n"
        "Введите текст рассылки всем игрокам:",
        reply_markup=owner_back_panel_kb(),
    )
    await call.answer()


@router.message(OwnerStates.waiting_broadcast)
async def owner_broadcast_process(message: Message, state: FSMContext):
    if not _is_owner(message.from_user.id):
        return

    # ─── Обычная рассылка ───
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

    await message.answer(
        f"✅ РАССЫЛКА ЗАВЕРШЕНА\n══════════════════════\n\n"
        f"┠📨 Отправлено: {sent}\n┗❌ Ошибок: {fail}",
        reply_markup=owner_panel_kb(),
    )


# ════════════════════════════════════════════════════════
#  📋 ТИКЕТЫ (с диалогом)
# ════════════════════════════════════════════════════════
@router.callback_query(F.data == "owner_tickets")
async def owner_tickets(call: CallbackQuery, state: FSMContext = None):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    if state:
        await state.clear()

    rows = await get_open_tickets(20, viewer_id=call.from_user.id)

    if not rows:
        text = (
            "📋 ТИКЕТЫ / ЖАЛОБЫ\n"
            "══════════════════════\n\n"
            "✨ Нет открытых обращений.\n\n"
            "══════════════════════"
        )
        await call.message.edit_text(text, reply_markup=owner_back_panel_kb())
    else:
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
                callback_data=f"oticket_view_{tid}",
            )])
        kb.append([InlineKeyboardButton(text="⬅️ Панель", callback_data="owner_panel")])
        await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await call.answer()


@router.callback_query(F.data.regexp(r"^oticket_view_\d+$"))
async def owner_ticket_view(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    tid = int(call.data.split("_")[-1])
    ticket = await get_ticket_by_id(tid)
    if not ticket:
        return await call.answer("❌ Тикет не найден", show_alert=True)

    # Claim: владелец автоматически видит все, но помечаем
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
            who = "👑 Админ" if (sid == OWNER_ID or await is_admin(sid)) else "👤 Игрок"
            text += f"  {who}  │  {(dt or '')[:16]}\n  {msg}\n\n"

    text += "══════════════════════"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Принять", callback_data=f"oticket_accept_{tid}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"oticket_reject_{tid}"),
        ],
        [InlineKeyboardButton(text="💬 Ответить", callback_data=f"oticket_reply_{tid}")],
        [InlineKeyboardButton(text="👀 Переписки отправителя", callback_data=f"oticket_chats_{ticket['user_id']}")],
        [InlineKeyboardButton(text="🔒 Закрыть", callback_data=f"oticket_close_{tid}")],
        [InlineKeyboardButton(text="⬅️ Все тикеты", callback_data="owner_tickets")],
    ])
    try:
        await call.message.edit_text(text, reply_markup=kb)
    except Exception:
        await call.message.answer(text, reply_markup=kb)
    await call.answer()

@router.callback_query(F.data.regexp(r"^oticket_reply_\d+$"))
async def owner_ticket_reply_start(call: CallbackQuery, state: FSMContext):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    tid = int(call.data.split("_")[-1])
    await state.set_state(OwnerStates.waiting_ticket_reply)
    await state.update_data(ticket_reply_id=tid)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Отмена", callback_data=f"oticket_view_{tid}")],
    ])
    await call.message.edit_text(
        f"💬 ОТВЕТ НА ТИКЕТ #{tid}\n"
        "══════════════════════\n\n"
        "Введите ваш ответ:",
        reply_markup=kb,
    )
    await call.answer()


@router.message(OwnerStates.waiting_ticket_reply)
async def owner_ticket_reply_save(message: Message, state: FSMContext):
    if not _is_owner(message.from_user.id):
        return
    data = await state.get_data()
    tid = data.get("ticket_reply_id")
    txt = (message.text or "").strip()
    if not txt:
        return await message.answer("❌ Введите текст ответа:")
    await state.clear()
    ticket = await get_ticket_by_id(tid)
    if not ticket:
        return await message.answer("❌ Тикет не найден.", reply_markup=owner_panel_kb())
    await add_ticket_reply(tid, message.from_user.id, txt)
    try:
        await message.bot.send_message(
            ticket["user_id"],
            f"💬 ОТВЕТ ПО ТИКЕТУ #{tid}\n"
            f"══════════════════════\n\n"
            f"👑 Администрация:\n{txt}\n\n"
            f"══════════════════════",
        )
    except Exception:
        pass
    await message.answer(
        f"✅ Ответ отправлен по тикету #{tid}!",
        reply_markup=owner_panel_kb(),
    )


@router.callback_query(F.data.regexp(r"^oticket_accept_\d+$"))
async def owner_ticket_accept(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    tid = int(call.data.split("_")[-1])
    ticket = await get_ticket_by_id(tid)
    if not ticket:
        return await call.answer("❌", show_alert=True)
    await update_ticket_status(tid, "accepted")
    await claim_ticket(tid, call.from_user.id)
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
            callback_data=f"oticket_ban_author_{tid}",
        )],
        [InlineKeyboardButton(
            text="🔨 Забанить другого (по ID)",
            callback_data=f"oticket_ban_other_{tid}",
        )],
        [InlineKeyboardButton(text="📋 Назад к тикету", callback_data=f"oticket_view_{tid}")],
        [InlineKeyboardButton(text="⬅️ Все тикеты", callback_data="owner_tickets")],
    ])
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


@router.callback_query(F.data.regexp(r"^oticket_reject_\d+$"))
async def owner_ticket_reject(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    tid = int(call.data.split("_")[-1])
    ticket = await get_ticket_by_id(tid)
    if not ticket:
        return await call.answer("❌", show_alert=True)
    await update_ticket_status(tid, "rejected")
    try:
        await call.bot.send_message(
            ticket["user_id"],
            f"❌ Ваш тикет #{tid} отклонён.",
        )
    except Exception:
        pass
    await call.answer(f"❌ Тикет #{tid} отклонён!", show_alert=True)
    await owner_tickets(call)


@router.callback_query(F.data.regexp(r"^oticket_close_\d+$"))
async def owner_ticket_close(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    tid = int(call.data.split("_")[-1])
    await update_ticket_status(tid, "closed")
    await call.answer(f"🔒 Тикет #{tid} закрыт!", show_alert=True)
    await owner_tickets(call)


# ════════════════════════════════════════════════════════
#  🎨 СОЗДАНИЕ НФТ
# ════════════════════════════════════════════════════════
def _rarity_label(rarity: int) -> str:
    return {
        1:  "📦 Обычный (100%)",
        2:  "🧩 Необычный (50%)",
        3:  "💎 Редкий (25%)",
        4:  "🔮 Эпический (15%)",
        5:  "👑 Легендарный (10%)",
        6:  "🐉 Мифический (7%)",
        7:  "⚡ Божественный (5%)",
        8:  "🌌 Космический (3%)",
        9:  "♾️ Вечный (2%)",
        10: "🏆 Запредельный (1%)",
    }.get(rarity, "📦 Обычный (100%)")


@router.callback_query(F.data == "owner_nft_create")
async def owner_nft_create(call: CallbackQuery, state: FSMContext):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    await state.set_state(OwnerStates.nft_name)
    await call.message.edit_text(
        "🎨 СОЗДАНИЕ НФТ\n══════════════════════\n\n"
        "Шаг 1/4 — Введите название НФТ:",
        reply_markup=owner_back_panel_kb(),
    )
    await call.answer()


@router.message(OwnerStates.nft_name)
async def owner_nft_step_name(message: Message, state: FSMContext):
    if not _is_owner(message.from_user.id):
        return
    name = (message.text or "").strip()
    if not name or len(name) > 64:
        return await message.answer("❌ 1-64 символа:")
    await state.update_data(nft_name=name)
    await state.set_state(OwnerStates.nft_rarity)
    await message.answer(
        f"✅ Название: {name}\n\n"
        "Шаг 2/4 — Редкость (1-10):\n\n"
        " 1 — 📦 Обычный (100%)\n"
        " 2 — 🧩 Необычный (50%)\n"
        " 3 — 💎 Редкий (25%)\n"
        " 4 — 🔮 Эпический (15%)\n"
        " 5 — 👑 Легендарный (10%)\n"
        " 6 — 🐉 Мифический (7%)\n"
        " 7 — ⚡ Божественный (5%)\n"
        " 8 — 🌌 Космический (3%)\n"
        " 9 — ♾️ Вечный (2%)\n"
        "10 — 🏆 Запредельный (1%)",
    )


@router.message(OwnerStates.nft_rarity)
async def owner_nft_step_rarity(message: Message, state: FSMContext):
    if not _is_owner(message.from_user.id):
        return
    try:
        rarity = int(message.text.strip())
        assert 1 <= rarity <= 10
    except (ValueError, AssertionError, AttributeError):
        return await message.answer("❌ Число от 1 до 10:")
    await state.update_data(nft_rarity=rarity)
    await state.set_state(OwnerStates.nft_income)
    await message.answer(
        f"✅ Редкость: {_rarity_label(rarity)}\n\n"
        "Шаг 3/4 — Доход в час (💢/ч):",
    )


@router.message(OwnerStates.nft_income)
async def owner_nft_step_income(message: Message, state: FSMContext):
    if not _is_owner(message.from_user.id):
        return
    try:
        income = float(message.text.strip().replace(",", "."))
        assert income > 0
    except (ValueError, AssertionError, AttributeError):
        return await message.answer("❌ Положительное число:")
    await state.update_data(nft_income=income)
    await state.set_state(OwnerStates.nft_price)
    await message.answer(f"✅ Доход: +{fnum(income)} 💢/ч\n\nШаг 4/4 — Цена (💢):")


@router.message(OwnerStates.nft_price)
async def owner_nft_step_price(message: Message, state: FSMContext):
    if not _is_owner(message.from_user.id):
        return
    try:
        price = float(message.text.strip().replace(",", "."))
        assert price > 0
    except (ValueError, AssertionError, AttributeError):
        return await message.answer("❌ Положительное число:")
    await state.update_data(nft_price=price)
    await state.set_state(OwnerStates.nft_confirm)

    data = await state.get_data()
    name, rarity, income = data["nft_name"], data["nft_rarity"], data["nft_income"]

    preview = (
        "🎨 ПРЕВЬЮ НФТ\n══════════════════════\n\n"
        f"┠📛 Название: {name}\n"
        f"┠🏷 Редкость: {_rarity_label(rarity)}\n"
        f"┠📈 Доход: +{fnum(income)} 💢/ч\n"
        f"┗💰 Цена: {int(price):,} 💢\n\n"
        "══════════════════════\nОпубликовать?"
    )
    await message.answer(preview, reply_markup=owner_nft_publish_kb())


@router.callback_query(F.data == "owner_nft_publish")
async def owner_nft_publish(call: CallbackQuery, state: FSMContext):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)

    data = await state.get_data()
    name = data.get("nft_name")
    rarity = data.get("nft_rarity")
    income = data.get("nft_income")
    price = data.get("nft_price")

    if not all([name, rarity is not None, income is not None, price is not None]):
        await state.clear()
        return await call.message.edit_text(
            "❌ Данные утеряны.", reply_markup=owner_panel_kb(),
        )

    nft_id = await create_nft_template(name, income, rarity, price, call.from_user.id)
    await state.clear()

    text = (
        "✅ НФТ ОПУБЛИКОВАН!\n══════════════════════\n\n"
        f"┠📛 {name}\n"
        f"┠🏷 {_rarity_label(rarity)}\n"
        f"┠📈 +{fnum(income)} 💢/ч\n"
        f"┠💰 {int(price):,} 💢\n"
        f"┗🆔 #{nft_id}\n\n"
        "Доступен в 🏪 Торговой площадке!"
    )
    await call.message.edit_text(text, reply_markup=owner_panel_kb())
    await call.answer("✅ Опубликовано!", show_alert=True)


@router.callback_query(F.data == "owner_nft_cancel")
async def owner_nft_cancel(call: CallbackQuery, state: FSMContext):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    await state.clear()
    await call.message.edit_text("❌ Отменено.", reply_markup=owner_panel_kb())
    await call.answer()


# ════════════════════════════════════════════════════════
#  🗑 УДАЛИТЬ НФТ
# ════════════════════════════════════════════════════════
@router.callback_query(F.data == "owner_nft_list")
async def owner_nft_list(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    templates = await get_all_nft_templates()
    if not templates:
        await call.message.edit_text(
            "🗑 УДАЛИТЬ НФТ\n══════════════════════\n\nНет НФТ.",
            reply_markup=owner_back_panel_kb(),
        )
    else:
        await call.message.edit_text(
            "🗑 УДАЛИТЬ НФТ\n══════════════════════\n\nВыберите НФТ:",
            reply_markup=owner_nft_list_kb(templates),
        )
    await call.answer()


@router.callback_query(F.data.startswith("owner_nft_del_"))
async def owner_nft_delete(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    nft_id = int(call.data.replace("owner_nft_del_", ""))
    await delete_nft_template(nft_id)
    await call.answer("🗑 Удалён!", show_alert=True)
    templates = await get_all_nft_templates()
    if not templates:
        await call.message.edit_text(
            "🗑 УДАЛИТЬ НФТ\n══════════════════════\n\nНет НФТ.",
            reply_markup=owner_back_panel_kb(),
        )
    else:
        await call.message.edit_text(
            "🗑 УДАЛИТЬ НФТ\n══════════════════════\n\nВыберите НФТ:",
            reply_markup=owner_nft_list_kb(templates),
        )


# ════════════════════════════════════════════════════════
#  ⚙️ НАСТРОЙКИ
# ════════════════════════════════════════════════════════
@router.callback_query(F.data == "owner_settings")
async def owner_settings_menu(call: CallbackQuery, state: FSMContext):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    await state.clear()

    settings = await get_all_settings()

    text = (
        "⚙️ НАСТРОЙКИ БОТА\n"
        "══════════════════════\n\n"
    )
    for key, label in _SETTINGS_LABELS.items():
        val = settings.get(key, _SETTINGS_DEFAULTS[key])
        text += f"┠{label}: {val}\n"
    text += (
        "\n══════════════════════\n"
        "Нажмите для изменения:"
    )

    kb = []
    for key, label in _SETTINGS_LABELS.items():
        val = settings.get(key, _SETTINGS_DEFAULTS[key])
        kb.append([InlineKeyboardButton(
            text=f"✏️ {label} = {val}",
            callback_data=f"oset_{key}",
        )])
    kb.append([InlineKeyboardButton(text="🔄 Сбросить всё", callback_data="oset_reset_all")])
    kb.append([InlineKeyboardButton(text="⬅️ Панель", callback_data="owner_panel")])

    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await call.answer()


@router.callback_query(F.data.startswith("oset_") & ~F.data.startswith("oset_reset"))
async def owner_setting_edit(call: CallbackQuery, state: FSMContext):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)

    key = call.data.replace("oset_", "")
    label = _SETTINGS_LABELS.get(key, key)
    current = await get_setting(key)

    await state.set_state(OwnerStates.waiting_setting_value)
    await state.update_data(setting_key=key)

    text = (
        f"✏️ ИЗМЕНИТЬ НАСТРОЙКУ\n"
        f"══════════════════════\n\n"
        f"┠📋 Параметр: {label}\n"
        f"┗📊 Текущее: {current}\n\n"
        f"══════════════════════\n\n"
        f"Введите новое значение:"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚙️ К настройкам", callback_data="owner_settings")],
        [InlineKeyboardButton(text="⬅️ Панель", callback_data="owner_panel")],
    ])
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


@router.message(OwnerStates.waiting_setting_value)
async def owner_setting_save(message: Message, state: FSMContext):
    if not _is_owner(message.from_user.id):
        return

    data = await state.get_data()
    key = data.get("setting_key")
    if not key:
        await state.clear()
        return await message.answer("❌ Ошибка.", reply_markup=owner_panel_kb())

    value = (message.text or "").strip()
    if not value:
        return await message.answer("❌ Введите значение:")

    try:
        float(value.replace(",", "."))
        value = value.replace(",", ".")
    except ValueError:
        return await message.answer("❌ Введите число:")

    await set_setting(key, value)
    _apply_setting_runtime(key, value)
    await state.clear()

    label = _SETTINGS_LABELS.get(key, key)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚙️ К настройкам", callback_data="owner_settings")],
        [InlineKeyboardButton(text="⬅️ Панель", callback_data="owner_panel")],
    ])
    await message.answer(
        f"✅ СОХРАНЕНО\n══════════════════════\n\n"
        f"┠📋 {label}\n┗📊 Новое: {value}\n\n"
        f"Применено!",
        reply_markup=kb,
    )


@router.callback_query(F.data == "oset_reset_all")
async def owner_settings_reset(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)

    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM bot_settings")
        await db.commit()

    # Восстанавливаем runtime
    import config
    config.BASE_CLICK_POWER = 0.05
    config.CHAT_SEARCH_COST = 50
    config.MAX_NFT = 5
    config.REF_FIRST_CLICKS = 200
    config.REF_FIRST_POWER = 0.5
    config.REF_EACH_CLICKS = 100
    config.REF_EACH_POWER = 0.5

    await call.answer("🔄 Сброшено!", show_alert=True)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚙️ Настройки", callback_data="owner_settings")],
        [InlineKeyboardButton(text="⬅️ Панель", callback_data="owner_panel")],
    ])
    await call.message.edit_text(
        "🔄 Все настройки сброшены к значениям по умолчанию!",
        reply_markup=kb,
    )


# ════════════════════════════════════════════════════════
#  👮 УПРАВЛЕНИЕ АДМИНИСТРАТОРАМИ (только владелец)
# ════════════════════════════════════════════════════════
@router.callback_query(F.data == "owner_admins")
async def owner_admins_menu(call: CallbackQuery, state: FSMContext = None):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    if state:
        await state.clear()
    text = (
        "👮 УПРАВЛЕНИЕ АДМИНИСТРАТОРАМИ\n"
        "══════════════════════\n\n"
        "┠👮 Список — все текущие админы\n"
        "┠🔑 Создать ключ — для назначения\n"
        "┠📋 Все ключи — история ключей\n"
        "┠📊 Лог действий — что делали\n"
        "┗❌ Снять админа — удалить права\n\n"
        "══════════════════════"
    )
    await call.message.edit_text(text, reply_markup=owner_admins_kb())
    await call.answer()


# ─── Список админов ───
@router.callback_query(F.data == "owner_admin_list")
async def owner_admin_list(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)

    admins = await get_all_admins()
    if not admins:
        text = "👮 АДМИНИСТРАТОРЫ\n══════════════════════\n\n😔 Нет назначенных администраторов."
    else:
        text = "👮 АДМИНИСТРАТОРЫ\n══════════════════════\n\n"
        for uid, uname, added_at in admins:
            name = f"@{uname}" if uname else f"ID:{uid}"
            text += f"┠🛡 {name}\n   ID: {uid} │ с {(added_at or '')[:10]}\n\n"
        text += "══════════════════════"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="owner_admins")],
    ])
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


# ─── Создать ключ ───
@router.callback_query(F.data == "owner_admin_genkey")
async def owner_admin_genkey(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)

    key = await create_admin_key(call.from_user.id)
    text = (
        "🔑 КЛЮЧ СОЗДАН\n"
        "══════════════════════\n\n"
        f"┠🔑 Ключ:\n┗ <code>{key}</code>\n\n"
        "Передайте этот ключ пользователю.\n"
        "Он активирует его через /admin\n\n"
        "⚠️ Ключ одноразовый!\n\n"
        "══════════════════════"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔑 Ещё ключ", callback_data="owner_admin_genkey")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="owner_admins")],
    ])
    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await call.answer()


# ─── Все ключи ───
@router.callback_query(F.data == "owner_admin_keys")
async def owner_admin_keys(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)

    keys = await get_all_admin_keys()
    if not keys:
        text = "📋 КЛЮЧИ\n══════════════════════\n\n😔 Ключей нет."
    else:
        text = "📋 КЛЮЧИ АДМИНИСТРАТОРОВ\n══════════════════════\n\n"
        for kid, key, by, used_by, status, created, used_at in keys:
            st = "✅ Активен" if status == "active" else f"🔒 Использован (ID:{used_by})"
            masked = key[:4] + "•" * 12
            text += f"┠🔑 {masked}\n   {st} │ {(created or '')[:10]}\n\n"
        text += "══════════════════════"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="owner_admins")],
    ])
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


# ─── Лог действий ───
@router.callback_query(F.data == "owner_admin_log")
async def owner_admin_log(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)

    actions = await get_admin_actions(limit=20)
    if not actions:
        text = "📊 ЛОГ ДЕЙСТВИЙ\n══════════════════════\n\n😔 Нет записей."
    else:
        text = "📊 ЛОГ ДЕЙСТВИЙ АДМИНОВ\n══════════════════════\n\n"
        for aid, admin_id, action, target, details, dt in actions:
            act_icon = {"ban": "🔨", "unban": "✅", "ticket_reply": "💬",
                        "ticket_accept": "📗", "ticket_reject": "📕"}.get(action, "📝")
            target_s = f" → ID:{target}" if target else ""
            text += (
                f"┠{act_icon} {action}{target_s}\n"
                f"   Админ: {admin_id} │ {(dt or '')[:16]}\n"
            )
            if details:
                text += f"   {details[:50]}\n"
            text += "\n"
        text += "══════════════════════"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="owner_admins")],
    ])
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


# ─── Снять админа ───
@router.callback_query(F.data == "owner_admin_remove")
async def owner_admin_remove_list(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)

    admins = await get_all_admins()
    if not admins:
        await call.answer("😔 Нет админов для удаления", show_alert=True)
        return

    text = "❌ СНЯТЬ АДМИНИСТРАТОРА\n══════════════════════\n\nВыберите:"
    kb = []
    for uid, uname, added_at in admins:
        name = f"@{uname}" if uname else f"ID:{uid}"
        kb.append([InlineKeyboardButton(
            text=f"❌ {name}",
            callback_data=f"owner_admin_rm_{uid}",
        )])
    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="owner_admins")])
    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await call.answer()


@router.callback_query(F.data.regexp(r"^owner_admin_rm_\d+$"))
async def owner_admin_rm_confirm(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    uid = int(call.data.split("_")[-1])
    await remove_admin(uid)
    try:
        await call.bot.send_message(uid, "🚫 Ваши права администратора были отозваны.")
    except Exception:
        pass
    await call.answer(f"✅ Админ {uid} снят!", show_alert=True)
    await owner_admins_menu(call)


# ════════════════════════════════════════════════════════
#  👀 ПРОСМОТР ПЕРЕПИСОК (владелец)
# ════════════════════════════════════════════════════════
@router.callback_query(F.data == "owner_chat_logs")
async def owner_chat_logs_list(call: CallbackQuery):
    """Список последних чатов для просмотра."""
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)

    chats = await get_recent_chats(20)
    if not chats:
        text = (
            "👀 ПЕРЕПИСКИ\n"
            "══════════════════════\n\n"
            "📭 Список чат-логов пуст.\n\n"
            "══════════════════════"
        )
        await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Панель владельца", callback_data="owner_panel")],
        ]))
        return await call.answer()

    text = "👀 ПОСЛЕДНИЕ ПЕРЕПИСКИ\n══════════════════════\n\n"
    kb = []
    for chat_id, users_str, msg_count, started in chats:
        text += f"💬 Чат #{chat_id} │ 👥 {users_str} │ ✉️ {msg_count} сообщ.\n"
        text += f"   📅 {(started or '')[:16]}\n\n"
        kb.append([
            InlineKeyboardButton(
                text=f"👀 Чат #{chat_id} ({msg_count} сообщ.)",
                callback_data=f"owner_chatlog:{chat_id}",
            ),
            InlineKeyboardButton(
                text=f"🗑",
                callback_data=f"owner_delchat:{chat_id}",
            ),
        ])
    text += "══════════════════════"
    kb.append([InlineKeyboardButton(text="🗑 Очистить все переписки", callback_data="owner_clear_all_chats")])
    kb.append([InlineKeyboardButton(text="⬅️ Панель владельца", callback_data="owner_panel")])

    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await call.answer()


@router.callback_query(F.data == "owner_clear_all_chats")
async def owner_clear_all_chats(call: CallbackQuery):
    """Очистить все чат-логи."""
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    await clear_all_chat_logs()
    await call.answer("✅ Все переписки удалены!", show_alert=True)
    # Обновляем список
    call.data = "owner_chat_logs"
    await owner_chat_logs_list(call)


@router.callback_query(F.data.startswith("owner_delchat:"))
async def owner_delete_one_chat(call: CallbackQuery):
    """Удалить лог одного чата."""
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    chat_id = int(call.data.split(":")[1])
    await clear_chat_log(chat_id)
    await call.answer(f"✅ Чат #{chat_id} удалён!", show_alert=True)
    call.data = "owner_chat_logs"
    await owner_chat_logs_list(call)


@router.callback_query(F.data.startswith("owner_chatlog:"))
async def owner_chat_log_view(call: CallbackQuery):
    """Просмотр конкретного чата."""
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)

    chat_id = int(call.data.split(":")[1])
    messages = await get_chat_log_messages(chat_id, limit=50)

    if not messages:
        text = f"👀 ЧАТ #{chat_id}\n══════════════════════\n\n📭 Нет сообщений."
    else:
        text = f"👀 ЧАТ #{chat_id}\n══════════════════════\n\n"
        for sender_id, msg, dt in messages:
            time_str = (dt or "")[-8:-3] if dt else ""
            short_msg = msg[:100] if msg else ""
            text += f"👤 {sender_id} [{time_str}]:\n   {short_msg}\n\n"

        if len(text) > 4000:
            text = text[:3950] + "\n\n... (обрезано)"
        text += "══════════════════════"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Все переписки", callback_data="owner_chat_logs")],
        [InlineKeyboardButton(text="⬅️ Панель владельца", callback_data="owner_panel")],
    ])
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


@router.callback_query(F.data.regexp(r"^oticket_chats_\d+$"))
async def owner_ticket_user_chats(call: CallbackQuery):
    """Переписки конкретного пользователя (из тикета)."""
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)

    uid = int(call.data.split("_")[-1])
    chats = await chat_get_history_for_user(uid, limit=15)

    if not chats:
        text = f"👀 ПЕРЕПИСКИ ID:{uid}\n══════════════════════\n\n📭 Нет чат-логов."
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Панель", callback_data="owner_panel")],
        ])
        await call.message.edit_text(text, reply_markup=kb)
        return await call.answer()

    text = f"👀 ПЕРЕПИСКИ ID:{uid}\n══════════════════════\n\n"
    kb_rows = []
    for chat_id, msg_count, started in chats:
        text += f"💬 Чат #{chat_id} │ ✉️ {msg_count} сообщ. │ 📅 {(started or '')[:16]}\n\n"
        kb_rows.append([InlineKeyboardButton(
            text=f"👀 Чат #{chat_id}",
            callback_data=f"owner_chatlog:{chat_id}",
        )])
    text += "══════════════════════"
    kb_rows.append([InlineKeyboardButton(text="⬅️ Панель", callback_data="owner_panel")])

    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))
    await call.answer()


# ════════════════════════════════════════════════════════
#  🔨 БАН ИЗ ТИКЕТА (владелец) — автор / другой
# ════════════════════════════════════════════════════════
@router.callback_query(F.data.regexp(r"^oticket_ban_author_\d+$"))
async def owner_ticket_ban_author(call: CallbackQuery):
    """Забанить отправителя тикета."""
    if not _is_owner(call.from_user.id):
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
    kb = _owner_ban_duration_kb(uid, back_cb=f"oticket_view_{tid}")
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


@router.callback_query(F.data.regexp(r"^oticket_ban_other_\d+$"))
async def owner_ticket_ban_other(call: CallbackQuery, state: FSMContext):
    """Забанить другого пользователя (по ID) из тикета."""
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    tid = int(call.data.split("_")[-1])
    await state.set_state(OwnerStates.waiting_ban_id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Отмена", callback_data=f"oticket_view_{tid}")],
    ])
    await call.message.edit_text(
        f"🔨 ЗАБАНИТЬ НАРУШИТЕЛЯ\n"
        f"══════════════════════\n\n"
        f"Из тикета #{tid}\n"
        f"Введите ID нарушителя:",
        reply_markup=kb,
    )
    await call.answer()

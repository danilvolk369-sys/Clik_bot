# ======================================================
# OWNER — Панель владельца (3 страницы)
# /admin — только для OWNER_ID
# ======================================================
import math
import random
import json
import uuid

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from config import (
    OWNER_ID, NFT_RARITIES, NFT_RARITY_EMOJI, MIN_AUCTION_PARTICIPANTS,
    MAX_AUCTION_PARTICIPANTS, VERSION, CLICK_PACKAGES, VIP_PACKAGES,
    RANKS_LIST,
)
from states import OwnerStates, EventStates
from database import (
    get_user, count_users, count_users_all, get_online_count,
    ban_user, unban_user, get_banned_users, count_banned_users,
    get_users_page, update_clicks, reset_user_progress, reset_all_users,
    get_open_tickets, count_open_tickets, get_ticket, close_ticket,
    add_ticket_reply, get_ticket_replies,
    create_nft_template, get_nft_templates, delete_nft_template,
    give_nft_to_user, get_nft_template, grant_nft_to_user,
    count_user_nfts, get_user_nft_slots,
    create_market_listing,
    log_admin_action, get_admin_actions,
    log_activity, get_activity_logs, count_activity_logs,
    create_admin_key, get_all_admin_keys, get_all_admins,
    remove_admin, get_admin_permissions, set_admin_permissions,
    is_admin, set_user_online,
    get_chat_logs_list, get_chat_messages,
    create_event, set_setting, get_all_settings, get_setting,
    get_pending_complaints, count_pending_complaints, get_complaint,
    resolve_complaint,
    get_pending_orders, count_pending_orders, get_payment_order,
    resolve_payment_order, update_clicks as db_update_clicks,
    set_user_vip, remove_user_vip,
    get_active_events, get_event, join_event, update_event_bid,
    get_event_participants, count_event_participants,
    get_user_event_bid, get_highest_bidder,
    finish_event, cancel_event, finish_event_with_winner,
    get_expired_active_events,
    save_auction_message, get_auction_messages, delete_auction_messages,
    ban_payment, unban_payment,
    update_bonus_click, update_passive_income, update_income_capacity,
    add_nft_slot,
)
from keyboards import (
    owner_panel_kb, owner_back_panel_kb, owner_admins_kb,
    owner_tickets_kb, owner_nft_list_kb, owner_nft_publish_kb,
    banned_list_kb, users_list_kb, user_profile_admin_kb,
    owner_logs_kb, complaints_list_kb, complaint_action_kb,
    owner_orders_kb, order_action_kb, ban_duration_kb,
    user_nfts_view_kb,
)
from handlers.common import fnum

router = Router()


def _is_owner(uid: int) -> bool:
    return uid == OWNER_ID


# ── /admin | /owner — открыть панель (только владелец) ──
@router.message(Command("admin"))
@router.message(Command("owner"))
async def cmd_admin(message: Message, state: FSMContext):
    uid = message.from_user.id
    if not _is_owner(uid):
        # Может быть админ — используем admin.py
        return
    await state.clear()
    await set_user_online(uid)
    # Регистрируем как игрока если нет
    from database import create_user
    username = message.from_user.username or "Аноним"
    await create_user(uid, username)
    total = await count_users_all()
    online = await get_online_count()
    text = (
        f"<b>👑 Панель владельца</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"🌐 Версия: <b>{VERSION}</b>\n"
        f"👥 Всего: <b>{total}</b> · 🟢 Онлайн: <b>{online}</b>"
    )
    await message.answer(text, reply_markup=owner_panel_kb(0))


@router.callback_query(F.data == "owner_panel")
async def owner_panel(call: CallbackQuery, state: FSMContext):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌ Нет доступа", show_alert=True)
    await state.clear()
    total = await count_users_all()
    online = await get_online_count()
    text = (
        f"<b>👑 Панель владельца</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"🌐 Версия: <b>{VERSION}</b>\n"
        f"👥 Всего: <b>{total}</b> · 🟢 Онлайн: <b>{online}</b>"
    )
    await call.message.edit_text(text, reply_markup=owner_panel_kb(0))
    await call.answer()


@router.callback_query(F.data.startswith("owner_panel_page:"))
async def owner_panel_page(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    page = int(call.data.split(":")[1])
    total = await count_users_all()
    online = await get_online_count()
    text = (
        f"<b>👑 Панель владельца</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"👥 Всего: <b>{total}</b> · 🟢 Онлайн: <b>{online}</b>"
    )
    await call.message.edit_text(text, reply_markup=owner_panel_kb(page))
    await call.answer()


# ══════════════════════════════════════════
#  СТАТИСТИКА
# ══════════════════════════════════════════
@router.callback_query(F.data == "owner_stats")
async def owner_stats(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    total = await count_users_all()
    active = await count_users()
    online = await get_online_count()
    banned = await count_banned_users()
    tickets = await count_open_tickets()
    complaints = await count_pending_complaints()

    text = (
        f"<b>📊 Статистика</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"👥 Всего игроков: <b>{total}</b>\n"
        f"✅ Активные: <b>{active}</b>\n"
        f"🟢 Онлайн (5 мин): <b>{online}</b>\n"
        f"🚫 Заблокированные: <b>{banned}</b>\n"
        f"📋 Открытых тикетов: <b>{tickets}</b>\n"
        f"📨 Жалоб (ожидание): <b>{complaints}</b>"
    )
    await call.message.edit_text(text, reply_markup=owner_back_panel_kb())
    await call.answer()


# ══════════════════════════════════════════
#  УЧАСТНИКИ (пагинация + поиск)
# ══════════════════════════════════════════
@router.callback_query(F.data == "owner_users")
async def owner_users(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    await _show_users_page(call, 0, "owner")


@router.callback_query(F.data.startswith("owner_users_pg:"))
async def owner_users_pg(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    page = int(call.data.split(":")[1])
    await _show_users_page(call, page, "owner")


async def _show_users_page(call, page, prefix):
    per_page = 10
    total = await count_users_all()
    total_pages = max(1, math.ceil(total / per_page))
    users = await get_users_page(page, per_page)
    text = f"<b>👥 Участники ({total})</b>\n━━━━━━━━━━━━━━━━━━━\n"
    await call.message.edit_text(text, reply_markup=users_list_kb(users, page, total_pages, prefix))
    await call.answer()


# ── Поиск по ID ──
@router.callback_query(F.data == "owner_user_search")
async def owner_user_search(call: CallbackQuery, state: FSMContext):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    await state.set_state(OwnerStates.waiting_user_search_id)
    text = "🔍 Введите ID участника:"
    await call.message.edit_text(text, reply_markup=owner_back_panel_kb())
    await call.answer()


@router.message(OwnerStates.waiting_user_search_id)
async def owner_user_search_id(message: Message, state: FSMContext):
    await state.clear()
    if not _is_owner(message.from_user.id):
        return
    try:
        uid = int(message.text.strip())
    except (ValueError, TypeError):
        return await message.answer("❌ Введите число", reply_markup=owner_back_panel_kb())

    user = await get_user(uid)
    if not user:
        return await message.answer("❌ Участник не найден", reply_markup=owner_back_panel_kb())

    text = await _user_profile_text(user)
    await message.answer(text, reply_markup=user_profile_admin_kb(uid, "owner"))


# ── Профиль участника ──
@router.callback_query(F.data.startswith("owner_user_view_"))
async def owner_user_view(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    uid = int(call.data.replace("owner_user_view_", ""))
    user = await get_user(uid)
    if not user:
        return await call.answer("❌ Не найден", show_alert=True)
    text = await _user_profile_text(user)
    await call.message.edit_text(text, reply_markup=user_profile_admin_kb(uid, "owner"))
    await call.answer()


async def _user_profile_text(user) -> str:
    uid = user["user_id"]
    uname = user["username"]
    from config import RANKS_LIST, NFT_RARITY_EMOJI
    rank_name = RANKS_LIST.get(user["rank"] or 1, "🍼")
    nft_count = await count_user_nfts(uid)
    max_slots = await get_user_nft_slots(uid)
    from database import count_user_complaints_received, is_payment_banned, get_user_pinned_nft
    complaints = await count_user_complaints_received(uid)
    vip = user["vip_type"]
    vip_line = ""
    if vip:
        exp = user.get("vip_expires", None)
        if exp == "permanent":
            exp_str = "навсегда"
        elif exp:
            try:
                from datetime import datetime as _dtfmt
                d = _dtfmt.fromisoformat(exp[:10])
                exp_str = f"до {d.strftime('%d.%m.%Y')}"
            except (ValueError, TypeError):
                exp_str = f"до {exp[:10]}"
        else:
            exp_str = "—"
        emoji = "💎" if vip.lower() == "premium" else "⭐"
        vip_line = f"{emoji} Статус: {vip} — {exp_str}\n"
    # Pinned NFT
    pinned = await get_user_pinned_nft(uid)
    pin_line = ""
    if pinned:
        p_emoji = NFT_RARITY_EMOJI.get(pinned[8], "🟢")
        pin_line = f"📌 Закреп: {p_emoji} {pinned[5]} ({fnum(pinned[6])}/ч)\n"
    pay_banned = await is_payment_banned(uid)
    return (
        f"👤 ПРОФИЛЬ УЧАСТНИКА\n"
        f"══════════════════════\n\n"
        f"🆔 ID: {uid}\n"
        f"📛 @{uname}\n"
        f"🪪 Ранг: {rank_name}\n"
        f"{vip_line}"
        f"💢 Баланс: {fnum(user['clicks'])} Тохн\n"
        f"⚡ Сила клика: +{fnum(user['bonus_click'])}\n"
        f"📈 Доход: {fnum(user['passive_income'])} Тохн/ч\n"
        f"🎨 НФТ: {nft_count}/{max_slots}\n"
        f"{pin_line}"
        f"🔗 Рефералы: {user['referrals']}\n"
        f"⚠️ Жалоб: {complaints}\n"
        f"🚫 Забанен: {'Да' if user['is_banned'] else 'Нет'}\n"
        f"💳 Оплата: {'🚫 Заблокирована' if pay_banned else '✅ Доступна'}\n\n"
        f"══════════════════════"
    )


# ══════════════════════════════════════════
#  БАН / РАЗБАН
# ══════════════════════════════════════════
@router.callback_query(F.data == "owner_ban")
async def owner_ban(call: CallbackQuery, state: FSMContext):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    await state.set_state(OwnerStates.waiting_ban_id)
    await call.message.edit_text("🔨 Введите ID для бана:", reply_markup=owner_back_panel_kb())
    await call.answer()


@router.message(OwnerStates.waiting_ban_id)
async def owner_ban_id(message: Message, state: FSMContext):
    if not _is_owner(message.from_user.id):
        return
    try:
        uid = int(message.text.strip())
    except (ValueError, TypeError):
        return await message.answer("❌ ID должен быть числом")
    await state.set_state(OwnerStates.waiting_ban_duration)
    await state.set_data({"ban_uid": uid})
    await message.answer("⏱ Введите длительность в часах (или «permanent» для перманентного):")


@router.message(OwnerStates.waiting_ban_duration)
async def owner_ban_duration(message: Message, state: FSMContext):
    if not _is_owner(message.from_user.id):
        return
    data = await state.get_data()
    uid = data["ban_uid"]
    duration = message.text.strip()
    await state.clear()
    await ban_user(uid, duration)
    await log_admin_action(message.from_user.id, "ban", uid, f"Бан: {duration}")
    await log_activity(uid, "ban", f"Забанен владельцем на {duration}")
    await message.answer(f"✅ Пользователь {uid} забанен!", reply_markup=owner_back_panel_kb())


@router.callback_query(F.data == "owner_unban")
async def owner_unban(call: CallbackQuery, state: FSMContext):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    await state.set_state(OwnerStates.waiting_unban_id)
    await call.message.edit_text("✅ Введите ID для разбана:", reply_markup=owner_back_panel_kb())
    await call.answer()


@router.message(OwnerStates.waiting_unban_id)
async def owner_unban_id(message: Message, state: FSMContext):
    if not _is_owner(message.from_user.id):
        return
    try:
        uid = int(message.text.strip())
    except (ValueError, TypeError):
        return await message.answer("❌ Число")
    await state.clear()
    await unban_user(uid)
    await log_admin_action(message.from_user.id, "unban", uid)
    await message.answer(f"✅ {uid} разбанен!", reply_markup=owner_back_panel_kb())


# Быстрый разбан из списка
@router.callback_query(F.data.startswith("owner_unban_quick_"))
async def owner_unban_quick(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    uid = int(call.data.replace("owner_unban_quick_", ""))
    await unban_user(uid)
    await log_admin_action(call.from_user.id, "unban", uid)
    await call.answer(f"✅ {uid} разбанен!", show_alert=True)
    await owner_banned_list(call)


# Бан из профиля — показывает меню выбора длительности
@router.callback_query(F.data.startswith("owner_banmenu_"))
async def owner_ban_menu_profile(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    uid = int(call.data.replace("owner_banmenu_", ""))
    await call.message.edit_text(
        f"🔨 Бан пользователя {uid}\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"Выберите длительность бана:",
        reply_markup=ban_duration_kb(uid, "owner"),
    )
    await call.answer()


# Быстрый бан по кнопке длительности
@router.callback_query(F.data.startswith("owner_doban_"))
async def owner_doban(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    parts = call.data.split("_")  # owner_doban_{uid}_{duration}
    uid = int(parts[2])
    duration = parts[3]  # 1, 3, 6, 12, 24, permanent
    await ban_user(uid, duration)
    await log_admin_action(call.from_user.id, "ban", uid, f"Бан: {duration}")
    await log_activity(uid, "ban", f"Забанен владельцем на {duration}")
    if duration == "permanent":
        dur_text = "навсегда"
    else:
        dur_text = f"{duration}ч"
    await call.answer(f"✅ {uid} забанен на {dur_text}", show_alert=True)
    # Вернуться в профиль
    user = await get_user(uid)
    if user:
        text = await _user_profile_text(user)
        await call.message.edit_text(text, reply_markup=user_profile_admin_kb(uid, "owner", 0))


# Старый хендлер бана (текстовый ввод) — оставляем для совместимости
@router.callback_query(F.data.startswith("owner_ban_user_"))
async def owner_ban_user_profile(call: CallbackQuery, state: FSMContext):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    uid = int(call.data.replace("owner_ban_user_", ""))
    await state.set_state(OwnerStates.waiting_ban_duration)
    await state.set_data({"ban_uid": uid})
    await call.message.edit_text(f"⏱ Бан {uid}. Введите часы или «permanent»:", reply_markup=owner_back_panel_kb())
    await call.answer()


@router.callback_query(F.data.startswith("owner_unban_user_"))
async def owner_unban_user_profile(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    uid = int(call.data.replace("owner_unban_user_", ""))
    await unban_user(uid)
    await call.answer(f"✅ {uid} разбанен", show_alert=True)
    # Обновляем профиль
    user = await get_user(uid)
    if user:
        text = await _user_profile_text(user)
        await call.message.edit_text(text, reply_markup=user_profile_admin_kb(uid, "owner", 0))


# ── Пагинация профиля ──
@router.callback_query(F.data.startswith("owner_profile_pg_"))
async def owner_profile_page(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    parts = call.data.split("_")  # owner_profile_pg_{uid}_{page}
    uid = int(parts[3])
    page = int(parts[4])
    user = await get_user(uid)
    if not user:
        return await call.answer("❌ Не найден", show_alert=True)
    text = await _user_profile_text(user)
    await call.message.edit_text(text, reply_markup=user_profile_admin_kb(uid, "owner", page))
    await call.answer()


# ── VIP / Premium из профиля ──
@router.callback_query(F.data.startswith("owner_setvip_"))
async def owner_set_vip(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    parts = call.data.split("_")  # owner_setvip_{uid}_{action}
    uid = int(parts[2])
    action = parts[3]

    if action == "remove":
        await remove_user_vip(uid)
        await log_admin_action(call.from_user.id, "remove_vip", uid)
        await call.answer("✅ VIP/Premium снят", show_alert=True)
    elif action == "vip7":
        await set_user_vip(uid, "VIP", 2, 1, 7)
        await log_admin_action(call.from_user.id, "set_vip", uid, "VIP 7d")
        await call.answer("✅ VIP на 7 дней выдан", show_alert=True)
    elif action == "vip30":
        await set_user_vip(uid, "VIP", 2, 1, 30)
        await log_admin_action(call.from_user.id, "set_vip", uid, "VIP 30d")
        await call.answer("✅ VIP на 30 дней выдан", show_alert=True)
    elif action == "vip0":
        await set_user_vip(uid, "VIP", 2, 1, 0)
        await log_admin_action(call.from_user.id, "set_vip", uid, "VIP permanent")
        await call.answer("✅ VIP навсегда выдан", show_alert=True)
    elif action == "prem7":
        await set_user_vip(uid, "Premium", 3, 3, 7)
        await log_admin_action(call.from_user.id, "set_vip", uid, "Premium 7d")
        await call.answer("✅ Premium на 7 дней выдан", show_alert=True)
    elif action == "prem30":
        await set_user_vip(uid, "Premium", 3, 3, 30)
        await log_admin_action(call.from_user.id, "set_vip", uid, "Premium 30d")
        await call.answer("✅ Premium на 30 дней выдан", show_alert=True)
    elif action == "prem0":
        await set_user_vip(uid, "Premium", 3, 3, 0)
        await log_admin_action(call.from_user.id, "set_vip", uid, "Premium permanent")
        await call.answer("✅ Premium навсегда выдан", show_alert=True)
    else:
        return await call.answer("❓ Неизвестное действие", show_alert=True)

    # Показать обновлённый донат-меню
    user = await get_user(uid)
    if user:
        from keyboards import donate_submenu_kb
        vip = user["vip_type"]
        await call.message.edit_text(
            await _user_profile_text(user),
            reply_markup=donate_submenu_kb(uid, "owner", vip),
        )


# ── Бан / Разбан оплаты из профиля ──
@router.callback_query(F.data.startswith("owner_payban_"))
async def owner_payban(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    uid = int(call.data.replace("owner_payban_", ""))
    await ban_payment(uid)
    await log_admin_action(call.from_user.id, "payment_ban", uid)
    await call.answer("🚫 Оплата заблокирована", show_alert=True)
    user = await get_user(uid)
    if user:
        text = await _user_profile_text(user)
        await call.message.edit_text(text, reply_markup=user_profile_admin_kb(uid, "owner", 0))


@router.callback_query(F.data.startswith("owner_payunban_"))
async def owner_payunban(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    uid = int(call.data.replace("owner_payunban_", ""))
    await unban_payment(uid)
    await log_admin_action(call.from_user.id, "payment_unban", uid)
    await call.answer("✅ Оплата разблокирована", show_alert=True)
    user = await get_user(uid)
    if user:
        text = await _user_profile_text(user)
        await call.message.edit_text(text, reply_markup=user_profile_admin_kb(uid, "owner", 0))


# ═══════════════════════════════════════════
#  СТРАНИЦА — Донат, Написать, +Значения
# ═══════════════════════════════════════════

# ── Подменю Донат (VIP/Premium + пакеты кликов) ──
@router.callback_query(F.data.startswith("owner_donate_"))
async def owner_donate_menu(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    uid = int(call.data.replace("owner_donate_", ""))
    user = await get_user(uid)
    vip = user["vip_type"] if user else None
    from keyboards import donate_submenu_kb
    await call.message.edit_text(
        f"🎁 <b>Донат — {uid}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"Статус: <b>{vip or 'нет'}</b>\n\n"
        f"Выберите действие:",
        reply_markup=donate_submenu_kb(uid, "owner", vip),
    )
    await call.answer()


# ── Выдать донат (пакеты кликов по кнопкам) ──
@router.callback_query(F.data.startswith("owner_givedon_"))
async def owner_give_donate(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    uid = int(call.data.replace("owner_givedon_", ""))
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="1.000 💢", callback_data=f"owner_don_{uid}_1000"),
            InlineKeyboardButton(text="5.000 💢", callback_data=f"owner_don_{uid}_5000"),
        ],
        [
            InlineKeyboardButton(text="10.000 💢", callback_data=f"owner_don_{uid}_10000"),
            InlineKeyboardButton(text="50.000 💢", callback_data=f"owner_don_{uid}_50000"),
        ],
        [
            InlineKeyboardButton(text="100.000 💢", callback_data=f"owner_don_{uid}_100000"),
            InlineKeyboardButton(text="500.000 💢", callback_data=f"owner_don_{uid}_500000"),
        ],
        [
            InlineKeyboardButton(text="1.000.000 💢", callback_data=f"owner_don_{uid}_1000000"),
        ],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"owner_profile_pg_{uid}_1")],
    ])
    await call.message.edit_text(
        f"🎁 Выдать донат пользователю {uid}\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"Выберите количество Тохн:", reply_markup=kb)
    await call.answer()


@router.callback_query(F.data.startswith("owner_don_"))
async def owner_donate_exec(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    parts = call.data.split("_")  # owner_don_{uid}_{amount}
    uid = int(parts[2])
    amount = int(parts[3])
    await update_clicks(uid, amount)
    await log_admin_action(call.from_user.id, "donate", uid, f"+{amount} clicks")
    await log_activity(uid, "donate", f"Получен донат +{fnum(amount)} от владельца")
    # Уведомляем пользователя
    try:
        await call.bot.send_message(
            uid,
            f"🎁 <b>Вам выдан донат!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━\n\n"
            f"💢 +{fnum(amount)} Тохн\n\n"
            f"Приятной игры! 🎉",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ В меню", callback_data="menu")],
            ]),
        )
    except Exception:
        pass
    await call.answer(f"✅ +{fnum(amount)} 💢 выдано", show_alert=True)
    user = await get_user(uid)
    if user:
        text = await _user_profile_text(user)
        await call.message.edit_text(text, reply_markup=user_profile_admin_kb(uid, "owner", 0))


# ── Написать участнику (из профиля) ──
@router.callback_query(F.data.startswith("owner_msgusr_"))
async def owner_msg_user_start(call: CallbackQuery, state: FSMContext):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    uid = int(call.data.replace("owner_msgusr_", ""))
    await state.set_state(OwnerStates.msg_to_user)
    await state.update_data(target_uid=uid)
    await call.message.answer(
        f"💬 Введите сообщение для пользователя {uid}:\n\n"
        f"Отправьте текст или /cancel для отмены.",
    )
    await call.answer()


@router.message(OwnerStates.msg_to_user)
async def owner_msg_user_send(message: Message, state: FSMContext):
    if not _is_owner(message.from_user.id):
        return
    if message.text and message.text.strip() == "/cancel":
        await state.clear()
        return await message.answer("❌ Отменено.")
    data = await state.get_data()
    uid = data.get("target_uid")
    if not uid:
        await state.clear()
        return
    text_to_send = (
        f"📩 <b>Сообщение от администрации</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"{message.text or '(файл)'}\n\n"
        f"━━━━━━━━━━━━━━━━━━━"
    )
    try:
        from keyboards import dialog_user_reply_kb, dialog_after_send_kb
        await message.bot.send_message(
            uid, text_to_send, parse_mode="HTML",
            reply_markup=dialog_user_reply_kb("owner", message.from_user.id),
        )
        await message.answer(
            f"✅ Сообщение отправлено пользователю {uid}.",
            reply_markup=dialog_after_send_kb("owner", uid),
        )
    except Exception as e:
        err = str(e).lower()
        if "chat not found" in err or "user is deactivated" in err:
            await message.answer("❌ Пользователь не начал диалог с ботом или удалил аккаунт.")
        elif "bot was blocked" in err:
            await message.answer("❌ Пользователь заблокировал бота.")
        else:
            await message.answer(f"❌ Не удалось: {e}")
    await state.clear()


# ── Диалог: продолжить / завершить ──
@router.callback_query(F.data.startswith("owner_dialog_cont_"))
async def owner_dialog_continue(call: CallbackQuery, state: FSMContext):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    uid = int(call.data.split("_")[-1])
    await state.set_state(OwnerStates.msg_to_user)
    await state.update_data(target_uid=uid)
    await call.message.answer(
        f"💬 Введите сообщение для пользователя {uid}:\n\n"
        f"Отправьте текст или /cancel для отмены.",
    )
    await call.answer()


@router.callback_query(F.data.startswith("owner_dialog_end_"))
async def owner_dialog_end(call: CallbackQuery, state: FSMContext):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    uid = int(call.data.split("_")[-1])
    await state.clear()
    await call.message.edit_text("🚪 Диалог завершён.")
    try:
        await call.bot.send_message(uid, "ℹ️ Администратор завершил диалог.")
    except Exception:
        pass
    await call.answer()


# ── Добавить значение (сила клика / доход / ёмкость / слоты) ──
@router.callback_query(F.data.startswith("owner_addval_"))
async def owner_addval_menu(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    parts = call.data.split("_")  # owner_addval_{uid}_{type}
    uid = int(parts[2])
    val_type = parts[3]

    type_names = {"click": "⚡ Сила клика", "income": "📈 Доход/ч", "cap": "📦 Ёмкость", "slot": "🎯 Слот НФТ"}
    name = type_names.get(val_type, val_type)

    if val_type == "slot":
        amounts = [1, 2, 3, 5]
    elif val_type == "click":
        amounts = [0.5, 1, 5, 10, 50, 100]
    elif val_type == "income":
        amounts = [1, 5, 10, 50, 100, 500]
    else:  # cap
        amounts = [50, 100, 500, 1000, 5000, 10000]

    rows = []
    for i in range(0, len(amounts), 2):
        row = []
        for a in amounts[i:i+2]:
            label = f"+{a}" if isinstance(a, int) else f"+{a}"
            row.append(InlineKeyboardButton(
                text=label, callback_data=f"owner_doval_{uid}_{val_type}_{a}"))
        rows.append(row)
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=f"owner_profile_pg_{uid}_2")])

    await call.message.edit_text(
        f"{name} для {uid}\n━━━━━━━━━━━━━━━━━━━\n\nВыберите значение:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await call.answer()


@router.callback_query(F.data.startswith("owner_doval_"))
async def owner_doval_exec(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    parts = call.data.split("_")  # owner_doval_{uid}_{type}_{amount}
    uid = int(parts[2])
    val_type = parts[3]
    amount = float(parts[4])

    if val_type == "click":
        await update_bonus_click(uid, amount)
        label = f"⚡ +{amount} сила клика"
    elif val_type == "income":
        await update_passive_income(uid, amount)
        label = f"📈 +{amount} доход/ч"
    elif val_type == "cap":
        await update_income_capacity(uid, amount)
        label = f"📦 +{amount} ёмкость"
    elif val_type == "slot":
        await add_nft_slot(uid, int(amount))
        label = f"🎯 +{int(amount)} слот НФТ"
    else:
        return await call.answer("❓", show_alert=True)

    await log_admin_action(call.from_user.id, f"add_{val_type}", uid, str(amount))
    await log_activity(uid, "admin_boost", f"Владелец выдал: {label}")
    try:
        await call.bot.send_message(
            uid, f"🎁 <b>Подарок от администрации!</b>\n━━━━━━━━━━━━━━━━━━━\n\n{label}\n",
            parse_mode="HTML")
    except Exception:
        pass
    await call.answer(f"✅ {label}", show_alert=True)
    user = await get_user(uid)
    if user:
        text = await _user_profile_text(user)
        await call.message.edit_text(text, reply_markup=user_profile_admin_kb(uid, "owner", 1))


# ═══════════════════════════════════════════
#  СТРАНИЦА 4 — Мут, Ранг, Логи, Рефералы
# ═══════════════════════════════════════════

# ── Мут / Размут ──
@router.callback_query(F.data.startswith("owner_mute_"))
async def owner_mute_user(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    uid = int(call.data.replace("owner_mute_", ""))
    from database import get_db
    db = await get_db()
    await db.execute("UPDATE users SET anonymous = 1 WHERE user_id = ?", (uid,))
    await db.commit()
    await log_admin_action(call.from_user.id, "mute", uid)
    await call.answer(f"🔕 {uid} замучен", show_alert=True)
    user = await get_user(uid)
    if user:
        text = await _user_profile_text(user)
        await call.message.edit_text(text, reply_markup=user_profile_admin_kb(uid, "owner", 1))


@router.callback_query(F.data.startswith("owner_unmute_"))
async def owner_unmute_user(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    uid = int(call.data.replace("owner_unmute_", ""))
    from database import get_db
    db = await get_db()
    await db.execute("UPDATE users SET anonymous = 0 WHERE user_id = ?", (uid,))
    await db.commit()
    await log_admin_action(call.from_user.id, "unmute", uid)
    await call.answer(f"🔔 {uid} размучен", show_alert=True)
    user = await get_user(uid)
    if user:
        text = await _user_profile_text(user)
        await call.message.edit_text(text, reply_markup=user_profile_admin_kb(uid, "owner", 1))


# ── Сменить ранг ──
@router.callback_query(F.data.startswith("owner_setrank_"))
async def owner_set_rank_menu(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    uid = int(call.data.replace("owner_setrank_", ""))
    rows = []
    for i in range(1, 16, 3):
        row = []
        for r in range(i, min(i+3, 16)):
            row.append(InlineKeyboardButton(
                text=f"{r}. {RANKS_LIST[r].split(' ', 1)[0]}",
                callback_data=f"owner_dorank_{uid}_{r}"))
        rows.append(row)
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=f"owner_profile_pg_{uid}_3")])
    await call.message.edit_text(
        f"🏷️ Сменить ранг для {uid}\n━━━━━━━━━━━━━━━━━━━\n\nВыберите ранг:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await call.answer()


@router.callback_query(F.data.startswith("owner_dorank_"))
async def owner_set_rank_exec(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    parts = call.data.split("_")
    uid = int(parts[2])
    rank = int(parts[3])
    from database import get_db
    db = await get_db()
    await db.execute("UPDATE users SET rank = ? WHERE user_id = ?", (rank, uid))
    await db.commit()
    from database import _invalidate
    _invalidate(uid)
    await log_admin_action(call.from_user.id, "set_rank", uid, f"Ранг → {rank}")
    await call.answer(f"✅ Ранг → {RANKS_LIST.get(rank, rank)}", show_alert=True)
    user = await get_user(uid)
    if user:
        text = await _user_profile_text(user)
        await call.message.edit_text(text, reply_markup=user_profile_admin_kb(uid, "owner", 1))


# ── Логи действий пользователя ──
@router.callback_query(F.data.startswith("owner_actlog_"))
async def owner_activity_log(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    uid = int(call.data.replace("owner_actlog_", ""))
    logs = await get_activity_logs(uid, 0, 15)
    lines = [f"📊 Логи действий {uid}\n━━━━━━━━━━━━━━━━━━━\n"]
    if not logs:
        lines.append("Нет записей.")
    else:
        for log in logs:
            dt = log[3][:16] if log[3] else "?"
            lines.append(f"• {dt} │ {log[1]} │ {log[2]}")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"owner_profile_pg_{uid}_3")],
    ])
    await call.message.edit_text("\n".join(lines), reply_markup=kb)
    await call.answer()


# ── Обнулить рефералов ──
@router.callback_query(F.data.startswith("owner_resetref_"))
async def owner_reset_referrals(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    uid = int(call.data.replace("owner_resetref_", ""))
    from database import get_db
    db = await get_db()
    await db.execute("UPDATE users SET referrals = 0, referrer_id = 0 WHERE user_id = ?", (uid,))
    await db.commit()
    from database import _invalidate
    _invalidate(uid)
    await log_admin_action(call.from_user.id, "reset_refs", uid)
    await call.answer(f"✅ Рефералы обнулены", show_alert=True)
    user = await get_user(uid)
    if user:
        text = await _user_profile_text(user)
        await call.message.edit_text(text, reply_markup=user_profile_admin_kb(uid, "owner", 1))


# ── Просмотр НФТ юзера (топ-5) ──
@router.callback_query(F.data.startswith("owner_usernfts_"))
async def owner_view_user_nfts(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    uid = int(call.data.replace("owner_usernfts_", ""))
    from database import get_user_top_nfts
    nfts = await get_user_top_nfts(uid, 5)
    user = await get_user(uid)
    uname = user["username"] if user else uid
    text = (
        f"<b>🎨 НФТ · @{uname}</b>\n"
        "━━━━━━━━━━━━━━━━━━━\n\n"
        f"Топ-5 НФТ по доходу:\n"
    )
    if not nfts:
        text += "\n— нет НФТ —\n"
    else:
        from config import NFT_RARITY_EMOJI
        for n in nfts:
            emoji = NFT_RARITY_EMOJI.get(n[4], "🟢")
            text += f"\n{emoji} <b>{n[1]}</b> — {fnum(n[2])}/ч"
    text += "\n\n━━━━━━━━━━━━━━━━━━━"
    await call.message.edit_text(text, reply_markup=user_nfts_view_kb(nfts, uid, "owner"))
    await call.answer()


# ── Сменить ник (юзернейм в БД) ──
@router.callback_query(F.data.startswith("owner_setname_"))
async def owner_set_name(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    uid = int(call.data.replace("owner_setname_", ""))
    # Обновляем ник из Telegram
    try:
        chat = await call.bot.get_chat(uid)
        new_name = chat.username or "anon"
        from database import get_db
        db = await get_db()
        await db.execute("UPDATE users SET username = ? WHERE user_id = ?", (new_name, uid))
        await db.commit()
        from database import _invalidate
        _invalidate(uid)
        await call.answer(f"✅ Ник обновлён → @{new_name}", show_alert=True)
    except Exception as e:
        await call.answer(f"❌ {e}", show_alert=True)
    user = await get_user(uid)
    if user:
        text = await _user_profile_text(user)
        await call.message.edit_text(text, reply_markup=user_profile_admin_kb(uid, "owner", 1))
@router.callback_query(F.data.startswith("owner_banned:"))
async def owner_banned_list(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    page = int(call.data.split(":")[1]) if ":" in call.data else 0
    total = await count_banned_users()
    per_page = 10
    total_pages = max(1, math.ceil(total / per_page))
    users = await get_banned_users(page, per_page)
    text = f"<b>🚫 Забаненные ({total})</b>\n━━━━━━━━━━━━━━━━━━━\n"
    await call.message.edit_text(text, reply_markup=banned_list_kb(users, page, total_pages, "owner"))
    await call.answer()


# ══════════════════════════════════════════
#  КЛИКИ — ВЫДАТЬ / СНЯТЬ
# ══════════════════════════════════════════
@router.callback_query(F.data == "owner_give")
async def owner_give(call: CallbackQuery, state: FSMContext):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    await state.set_state(OwnerStates.waiting_give)
    text = "💰 Введите: ID СУММА\n(напр. 12345 1000 для выдачи, 12345 -500 для снятия)"
    await call.message.edit_text(text, reply_markup=owner_back_panel_kb())
    await call.answer()


@router.message(OwnerStates.waiting_give)
async def owner_give_process(message: Message, state: FSMContext):
    if not _is_owner(message.from_user.id):
        return
    await state.clear()
    parts = message.text.strip().split()
    if len(parts) < 2:
        return await message.answer("❌ Формат: ID СУММА", reply_markup=owner_back_panel_kb())
    try:
        uid = int(parts[0])
        amount = float(parts[1])
    except (ValueError, TypeError):
        return await message.answer("❌ Неверный формат", reply_markup=owner_back_panel_kb())
    user = await get_user(uid)
    if not user:
        return await message.answer("❌ Не найден", reply_markup=owner_back_panel_kb())
    await update_clicks(uid, amount)
    action = "выдал" if amount >= 0 else "снял"
    await log_admin_action(message.from_user.id, f"clicks_{action}", uid, f"{amount}")
    await log_activity(uid, "admin", f"Владелец {action} {amount} кликов")
    await message.answer(f"✅ {action.title()} {fnum(abs(amount))} 💢 для {uid}", reply_markup=owner_back_panel_kb())


# Из профиля
@router.callback_query(F.data.startswith("owner_give_user_"))
async def owner_give_user_cb(call: CallbackQuery, state: FSMContext):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    uid = int(call.data.replace("owner_give_user_", ""))
    await state.set_state(OwnerStates.waiting_give)
    await state.set_data({"target_uid": uid})
    await call.message.edit_text(f"💰 Введите сумму для {uid} (число, минус = снять):", reply_markup=owner_back_panel_kb())
    await call.answer()


@router.callback_query(F.data.startswith("owner_take_user_"))
async def owner_take_user_cb(call: CallbackQuery, state: FSMContext):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    uid = int(call.data.replace("owner_take_user_", ""))
    await state.set_state(OwnerStates.waiting_take)
    await state.set_data({"target_uid": uid})
    await call.message.edit_text(f"💸 Введите сумму для снятия у {uid}:", reply_markup=owner_back_panel_kb())
    await call.answer()


@router.message(OwnerStates.waiting_take)
async def owner_take_process(message: Message, state: FSMContext):
    if not _is_owner(message.from_user.id):
        return
    data = await state.get_data()
    uid = data.get("target_uid")
    await state.clear()
    if not uid:
        return await message.answer("❌ Ошибка", reply_markup=owner_back_panel_kb())
    try:
        amount = float(message.text.strip())
    except (ValueError, TypeError):
        return await message.answer("❌ Число", reply_markup=owner_back_panel_kb())
    await update_clicks(uid, -abs(amount))
    await log_admin_action(message.from_user.id, "clicks_take", uid, f"-{abs(amount)}")
    await message.answer(f"✅ Снято {fnum(abs(amount))} 💢 у {uid}", reply_markup=owner_back_panel_kb())


# ══════════════════════════════════════════
#  НФТ УПРАВЛЕНИЕ
# ══════════════════════════════════════════
@router.callback_query(F.data == "owner_nft_manage")
async def owner_nft_manage(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    text = (
        "<b>🎨 НФТ управление</b>\n"
        "━━━━━━━━━━━━━━━━━━━\n\n"
        "Выдать / снять НФТ у игрока."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 Выдать НФТ", callback_data="owner_give_nft_start")],
        [InlineKeyboardButton(text="📥 Снять НФТ", callback_data="owner_take_nft_start")],
        [InlineKeyboardButton(text="⬅️ Панель", callback_data="owner_panel")],
    ])
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


@router.callback_query(F.data.startswith("owner_give_nft_"))
async def owner_give_nft(call: CallbackQuery, state: FSMContext):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    uid_str = call.data.replace("owner_give_nft_", "")
    if uid_str == "start":
        await state.set_state(OwnerStates.waiting_give_nft_user)
        await call.message.edit_text("Введите ID участника:", reply_markup=owner_back_panel_kb())
        return await call.answer()
    # Если uid передан
    uid = int(uid_str)
    await state.set_state(OwnerStates.waiting_give_nft_id)
    await state.set_data({"target_uid": uid})
    # Показать доступные шаблоны
    templates = await get_nft_templates()
    if not templates:
        await state.clear()
        return await call.answer("❌ Нет НФТ шаблонов", show_alert=True)
    kb = []
    for t in templates:
        tid = t[0]
        name = t[1]
        kb.append([InlineKeyboardButton(text=f"#{tid} {name}", callback_data=f"owner_gnft_{uid}_{tid}")])
    kb.append([InlineKeyboardButton(text="⬅️ Панель", callback_data="owner_panel")])
    await call.message.edit_text(
        f"🎨 Выберите НФТ для выдачи {uid}:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
    )
    await call.answer()


@router.message(OwnerStates.waiting_give_nft_user)
async def owner_give_nft_user_msg(message: Message, state: FSMContext):
    if not _is_owner(message.from_user.id):
        return
    try:
        uid = int(message.text.strip())
    except (ValueError, TypeError):
        return await message.answer("❌ Число", reply_markup=owner_back_panel_kb())
    user = await get_user(uid)
    if not user:
        await state.clear()
        return await message.answer("❌ Не найден", reply_markup=owner_back_panel_kb())
    await state.set_state(OwnerStates.waiting_give_nft_id)
    await state.set_data({"target_uid": uid})
    templates = await get_nft_templates()
    if not templates:
        await state.clear()
        return await message.answer("❌ Нет шаблонов", reply_markup=owner_back_panel_kb())
    lines = ["Введите ID шаблона НФТ:"]
    for t in templates[:20]:
        tid = t[0]
        name = t[1]
        lines.append(f"  #{tid} — {name}")
    await message.answer("\n".join(lines), reply_markup=owner_back_panel_kb())


@router.message(OwnerStates.waiting_give_nft_id)
async def owner_give_nft_id_msg(message: Message, state: FSMContext):
    if not _is_owner(message.from_user.id):
        return
    data = await state.get_data()
    uid = data.get("target_uid")
    await state.clear()
    try:
        tid = int(message.text.strip())
    except (ValueError, TypeError):
        return await message.answer("❌ Число", reply_markup=owner_back_panel_kb())
    ok = await give_nft_to_user(uid, tid)
    if ok:
        await log_admin_action(message.from_user.id, "give_nft", uid, f"Шаблон #{tid}")
        await message.answer(f"✅ НФТ #{tid} выдан игроку {uid}!", reply_markup=owner_back_panel_kb())
    else:
        await message.answer("❌ Ошибка (шаблон не найден?)", reply_markup=owner_back_panel_kb())


@router.callback_query(F.data.regexp(r"^owner_gnft_\d+_\d+$"))
async def owner_gnft_quick(call: CallbackQuery, state: FSMContext):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    parts = call.data.split("_")
    uid = int(parts[2])
    tid = int(parts[3])
    await state.clear()
    ok = await give_nft_to_user(uid, tid)
    if ok:
        await log_admin_action(call.from_user.id, "give_nft", uid, f"Шаблон #{tid}")
        await call.answer(f"✅ НФТ #{tid} выдан {uid}!", show_alert=True)
    else:
        await call.answer("❌ Ошибка", show_alert=True)


# ══════════════════════════════════════════
#  СОЗДАНИЕ НФТ
# ══════════════════════════════════════════
@router.callback_query(F.data == "owner_nft_create")
async def owner_nft_create(call: CallbackQuery, state: FSMContext):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    await state.set_state(OwnerStates.nft_name)
    await call.message.edit_text("🎨 Введите название НФТ:", reply_markup=owner_back_panel_kb())
    await call.answer()


@router.message(OwnerStates.nft_name)
async def owner_nft_name(message: Message, state: FSMContext):
    if not _is_owner(message.from_user.id):
        return
    await state.update_data(nft_name=message.text.strip())
    # Показать редкости
    kb = []
    for rn, pct in NFT_RARITIES.items():
        emoji = NFT_RARITY_EMOJI.get(rn, "🟢")
        kb.append([InlineKeyboardButton(
            text=f"{emoji} {rn} ({pct}%)",
            callback_data=f"owner_rarity_{rn}",
        )])
    await state.set_state(OwnerStates.nft_rarity)
    await message.answer("Выберите редкость:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))


@router.callback_query(F.data.startswith("owner_rarity_"), OwnerStates.nft_rarity)
async def owner_nft_rarity_cb(call: CallbackQuery, state: FSMContext):
    rn = call.data.replace("owner_rarity_", "")
    pct = NFT_RARITIES.get(rn, 10.0)
    await state.update_data(rarity_name=rn, rarity_pct=pct)
    await state.set_state(OwnerStates.nft_income)
    await call.message.edit_text("💰 Введите доход/час:", reply_markup=owner_back_panel_kb())
    await call.answer()


@router.message(OwnerStates.nft_income)
async def owner_nft_income(message: Message, state: FSMContext):
    if not _is_owner(message.from_user.id):
        return
    try:
        income = float(message.text.strip())
    except (ValueError, TypeError):
        return await message.answer("❌ Число")
    await state.update_data(nft_income=income)
    await state.set_state(OwnerStates.nft_price)
    await message.answer("🏷 Введите цену покупки:")


@router.message(OwnerStates.nft_price)
async def owner_nft_price(message: Message, state: FSMContext):
    if not _is_owner(message.from_user.id):
        return
    try:
        price = float(message.text.strip())
    except (ValueError, TypeError):
        return await message.answer("❌ Число")
    data = await state.get_data()
    data["nft_price"] = price
    await state.update_data(**data)
    rn = data.get("rarity_name", "Обычный")
    emoji = NFT_RARITY_EMOJI.get(rn, "🟢")
    text = (
        "<b>📋 Предпросмотр НФТ</b>\n"
        "━━━━━━━━━━━━━━━━━━━\n\n"
        f"📛 <b>{data['nft_name']}</b>\n"
        f"✨ {emoji} {rn} ({data.get('rarity_pct', 10)}%)\n"
        f"💰 Доход: <b>{fnum(data['nft_income'])}</b> Тохн/ч\n"
        f"🏷 Цена: <b>{fnum(price)}</b> 💢\n\n"
        "Опубликовать?"
    )
    await state.set_state(OwnerStates.nft_confirm)
    await message.answer(text, reply_markup=owner_nft_publish_kb())


@router.callback_query(F.data == "owner_nft_publish", OwnerStates.nft_confirm)
async def owner_nft_publish(call: CallbackQuery, state: FSMContext):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    data = await state.get_data()
    await state.clear()
    owner_id = call.from_user.id
    tid = await create_nft_template(
        data["nft_name"], data["rarity_name"], data["rarity_pct"],
        data["nft_income"], data["nft_price"], owner_id,
    )
    # Выдать НФТ владельцу и выставить на торговую площадку
    user_nft_id = await grant_nft_to_user(owner_id, tid, bought_price=0)
    await create_market_listing(owner_id, user_nft_id, tid, data["nft_price"])
    await log_admin_action(owner_id, "create_nft", details=f"НФТ #{tid} → площадка за {data['nft_price']} 💢")
    rn = data.get("rarity_name", "Обычный")
    emoji = NFT_RARITY_EMOJI.get(rn, "🎨")
    await call.message.edit_text(
        f"✅ НФТ создан и выставлен на площадку!\n\n"
        f"{emoji} <b>{data['nft_name']}</b>\n"
        f"✨ {rn} ({data.get('rarity_pct', 10)}%)\n"
        f"💰 Доход: {fnum(data['nft_income'])}/ч\n"
        f"🏷 Цена: {fnum(data['nft_price'])} 💢",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏪 Площадка", callback_data="market_menu")],
            [InlineKeyboardButton(text="👑 Назад в панель", callback_data="owner_panel")],
        ]),
    )
    await call.answer()


@router.callback_query(F.data == "owner_nft_cancel")
async def owner_nft_cancel(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.answer("❌ Отменено", show_alert=True)
    await owner_panel(call, state)


# ── Список НФТ / Удаление (с пагинацией) ──
_NFT_PER_PAGE = 5


@router.callback_query(F.data == "owner_nft_list")
async def owner_nft_list(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    await _show_nft_page(call, 0)


@router.callback_query(F.data.startswith("owner_nft_pg_"))
async def owner_nft_page(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    page = int(call.data.replace("owner_nft_pg_", ""))
    await _show_nft_page(call, page)


async def _show_nft_page(call, page: int):
    from database import count_nft_templates, get_nft_templates_page
    total = await count_nft_templates()
    if total == 0:
        await call.message.edit_text("Нет активных НФТ шаблонов.", reply_markup=owner_back_panel_kb())
        return await call.answer()
    total_pages = max(1, math.ceil(total / _NFT_PER_PAGE))
    page = max(0, min(page, total_pages - 1))
    templates = await get_nft_templates_page(page, _NFT_PER_PAGE)
    await call.message.edit_text(
        f"<b>🎨 НФТ шаблоны ({total})</b>\n━━━━━━━━━━━━━━━━━━━\n\n"
        f"Выберите НФТ для просмотра:",
        reply_markup=owner_nft_list_kb(templates, page, total_pages),
        parse_mode="HTML",
    )
    await call.answer()


@router.callback_query(F.data.startswith("owner_nft_view_"))
async def owner_nft_view(call: CallbackQuery):
    """Просмотр карточки НФТ-шаблона перед удалением."""
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    tid = int(call.data.replace("owner_nft_view_", ""))
    from database import get_nft_template
    t = await get_nft_template(tid)
    if not t:
        return await call.answer("❌ Не найден", show_alert=True)
    emoji = NFT_RARITY_EMOJI.get(t["rarity_name"], "🟢")
    text = (
        f"<b>📋 НФТ #{t['id']}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"📛 Название: <b>{t['name']}</b>\n"
        f"📂 Коллекция: #{t['collection_num']}\n"
        f"✨ Редкость: {emoji} {t['rarity_name']} ({t['rarity_pct']}%)\n"
        f"💰 Доход: <b>{fnum(t['income_per_hour'])}</b>/ч\n"
        f"🏷 Цена: {fnum(t['price'])} 💢\n"
        f"👤 Создатель: {t['created_by']}\n"
        f"📅 Создан: {(t['created_at'] or '')[:10]}\n\n"
        f"━━━━━━━━━━━━━━━━━━━"
    )
    from keyboards import owner_nft_detail_kb
    await call.message.edit_text(text, reply_markup=owner_nft_detail_kb(tid, 0), parse_mode="HTML")
    await call.answer()


@router.callback_query(F.data.startswith("owner_nft_del_"))
async def owner_nft_del(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    tid = int(call.data.replace("owner_nft_del_", ""))
    # Показать подтверждение
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"owner_nft_del_yes_{tid}"),
            InlineKeyboardButton(text="❌ Нет", callback_data=f"owner_nft_view_{tid}"),
        ],
    ])
    await call.message.edit_text(
        f"⚠️ <b>Удалить НФТ #{tid}?</b>\n\nЭто действие необратимо.",
        reply_markup=kb, parse_mode="HTML",
    )
    await call.answer()


@router.callback_query(F.data.startswith("owner_nft_del_yes_"))
async def owner_nft_del_confirm(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    tid = int(call.data.replace("owner_nft_del_yes_", ""))
    await delete_nft_template(tid)
    await log_admin_action(call.from_user.id, "delete_nft", details=f"#{tid}")
    await call.answer("✅ НФТ удалён!", show_alert=True)
    await _show_nft_page(call, 0)


# ══════════════════════════════════════════
#  АВТО-НФТ (1-50)
# ══════════════════════════════════════════

# Словарь для генерации крутых имён НФТ
_NFT_PREFIXES = [
    "Дракон", "Феникс", "Грифон", "Кракен", "Левиафан",
    "Голем", "Титан", "Страж", "Рыцарь", "Маг",
    "Демон", "Ангел", "Призрак", "Оракул", "Стихия",
    "Ворон", "Волк", "Медведь", "Сокол", "Пантера",
    "Кобра", "Скорпион", "Ястреб", "Мантикора", "Гидра",
    "Химера", "Виверна", "Базилиск", "Минотавр", "Цербер",
]
_NFT_SUFFIXES = [
    "Огня", "Льда", "Тьмы", "Света", "Хаоса",
    "Порядка", "Бури", "Песков", "Неба", "Бездны",
    "Космоса", "Времени", "Теней", "Грома", "Пламени",
    "Моря", "Земли", "Ветра", "Ночи", "Зари",
]


def _gen_nft_name() -> str:
    return f"{random.choice(_NFT_PREFIXES)} {random.choice(_NFT_SUFFIXES)}"


# ══ БЫСТРОЕ НФТ (пошаговое: название → количество → создание) ══
@router.callback_query(F.data == "owner_quick_nft")
async def owner_quick_nft(call: CallbackQuery, state: FSMContext):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    await state.set_state(OwnerStates.quick_nft_name)
    await call.message.edit_text(
        "<b>⚡ Быстрое создание НФТ</b>\n"
        "━━━━━━━━━━━━━━━━━━━\n\n"
        "Шаг 1/2 — Введите название (префикс) НФТ:\n\n"
        "💡 Например: Пламя, Клинок, Тень\n"
        "К нему добавится случайный суффикс.",
        reply_markup=owner_back_panel_kb(),
    )
    await call.answer()


@router.message(OwnerStates.quick_nft_name)
async def owner_quick_nft_name(message: Message, state: FSMContext):
    if not _is_owner(message.from_user.id):
        return
    name = (message.text or "").strip()
    if not name or len(name) > 30:
        return await message.answer("❌ Название от 1 до 30 символов")
    await state.update_data(qnft_name=name)
    await state.set_state(OwnerStates.quick_nft_count)
    await message.answer(
        "<b>⚡ Быстрое создание НФТ</b>\n"
        "━━━━━━━━━━━━━━━━━━━\n\n"
        f"Название: <b>{name}</b> + суффикс\n\n"
        "Шаг 2/2 — Введите количество (1-50):",
        reply_markup=owner_back_panel_kb(),
        parse_mode="HTML",
    )


@router.message(OwnerStates.quick_nft_count)
async def owner_quick_nft_count(message: Message, state: FSMContext):
    if not _is_owner(message.from_user.id):
        return
    try:
        count = int(message.text.strip())
        if not 1 <= count <= 50:
            raise ValueError
    except (ValueError, TypeError):
        return await message.answer("❌ Введите число от 1 до 50")

    data = await state.get_data()
    prefix = data.get("qnft_name", "НФТ")
    await state.clear()

    await message.answer("⏳ Создаю НФТ...")

    rarity_list = list(NFT_RARITIES.items())
    created = 0
    results = []
    owner_id = message.from_user.id
    for _ in range(count):
        rn, pct = random.choice(rarity_list)
        # Доход обратно пропорционален % шанса (редкие — больше)
        income = round(random.uniform(0.5, 50.0) * (10.0 / max(pct, 0.01)), 2)
        price = round(income * random.uniform(50, 200), 0)
        suffix = random.choice(_NFT_SUFFIXES)
        name = f"{prefix} {suffix}"
        emoji = NFT_RARITY_EMOJI.get(rn, "🎨")
        template_id = await create_nft_template(
            name, rn, pct, income, price,
            owner_id,
            collection_num=random.randint(1, 999),
        )
        # Присвоить НФТ владельцу и выставить на площадку
        user_nft_id = await grant_nft_to_user(owner_id, template_id, bought_price=0)
        await create_market_listing(owner_id, user_nft_id, template_id, price)
        created += 1
        results.append(f"{emoji} {name} — {rn} | 💰{income}/ч | 🏷{int(price)}")

    await log_admin_action(owner_id, "quick_nft", details=f"Создано {created} НФТ (префикс: {prefix}), выставлены на площадку")

    # Показываем результат (ограничим до 15 позиций чтобы не перегрузить сообщение)
    preview = "\n".join(results[:15])
    if len(results) > 15:
        preview += f"\n... и ещё {len(results) - 15}"

    await message.answer(
        f"✅ Создано {created} НФТ и выставлено на площадку!\n\n{preview}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👑 Назад в панель", callback_data="owner_panel")],
        ]),
    )


# ══════════════════════════════════════════
#  ТИКЕТЫ (with dialog)
# ══════════════════════════════════════════
@router.callback_query(F.data.startswith("owner_tickets:"))
async def owner_tickets(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    page = int(call.data.split(":")[1])
    total = await count_open_tickets()
    per_page = 5
    total_pages = max(1, math.ceil(total / per_page))
    tickets = await get_open_tickets(page, per_page)
    text = f"<b>📋 Тикеты ({total} открытых)</b>\n━━━━━━━━━━━━━━━━━━━\n"
    if not tickets:
        text += "\nНет открытых тикетов."
    await call.message.edit_text(text, reply_markup=owner_tickets_kb(tickets, page, total_pages))
    await call.answer()


@router.callback_query(F.data.startswith("ticket_view_"))
async def ticket_view(call: CallbackQuery):
    uid = call.from_user.id
    if not _is_owner(uid) and not await is_admin(uid):
        return await call.answer("❌", show_alert=True)
    ticket_id = int(call.data.replace("ticket_view_", ""))
    ticket = await get_ticket(ticket_id)
    if not ticket:
        return await call.answer("❌ Не найден", show_alert=True)

    replies = await get_ticket_replies(ticket_id)
    lines = [
        f"<b>📋 Тикет #{ticket_id}</b>",
        f"━━━━━━━━━━━━━━━━━━━",
        f"👤 От: {ticket['user_id']}",
        f"📝 Тип: {ticket['type']}",
        f"📅 {ticket['created_at'][:16]}",
        f"",
        f"💬 {ticket['message']}",
        f"",
    ]
    for r in replies:
        sender, msg, dt = r
        role = "👑" if sender == OWNER_ID else ("👮" if await is_admin(sender) else "👤")
        lines.append(f"{role} {sender}: {msg}")

    lines.append("━━━━━━━━━━━━━━━━━━━")

    back_cb = "owner_tickets:0" if _is_owner(uid) else "adm_tickets:0"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Ответить", callback_data=f"ticket_reply_{ticket_id}")],
        [InlineKeyboardButton(text="✅ Закрыть тикет", callback_data=f"ticket_close_{ticket_id}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=back_cb)],
    ])
    await call.message.edit_text("\n".join(lines), reply_markup=kb)
    await call.answer()


@router.callback_query(F.data.startswith("ticket_reply_"))
async def ticket_reply_start(call: CallbackQuery, state: FSMContext):
    uid = call.from_user.id
    if not _is_owner(uid) and not await is_admin(uid):
        return await call.answer("❌", show_alert=True)
    ticket_id = int(call.data.replace("ticket_reply_", ""))
    await state.set_state(OwnerStates.waiting_ticket_reply)
    await state.set_data({"ticket_id": ticket_id})
    await call.message.edit_text(f"💬 Введите ответ на тикет #{ticket_id}:", reply_markup=owner_back_panel_kb())
    await call.answer()


@router.message(OwnerStates.waiting_ticket_reply)
async def ticket_reply_msg(message: Message, state: FSMContext):
    uid = message.from_user.id
    if not _is_owner(uid) and not await is_admin(uid):
        return
    data = await state.get_data()
    ticket_id = data.get("ticket_id")
    await state.clear()
    reply_text = message.text.strip()
    await add_ticket_reply(ticket_id, uid, reply_text)

    # Уведомить пользователя
    ticket = await get_ticket(ticket_id)
    if ticket:
        try:
            await message.bot.send_message(
                ticket["user_id"],
                f"📬 Ответ на ваше обращение #{ticket_id}:\n\n{reply_text}",
            )
        except Exception:
            pass

    await message.answer("✅ Ответ отправлен!", reply_markup=owner_back_panel_kb())


@router.callback_query(F.data.startswith("ticket_close_"))
async def ticket_close(call: CallbackQuery):
    uid = call.from_user.id
    if not _is_owner(uid) and not await is_admin(uid):
        return await call.answer("❌", show_alert=True)
    ticket_id = int(call.data.replace("ticket_close_", ""))
    await close_ticket(ticket_id)
    await call.answer("✅ Тикет закрыт", show_alert=True)


# ══════════════════════════════════════════
#  ЖАЛОБЫ НА ЧЕКИ
# ══════════════════════════════════════════
@router.callback_query(F.data.startswith("compl_pg:"))
async def complaints_page(call: CallbackQuery):
    uid = call.from_user.id
    if not _is_owner(uid) and not await is_admin(uid):
        return await call.answer("❌", show_alert=True)
    page = int(call.data.split(":")[1])
    total = await count_pending_complaints()
    per_page = 5
    total_pages = max(1, math.ceil(total / per_page))
    items = await get_pending_complaints(page, per_page)
    text = f"<b>📨 Жалобы ({total})</b>\n━━━━━━━━━━━━━━━━━━━\n"
    await call.message.edit_text(text, reply_markup=complaints_list_kb(items, page, total_pages))
    await call.answer()


@router.callback_query(F.data.startswith("compl_view:"))
async def complaint_view(call: CallbackQuery):
    uid = call.from_user.id
    if not _is_owner(uid) and not await is_admin(uid):
        return await call.answer("❌", show_alert=True)
    cid = int(call.data.split(":")[1])
    c = await get_complaint(cid)
    if not c:
        return await call.answer("❌ Не найдена", show_alert=True)
    text = (
        f"<b>📨 Жалоба #{cid}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 От: {c['user_id']}\n"
        f"📋 Чек: #{c['transaction_id']}\n"
        f"📝 {c['reason']}\n"
        f"📅 {c['created_at'][:16]}"
    )
    await call.message.edit_text(text, reply_markup=complaint_action_kb(cid))
    await call.answer()


@router.callback_query(F.data.startswith("compl_act:"))
async def complaint_action(call: CallbackQuery):
    uid = call.from_user.id
    if not _is_owner(uid) and not await is_admin(uid):
        return await call.answer("❌", show_alert=True)
    parts = call.data.split(":")
    cid = int(parts[1])
    action = parts[2]
    await resolve_complaint(cid, uid, action)
    await log_admin_action(uid, f"complaint_{action}", details=f"Жалоба #{cid}")
    await call.answer(f"✅ Жалоба: {action}", show_alert=True)
    # Возврат к списку жалоб (page 0)
    total = await count_pending_complaints()
    per_page = 5
    total_pages = max(1, math.ceil(total / per_page))
    items = await get_pending_complaints(0, per_page)
    text = f"<b>📨 Жалобы ({total})</b>\n━━━━━━━━━━━━━━━━━━━\n"
    await call.message.edit_text(text, reply_markup=complaints_list_kb(items, 0, total_pages))


# ══════════════════════════════════════════
#  РАССЫЛКА
# ══════════════════════════════════════════
@router.callback_query(F.data == "owner_broadcast")
async def owner_broadcast(call: CallbackQuery, state: FSMContext):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    await state.set_state(OwnerStates.waiting_broadcast)
    await call.message.edit_text("📢 Введите текст рассылки:", reply_markup=owner_back_panel_kb())
    await call.answer()


@router.message(OwnerStates.waiting_broadcast)
async def owner_broadcast_send(message: Message, state: FSMContext):
    if not _is_owner(message.from_user.id):
        return
    await state.clear()
    text = message.text.strip()
    from database import get_db
    db = await get_db()
    cur = await db.execute("SELECT user_id FROM users WHERE is_banned = 0")
    rows = await cur.fetchall()
    sent = 0
    for row in rows:
        try:
            await message.bot.send_message(row[0], f"📢 ОБЪЯВЛЕНИЕ:\n\n{text}")
            sent += 1
        except Exception:
            pass
    await message.answer(f"✅ Отправлено {sent} из {len(rows)} игрокам", reply_markup=owner_back_panel_kb())


# ══════════════════════════════════════════
#  ЛОГИ
# ══════════════════════════════════════════
@router.callback_query(F.data == "owner_logs")
async def owner_logs(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    await call.message.edit_text("<b>📝 Логи</b>\n━━━━━━━━━━━━━━━━━━━\n\nВыберите тип:", reply_markup=owner_logs_kb())
    await call.answer()


@router.callback_query(F.data.startswith("olog:"))
async def owner_log_type(call: CallbackQuery, state: FSMContext):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    parts = call.data.split(":")
    action = parts[1]

    if action == "search":
        await state.set_state(OwnerStates.waiting_log_user_id)
        await call.message.edit_text("🔍 Введите ID участника:", reply_markup=owner_back_panel_kb())
        return await call.answer()

    page = int(parts[2]) if len(parts) > 2 else 0
    logs = await get_activity_logs(action=action, page=page, per_page=10)
    total = await count_activity_logs(action=action)
    total_pages = max(1, math.ceil(total / 10))

    lines = [f"<b>📝 Логи: {action.upper()} ({total})</b>\n━━━━━━━━━━━━━━━━━━━\n"]
    for log in logs:
        lid = log[0]
        uid = log[1]
        act = log[2]
        det = log[3] or ""
        dt = log[4][:16] if log[4] else ""
        lines.append(f"#{lid} │ {uid} │ {det[:40]} │ {dt}")

    nav = []
    if total_pages > 1:
        if page > 0:
            nav.append(InlineKeyboardButton(text="◀️", callback_data=f"olog:{action}:{page-1}"))
        nav.append(InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="noop"))
        if page < total_pages - 1:
            nav.append(InlineKeyboardButton(text="▶️", callback_data=f"olog:{action}:{page+1}"))

    kb = []
    if nav:
        kb.append(nav)
    kb.append([InlineKeyboardButton(text="⬅️ Логи", callback_data="owner_logs")])
    await call.message.edit_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await call.answer()


@router.message(OwnerStates.waiting_log_user_id)
async def owner_log_user(message: Message, state: FSMContext):
    if not _is_owner(message.from_user.id):
        return
    await state.clear()
    try:
        uid = int(message.text.strip())
    except (ValueError, TypeError):
        return await message.answer("❌ Число", reply_markup=owner_back_panel_kb())
    logs = await get_activity_logs(user_id=uid, page=0, per_page=20)
    if not logs:
        return await message.answer(f"У {uid} нет логов.", reply_markup=owner_back_panel_kb())
    lines = [f"<b>📝 Логи участника {uid}</b>\n━━━━━━━━━━━━━━━━━━━\n"]
    for log in logs:
        act = log[2]
        det = log[3] or ""
        dt = log[4][:16] if log[4] else ""
        lines.append(f"• {act}: {det[:50]} ({dt})")
    await message.answer("\n".join(lines), reply_markup=owner_back_panel_kb())


# ══════════════════════════════════════════
#  СБРОС / ВАЙП
# ══════════════════════════════════════════
@router.callback_query(F.data == "owner_reset_user")
async def owner_reset_user(call: CallbackQuery, state: FSMContext):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    await state.set_state(OwnerStates.waiting_reset_user_id)
    await call.message.edit_text("🔄 Введите ID для сброса:", reply_markup=owner_back_panel_kb())
    await call.answer()


@router.message(OwnerStates.waiting_reset_user_id)
async def owner_reset_user_msg(message: Message, state: FSMContext):
    if not _is_owner(message.from_user.id):
        return
    await state.clear()
    try:
        uid = int(message.text.strip())
    except (ValueError, TypeError):
        return await message.answer("❌ Число", reply_markup=owner_back_panel_kb())
    await reset_user_progress(uid)
    await log_admin_action(message.from_user.id, "reset", uid)
    await message.answer(f"✅ {uid} сброшен!", reply_markup=owner_back_panel_kb())


@router.callback_query(F.data.startswith("owner_reset_"))
async def owner_reset_from_profile(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    uid = int(call.data.replace("owner_reset_", ""))
    await reset_user_progress(uid)
    await log_admin_action(call.from_user.id, "reset", uid)
    await call.answer(f"✅ {uid} сброшен!", show_alert=True)


@router.callback_query(F.data == "owner_wipe_all")
async def owner_wipe_all(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="☢️ ДА, СБРОСИТЬ ВСЕХ", callback_data="owner_wipe_confirm")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="owner_panel")],
    ])
    await call.message.edit_text("⚠️ СБРОСИТЬ ВСЕХ УЧАСТНИКОВ?\nЭто необратимо!", reply_markup=kb)
    await call.answer()


@router.callback_query(F.data == "owner_wipe_confirm")
async def owner_wipe_confirm(call: CallbackQuery, state: FSMContext):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    await reset_all_users()
    await log_admin_action(call.from_user.id, "wipe_all")
    await call.answer("☢️ Все сброшены!", show_alert=True)
    await owner_panel(call, state)


# ══════════════════════════════════════════
#  ПЕРЕПИСКИ
# ══════════════════════════════════════════
@router.callback_query(F.data == "owner_chat_logs")
async def owner_chat_logs(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)

    from database import get_all_active_chats
    active = await get_all_active_chats()

    kb = []
    # Сначала активные чаты
    if active:
        kb.append([InlineKeyboardButton(text="🟢 АКТИВНЫЕ ЧАТЫ", callback_data="noop")])
        for a in active[:15]:
            cid, u1, u2, dt = a[0], a[1], a[2], a[3]
            dt_short = dt[11:16] if dt else ""
            kb.append([InlineKeyboardButton(
                text=f"🟢 #{cid} — {u1} ↔ {u2} ({dt_short})",
                callback_data=f"owner_chat_active_{cid}",
            )])

    # Потом история
    logs = await get_chat_logs_list(0, 15)
    if logs:
        kb.append([InlineKeyboardButton(text="📋 ИСТОРИЯ ЧАТОВ", callback_data="noop")])
        for log in logs:
            chat_id, started = log
            kb.append([InlineKeyboardButton(
                text=f"💬 #{chat_id} — {started[:16]}",
                callback_data=f"owner_chat_view_{chat_id}",
            )])

    if not kb:
        await call.message.edit_text("👀 Нет переписок.", reply_markup=owner_back_panel_kb())
        return await call.answer()

    kb.append([InlineKeyboardButton(text="⬅️ Панель", callback_data="owner_panel")])
    a_count = len(active) if active else 0
    await call.message.edit_text(
        f"<b>👀 Переписки</b>\n━━━━━━━━━━━━━━━━━━━\n\n"
        f"🟢 Активных: <b>{a_count}</b>\n",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
    )
    await call.answer()


# ── Просмотр активного чата ──
@router.callback_query(F.data.startswith("owner_chat_active_"))
async def owner_chat_active_view(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    chat_id = int(call.data.replace("owner_chat_active_", ""))

    from database import get_active_chat_by_id, count_chat_messages
    chat = await get_active_chat_by_id(chat_id)
    if not chat:
        return await call.answer("ℹ️ Чат уже завершён", show_alert=True)

    cid, u1, u2, dt = chat[0], chat[1], chat[2], chat[3]
    msg_count = await count_chat_messages(cid)

    # Последние сообщения
    messages = await get_chat_messages(cid, 0, 20)
    lines = [
        f"<b>🟢 Активный чат #{cid}</b>\n━━━━━━━━━━━━━━━━━━━\n",
        f"👤 Участник 1: {u1}",
        f"👤 Участник 2: {u2}",
        f"📅 Начат: {dt[:16] if dt else '—'}",
        f"💬 Сообщений: {msg_count}\n",
        "——— Последние сообщения ———",
    ]
    for m in messages:
        sid, msg, mdt = m
        time_s = mdt[11:16] if mdt else ""
        lines.append(f"[{sid}] {time_s}: {msg}")
    lines.append("\n━━━━━━━━━━━━━━━━━━━")

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data=f"owner_chat_active_{cid}")],
        [InlineKeyboardButton(text="🛑 Завершить чат", callback_data=f"owner_chat_end_{cid}")],
        [
            InlineKeyboardButton(text=f"⚠️ Жалоба на {u1}", callback_data=f"owner_chat_warn_{cid}_{u1}"),
            InlineKeyboardButton(text=f"⚠️ Жалоба на {u2}", callback_data=f"owner_chat_warn_{cid}_{u2}"),
        ],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="owner_chat_logs")],
    ])
    text = "\n".join(lines)
    if len(text) > 4000:
        text = text[:4000] + "\n...(обрезано)"
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


# ── Просмотр завершённого чата (история) ──
@router.callback_query(F.data.startswith("owner_chat_view_"))
async def owner_chat_view(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    chat_id = int(call.data.replace("owner_chat_view_", ""))
    messages = await get_chat_messages(chat_id, 0, 30)

    # Узнаём участников из логов
    participants = set()
    for m in messages:
        participants.add(m[0])
    p_list = list(participants)

    lines = [f"<b>💬 Чат #{chat_id} (завершён)</b>\n━━━━━━━━━━━━━━━━━━━\n"]
    if p_list:
        lines.append(f"👤 Участники: {', '.join(str(p) for p in p_list)}\n")
    for m in messages:
        sid, msg, dt = m
        time_s = dt[11:16] if dt else ""
        lines.append(f"[{sid}] {time_s}: {msg}")
    lines.append("\n━━━━━━━━━━━━━━━━━━━")

    # Кнопки жалобы на участников
    kb_rows = []
    if len(p_list) >= 2:
        kb_rows.append([
            InlineKeyboardButton(text=f"⚠️ Жалоба на {p_list[0]}", callback_data=f"owner_chat_warn_{chat_id}_{p_list[0]}"),
            InlineKeyboardButton(text=f"⚠️ Жалоба на {p_list[1]}", callback_data=f"owner_chat_warn_{chat_id}_{p_list[1]}"),
        ])
    elif len(p_list) == 1:
        kb_rows.append([InlineKeyboardButton(text=f"⚠️ Жалоба на {p_list[0]}", callback_data=f"owner_chat_warn_{chat_id}_{p_list[0]}")])
    kb_rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="owner_chat_logs")])

    text = "\n".join(lines)
    if len(text) > 4000:
        text = text[:4000] + "\n...(обрезано)"
    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))
    await call.answer()


# ── Завершить активный чат (владелец) ──
@router.callback_query(F.data.startswith("owner_chat_end_"))
async def owner_chat_end(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    chat_id = int(call.data.replace("owner_chat_end_", ""))

    from database import get_active_chat_by_id, end_active_chat as _end_chat
    chat = await get_active_chat_by_id(chat_id)
    if not chat:
        return await call.answer("ℹ️ Чат уже завершён", show_alert=True)

    u1, u2 = chat[1], chat[2]
    await _end_chat(chat_id)

    # Уведомляем обоих участников
    for uid in (u1, u2):
        try:
            await call.bot.send_message(
                uid,
                "🛑 Чат завершён администрацией.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="💬 К чату", callback_data="chat_menu")],
                    [InlineKeyboardButton(text="⬅️ В меню", callback_data="menu")],
                ]),
            )
        except Exception:
            pass

    await log_admin_action(call.from_user.id, "chat_terminate", 0, f"chat #{chat_id} ({u1} <> {u2})")
    await call.answer(f"🛑 Чат #{chat_id} завершён!", show_alert=True)
    # Возвращаемся к списку
    await owner_chat_logs(call)


# ── Жалоба на участника чата (владелец — выбор действия) ──
@router.callback_query(F.data.startswith("owner_chat_warn_"))
async def owner_chat_warn(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    parts = call.data.replace("owner_chat_warn_", "").split("_")
    if len(parts) < 2:
        return await call.answer("❌", show_alert=True)
    chat_id = int(parts[0])
    target_uid = int(parts[1])

    user = await get_user(target_uid)
    uname = f"@{user['username']}" if user else str(target_uid)

    text = (
        f"<b>⚠️ Жалоба на участника</b>\n━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 {target_uid} ({uname})\n"
        f"💬 Чат: #{chat_id}\n\n"
        f"Выберите действие:"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚠️ Предупредить", callback_data=f"owner_chat_action_warn_{chat_id}_{target_uid}")],
        [InlineKeyboardButton(text="🔨 Забанить", callback_data=f"owner_chat_action_ban_{chat_id}_{target_uid}")],
        [InlineKeyboardButton(text="🛑 Завершить + Предупредить", callback_data=f"owner_chat_action_endwarn_{chat_id}_{target_uid}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"owner_chat_active_{chat_id}")],
    ])
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


# ── Действия по жалобе ──
@router.callback_query(F.data.startswith("owner_chat_action_"))
async def owner_chat_action(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)

    raw = call.data.replace("owner_chat_action_", "")
    # endwarn_123_456 / warn_123_456 / ban_123_456
    if raw.startswith("endwarn_"):
        action = "endwarn"
        rest = raw.replace("endwarn_", "")
    elif raw.startswith("warn_"):
        action = "warn"
        rest = raw.replace("warn_", "")
    elif raw.startswith("ban_"):
        action = "ban"
        rest = raw.replace("ban_", "")
    else:
        return await call.answer("❌", show_alert=True)

    parts = rest.split("_")
    chat_id = int(parts[0])
    target_uid = int(parts[1])

    result_lines = []

    if action in ("warn", "endwarn"):
        try:
            await call.bot.send_message(
                target_uid,
                "<b>⚠️ Предупреждение</b>\n"
                "━━━━━━━━━━━━━━━━━━━\n\n"
                "Вы получили предупреждение от администрации\n"
                "за нарушение правил чата.\n\n"
                "Повторное нарушение приведёт к бану!",
            )
            result_lines.append(f"⚠️ Предупреждение отправлено {target_uid}")
        except Exception:
            result_lines.append(f"❌ Не удалось отправить {target_uid}")

    if action == "ban":
        await ban_user(target_uid)
        result_lines.append(f"🔨 {target_uid} забанен")
        try:
            await call.bot.send_message(target_uid, "🔨 Вы забанены за нарушение правил чата.")
        except Exception:
            pass

    if action == "endwarn":
        from database import get_active_chat_by_id, end_active_chat as _end_chat2
        chat = await get_active_chat_by_id(chat_id)
        if chat:
            u1, u2 = chat[1], chat[2]
            await _end_chat2(chat_id)
            for uid in (u1, u2):
                try:
                    await call.bot.send_message(
                        uid,
                        "🛑 Чат завершён администрацией.",
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="⬅️ В меню", callback_data="menu")],
                        ]),
                    )
                except Exception:
                    pass
            result_lines.append(f"🛑 Чат #{chat_id} завершён")

    await log_admin_action(call.from_user.id, f"chat_{action}", target_uid, f"chat #{chat_id}")
    await call.answer("\n".join(result_lines) or "✅", show_alert=True)
    await owner_chat_logs(call)


# ══════════════════════════════════════════
#  НАСТРОЙКИ
# ══════════════════════════════════════════

# Схема настроек: ключ → (название, тип, значение по умолчанию, описание)
_SETTINGS_SCHEMA = {
    "maintenance":         ("🔧 Тех. работы",           "bool",  "false",    "Бот не отвечает участникам"),
    "payment_closed":      ("🚫 Оплата закрыта",        "bool",  "false",    "Временно закрыть оплату"),
    "welcome_msg":         ("👋 Приветствие",            "text",  "",         "Доп. текст при /start"),
    "sber_card":           ("💳 Реквизиты",             "text",  "",         "Номер карты / счёта"),
    "pay_fio":             ("📝 ФИО получателя",       "text",  "",         "ФИО для перевода"),
    "pay_method":          ("🏦 Способ оплаты",         "text",  "СБП",      "СБП / Сбербанк / Тинькофф"),
    "chat_cost":           ("💬 Стоимость чата",        "int",   "50",       "Клики за поиск чата"),
    "min_auction_bet":     ("🎪 Мин. ставка аукциона",  "int",   "100",      "Минимум для участия"),
    "max_nft_slots":       ("📦 Макс. слотов НФТ",      "int",   "5",        "По умолчанию слотов"),
    "nft_delete_cost":     ("🗑 Стоимость удаления НФТ","int",   "3500",     "Клики за удаление"),
    "ref_clicks":          ("🎁 Бонус реферала",        "int",   "200",      "Клики за реферала"),
    "shop_open_clicks":    ("🛒 Мин. клики магазин",    "int",   "10",       "Открыть магазин"),
    "minigames_clicks":    ("🎮 Мин. клики мини-игры",  "int",   "150",      "Открыть мини-игры"),
    "auto_approve_pay":    ("✅ Авто-одобрение",        "bool",  "false",    "Авто-одобрять платежи"),
    "notify_new_user":     ("🔔 Новый участник",        "bool",  "true",     "Уведомлять о регистрации"),
}


_SETTINGS_KEYS = list(_SETTINGS_SCHEMA.keys())
_STG_PER_PAGE = 5


async def _render_settings_page(call: CallbackQuery, page: int = 0):
    """Render a single settings page with pagination."""
    total = len(_SETTINGS_KEYS)
    total_pages = max(1, math.ceil(total / _STG_PER_PAGE))
    page = max(0, min(page, total_pages - 1))

    start = page * _STG_PER_PAGE
    end = min(start + _STG_PER_PAGE, total)
    page_keys = _SETTINGS_KEYS[start:end]

    lines = [f"<b>⚙️ Настройки бота</b>\n━━━━━━━━━━━━━━━━━━━\n"]
    kb_rows = []
    for key in page_keys:
        label, stype, default, desc = _SETTINGS_SCHEMA[key]
        val = await get_setting(key, default)
        if stype == "bool":
            icon = "🟢" if val.lower() in ("true", "1", "yes", "да") else "🔴"
            display = "ВКЛ" if val.lower() in ("true", "1", "yes", "да") else "ВЫКЛ"
            lines.append(f"  {icon} {label}: {display}")
            kb_rows.append([InlineKeyboardButton(
                text=f"{icon} {label}",
                callback_data=f"stg_toggle:{key}:{page}",
            )])
        else:
            short_val = (val[:25] + "…") if len(val) > 25 else (val or "—")
            lines.append(f"  {label}: {short_val}")
            kb_rows.append([InlineKeyboardButton(
                text=f"✏️ {label}",
                callback_data=f"stg_edit:{key}",
            )])
    lines.append("\n━━━━━━━━━━━━━━━━━━━")

    # Навигация
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⏮️", callback_data="stg_pg:0"))
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"stg_pg:{page-1}"))
    nav.append(InlineKeyboardButton(text=f"📂 {page+1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"stg_pg:{page+1}"))
        nav.append(InlineKeyboardButton(text="⏭️", callback_data=f"stg_pg:{total_pages-1}"))
    kb_rows.append(nav)

    kb_rows.append([InlineKeyboardButton(text="🔄 Сбросить все", callback_data="stg_reset_all")])
    kb_rows.append([InlineKeyboardButton(text="⬅️ Панель", callback_data="owner_panel")])
    await call.message.edit_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))
    await call.answer()


@router.callback_query(F.data == "owner_settings")
async def owner_settings(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    await _render_settings_page(call, 0)


@router.callback_query(F.data.startswith("stg_pg:"))
async def stg_page(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    page = int(call.data.split(":")[1])
    await _render_settings_page(call, page)


@router.callback_query(F.data.startswith("stg_toggle:"))
async def stg_toggle(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    parts = call.data.split(":")
    key = parts[1]
    page = int(parts[2]) if len(parts) > 2 else 0
    if key not in _SETTINGS_SCHEMA:
        return await call.answer("❌", show_alert=True)
    _, _, default, _ = _SETTINGS_SCHEMA[key]
    current = await get_setting(key, default)
    new_val = "false" if current.lower() in ("true", "1", "yes", "да") else "true"
    await set_setting(key, new_val)
    await log_admin_action(call.from_user.id, "setting", details=f"{key} = {new_val}")
    # Перерисовать ту же страницу
    await _render_settings_page(call, page)


@router.callback_query(F.data.startswith("stg_edit:"))
async def stg_edit(call: CallbackQuery, state: FSMContext):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    key = call.data.split(":")[1]
    if key not in _SETTINGS_SCHEMA:
        return await call.answer("❌", show_alert=True)
    label, stype, default, desc = _SETTINGS_SCHEMA[key]
    current = await get_setting(key, default)
    await state.set_state(OwnerStates.waiting_setting_value)
    await state.update_data(stg_key=key)
    hint = "число" if stype == "int" else "текст"
    await call.message.edit_text(
        f"✏️ {label}\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"📝 {desc}\n"
        f"Текущее: <b>{current or '—'}</b>\n"
        f"Тип: {hint}\n\n"
        f"Введите новое значение:",
        reply_markup=owner_back_panel_kb(),
        parse_mode="HTML",
    )
    await call.answer()


@router.message(OwnerStates.waiting_setting_value)
async def owner_setting_value(message: Message, state: FSMContext):
    if not _is_owner(message.from_user.id):
        return
    data = await state.get_data()
    key = data.get("stg_key")
    await state.clear()

    if not key or key not in _SETTINGS_SCHEMA:
        return await message.answer("❌ Ошибка", reply_markup=owner_back_panel_kb())

    label, stype, default, desc = _SETTINGS_SCHEMA[key]
    val = message.text.strip()

    # Валидация
    if stype == "int":
        try:
            int(val)
        except ValueError:
            return await message.answer("❌ Нужно целое число", reply_markup=owner_back_panel_kb())

    await set_setting(key, val)
    await log_admin_action(message.from_user.id, "setting", details=f"{key} = {val}")
    await message.answer(
        f"✅ {label} = <b>{val}</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⚙️ К настройкам", callback_data="owner_settings")],
            [InlineKeyboardButton(text="⬅️ Панель", callback_data="owner_panel")],
        ]),
    )


@router.callback_query(F.data == "stg_reset_all")
async def stg_reset_all(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    for key, (_, _, default, _) in _SETTINGS_SCHEMA.items():
        await set_setting(key, default)
    await log_admin_action(call.from_user.id, "setting", details="Сброс всех настроек")
    await call.answer("✅ Все настройки сброшены!", show_alert=True)
    await owner_settings(call)


# ══════════════════════════════════════════
#  УПРАВЛЕНИЕ АДМИНИСТРАТОРАМИ
# ══════════════════════════════════════════
@router.callback_query(F.data == "owner_admins")
async def owner_admins(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    await call.message.edit_text(
        "<b>👮 Управление администраторами</b>\n━━━━━━━━━━━━━━━━━━━\n",
        reply_markup=owner_admins_kb(),
    )
    await call.answer()


@router.callback_query(F.data == "owner_admin_list")
async def owner_admin_list(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    admins = await get_all_admins()
    if not admins:
        text = "Нет администраторов."
    else:
        lines = ["<b>👮 Администраторы</b>\n━━━━━━━━━━━━━━━━━━━\n"]
        for a in admins:
            uid, uname, added_at = a
            lines.append(f"• ID:{uid} @{uname} ({added_at[:10]})")
        text = "\n".join(lines)
    await call.message.edit_text(text, reply_markup=owner_admins_kb())
    await call.answer()


@router.callback_query(F.data == "owner_admin_genkey")
async def owner_admin_genkey(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    key = str(uuid.uuid4())[:12].upper()
    await create_admin_key(key, call.from_user.id)
    text = f"🔑 Ключ создан:\n\n`{key}`\n\nОтправьте его администратору."
    await call.message.edit_text(text, parse_mode="Markdown", reply_markup=owner_admins_kb())
    await call.answer()


@router.callback_query(F.data == "owner_admin_keys")
async def owner_admin_keys(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    keys = await get_all_admin_keys()
    if not keys:
        text = "Нет ключей."
    else:
        lines = ["📋 КЛЮЧИ\n══════════════════════\n"]
        for k in keys[:20]:
            kid, key_str, status, created_by, used_by, created_at = k
            s = "✅" if status == "active" else "🔴"
            lines.append(f"{s} {key_str} │ {status}")
        text = "\n".join(lines)
    await call.message.edit_text(text, reply_markup=owner_admins_kb())
    await call.answer()


@router.callback_query(F.data == "owner_admin_log")
async def owner_admin_log(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    actions = await get_admin_actions(limit=20)
    if not actions:
        text = "Нет действий."
    else:
        lines = ["📊 ДЕЙСТВИЯ АДМИНОВ\n══════════════════════\n"]
        for a in actions:
            aid = a[1]
            act = a[2]
            target = a[3]
            det = a[4] or ""
            lines.append(f"• {aid}: {act} → {target or '—'} {det[:30]}")
        text = "\n".join(lines)
    await call.message.edit_text(text, reply_markup=owner_admins_kb())
    await call.answer()


@router.callback_query(F.data == "owner_admin_remove")
async def owner_admin_remove(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    admins = await get_all_admins()
    if not admins:
        return await call.answer("Нет админов", show_alert=True)
    kb = []
    for a in admins:
        uid, uname, _ = a
        kb.append([InlineKeyboardButton(text=f"❌ @{uname} (ID:{uid})", callback_data=f"owner_rm_admin_{uid}")])
    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="owner_admins")])
    await call.message.edit_text("Выберите админа для удаления:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await call.answer()


@router.callback_query(F.data.startswith("owner_rm_admin_"))
async def owner_rm_admin(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    uid = int(call.data.replace("owner_rm_admin_", ""))
    await remove_admin(uid)
    await log_admin_action(call.from_user.id, "remove_admin", uid)
    await call.answer(f"✅ {uid} удалён из админов", show_alert=True)
    await owner_admins(call)


# ── Права админов (с пагинацией) ──
_PERM_LABELS = {
    "ban": "🔨 Бан/Разбан",
    "tickets": "📋 Тикеты",
    "nft": "🎨 Создание НФТ",
    "give_clicks": "💰 Выдача кликов",
    "broadcast": "📢 Рассылка",
    "events": "🎪 Ивенты",
    "complaints": "📨 Жалобы",
}


async def _show_admin_perms_page(call: CallbackQuery, page: int = 0):
    """Показать права одного админа с пагинацией по всем админам."""
    admins = await get_all_admins()
    if not admins:
        return await call.answer("Нет админов", show_alert=True)
    total = len(admins)
    page = max(0, min(page, total - 1))
    a = admins[page]
    uid, uname, added_at = a
    perms = await get_admin_permissions(uid)
    kb = []
    for perm_key, label in _PERM_LABELS.items():
        is_on = perms.get(perm_key, False)
        icon = "🟢" if is_on else "🔴"
        kb.append([InlineKeyboardButton(
            text=f"{icon} {label}",
            callback_data=f"perm_toggle_{uid}_{perm_key}_{page}",
        )])
    # Включить / выключить все
    all_on = all(perms.get(k, False) for k in _PERM_LABELS)
    toggle_text = "🔴 Выключить все" if all_on else "🟢 Включить все"
    kb.append([InlineKeyboardButton(text=toggle_text, callback_data=f"perm_all_{uid}_{page}")])
    # Разжаловать
    kb.append([InlineKeyboardButton(text="❌ Разжаловать", callback_data=f"perm_demote_{uid}_{page}")])
    # Пагинация
    nav = []
    if total > 1:
        nav.append(InlineKeyboardButton(text="⏮️", callback_data="adm_perm_pg_0"))
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"adm_perm_pg_{max(0, page - 1)}"))
        nav.append(InlineKeyboardButton(text=f"📂 {page + 1}/{total}", callback_data="noop"))
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"adm_perm_pg_{min(total - 1, page + 1)}"))
        nav.append(InlineKeyboardButton(text="⏭️", callback_data=f"adm_perm_pg_{total - 1}"))
        kb.append(nav)
    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="owner_admins")])
    text = (
        f"🔧 ПРАВА АДМИНА\n"
        f"══════════════════════\n\n"
        f"👤 @{uname} (ID: {uid})\n"
        f"📅 Добавлен: {added_at[:10] if added_at else '—'}\n"
    )
    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))


@router.callback_query(F.data == "owner_admin_perms")
async def owner_admin_perms(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    await _show_admin_perms_page(call, 0)
    await call.answer()


@router.callback_query(F.data.startswith("adm_perm_pg_"))
async def admin_perms_page(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    page = int(call.data.replace("adm_perm_pg_", ""))
    await _show_admin_perms_page(call, page)
    await call.answer()


@router.callback_query(F.data.startswith("perm_toggle_"))
async def perm_toggle(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    parts = call.data.replace("perm_toggle_", "").split("_")
    uid = int(parts[0])
    perm_key = parts[1]
    page = int(parts[2]) if len(parts) > 2 else 0
    perms = await get_admin_permissions(uid)
    perms[perm_key] = not perms.get(perm_key, False)
    await set_admin_permissions(uid, perms)
    await call.answer(f"{'🟢 Вкл' if perms[perm_key] else '🔴 Выкл'}", show_alert=True)
    await _show_admin_perms_page(call, page)


@router.callback_query(F.data.startswith("perm_all_"))
async def perm_toggle_all(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    parts = call.data.replace("perm_all_", "").split("_")
    uid = int(parts[0])
    page = int(parts[1]) if len(parts) > 1 else 0
    perms = await get_admin_permissions(uid)
    all_on = all(perms.get(k, False) for k in _PERM_LABELS)
    new_val = not all_on
    for k in _PERM_LABELS:
        perms[k] = new_val
    await set_admin_permissions(uid, perms)
    await log_admin_action(call.from_user.id, "perm_all", uid, f"{'all_on' if new_val else 'all_off'}")
    await call.answer(f"{'🟢 Все включены' if new_val else '🔴 Все выключены'}", show_alert=True)
    await _show_admin_perms_page(call, page)


@router.callback_query(F.data.startswith("perm_demote_"))
async def perm_demote(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    parts = call.data.replace("perm_demote_", "").split("_")
    uid = int(parts[0])
    page = int(parts[1]) if len(parts) > 1 else 0
    await remove_admin(uid)
    await log_admin_action(call.from_user.id, "demote_admin", uid)
    await call.answer(f"✅ Админ {uid} разжалован", show_alert=True)
    # Перезагрузить страницу (может быть меньше админов)
    admins = await get_all_admins()
    if not admins:
        await call.message.edit_text(
            "<b>👮 Управление администраторами</b>\n━━━━━━━━━━━━━━━━━━━\n",
            reply_markup=owner_admins_kb(),
        )
    else:
        await _show_admin_perms_page(call, min(page, len(admins) - 1))


# ══════════════════════════════════════════
#  АУКЦИОН (Создание ивента)
# ══════════════════════════════════════════
@router.callback_query(F.data == "event_create")
async def event_create_start(call: CallbackQuery, state: FSMContext):
    uid = call.from_user.id
    if not _is_owner(uid) and not await is_admin(uid):
        return await call.answer("❌", show_alert=True)
    await state.set_state(EventStates.waiting_name)
    back_cb = "owner_panel" if _is_owner(uid) else "admin_panel"
    await call.message.edit_text("🎪 Название аукциона:", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data=back_cb)]
    ]))
    await call.answer()


@router.message(EventStates.waiting_name)
async def event_name(message: Message, state: FSMContext):
    await state.update_data(event_name=message.text.strip())
    await state.set_state(EventStates.waiting_nft_name)
    await message.answer("🎨 Название НФТ-приза:")


@router.message(EventStates.waiting_nft_name)
async def event_nft_name(message: Message, state: FSMContext):
    await state.update_data(nft_name=message.text.strip())
    kb = []
    for rn, pct in NFT_RARITIES.items():
        emoji = NFT_RARITY_EMOJI.get(rn, "🟢")
        kb.append([InlineKeyboardButton(text=f"{emoji} {rn} ({pct}%)", callback_data=f"ev_rarity_{rn}")])
    await state.set_state(EventStates.waiting_rarity)
    await message.answer("Выберите редкость НФТ:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))


@router.callback_query(F.data.startswith("ev_rarity_"), EventStates.waiting_rarity)
async def event_rarity(call: CallbackQuery, state: FSMContext):
    rn = call.data.replace("ev_rarity_", "")
    pct = NFT_RARITIES.get(rn, 10)
    await state.update_data(nft_rarity=rn, nft_rarity_pct=pct)
    await state.set_state(EventStates.waiting_income)
    await call.message.edit_text("💰 Доход НФТ (Тохн/час):")
    await call.answer()


@router.message(EventStates.waiting_income)
async def event_income(message: Message, state: FSMContext):
    try:
        income = float(message.text.strip())
    except (ValueError, TypeError):
        return await message.answer("❌ Число")
    await state.update_data(nft_income=income)
    await state.set_state(EventStates.waiting_bet)
    await message.answer("💰 Минимальная ставка:")


@router.message(EventStates.waiting_bet)
async def event_bet(message: Message, state: FSMContext):
    try:
        bet = float(message.text.strip())
    except (ValueError, TypeError):
        return await message.answer("❌ Число")
    await state.update_data(bet=bet)
    await state.set_state(EventStates.waiting_duration)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="1 мин", callback_data="ev_dur_1"),
            InlineKeyboardButton(text="3 мин", callback_data="ev_dur_3"),
            InlineKeyboardButton(text="5 мин", callback_data="ev_dur_5"),
        ],
        [
            InlineKeyboardButton(text="10 мин", callback_data="ev_dur_10"),
            InlineKeyboardButton(text="25 мин", callback_data="ev_dur_25"),
            InlineKeyboardButton(text="40 мин", callback_data="ev_dur_40"),
        ],
    ])
    await message.answer("⏱ Длительность аукциона:", reply_markup=kb)


@router.callback_query(F.data.startswith("ev_dur_"), EventStates.waiting_duration)
async def event_duration_btn(call: CallbackQuery, state: FSMContext):
    dur = int(call.data.replace("ev_dur_", ""))
    await state.update_data(duration=dur)
    await state.set_state(EventStates.waiting_max_participants)
    await call.message.edit_text(f"👥 Максимум участников ({MIN_AUCTION_PARTICIPANTS}-{MAX_AUCTION_PARTICIPANTS}):")
    await call.answer()

@router.message(EventStates.waiting_max_participants)
async def event_max_part(message: Message, state: FSMContext):
    try:
        mp = int(message.text.strip())
        if not MIN_AUCTION_PARTICIPANTS <= mp <= MAX_AUCTION_PARTICIPANTS:
            raise ValueError
    except (ValueError, TypeError):
        return await message.answer(f"❌ {MIN_AUCTION_PARTICIPANTS}-{MAX_AUCTION_PARTICIPANTS}")
    await state.update_data(max_part=mp)
    data = await state.get_data()
    rn = data.get("nft_rarity", "Обычный")
    emoji = NFT_RARITY_EMOJI.get(rn, "🟢")
    text = (
        "🎪 ПРЕДПРОСМОТР АУКЦИОНА\n"
        "══════════════════════\n\n"
        f"📛 {data['event_name']}\n"
        f"🎨 Приз: {data['nft_name']}\n"
        f"✨ {emoji} {rn} ({data.get('nft_rarity_pct', 10)}%)\n"
        f"💰 Доход: {fnum(data['nft_income'])} Тохн/ч\n"
        f"💵 Мин. ставка: {fnum(data['bet'])} 💢\n"
        f"⏱ Длительность: {data['duration']} мин\n"
        f"👥 Макс. участников: {mp}\n\n"
        "Создать?"
    )
    await state.set_state(EventStates.confirm)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Создать", callback_data="event_confirm")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="owner_panel")],
    ])
    await message.answer(text, reply_markup=kb)


@router.callback_query(F.data == "event_confirm", EventStates.confirm)
async def event_confirm(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    eid = await create_event(
        data["event_name"], data["nft_name"], data.get("nft_rarity", "Обычный"),
        data["nft_income"], data["bet"], data["duration"],
        data["max_part"], call.from_user.id,
    )
    await log_admin_action(call.from_user.id, "create_event", details=f"Ивент #{eid}")
    await call.answer(f"✅ Аукцион #{eid} создан!", show_alert=True)
    await owner_panel(call, state)


# Просмотр участников (из профиля)
@router.callback_query(F.data.startswith("owner_user_hist_"))
async def owner_user_hist(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    uid = int(call.data.replace("owner_user_hist_", ""))
    logs = await get_activity_logs(user_id=uid, page=0, per_page=15)
    lines = [f"📝 ИСТОРИЯ {uid}\n══════════════════════\n"]
    for log in logs:
        act = log[2]
        det = log[3] or ""
        dt = log[4][:16] if log[4] else ""
        lines.append(f"• {act}: {det[:40]} ({dt})")
    if not logs:
        lines.append("Нет записей.")

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ К профилю", callback_data=f"owner_user_view_{uid}")]
    ])
    await call.message.edit_text("\n".join(lines), reply_markup=kb)
    await call.answer()


# ══════════════════════════════════════════
#  ЗАКАЗЫ НА ОПЛАТУ (владелец)
# ══════════════════════════════════════════
@router.callback_query(F.data.startswith("owner_orders:"))
async def owner_orders_list(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    page = int(call.data.split(":")[1])
    total = await count_pending_orders()
    per_page = 10
    total_pages = max(1, math.ceil(total / per_page))
    orders = await get_pending_orders(page, per_page)

    text = (
        f"💳 ЗАКАЗЫ НА ОПЛАТУ ({total})\n"
        "══════════════════════\n"
    )
    await call.message.edit_text(text, reply_markup=owner_orders_kb(orders, page, total_pages))
    await call.answer()


@router.callback_query(F.data.startswith("order_view:"))
async def order_view(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    order_id = int(call.data.split(":")[1])
    order = await get_payment_order(order_id)
    if not order:
        return await call.answer("❌ Не найден", show_alert=True)

    pkg_type = order["package_type"]
    pkg_id = order["package_id"]
    method = order["pay_method"]
    _METHOD_LABELS = {"sbp": "💳 СБП", "sber": "🟢 Сбербанк", "tinkoff": "🟡 Тинькофф", "yukassa_auto": "🤖 ЮKassa"}
    method_label = _METHOD_LABELS.get(method, method)

    if pkg_type == "clicks" and pkg_id in CLICK_PACKAGES:
        clicks, price_rub, pkg_label = CLICK_PACKAGES[pkg_id]
        desc = f"💢 {fnum(clicks)} Тохн"
    elif pkg_type == "vip" and pkg_id in VIP_PACKAGES:
        mc, mi, dur, price_rub, pkg_label = VIP_PACKAGES[pkg_id]
        dur_text = f"{dur} дней" if dur > 0 else "навсегда"
        desc = f"⭐ ×{mc} клик, ×{mi} доход ({dur_text})"
    else:
        desc = f"{pkg_type}/{pkg_id}"
        pkg_label = "?"

    text = (
        f"📋 ЗАКАЗ #{order_id}\n"
        "══════════════════════\n\n"
        f"👤 Пользователь: {order['user_id']}\n"
        f"📦 Пакет: {pkg_label}\n"
        f"📝 Что получит: {desc}\n"
        f"💳 Способ: {method_label}\n"
        f"💰 Сумма: {order['amount_rub']}₽\n"
        f"Статус: {order['status']}\n"
        f"Дата: {order['created_at'][:16] if order['created_at'] else '—'}\n"
        "══════════════════════"
    )
    kb = order_action_kb(order_id)
    # Показать фото скриншота, если есть
    screenshot = order["screenshot_file_id"] if "screenshot_file_id" in order.keys() else None
    if screenshot:
        try:
            await call.message.delete()
        except Exception:
            pass
        try:
            await call.bot.send_photo(
                call.message.chat.id, screenshot,
                caption=text, reply_markup=kb,
            )
        except Exception:
            await call.bot.send_message(
                call.message.chat.id, text, reply_markup=kb,
            )
    else:
        await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


@router.callback_query(F.data.startswith("order_approve:"))
async def order_approve(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    order_id = int(call.data.split(":")[1])
    order = await get_payment_order(order_id)
    if not order:
        return await call.answer("❌ Не найден", show_alert=True)
    if order["status"] != "pending":
        return await call.answer(f"ℹ️ Статус: {order['status']}", show_alert=True)

    uid = order["user_id"]
    pkg_type = order["package_type"]
    pkg_id = order["package_id"]

    # Выдаём покупку
    if pkg_type == "clicks" and pkg_id in CLICK_PACKAGES:
        clicks, _, _ = CLICK_PACKAGES[pkg_id]
        await update_clicks(uid, clicks)
        reward_text = f"💢 +{fnum(clicks)} Тохн выдано!"
    elif pkg_type == "vip" and pkg_id in VIP_PACKAGES:
        mc, mi, dur, _, label = VIP_PACKAGES[pkg_id]
        vip_name = "VIP" if mc == 2 and mi == 1 else "Premium"
        await set_user_vip(uid, vip_name, mc, mi, dur)
        dur_text = f"{dur} дней" if dur > 0 else "навсегда"
        reward_text = f"⭐ {vip_name} выдан ({dur_text})"
    else:
        reward_text = "❓ Неизвестный пакет"

    await resolve_payment_order(order_id, call.from_user.id, "approved")
    # Снимаем бан оплаты если был
    await unban_payment(uid)
    await log_admin_action(call.from_user.id, "approve_payment",
                           uid, f"order #{order_id}")

    # Уведомляем пользователя
    try:
        await call.bot.send_message(
            uid,
            f"✅ ПОКУПКА ВЫДАНА!\n"
            f"══════════════════════\n\n"
            f"Заказ #{order_id} одобрен!\n"
            f"{reward_text}\n\n"
            f"Спасибо за покупку! 🎉",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ В меню", callback_data="menu")],
            ]),
        )
    except Exception:
        pass

    await call.answer(f"✅ {reward_text}", show_alert=True)
    # Возвращаемся к списку (page 0)
    total = await count_pending_orders()
    per_page = 10
    total_pages = max(1, math.ceil(total / per_page))
    orders = await get_pending_orders(0, per_page)
    text = f"💳 ЗАКАЗЫ НА ОПЛАТУ ({total})\n══════════════════════\n"
    await call.message.edit_text(text, reply_markup=owner_orders_kb(orders, 0, total_pages))


@router.callback_query(F.data.startswith("order_reject:"))
async def order_reject(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    order_id = int(call.data.split(":")[1])
    order = await get_payment_order(order_id)
    if not order:
        return await call.answer("❌ Не найден", show_alert=True)
    if order["status"] != "pending":
        return await call.answer(f"ℹ️ Статус: {order['status']}", show_alert=True)

    await resolve_payment_order(order_id, call.from_user.id, "rejected")
    await log_admin_action(call.from_user.id, "reject_payment",
                           order["user_id"], f"order #{order_id}")

    # Уведомляем пользователя
    try:
        await call.bot.send_message(
            order["user_id"],
            f"❌ Платёж отклонён\n"
            f"══════════════════════\n\n"
            f"Заказ #{order_id} не подтверждён.\n"
            f"Если вы оплатили — нажмите кнопку ниже.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💬 Написать администрации", callback_data=f"order_reply:{order_id}")],
                [InlineKeyboardButton(text="⬅️ В меню", callback_data="menu")],
            ]),
        )
    except Exception:
        pass

    await call.answer(f"❌ Заказ #{order_id} отклонён", show_alert=True)
    # Возвращаемся к списку (page 0)
    total = await count_pending_orders()
    per_page = 10
    total_pages = max(1, math.ceil(total / per_page))
    orders_list = await get_pending_orders(0, per_page)
    text = f"💳 ЗАКАЗЫ НА ОПЛАТУ ({total})\n══════════════════════\n"
    await call.message.edit_text(text, reply_markup=owner_orders_kb(orders_list, 0, total_pages))


# ── Написать покупателю (диалог по заказу) ──
@router.callback_query(F.data.startswith("order_msg:"))
async def order_msg_start(call: CallbackQuery, state: FSMContext):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    order_id = int(call.data.split(":")[1])
    order = await get_payment_order(order_id)
    if not order:
        return await call.answer("❌ Заказ не найден", show_alert=True)
    await state.set_state(OwnerStates.payment_msg_to_user)
    await state.update_data(order_id=order_id, order_user_id=order["user_id"])
    await call.message.answer(
        f"💬 Введите сообщение для пользователя\n"
        f"(заказ #{order_id}, uid {order['user_id']}):\n\n"
        f"Отправьте текст или /cancel для отмены.",
    )
    await call.answer()


@router.message(OwnerStates.payment_msg_to_user)
async def order_msg_send(message: Message, state: FSMContext):
    if not _is_owner(message.from_user.id):
        return
    if message.text and message.text.strip() == "/cancel":
        await state.clear()
        return await message.answer("❌ Отменено.")
    data = await state.get_data()
    uid = data.get("order_user_id")
    order_id = data.get("order_id")
    if not uid:
        await state.clear()
        return
    text_to_send = (
        f"📩 <b>Сообщение от администрации</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"📋 Заказ: #{order_id}\n\n"
        f"{message.text or '(фото/файл)'}\n\n"
        f"━━━━━━━━━━━━━━━━━━━"
    )
    reply_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Ответить", callback_data=f"order_reply:{order_id}")],
    ])
    try:
        await message.bot.send_message(uid, text_to_send, parse_mode="HTML",
                                        reply_markup=reply_kb)
        await message.answer(f"✅ Сообщение отправлено пользователю {uid}.")
    except Exception as e:
        await message.answer(f"❌ Не удалось отправить: {e}")
    await state.clear()


# ── Фейк-чек: отклонить + забанить оплату ──
@router.callback_query(F.data.startswith("order_fake:"))
async def order_fake_ban(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    order_id = int(call.data.split(":")[1])
    order = await get_payment_order(order_id)
    if not order:
        return await call.answer("❌ Не найден", show_alert=True)

    uid = order["user_id"]
    # Отклоняем заказ
    if order["status"] == "pending":
        await resolve_payment_order(order_id, call.from_user.id, "rejected")
    # Баним оплату
    await ban_payment(uid)
    await log_admin_action(call.from_user.id, "payment_ban", uid,
                           f"Fake receipt, order #{order_id}")

    # Уведомляем пользователя
    try:
        await call.bot.send_message(
            uid,
            "🚫 <b>Доступ к оплате заблокирован</b>\n\n"
            f"Заказ #{order_id} отклонён.\n"
            "Причина: подозрение на поддельный чек.\n\n"
            "Раздел оплаты заблокирован \u043dавсегда.",
            parse_mode="HTML",
        )
    except Exception:
        pass

    await call.answer(f"🚫 Заказ #{order_id} отклонён, пользователь забанен в оплате.", show_alert=True)
    # Возвращаемся к списку
    total = await count_pending_orders()
    per_page = 10
    total_pages = max(1, math.ceil(total / per_page))
    orders_list = await get_pending_orders(0, per_page)
    text = f"💳 ЗАКАЗЫ НА ОПЛАТУ ({total})\n══════════════════════\n"
    try:
        await call.message.edit_text(text, reply_markup=owner_orders_kb(orders_list, 0, total_pages))
    except Exception:
        pass

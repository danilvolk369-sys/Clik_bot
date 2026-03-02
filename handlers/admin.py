# ======================================================
# ADMIN — Панель администратора (ключ-активация)
# ======================================================
import math
import random

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from config import OWNER_ID, NFT_RARITIES, NFT_RARITY_EMOJI, RANKS_LIST, CLICK_PACKAGES, VIP_PACKAGES
from states import AdminStates, EventStates
from database import (
    is_admin, add_admin, use_admin_key, get_admin_permissions,
    get_user, ban_user, unban_user,
    get_banned_users, count_banned_users,
    get_users_page, count_users_all, count_users, get_online_count,
    update_clicks, reset_user_progress,
    get_open_tickets, count_open_tickets,
    create_nft_template, delete_nft_template,
    log_admin_action, get_admin_actions,
    set_user_online,
    count_user_nfts, get_user_nft_slots,
    set_user_vip, remove_user_vip,
    ban_payment, unban_payment, is_payment_banned,
    log_activity, get_activity_logs, count_activity_logs,
    update_bonus_click, update_passive_income,
    update_income_capacity, add_nft_slot,
    count_pending_complaints,
    get_setting, set_setting,
    count_pending_orders, get_pending_orders, get_payment_order,
    resolve_payment_order,
    grant_nft_to_user, create_market_listing,
    get_chat_logs_list, get_chat_messages,
    get_all_active_chats, get_active_chat_by_id,
    count_chat_messages, end_active_chat,
    count_nft_templates, get_nft_templates_page, get_nft_template,
    remove_admin,
)
from keyboards import (
    admin_panel_kb, admin_back_kb,
    banned_list_kb, users_list_kb, user_profile_admin_kb,
    owner_nft_publish_kb, ban_duration_kb,
    user_nfts_view_kb, admin_logs_kb,
    owner_nft_list_kb, owner_nft_detail_kb, owner_orders_kb, order_action_kb,
    donate_submenu_kb,
)
from handlers.common import fnum

router = Router()


async def _user_profile_kb(uid: int, prefix: str = "adm", page: int = 0):
    """Клавиатура профиля."""
    return user_profile_admin_kb(uid, prefix, page)


def _has_perm(perms: dict, key: str) -> bool:
    return perms.get(key, False)


# ── Активация ключа ──
@router.callback_query(F.data == "admin_activate_key")
async def admin_activate_key(call: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.waiting_key)
    await call.message.edit_text("🔑 Введите ключ активации:", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="menu")]
    ]))
    await call.answer()


@router.message(AdminStates.waiting_key)
async def admin_key_msg(message: Message, state: FSMContext):
    await state.clear()
    key = message.text.strip()
    ok = await use_admin_key(key, message.from_user.id)
    if ok:
        await add_admin(message.from_user.id, message.from_user.username or "admin", OWNER_ID)
        await message.answer("✅ Вы стали администратором!", reply_markup=admin_panel_kb())
    else:
        await message.answer("❌ Неверный ключ.")


# ── Панель ──
@router.callback_query(F.data == "admin_panel")
async def admin_panel(call: CallbackQuery, state: FSMContext):
    uid = call.from_user.id
    if uid == OWNER_ID:
        # Владелец — перенаправляем в его панель
        from handlers.owner import owner_panel
        return await owner_panel(call, state)
    if not await is_admin(uid):
        return await call.answer("❌", show_alert=True)
    await state.clear()
    await set_user_online(uid)
    await call.message.edit_text("👮 ПАНЕЛЬ АДМИНИСТРАТОРА\n══════════════════════\n",
                                  reply_markup=admin_panel_kb(0))
    await call.answer()


@router.callback_query(F.data.startswith("adm_panel_page:"))
async def adm_panel_page(call: CallbackQuery):
    uid = call.from_user.id
    if not await is_admin(uid) and uid != OWNER_ID:
        return await call.answer("❌", show_alert=True)
    page = int(call.data.split(":")[1])
    await call.message.edit_text("👮 ПАНЕЛЬ АДМИНИСТРАТОРА\n══════════════════════\n",
                                  reply_markup=admin_panel_kb(page))
    await call.answer()


# ══════════════════════════════════════════
#  БАН / РАЗБАН
# ══════════════════════════════════════════
@router.callback_query(F.data == "adm_ban")
async def adm_ban(call: CallbackQuery, state: FSMContext):
    uid = call.from_user.id
    if not await is_admin(uid):
        return await call.answer("❌", show_alert=True)
    perms = await get_admin_permissions(uid)
    if not _has_perm(perms, "ban"):
        return await call.answer("❌ Нет прав", show_alert=True)
    await state.set_state(AdminStates.waiting_ban_id)
    await call.message.edit_text("🔨 ID для бана:", reply_markup=admin_back_kb())
    await call.answer()


@router.message(AdminStates.waiting_ban_id)
async def adm_ban_id(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    try:
        uid = int(message.text.strip())
    except (ValueError, TypeError):
        return await message.answer("❌ Число")
    await state.set_state(AdminStates.waiting_ban_duration)
    await state.set_data({"ban_uid": uid})
    await message.answer("⏱ Часы или «permanent»:")


@router.message(AdminStates.waiting_ban_duration)
async def adm_ban_duration(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    data = await state.get_data()
    uid = data["ban_uid"]
    duration = message.text.strip()
    await state.clear()
    await ban_user(uid, duration)
    await log_admin_action(message.from_user.id, "ban", uid, duration)
    await message.answer(f"✅ {uid} забанен!", reply_markup=admin_back_kb())


@router.callback_query(F.data == "adm_unban")
async def adm_unban(call: CallbackQuery, state: FSMContext):
    uid = call.from_user.id
    if not await is_admin(uid):
        return await call.answer("❌", show_alert=True)
    perms = await get_admin_permissions(uid)
    if not _has_perm(perms, "ban"):
        return await call.answer("❌ Нет прав", show_alert=True)
    await state.set_state(AdminStates.waiting_unban_id)
    await call.message.edit_text("✅ ID для разбана:", reply_markup=admin_back_kb())
    await call.answer()


@router.message(AdminStates.waiting_unban_id)
async def adm_unban_id(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    try:
        uid = int(message.text.strip())
    except (ValueError, TypeError):
        return await message.answer("❌ Число")
    await state.clear()
    await unban_user(uid)
    await log_admin_action(message.from_user.id, "unban", uid)
    await message.answer(f"✅ {uid} разбанен!", reply_markup=admin_back_kb())


@router.callback_query(F.data.startswith("adm_unban_quick_"))
async def adm_unban_quick(call: CallbackQuery):
    uid = call.from_user.id
    if not await is_admin(uid):
        return await call.answer("❌", show_alert=True)
    target = int(call.data.replace("adm_unban_quick_", ""))
    await unban_user(target)
    await log_admin_action(uid, "unban", target)
    await call.answer(f"✅ {target} разбанен!", show_alert=True)


@router.callback_query(F.data.startswith("adm_banned:"))
async def adm_banned_list(call: CallbackQuery):
    uid = call.from_user.id
    if not await is_admin(uid) and uid != OWNER_ID:
        return await call.answer("❌", show_alert=True)
    page = int(call.data.split(":")[1])
    total = await count_banned_users()
    per_page = 10
    total_pages = max(1, math.ceil(total / per_page))
    users = await get_banned_users(page, per_page)
    text = f"🚫 ЗАБАНЕННЫЕ ({total})\n══════════════════════\n"
    await call.message.edit_text(text, reply_markup=banned_list_kb(users, page, total_pages, "adm"))
    await call.answer()


# Бан/Разбан из профиля
@router.callback_query(F.data.startswith("adm_banmenu_"))
async def adm_ban_menu_profile(call: CallbackQuery):
    if not await is_admin(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    uid = int(call.data.replace("adm_banmenu_", ""))
    await call.message.edit_text(
        f"🔨 Бан пользователя {uid}\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"Выберите длительность бана:",
        reply_markup=ban_duration_kb(uid, "adm"),
    )
    await call.answer()


@router.callback_query(F.data.startswith("adm_doban_"))
async def adm_doban(call: CallbackQuery):
    if not await is_admin(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    parts = call.data.split("_")
    uid = int(parts[2])
    duration = parts[3]
    await ban_user(uid, duration)
    await log_admin_action(call.from_user.id, "ban", uid, f"Бан: {duration}")
    await log_activity(uid, "ban", f"Забанен админом на {duration}")
    dur_text = "навсегда" if duration == "permanent" else f"{duration}ч"
    await call.answer(f"✅ {uid} забанен на {dur_text}", show_alert=True)
    user = await get_user(uid)
    if user:
        text = await _adm_user_profile_text(user)
        await call.message.edit_text(text, reply_markup=await _user_profile_kb(uid, "adm", 0))


@router.callback_query(F.data.startswith("adm_ban_user_"))
async def adm_ban_user_profile(call: CallbackQuery, state: FSMContext):
    uid = call.from_user.id
    if not await is_admin(uid):
        return await call.answer("❌", show_alert=True)
    target = int(call.data.replace("adm_ban_user_", ""))
    await state.set_state(AdminStates.waiting_ban_duration)
    await state.set_data({"ban_uid": target})
    await call.message.edit_text(f"⏱ Бан {target}. Часы или «permanent»:", reply_markup=admin_back_kb())
    await call.answer()


@router.callback_query(F.data.startswith("adm_unban_user_"))
async def adm_unban_user_profile(call: CallbackQuery):
    uid = call.from_user.id
    if not await is_admin(uid):
        return await call.answer("❌", show_alert=True)
    target = int(call.data.replace("adm_unban_user_", ""))
    await unban_user(target)
    await call.answer(f"✅ {target} разбанен", show_alert=True)
    user = await get_user(target)
    if user:
        text = await _adm_user_profile_text(user)
        await call.message.edit_text(text, reply_markup=await _user_profile_kb(target, "adm", 0))


# ── Пагинация профиля ──
@router.callback_query(F.data.startswith("adm_profile_pg_"))
async def adm_profile_page(call: CallbackQuery):
    if not await is_admin(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    parts = call.data.split("_")
    uid = int(parts[3])
    page = int(parts[4])
    user = await get_user(uid)
    if not user:
        return await call.answer("❌ Не найден", show_alert=True)
    text = await _adm_user_profile_text(user)
    kb = await _user_profile_kb(uid, "adm", page)
    try:
        await call.message.edit_text(text, reply_markup=kb)
    except Exception:
        try:
            await call.message.delete()
        except Exception:
            pass
        await call.bot.send_message(call.message.chat.id, text, reply_markup=kb)
    await call.answer()


# ── VIP / Premium ──
@router.callback_query(F.data.startswith("adm_setvip_"))
async def adm_set_vip(call: CallbackQuery):
    if not await is_admin(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    parts = call.data.split("_")
    uid = int(parts[2])
    action = parts[3]
    if action == "remove":
        await remove_user_vip(uid)
        await log_admin_action(call.from_user.id, "remove_vip", uid)
        await call.answer("✅ VIP/Premium снят", show_alert=True)
    elif action == "rmvip":
        await remove_user_vip(uid)
        await log_admin_action(call.from_user.id, "remove_vip", uid, "VIP")
        await call.answer("✅ VIP снят", show_alert=True)
    elif action == "rmprem":
        await remove_user_vip(uid)
        await log_admin_action(call.from_user.id, "remove_vip", uid, "Premium")
        await call.answer("✅ Premium снят", show_alert=True)
    elif action == "vip7":
        await set_user_vip(uid, "VIP", 2, 0.5, 7)
        await log_admin_action(call.from_user.id, "set_vip", uid, "VIP 7d")
        await call.answer("✅ VIP на 7 дней", show_alert=True)
    elif action == "vip30":
        await set_user_vip(uid, "VIP", 2, 0.5, 30)
        await log_admin_action(call.from_user.id, "set_vip", uid, "VIP 30d")
        await call.answer("✅ VIP на 30 дней", show_alert=True)
    elif action == "vip0":
        await set_user_vip(uid, "VIP", 2, 0.5, 0)
        await log_admin_action(call.from_user.id, "set_vip", uid, "VIP perm")
        await call.answer("✅ VIP навсегда", show_alert=True)
    elif action == "prem7":
        await set_user_vip(uid, "Premium", 3, 2, 7)
        await log_admin_action(call.from_user.id, "set_vip", uid, "Prem 7d")
        await call.answer("✅ Premium на 7 дней", show_alert=True)
    elif action == "prem30":
        await set_user_vip(uid, "Premium", 3, 2, 30)
        await log_admin_action(call.from_user.id, "set_vip", uid, "Prem 30d")
        await call.answer("✅ Premium на 30 дней", show_alert=True)
    elif action == "prem0":
        await set_user_vip(uid, "Premium", 3, 2, 0)
        await log_admin_action(call.from_user.id, "set_vip", uid, "Prem perm")
        await call.answer("✅ Premium навсегда", show_alert=True)
    else:
        return await call.answer("❓", show_alert=True)
    user = await get_user(uid)
    if user:
        from keyboards import donate_submenu_kb
        vip = user["vip_type"]
        pb = await is_payment_banned(uid)
        await call.message.edit_text(
            f"🎁 <b>Донат — {uid}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━\n\n"
            f"Статус: <b>{vip or 'нет'}</b>\n\n"
            f"Выберите действие:",
            reply_markup=donate_submenu_kb(uid, "adm", vip, pb),
        )


# ── Бан/Разбан оплаты ──
@router.callback_query(F.data.startswith("adm_payban_"))
async def adm_payban(call: CallbackQuery):
    if not await is_admin(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    uid = int(call.data.replace("adm_payban_", ""))
    await ban_payment(uid)
    await log_admin_action(call.from_user.id, "payment_ban", uid)
    await call.answer("🚫 Оплата заблокирована", show_alert=True)
    user = await get_user(uid)
    if user:
        from keyboards import donate_submenu_kb
        vip = user["vip_type"]
        pb = await is_payment_banned(uid)
        await call.message.edit_text(
            f"🎁 <b>Донат — {uid}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━\n\n"
            f"Статус: <b>{vip or 'нет'}</b>\n\n"
            f"Выберите действие:",
            reply_markup=donate_submenu_kb(uid, "adm", vip, pb),
        )


@router.callback_query(F.data.startswith("adm_payunban_"))
async def adm_payunban(call: CallbackQuery):
    if not await is_admin(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    uid = int(call.data.replace("adm_payunban_", ""))
    await unban_payment(uid)
    await log_admin_action(call.from_user.id, "payment_unban", uid)
    await call.answer("✅ Оплата разблокирована", show_alert=True)
    user = await get_user(uid)
    if user:
        from keyboards import donate_submenu_kb
        vip = user["vip_type"]
        pb = await is_payment_banned(uid)
        await call.message.edit_text(
            f"🎁 <b>Донат — {uid}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━\n\n"
            f"Статус: <b>{vip or 'нет'}</b>\n\n"
            f"Выберите действие:",
            reply_markup=donate_submenu_kb(uid, "adm", vip, pb),
        )


# ══════════════════════════════════════════
#  Донат, Написать, Буст
# ══════════════════════════════════════════

# ── Подменю Донат (VIP/Premium) ──
@router.callback_query(F.data.startswith("adm_donate_"))
async def adm_donate_menu(call: CallbackQuery):
    if not await is_admin(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    uid = int(call.data.replace("adm_donate_", ""))
    user = await get_user(uid)
    vip = user["vip_type"] if user else None
    pb = await is_payment_banned(uid)
    from keyboards import donate_submenu_kb
    await call.message.edit_text(
        f"🎁 <b>Донат — {uid}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"Статус: <b>{vip or 'нет'}</b>\n\n"
        f"Выберите действие:",
        reply_markup=donate_submenu_kb(uid, "adm", vip, pb),
    )
    await call.answer()


# ── Выдать донат (клики) ──
@router.callback_query(F.data.startswith("adm_givedon_"))
async def adm_give_donate(call: CallbackQuery):
    if not await is_admin(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    uid = int(call.data.replace("adm_givedon_", ""))
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="1.000 💢", callback_data=f"adm_don_{uid}_1000"),
            InlineKeyboardButton(text="5.000 💢", callback_data=f"adm_don_{uid}_5000"),
        ],
        [
            InlineKeyboardButton(text="10.000 💢", callback_data=f"adm_don_{uid}_10000"),
            InlineKeyboardButton(text="50.000 💢", callback_data=f"adm_don_{uid}_50000"),
        ],
        [
            InlineKeyboardButton(text="100.000 💢", callback_data=f"adm_don_{uid}_100000"),
            InlineKeyboardButton(text="500.000 💢", callback_data=f"adm_don_{uid}_500000"),
        ],
        [
            InlineKeyboardButton(text="1.000.000 💢", callback_data=f"adm_don_{uid}_1000000"),
        ],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"adm_donate_{uid}")],
    ])
    await call.message.edit_text(
        f"🎁 Выдать донат пользователю {uid}\n"
        f"━━━━━━━━━━━━━━━━━━━\n\nВыберите количество Тохн:",
        reply_markup=kb)
    await call.answer()


@router.callback_query(F.data.startswith("adm_don_"))
async def adm_donate_exec(call: CallbackQuery):
    if not await is_admin(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    parts = call.data.split("_")  # adm_don_{uid}_{amount}
    uid = int(parts[2])
    amount = int(parts[3])
    await update_clicks(uid, amount)
    await log_admin_action(call.from_user.id, "donate", uid, f"+{amount} clicks")
    await log_activity(uid, "donate", f"Получен донат +{fnum(amount)} от администрации")
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
        from keyboards import donate_submenu_kb
        vip = user["vip_type"]
        pb = await is_payment_banned(uid)
        await call.message.edit_text(
            await _adm_profile_text(user),
            reply_markup=donate_submenu_kb(uid, "adm", vip, pb),
        )


# ── Написать участнику ──
@router.callback_query(F.data.startswith("adm_msgusr_"))
async def adm_msg_user_start(call: CallbackQuery, state: FSMContext):
    if not await is_admin(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    uid = int(call.data.replace("adm_msgusr_", ""))
    await state.set_state(AdminStates.msg_to_user)
    await state.update_data(target_uid=uid)
    await call.message.answer(
        f"💬 Введите сообщение для пользователя {uid}:\n\n"
        f"Отправьте текст или /cancel для отмены.",
    )
    await call.answer()


@router.message(AdminStates.msg_to_user)
async def adm_msg_user_send(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
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
            reply_markup=dialog_user_reply_kb("adm", message.from_user.id),
        )
        await message.answer(
            f"✅ Сообщение отправлено пользователю {uid}.",
            reply_markup=dialog_after_send_kb("adm", uid),
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
@router.callback_query(F.data.startswith("adm_dialog_cont_"))
async def adm_dialog_continue(call: CallbackQuery, state: FSMContext):
    if not await is_admin(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    uid = int(call.data.split("_")[-1])
    await state.set_state(AdminStates.msg_to_user)
    await state.update_data(target_uid=uid)
    await call.message.answer(
        f"💬 Введите сообщение для пользователя {uid}:\n\n"
        f"Отправьте текст или /cancel для отмены.",
    )
    await call.answer()


@router.callback_query(F.data.startswith("adm_dialog_end_"))
async def adm_dialog_end(call: CallbackQuery, state: FSMContext):
    if not await is_admin(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    uid = int(call.data.split("_")[-1])
    await state.clear()
    await call.message.edit_text("🚪 Диалог завершён.")
    # Уведомляем пользователя
    try:
        await call.bot.send_message(uid, "ℹ️ Администратор завершил диалог.")
    except Exception:
        pass
    await call.answer()


# ── Добавить значение (сила клика / доход / ёмкость / слоты) ──
@router.callback_query(F.data.startswith("adm_addval_"))
async def adm_addval_menu(call: CallbackQuery):
    if not await is_admin(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    parts = call.data.split("_")  # adm_addval_{uid}_{type}
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
                text=label, callback_data=f"adm_doval_{uid}_{val_type}_{a}"))
        rows.append(row)
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=f"adm_profile_pg_{uid}_1")])

    await call.message.edit_text(
        f"{name} для {uid}\n━━━━━━━━━━━━━━━━━━━\n\nВыберите значение:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await call.answer()


@router.callback_query(F.data.startswith("adm_doval_"))
async def adm_doval_exec(call: CallbackQuery):
    if not await is_admin(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    parts = call.data.split("_")  # adm_doval_{uid}_{type}_{amount}
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
    await log_activity(uid, "admin_boost", f"Администрация выдала: {label}")
    try:
        await call.bot.send_message(
            uid, f"🎁 <b>Подарок от администрации!</b>\n━━━━━━━━━━━━━━━━━━━\n\n{label}\n",
            parse_mode="HTML")
    except Exception:
        pass
    await call.answer(f"✅ {label}", show_alert=True)
    user = await get_user(uid)
    if user:
        text = await _adm_profile_text(user)
        await call.message.edit_text(text, reply_markup=await _user_profile_kb(uid, "adm", 1))


# ══════════════════════════════════════════
#  СТРАНЦА 2 – Ранг, Логи, Рефералы
# ══════════════════════════════════════════

# ── Сменить ранг ──
@router.callback_query(F.data.startswith("adm_setrank_"))
async def adm_set_rank_menu(call: CallbackQuery):
    if not await is_admin(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    uid = int(call.data.replace("adm_setrank_", ""))
    rows = []
    for i in range(1, 16, 3):
        row = []
        for r in range(i, min(i+3, 16)):
            row.append(InlineKeyboardButton(
                text=f"{r}. {RANKS_LIST[r].split(' ', 1)[0]}",
                callback_data=f"adm_dorank_{uid}_{r}"))
        rows.append(row)
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=f"adm_profile_pg_{uid}_1")])
    await call.message.edit_text(
        f"🏷️ Сменить ранг для {uid}\n━━━━━━━━━━━━━━━━━━━\n\nВыберите ранг:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await call.answer()


@router.callback_query(F.data.startswith("adm_dorank_"))
async def adm_set_rank_exec(call: CallbackQuery):
    if not await is_admin(call.from_user.id):
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
        text = await _adm_profile_text(user)
        await call.message.edit_text(text, reply_markup=await _user_profile_kb(uid, "adm", 1))


# ── Логи действий пользователя ──
@router.callback_query(F.data.startswith("adm_actlog_"))
async def adm_activity_log(call: CallbackQuery):
    if not await is_admin(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    uid = int(call.data.replace("adm_actlog_", ""))
    logs = await get_activity_logs(user_id=uid, page=0, per_page=15)
    lines = [f"📊 Логи действий {uid}\n━━━━━━━━━━━━━━━━━━━\n"]
    if not logs:
        lines.append("Нет записей.")
    else:
        for log in logs:
            dt = log[4][:16] if log[4] else "?"
            lines.append(f"• {dt} │ {log[2]} │ {log[3] or ''}")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"adm_profile_pg_{uid}_1")],
    ])
    await call.message.edit_text("\n".join(lines), reply_markup=kb)
    await call.answer()


# ── Обнулить рефералов ──
@router.callback_query(F.data.startswith("adm_resetref_"))
async def adm_reset_referrals(call: CallbackQuery):
    if not await is_admin(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    uid = int(call.data.replace("adm_resetref_", ""))
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
        text = await _adm_profile_text(user)
        await call.message.edit_text(text, reply_markup=await _user_profile_kb(uid, "adm", 1))


# ── Просмотр НФТ юзера (топ-5) ──
@router.callback_query(F.data.startswith("adm_usernfts_"))
async def adm_view_user_nfts(call: CallbackQuery):
    if not await is_admin(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    uid = int(call.data.replace("adm_usernfts_", ""))
    from database import get_user_top_nfts
    nfts = await get_user_top_nfts(uid, 5)
    user = await get_user(uid)
    uname = user["username"] if user else uid
    from config import NFT_RARITY_EMOJI
    text = (
        f"<b>🎨 НФТ · @{uname}</b>\n"
        "━━━━━━━━━━━━━━━━━━━\n\n"
        f"Топ-5 НФТ по доходу:\n"
    )
    if not nfts:
        text += "\n— нет НФТ —\n"
    else:
        for n in nfts:
            emoji = NFT_RARITY_EMOJI.get(n[4], "🟢")
            text += f"\n{emoji} <b>{n[1]}</b> — {fnum(n[2])}/ч"
    text += "\n\n━━━━━━━━━━━━━━━━━━━"
    await call.message.edit_text(text, reply_markup=user_nfts_view_kb(nfts, uid, "adm"))
    await call.answer()


# ── Сменить ник (обновить из Telegram) ──
@router.callback_query(F.data.startswith("adm_setname_"))
async def adm_set_name(call: CallbackQuery):
    if not await is_admin(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    uid = int(call.data.replace("adm_setname_", ""))
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
        text = await _adm_profile_text(user)
        await call.message.edit_text(text, reply_markup=await _user_profile_kb(uid, "adm", 1))


# ══════════════════════════════════════════
#  УЧАСТНК
# ══════════════════════════════════════════
@router.callback_query(F.data == "adm_users")
async def adm_users(call: CallbackQuery):
    uid = call.from_user.id
    if not await is_admin(uid) and uid != OWNER_ID:
        return await call.answer("❌", show_alert=True)
    perms = await get_admin_permissions(uid)
    if uid != OWNER_ID and not _has_perm(perms, "users"):
        return await call.answer("❌ Нет прав", show_alert=True)
    await _adm_show_users(call, 0)


@router.callback_query(F.data.startswith("adm_users_pg:"))
async def adm_users_pg(call: CallbackQuery):
    uid = call.from_user.id
    if not await is_admin(uid) and uid != OWNER_ID:
        return await call.answer("❌", show_alert=True)
    page = int(call.data.split(":")[1])
    await _adm_show_users(call, page)


async def _adm_show_users(call, page):
    per_page = 10
    total = await count_users_all()
    total_pages = max(1, math.ceil(total / per_page))
    users = await get_users_page(page, per_page)
    text = f"👥 УЧАСТНК ({total})\n══════════════════════\n"
    kb = users_list_kb(users, page, total_pages, "adm")
    try:
        await call.message.edit_text(text, reply_markup=kb)
    except Exception:
        try:
            await call.message.delete()
        except Exception:
            pass
        await call.bot.send_message(call.message.chat.id, text, reply_markup=kb)
    await call.answer()


@router.callback_query(F.data == "adm_user_search")
async def adm_user_search(call: CallbackQuery, state: FSMContext):
    uid = call.from_user.id
    if not await is_admin(uid):
        return await call.answer("❌", show_alert=True)
    await state.set_state(AdminStates.waiting_user_search_id)
    await call.message.edit_text("🔍 ID участника:", reply_markup=admin_back_kb())
    await call.answer()


@router.message(AdminStates.waiting_user_search_id)
async def adm_user_search_id(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    await state.clear()
    try:
        uid = int(message.text.strip())
    except (ValueError, TypeError):
        return await message.answer("❌ Число", reply_markup=admin_back_kb())
    user = await get_user(uid)
    if not user:
        return await message.answer("❌ Не найден", reply_markup=admin_back_kb())
    text = await _adm_profile_text(user)
    await message.answer(text, reply_markup=await _user_profile_kb(uid, "adm"))


async def _adm_profile_text(user) -> str:
    uid = user["user_id"]
    from config import RANKS_LIST, NFT_RARITY_EMOJI
    rank_name = RANKS_LIST.get(user["rank"] or 1, "🍼")
    nft_count = await count_user_nfts(uid)
    max_slots = await get_user_nft_slots(uid)
    vip = user["vip_type"]
    if vip:
        exp = user["vip_expires"]
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
    else:
        vip_line = "🔹 Статус: Обычный\n"
    # Pinned NFT
    from database import get_user_pinned_nft
    pinned = await get_user_pinned_nft(uid)
    pin_line = ""
    if pinned:
        p_emoji = NFT_RARITY_EMOJI.get(pinned[8], "🟢")
        pin_line = f"📌 Закреп: {p_emoji} {pinned[5]} ({fnum(pinned[6])}/ч)\n"
    pay_banned = await is_payment_banned(uid)
    return (
        f"👤 ПРОФИЛЬ\n══════════════════════\n\n"
        f"🆔 {uid} │ @{user['username']}\n"
        f"🪪 {rank_name}\n"
        f"{vip_line}"
        f"💢 {fnum(user['clicks'])} Тохн\n"
        f"⚡ +{fnum(user['bonus_click'])} клик\n"
        f"📈 {fnum(user['passive_income'])} Тохн/ч\n"
        f"🎨 НФТ: {nft_count}/{max_slots}\n"
        f"{pin_line}"
        f"🚫 Бан: {'Да' if user['is_banned'] else 'Нет'}\n"
        f"💳 Оплата: {'🚫 Заблок.' if pay_banned else '✅'}\n"
        f"══════════════════════"
    )

_adm_user_profile_text = _adm_profile_text


@router.callback_query(F.data.startswith("adm_user_view_"))
async def adm_user_view(call: CallbackQuery):
    uid = call.from_user.id
    if not await is_admin(uid) and uid != OWNER_ID:
        return await call.answer("❌", show_alert=True)
    target = int(call.data.replace("adm_user_view_", ""))
    user = await get_user(target)
    if not user:
        return await call.answer("❌", show_alert=True)
    text = await _adm_profile_text(user)
    kb = await _user_profile_kb(target, "adm")
    try:
        await call.message.edit_text(text, reply_markup=kb)
    except Exception:
        try:
            await call.message.delete()
        except Exception:
            pass
        await call.bot.send_message(call.message.chat.id, text, reply_markup=kb)
    await call.answer()


# ── Клики ──
@router.callback_query(F.data == "adm_give")
async def adm_give(call: CallbackQuery, state: FSMContext):
    uid = call.from_user.id
    if not await is_admin(uid):
        return await call.answer("❌", show_alert=True)
    perms = await get_admin_permissions(uid)
    if not _has_perm(perms, "give_clicks"):
        return await call.answer("❌ Нет прав", show_alert=True)
    await state.set_state(AdminStates.waiting_give)
    await call.message.edit_text("💰 ID СУММА:", reply_markup=admin_back_kb())
    await call.answer()


@router.message(AdminStates.waiting_give)
async def adm_give_process(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    await state.clear()
    parts = message.text.strip().split()
    if len(parts) < 2:
        return await message.answer("❌ ID СУММА", reply_markup=admin_back_kb())
    try:
        uid = int(parts[0])
        amount = float(parts[1])
    except (ValueError, TypeError):
        return await message.answer("❌ Формат", reply_markup=admin_back_kb())
    user = await get_user(uid)
    if not user:
        return await message.answer("❌ Не найден", reply_markup=admin_back_kb())
    await update_clicks(uid, amount)
    await log_admin_action(message.from_user.id, "give_clicks", uid, str(amount))
    await message.answer(f"✅ {fnum(amount)} → {uid}", reply_markup=admin_back_kb())


@router.callback_query(F.data.startswith("adm_give_user_"))
async def adm_give_user_cb(call: CallbackQuery, state: FSMContext):
    uid = call.from_user.id
    if not await is_admin(uid):
        return await call.answer("❌", show_alert=True)
    target = int(call.data.replace("adm_give_user_", ""))
    await state.set_state(AdminStates.waiting_give)
    await state.set_data({"target_uid": target})
    await call.message.edit_text(f"💰 Сумма для {target}:", reply_markup=admin_back_kb())
    await call.answer()


@router.callback_query(F.data.startswith("adm_take_user_"))
async def adm_take_user_cb(call: CallbackQuery, state: FSMContext):
    uid = call.from_user.id
    if not await is_admin(uid):
        return await call.answer("❌", show_alert=True)
    target = int(call.data.replace("adm_take_user_", ""))
    await state.set_state(AdminStates.waiting_take)
    await state.set_data({"target_uid": target})
    await call.message.edit_text(f"💸 Снять у {target}:", reply_markup=admin_back_kb())
    await call.answer()


@router.message(AdminStates.waiting_take)
async def adm_take_process(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    data = await state.get_data()
    target = data.get("target_uid")
    await state.clear()
    try:
        amount = float(message.text.strip())
    except (ValueError, TypeError):
        return await message.answer("❌ Число", reply_markup=admin_back_kb())
    await update_clicks(target, -abs(amount))
    await log_admin_action(message.from_user.id, "take_clicks", target, str(-abs(amount)))
    await message.answer(f"✅ -{fnum(abs(amount))} у {target}", reply_markup=admin_back_kb())


# ── Сброс ──
@router.callback_query(F.data.regexp(r"^adm_reset_\d+$"))
async def adm_reset(call: CallbackQuery):
    uid = call.from_user.id
    if not await is_admin(uid):
        return await call.answer("❌", show_alert=True)
    target = int(call.data.replace("adm_reset_", ""))
    await reset_user_progress(target)
    await log_admin_action(uid, "reset", target)
    await call.answer(f"✅ {target} сброшен", show_alert=True)
    user = await get_user(target)
    if user:
        text = await _adm_profile_text(user)
        await call.message.edit_text(text, reply_markup=await _user_profile_kb(target, "adm", 0))


# ══════════════════════════════════════════
#  ТИКЕТЫ (админ)
# ══════════════════════════════════════════
@router.callback_query(F.data.startswith("adm_tickets:"))
async def adm_tickets(call: CallbackQuery):
    uid = call.from_user.id
    if not await is_admin(uid) and uid != OWNER_ID:
        return await call.answer("❌", show_alert=True)
    perms = await get_admin_permissions(uid)
    if uid != OWNER_ID and not _has_perm(perms, "tickets"):
        return await call.answer("❌ Нет прав", show_alert=True)
    page = int(call.data.split(":")[1])
    total = await count_open_tickets()
    per_page = 5
    total_pages = max(1, math.ceil(total / per_page))
    tickets = await get_open_tickets(page, per_page)
    from keyboards import owner_tickets_kb
    text = f"📋 ТИКЕТЫ ({total})\n══════════════════════\n"
    # Reuse owner kb but adjust back
    kb_data = []
    for t in tickets:
        tid, tuid, ttype, msg, dt = t
        short = msg[:30] + "..." if len(msg) > 30 else msg
        kb_data.append([InlineKeyboardButton(text=f"#{tid} {ttype}: {short}", callback_data=f"ticket_view_{tid}")])
    nav = []
    if total_pages > 1:
        if page > 0:
            nav.append(InlineKeyboardButton(text="◀️", callback_data=f"adm_tickets:{page - 1}"))
        nav.append(InlineKeyboardButton(text=f"📂{page + 1}/{total_pages}", callback_data="noop"))
        if page < total_pages - 1:
            nav.append(InlineKeyboardButton(text="▶️", callback_data=f"adm_tickets:{page + 1}"))
        kb_data.append(nav)
    kb_data.append([InlineKeyboardButton(text="⬅️ Панель", callback_data="admin_panel")])
    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_data))
    await call.answer()


# ── НФТ создание (админ) ──
@router.callback_query(F.data == "adm_nft_create")
async def adm_nft_create(call: CallbackQuery, state: FSMContext):
    uid = call.from_user.id
    if not await is_admin(uid):
        return await call.answer("❌", show_alert=True)
    perms = await get_admin_permissions(uid)
    if not _has_perm(perms, "nft"):
        return await call.answer("❌ Нет прав", show_alert=True)
    await state.set_state(AdminStates.nft_name)
    await call.message.edit_text("🎨 Название НФТ:", reply_markup=admin_back_kb())
    await call.answer()


@router.message(AdminStates.nft_name)
async def adm_nft_name(message: Message, state: FSMContext):
    await state.update_data(nft_name=message.text.strip())
    kb = []
    for rn, pct in NFT_RARITIES.items():
        emoji = NFT_RARITY_EMOJI.get(rn, "🟢")
        kb.append([InlineKeyboardButton(text=f"{emoji} {rn} ({pct}%)", callback_data=f"adm_rarity_{rn}")])
    await state.set_state(AdminStates.nft_rarity)
    await message.answer("Редкость:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))


@router.callback_query(F.data.startswith("adm_rarity_"), AdminStates.nft_rarity)
async def adm_nft_rarity_cb(call: CallbackQuery, state: FSMContext):
    rn = call.data.replace("adm_rarity_", "")
    pct = NFT_RARITIES.get(rn, 10.0)
    await state.update_data(rarity_name=rn, rarity_pct=pct)
    await state.set_state(AdminStates.nft_income)
    await call.message.edit_text("💰 Доход/час:")
    await call.answer()


@router.message(AdminStates.nft_income)
async def adm_nft_income(message: Message, state: FSMContext):
    try:
        income = float(message.text.strip())
    except (ValueError, TypeError):
        return await message.answer("❌ Число")
    await state.update_data(nft_income=income)
    await state.set_state(AdminStates.nft_price)
    await message.answer("🏷 Цена:")


@router.message(AdminStates.nft_price)
async def adm_nft_price(message: Message, state: FSMContext):
    try:
        price = float(message.text.strip())
    except (ValueError, TypeError):
        return await message.answer("❌ Число")
    await state.update_data(nft_price=price)
    await state.set_state(AdminStates.nft_collection)
    await message.answer("📂 Номер коллекции (число):")


@router.message(AdminStates.nft_collection)
async def adm_nft_collection(message: Message, state: FSMContext):
    try:
        col = int(message.text.strip())
    except (ValueError, TypeError):
        return await message.answer("❌ Введите число")
    await state.update_data(nft_collection=col)
    data = await state.get_data()
    rn = data.get("rarity_name", "Обычный")
    emoji = NFT_RARITY_EMOJI.get(rn, "🟢")
    text = (
        f"📋 НФТ:\n{data['nft_name']}\n"
        f"📂 Коллекция: #{col}\n"
        f"{emoji} {rn} ({data.get('rarity_pct', 10)}%)\n"
        f"💰 {fnum(data['nft_income'])} Тохн/ч\n"
        f"🏷 {fnum(data['nft_price'])} 💢"
    )
    await state.set_state(AdminStates.nft_confirm)
    await message.answer(text, reply_markup=owner_nft_publish_kb())


@router.callback_query(F.data == "owner_nft_publish", AdminStates.nft_confirm)
async def adm_nft_publish(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    tid = await create_nft_template(
        data["nft_name"], data["rarity_name"], data["rarity_pct"],
        data["nft_income"], data["nft_price"], call.from_user.id,
        collection_num=data.get("nft_collection", 0),
    )
    await log_admin_action(call.from_user.id, "create_nft", details=f"#{tid}")
    await call.answer("✅ НФТ создан!", show_alert=True)
    await admin_panel(call, state)


# ── Рассылка ──
@router.callback_query(F.data == "adm_broadcast")
async def adm_broadcast(call: CallbackQuery, state: FSMContext):
    uid = call.from_user.id
    if not await is_admin(uid):
        return await call.answer("❌", show_alert=True)
    perms = await get_admin_permissions(uid)
    if not _has_perm(perms, "broadcast"):
        return await call.answer("❌ Нет прав", show_alert=True)
    await state.set_state(AdminStates.waiting_broadcast)
    await call.message.edit_text("📢 Текст рассылки:", reply_markup=admin_back_kb())
    await call.answer()


@router.message(AdminStates.waiting_broadcast)
async def adm_broadcast_send(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
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
    await message.answer(f"✅ Отправлено {sent}/{len(rows)}", reply_markup=admin_back_kb())


# ── Мои действия ──
@router.callback_query(F.data == "adm_my_log")
async def adm_my_log(call: CallbackQuery):
    uid = call.from_user.id
    if not await is_admin(uid):
        return await call.answer("❌", show_alert=True)
    actions = await get_admin_actions(admin_id=uid, limit=15)
    if not actions:
        text = "Нет записей."
    else:
        lines = ["📊 МОИ ДЕЙСТВИЯ\n══════════════════════\n"]
        for a in actions:
            act = a[2]
            target = a[3]
            det = a[4] or ""
            lines.append(f"• {act} → {target or '—'} {det[:30]}")
        text = "\n".join(lines)
    await call.message.edit_text(text, reply_markup=admin_back_kb())
    await call.answer()


# ── Разжаловаться (самоудаление из админов) ──
@router.callback_query(F.data == "adm_demote_self")
async def adm_demote_self(call: CallbackQuery):
    uid = call.from_user.id
    if not await is_admin(uid):
        return await call.answer("❌", show_alert=True)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, разжаловаться", callback_data="adm_demote_confirm")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_panel")],
    ])
    await call.message.edit_text(
        "⚠️ <b>Разжаловаться?</b>\n━━━━━━━━━━━━━━━━━━━\n\n"
        "Вы потеряете все права администратора.\n"
        "Для восстановления понадобится новый ключ.",
        reply_markup=kb,
    )
    await call.answer()


@router.callback_query(F.data == "adm_demote_confirm")
async def adm_demote_confirm(call: CallbackQuery, state: FSMContext):
    uid = call.from_user.id
    if not await is_admin(uid):
        return await call.answer("❌", show_alert=True)
    from database import remove_admin
    await remove_admin(uid)
    await log_admin_action(uid, "self_demote", uid, "Разжаловался добровольно")
    await state.clear()
    await call.message.edit_text(
        "✅ Вы разжалованы из администраторов.\n\n"
        "Для восстановления обратитесь к владельцу.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ В меню", callback_data="menu")],
        ]),
    )
    await call.answer()


# ── Выдать НФТ из профиля (админ) ──
@router.callback_query(F.data.startswith("adm_give_nft_"))
async def adm_give_nft(call: CallbackQuery):
    uid = call.from_user.id
    if not await is_admin(uid):
        return await call.answer("❌", show_alert=True)
    await call.answer("ℹ️ Используйте создание НФТ и выдайте вручную", show_alert=True)


# History from profile
@router.callback_query(F.data.startswith("adm_user_hist_"))
async def adm_user_hist(call: CallbackQuery):
    uid = call.from_user.id
    if not await is_admin(uid) and uid != OWNER_ID:
        return await call.answer("❌", show_alert=True)
    target = int(call.data.replace("adm_user_hist_", ""))
    from database import get_activity_logs
    logs = await get_activity_logs(user_id=target, page=0, per_page=15)
    lines = [f"📝 ИСТОРИЯ {target}\n══════════════════════\n"]
    for log in logs:
        act = log[2]
        det = log[3] or ""
        dt = log[4][:16] if log[4] else ""
        lines.append(f"• {act}: {det[:40]} ({dt})")
    if not logs:
        lines.append("Нет записей.")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️", callback_data=f"adm_user_view_{target}")]
    ])
    await call.message.edit_text("\n".join(lines), reply_markup=kb)
    await call.answer()


# ══════════════════════════════════════════════════════
# СТАТИСТИКА
# ══════════════════════════════════════════════════════

@router.callback_query(F.data == "adm_stats")
async def adm_stats(call: CallbackQuery):
    if not await is_admin(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    perms = await get_admin_permissions(call.from_user.id)
    if not _has_perm(perms, "stats"):
        return await call.answer("❌ Нет прав", show_alert=True)
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
    await call.message.edit_text(text, reply_markup=admin_back_kb())
    await call.answer()


# ══════════════════════════════════════════════════════
# ПЕРЕПИСКИ / ЧАТ-ЛОГИ
# ══════════════════════════════════════════════════════

@router.callback_query(F.data == "adm_chat_logs")
async def adm_chat_logs(call: CallbackQuery):
    if not await is_admin(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    perms = await get_admin_permissions(call.from_user.id)
    if not _has_perm(perms, "chat_logs"):
        return await call.answer("❌ Нет прав", show_alert=True)
    active = await get_all_active_chats()
    kb = []
    if active:
        kb.append([InlineKeyboardButton(text="🟢 АКТИВНЫЕ ЧАТЫ", callback_data="noop")])
        for a in active[:15]:
            cid, u1, u2, dt = a[0], a[1], a[2], a[3]
            dt_short = dt[11:16] if dt else ""
            kb.append([InlineKeyboardButton(
                text=f"🟢 #{cid} — {u1} ↔ {u2} ({dt_short})",
                callback_data=f"adm_chat_active_{cid}",
            )])
    logs = await get_chat_logs_list(0, 15)
    if logs:
        kb.append([InlineKeyboardButton(text="📋 ИСТОРИЯ ЧАТОВ", callback_data="noop")])
        for log in logs:
            chat_id, started = log
            kb.append([InlineKeyboardButton(
                text=f"💬 #{chat_id} — {started[:16]}",
                callback_data=f"adm_chat_view_{chat_id}",
            )])
    if not kb:
        await call.message.edit_text("👀 Нет переписок.", reply_markup=admin_back_kb())
        return await call.answer()
    kb.append([InlineKeyboardButton(text="⬅️ Панель", callback_data="admin_panel")])
    a_count = len(active) if active else 0
    await call.message.edit_text(
        f"<b>👀 Переписки</b>\n━━━━━━━━━━━━━━━━━━━\n\n"
        f"🟢 Активных: <b>{a_count}</b>\n",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
    )
    await call.answer()


@router.callback_query(F.data.startswith("adm_chat_active_"))
async def adm_chat_active_view(call: CallbackQuery):
    if not await is_admin(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    chat_id = int(call.data.replace("adm_chat_active_", ""))
    chat = await get_active_chat_by_id(chat_id)
    if not chat:
        return await call.answer("ℹ️ Чат уже завершён", show_alert=True)
    cid, u1, u2, dt = chat[0], chat[1], chat[2], chat[3]
    msg_count = await count_chat_messages(cid)
    messages = await get_chat_messages(cid, 0, 20)
    lines = [
        f"<b>🟢 Активный чат #{cid}</b>\n━━━━━━━━━━━━━━━━━━━\n",
        f"👤 Участник 1: {u1}", f"👤 Участник 2: {u2}",
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
        [InlineKeyboardButton(text="🔄 Обновить", callback_data=f"adm_chat_active_{cid}")],
        [InlineKeyboardButton(text="🛑 Завершить чат", callback_data=f"adm_chat_end_{cid}")],
        [
            InlineKeyboardButton(text=f"⚠️ Жалоба на {u1}", callback_data=f"adm_chat_warn_{cid}_{u1}"),
            InlineKeyboardButton(text=f"⚠️ Жалоба на {u2}", callback_data=f"adm_chat_warn_{cid}_{u2}"),
        ],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="adm_chat_logs")],
    ])
    text = "\n".join(lines)
    if len(text) > 4000:
        text = text[:4000] + "\n...(обрезано)"
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


@router.callback_query(F.data.startswith("adm_chat_view_"))
async def adm_chat_view(call: CallbackQuery):
    if not await is_admin(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    chat_id = int(call.data.replace("adm_chat_view_", ""))
    messages = await get_chat_messages(chat_id, 0, 30)
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
    kb_rows = []
    if len(p_list) >= 2:
        kb_rows.append([
            InlineKeyboardButton(text=f"⚠️ Жалоба на {p_list[0]}", callback_data=f"adm_chat_warn_{chat_id}_{p_list[0]}"),
            InlineKeyboardButton(text=f"⚠️ Жалоба на {p_list[1]}", callback_data=f"adm_chat_warn_{chat_id}_{p_list[1]}"),
        ])
    elif len(p_list) == 1:
        kb_rows.append([InlineKeyboardButton(text=f"⚠️ Жалоба на {p_list[0]}", callback_data=f"adm_chat_warn_{chat_id}_{p_list[0]}")])
    kb_rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="adm_chat_logs")])
    text = "\n".join(lines)
    if len(text) > 4000:
        text = text[:4000] + "\n...(обрезано)"
    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))
    await call.answer()


@router.callback_query(F.data.startswith("adm_chat_end_"))
async def adm_chat_end(call: CallbackQuery):
    if not await is_admin(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    chat_id = int(call.data.replace("adm_chat_end_", ""))
    chat = await get_active_chat_by_id(chat_id)
    if not chat:
        return await call.answer("ℹ️ Чат уже завершён", show_alert=True)
    u1, u2 = chat[1], chat[2]
    await end_active_chat(chat_id)
    for uid in (u1, u2):
        try:
            await call.bot.send_message(
                uid, "🛑 Чат завершён администрацией.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="💬 К чату", callback_data="chat_menu")],
                    [InlineKeyboardButton(text="⬅️ В меню", callback_data="menu")],
                ]),
            )
        except Exception:
            pass
    await log_admin_action(call.from_user.id, "chat_terminate", 0, f"chat #{chat_id} ({u1} <> {u2})")
    await call.answer(f"🛑 Чат #{chat_id} завершён!", show_alert=True)
    await adm_chat_logs(call)


@router.callback_query(F.data.startswith("adm_chat_warn_"))
async def adm_chat_warn(call: CallbackQuery):
    if not await is_admin(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    parts = call.data.replace("adm_chat_warn_", "").split("_")
    if len(parts) < 2:
        return await call.answer("❌", show_alert=True)
    chat_id = int(parts[0])
    target_uid = int(parts[1])
    user = await get_user(target_uid)
    uname = f"@{user['username']}" if user else str(target_uid)
    text = (
        f"<b>⚠️ Жалоба на участника</b>\n━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 {target_uid} ({uname})\n💬 Чат: #{chat_id}\n\nВыберите действие:"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚠️ Предупредить", callback_data=f"adm_chat_act_warn_{chat_id}_{target_uid}")],
        [InlineKeyboardButton(text="🔨 Забанить", callback_data=f"adm_chat_act_ban_{chat_id}_{target_uid}")],
        [InlineKeyboardButton(text="🛑 Завершить + Предупредить", callback_data=f"adm_chat_act_endwarn_{chat_id}_{target_uid}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"adm_chat_active_{chat_id}")],
    ])
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


@router.callback_query(F.data.startswith("adm_chat_act_"))
async def adm_chat_action(call: CallbackQuery):
    if not await is_admin(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    raw = call.data.replace("adm_chat_act_", "")
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
                "<b>⚠️ Предупреждение</b>\n━━━━━━━━━━━━━━━━━━━\n\n"
                "Вы получили предупреждение от администрации\n"
                "за нарушение правил чата.\n\nПовторное нарушение приведёт к бану!",
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
        chat = await get_active_chat_by_id(chat_id)
        if chat:
            u1, u2 = chat[1], chat[2]
            await end_active_chat(chat_id)
            for uid in (u1, u2):
                try:
                    await call.bot.send_message(
                        uid, "🛑 Чат завершён администрацией.",
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="⬅️ В меню", callback_data="menu")],
                        ]),
                    )
                except Exception:
                    pass
            result_lines.append(f"🛑 Чат #{chat_id} завершён")
    await log_admin_action(call.from_user.id, f"chat_{action}", target_uid, f"chat #{chat_id}")
    await call.answer("\n".join(result_lines) or "✅", show_alert=True)
    await adm_chat_logs(call)


# ══════════════════════════════════════════════════════
# ЗАКАЗЫ ОПЛАТЫ
# ══════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("adm_orders:"))
async def adm_orders_list(call: CallbackQuery):
    if not await is_admin(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    page = int(call.data.split(":")[1])
    total = await count_pending_orders()
    per_page = 10
    total_pages = max(1, math.ceil(total / per_page))
    orders = await get_pending_orders(page, per_page)
    text = f"💳 ЗАКАЗЫ НА ОПЛАТУ ({total})\n══════════════════════\n"
    await call.message.edit_text(text, reply_markup=owner_orders_kb(orders, page, total_pages, prefix="adm"))
    await call.answer()


@router.callback_query(F.data.startswith("adm_order_view:"))
async def adm_order_view(call: CallbackQuery):
    if not await is_admin(call.from_user.id):
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
        f"📋 ЗАКАЗ #{order_id}\n══════════════════════\n\n"
        f"👤 Пользователь: {order['user_id']}\n"
        f"📦 Пакет: {pkg_label}\n📝 Что получит: {desc}\n"
        f"💳 Способ: {method_label}\n💰 Сумма: {order['amount_rub']}₽\n"
        f"Статус: {order['status']}\n"
        f"Дата: {order['created_at'][:16] if order['created_at'] else '—'}\n"
        "══════════════════════"
    )
    kb = order_action_kb(order_id, prefix="adm")
    screenshot = order["screenshot_file_id"] if "screenshot_file_id" in order.keys() else None
    if screenshot:
        try:
            await call.message.delete()
        except Exception:
            pass
        try:
            await call.bot.send_photo(call.message.chat.id, screenshot, caption=text, reply_markup=kb)
        except Exception:
            await call.bot.send_message(call.message.chat.id, text, reply_markup=kb)
    else:
        await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


@router.callback_query(F.data.startswith("adm_order_approve:"))
async def adm_order_approve(call: CallbackQuery):
    if not await is_admin(call.from_user.id):
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
    if pkg_type == "clicks" and pkg_id in CLICK_PACKAGES:
        clicks, _, _ = CLICK_PACKAGES[pkg_id]
        await update_clicks(uid, clicks)
        reward_text = f"💢 +{fnum(clicks)} Тохн выдано!"
    elif pkg_type == "vip" and pkg_id in VIP_PACKAGES:
        mc, mi, dur, _, label = VIP_PACKAGES[pkg_id]
        vip_name = "VIP" if mc == 2 else "Premium"  # VIP: 2,0.5 | Premium: 3,2
        await set_user_vip(uid, vip_name, mc, mi, dur)
        dur_text = f"{dur} дней" if dur > 0 else "навсегда"
        reward_text = f"⭐ {vip_name} выдан ({dur_text})"
    else:
        reward_text = "❓ Неизвестный пакет"
    await resolve_payment_order(order_id, call.from_user.id, "approved")
    await unban_payment(uid)
    await log_admin_action(call.from_user.id, "approve_payment", uid, f"order #{order_id}")
    try:
        await call.bot.send_message(
            uid,
            f"✅ ПОКУПКА ВЫДАНА!\n══════════════════════\n\n"
            f"Заказ #{order_id} одобрен!\n{reward_text}\n\nСпасибо за покупку! 🎉",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ В меню", callback_data="menu")],
            ]),
        )
    except Exception:
        pass
    await call.answer(f"✅ {reward_text}", show_alert=True)
    total = await count_pending_orders()
    per_page = 10
    total_pages = max(1, math.ceil(total / per_page))
    orders = await get_pending_orders(0, per_page)
    text = f"💳 ЗАКАЗЫ НА ОПЛАТУ ({total})\n══════════════════════\n"
    await call.message.edit_text(text, reply_markup=owner_orders_kb(orders, 0, total_pages, prefix="adm"))


@router.callback_query(F.data.startswith("adm_order_reject:"))
async def adm_order_reject(call: CallbackQuery):
    if not await is_admin(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    order_id = int(call.data.split(":")[1])
    order = await get_payment_order(order_id)
    if not order:
        return await call.answer("❌ Не найден", show_alert=True)
    if order["status"] != "pending":
        return await call.answer(f"ℹ️ Статус: {order['status']}", show_alert=True)
    await resolve_payment_order(order_id, call.from_user.id, "rejected")
    await log_admin_action(call.from_user.id, "reject_payment", order["user_id"], f"order #{order_id}")
    try:
        await call.bot.send_message(
            order["user_id"],
            f"❌ Платёж отклонён\n══════════════════════\n\n"
            f"Заказ #{order_id} не подтверждён.\nЕсли вы оплатили — нажмите кнопку ниже.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💬 Написать администрации", callback_data=f"order_reply:{order_id}")],
                [InlineKeyboardButton(text="⬅️ В меню", callback_data="menu")],
            ]),
        )
    except Exception:
        pass
    await call.answer(f"❌ Заказ #{order_id} отклонён", show_alert=True)
    total = await count_pending_orders()
    per_page = 10
    total_pages = max(1, math.ceil(total / per_page))
    orders_list = await get_pending_orders(0, per_page)
    text = f"💳 ЗАКАЗЫ НА ОПЛАТУ ({total})\n══════════════════════\n"
    await call.message.edit_text(text, reply_markup=owner_orders_kb(orders_list, 0, total_pages, prefix="adm"))


@router.callback_query(F.data.startswith("adm_order_msg:"))
async def adm_order_msg_start(call: CallbackQuery, state: FSMContext):
    if not await is_admin(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    order_id = int(call.data.split(":")[1])
    order = await get_payment_order(order_id)
    if not order:
        return await call.answer("❌ Заказ не найден", show_alert=True)
    await state.set_state(AdminStates.payment_msg_to_user)
    await state.update_data(order_id=order_id, order_user_id=order["user_id"])
    await call.message.answer(
        f"💬 Введите сообщение для пользователя\n"
        f"(заказ #{order_id}, uid {order['user_id']}):\n\n"
        f"Отправьте текст или /cancel для отмены.",
    )
    await call.answer()


@router.message(AdminStates.payment_msg_to_user)
async def adm_order_msg_send(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
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
        f"📩 <b>Сообщение от администрации</b>\n━━━━━━━━━━━━━━━━━━━\n"
        f"📋 Заказ: #{order_id}\n\n{message.text or '(фото/файл)'}\n\n━━━━━━━━━━━━━━━━━━━"
    )
    reply_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Ответить", callback_data=f"order_reply:{order_id}")],
    ])
    try:
        await message.bot.send_message(uid, text_to_send, parse_mode="HTML", reply_markup=reply_kb)
        await message.answer(f"✅ Сообщение отправлено пользователю {uid}.")
    except Exception as e:
        await message.answer(f"❌ Не удалось отправить: {e}")
    await state.clear()


@router.callback_query(F.data.startswith("adm_order_fake:"))
async def adm_order_fake_ban(call: CallbackQuery):
    if not await is_admin(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    order_id = int(call.data.split(":")[1])
    order = await get_payment_order(order_id)
    if not order:
        return await call.answer("❌ Не найден", show_alert=True)
    uid = order["user_id"]
    if order["status"] == "pending":
        await resolve_payment_order(order_id, call.from_user.id, "rejected")
    await ban_payment(uid)
    await log_admin_action(call.from_user.id, "payment_ban", uid, f"Fake receipt, order #{order_id}")
    try:
        await call.bot.send_message(
            uid,
            "🚫 <b>Доступ к оплате заблокирован</b>\n\n"
            f"Заказ #{order_id} отклонён.\nПричина: подозрение на поддельный чек.\n\n"
            "Раздел оплаты заблокирован навсегда.", parse_mode="HTML",
        )
    except Exception:
        pass
    await call.answer(f"🚫 Заказ #{order_id} отклонён, пользователь забанен в оплате.", show_alert=True)
    total = await count_pending_orders()
    per_page = 10
    total_pages = max(1, math.ceil(total / per_page))
    orders_list = await get_pending_orders(0, per_page)
    text = f"💳 ЗАКАЗЫ НА ОПЛАТУ ({total})\n══════════════════════\n"
    try:
        await call.message.edit_text(text, reply_markup=owner_orders_kb(orders_list, 0, total_pages, prefix="adm"))
    except Exception:
        pass


# ══════════════════════════════════════════════════════
# НАСТРОЙКИ БОТА
# ══════════════════════════════════════════════════════

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


async def _adm_render_settings_page(call: CallbackQuery, page: int = 0):
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
                text=f"{icon} {label}", callback_data=f"astg_toggle:{key}:{page}",
            )])
        else:
            short_val = (val[:25] + "…") if len(val) > 25 else (val or "—")
            lines.append(f"  {label}: {short_val}")
            kb_rows.append([InlineKeyboardButton(
                text=f"✏️ {label}", callback_data=f"astg_edit:{key}",
            )])
    lines.append("\n━━━━━━━━━━━━━━━━━━━")
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⏮️", callback_data="astg_pg:0"))
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"astg_pg:{page-1}"))
    nav.append(InlineKeyboardButton(text=f"📂 {page+1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"astg_pg:{page+1}"))
        nav.append(InlineKeyboardButton(text="⏭️", callback_data=f"astg_pg:{total_pages-1}"))
    kb_rows.append(nav)
    kb_rows.append([InlineKeyboardButton(text="🔄 Сбросить все", callback_data="astg_reset_all")])
    kb_rows.append([InlineKeyboardButton(text="⬅️ Панель", callback_data="admin_panel")])
    await call.message.edit_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))
    await call.answer()


@router.callback_query(F.data == "adm_settings")
async def adm_settings(call: CallbackQuery):
    if not await is_admin(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    perms = await get_admin_permissions(call.from_user.id)
    if not _has_perm(perms, "settings"):
        return await call.answer("❌ Нет прав", show_alert=True)
    await _adm_render_settings_page(call, 0)


@router.callback_query(F.data.startswith("astg_pg:"))
async def astg_page(call: CallbackQuery):
    if not await is_admin(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    page = int(call.data.split(":")[1])
    await _adm_render_settings_page(call, page)


@router.callback_query(F.data.startswith("astg_toggle:"))
async def astg_toggle(call: CallbackQuery):
    if not await is_admin(call.from_user.id):
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
    await _adm_render_settings_page(call, page)


@router.callback_query(F.data.startswith("astg_edit:"))
async def astg_edit(call: CallbackQuery, state: FSMContext):
    if not await is_admin(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    key = call.data.split(":")[1]
    if key not in _SETTINGS_SCHEMA:
        return await call.answer("❌", show_alert=True)
    label, stype, default, desc = _SETTINGS_SCHEMA[key]
    current = await get_setting(key, default)
    await state.set_state(AdminStates.waiting_setting_value)
    await state.update_data(stg_key=key)
    hint = "число" if stype == "int" else "текст"
    await call.message.edit_text(
        f"✏️ {label}\n━━━━━━━━━━━━━━━━━━━\n\n"
        f"📝 {desc}\nТекущее: <b>{current or '—'}</b>\nТип: {hint}\n\n"
        f"Введите новое значение:",
        reply_markup=admin_back_kb(), parse_mode="HTML",
    )
    await call.answer()


@router.message(AdminStates.waiting_setting_value)
async def adm_setting_value(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    data = await state.get_data()
    key = data.get("stg_key")
    await state.clear()
    if not key or key not in _SETTINGS_SCHEMA:
        return await message.answer("❌ Ошибка", reply_markup=admin_back_kb())
    label, stype, default, desc = _SETTINGS_SCHEMA[key]
    val = message.text.strip()
    if stype == "int":
        try:
            int(val)
        except ValueError:
            return await message.answer("❌ Нужно целое число", reply_markup=admin_back_kb())
    await set_setting(key, val)
    await log_admin_action(message.from_user.id, "setting", details=f"{key} = {val}")
    await message.answer(
        f"✅ {label} = <b>{val}</b>", parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⚙️ К настройкам", callback_data="adm_settings")],
            [InlineKeyboardButton(text="⬅️ Панель", callback_data="admin_panel")],
        ]),
    )


@router.callback_query(F.data == "astg_reset_all")
async def astg_reset_all(call: CallbackQuery):
    if not await is_admin(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    for key, (_, _, default, _) in _SETTINGS_SCHEMA.items():
        await set_setting(key, default)
    await log_admin_action(call.from_user.id, "setting", details="Сброс всех настроек")
    await call.answer("✅ Все настройки сброшены!", show_alert=True)
    await adm_settings(call)


# ══════════════════════════════════════════════════════
# БЫСТРОЕ СОЗДАНИЕ НФТ
# ══════════════════════════════════════════════════════

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


@router.callback_query(F.data == "adm_quick_nft")
async def adm_quick_nft(call: CallbackQuery, state: FSMContext):
    if not await is_admin(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    await state.set_state(AdminStates.quick_nft_name)
    await call.message.edit_text(
        "<b>⚡ Быстрое создание НФТ</b>\n━━━━━━━━━━━━━━━━━━━\n\n"
        "Шаг 1/2 — Введите название (префикс) НФТ:\n\n"
        "💡 Например: Пламя, Клинок, Тень\nК нему добавится случайный суффикс.",
        reply_markup=admin_back_kb(),
    )
    await call.answer()


@router.message(AdminStates.quick_nft_name)
async def adm_quick_nft_name(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    name = (message.text or "").strip()
    if not name or len(name) > 30:
        return await message.answer("❌ Название от 1 до 30 символов")
    await state.update_data(qnft_name=name)
    await state.set_state(AdminStates.quick_nft_count)
    await message.answer(
        "<b>⚡ Быстрое создание НФТ</b>\n━━━━━━━━━━━━━━━━━━━\n\n"
        f"Название: <b>{name}</b> + суффикс\n\nШаг 2/2 — Введите количество (1-50):",
        reply_markup=admin_back_kb(), parse_mode="HTML",
    )


@router.message(AdminStates.quick_nft_count)
async def adm_quick_nft_count(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
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
    admin_id = message.from_user.id
    for _ in range(count):
        rn, pct = random.choice(rarity_list)
        income = round(random.uniform(0.5, 50.0) * (10.0 / max(pct, 0.01)), 2)
        price = round(income * random.uniform(50, 200), 0)
        suffix = random.choice(_NFT_SUFFIXES)
        name = f"{prefix} {suffix}"
        emoji = NFT_RARITY_EMOJI.get(rn, "🎨")
        template_id = await create_nft_template(
            name, rn, pct, income, price, admin_id,
            collection_num=random.randint(1, 999),
        )
        user_nft_id = await grant_nft_to_user(admin_id, template_id, bought_price=0)
        await create_market_listing(admin_id, user_nft_id, template_id, price)
        created += 1
        results.append(f"{emoji} {name} — {rn} | 💰{income}/ч | 🏷{int(price)}")
    await log_admin_action(admin_id, "quick_nft", details=f"Создано {created} НФТ (префикс: {prefix}), выставлены на площадку")
    preview = "\n".join(results[:15])
    if len(results) > 15:
        preview += f"\n... и ещё {len(results) - 15}"
    await message.answer(
        f"✅ Создано {created} НФТ и выставлено на площадку!\n\n{preview}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад в панель", callback_data="admin_panel")],
        ]),
    )


# ══════════════════════════════════════════════════════
# УДАЛЕНИЕ НФТ-ШАБЛОНОВ
# ══════════════════════════════════════════════════════

_NFT_PER_PAGE = 5


async def _adm_show_nft_page(call, page: int):
    total = await count_nft_templates()
    if total == 0:
        await call.message.edit_text("Нет активных НФТ шаблонов.", reply_markup=admin_back_kb())
        return await call.answer()
    total_pages = max(1, math.ceil(total / _NFT_PER_PAGE))
    page = max(0, min(page, total_pages - 1))
    templates = await get_nft_templates_page(page, _NFT_PER_PAGE)
    await call.message.edit_text(
        f"<b>🎨 НФТ шаблоны ({total})</b>\n━━━━━━━━━━━━━━━━━━━\n\n"
        f"Выберите НФТ для просмотра:",
        reply_markup=owner_nft_list_kb(templates, page, total_pages, prefix="adm"),
        parse_mode="HTML",
    )
    await call.answer()


@router.callback_query(F.data == "adm_nft_list")
async def adm_nft_list(call: CallbackQuery):
    if not await is_admin(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    await _adm_show_nft_page(call, 0)


@router.callback_query(F.data.startswith("adm_nft_pg_"))
async def adm_nft_page(call: CallbackQuery):
    if not await is_admin(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    page = int(call.data.replace("adm_nft_pg_", ""))
    await _adm_show_nft_page(call, page)


@router.callback_query(F.data.startswith("adm_nft_view_"))
async def adm_nft_view(call: CallbackQuery):
    if not await is_admin(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    tid = int(call.data.replace("adm_nft_view_", ""))
    t = await get_nft_template(tid)
    if not t:
        return await call.answer("❌ Не найден", show_alert=True)
    emoji = NFT_RARITY_EMOJI.get(t["rarity_name"], "🟢")
    text = (
        f"<b>📋 НФТ #{t['id']}</b>\n━━━━━━━━━━━━━━━━━━━\n\n"
        f"📛 Название: <b>{t['name']}</b>\n"
        f"📂 Коллекция: <b>#{t['collection_num']}</b>\n"
        f"✨ Редкость: {emoji} {t['rarity_name']} ({t['rarity_pct']}%)\n"
        f"💰 Доход: <b>{fnum(t['income_per_hour'])}</b>/ч\n\n\n"
        f"🏷 Цена: {fnum(t['price'])} 💢\n"
        f"👤 Создатель: {t['created_by']}\n\n━━━━━━━━━━━━━━━━━━━"
    )
    await call.message.edit_text(text, reply_markup=owner_nft_detail_kb(tid, 0, prefix="adm"), parse_mode="HTML")
    await call.answer()


@router.callback_query(F.data.startswith("adm_nft_del_yes_"))
async def adm_nft_del_confirm(call: CallbackQuery):
    if not await is_admin(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    tid = int(call.data.replace("adm_nft_del_yes_", ""))
    await delete_nft_template(tid)
    await log_admin_action(call.from_user.id, "delete_nft", details=f"#{tid}")
    await call.answer("✅ НФТ удалён!", show_alert=True)
    await _adm_show_nft_page(call, 0)


@router.callback_query(F.data.startswith("adm_nft_del_"))
async def adm_nft_del(call: CallbackQuery):
    if not await is_admin(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    tid = int(call.data.replace("adm_nft_del_", ""))
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"adm_nft_del_yes_{tid}"),
            InlineKeyboardButton(text="❌ Нет", callback_data=f"adm_nft_view_{tid}"),
        ],
    ])
    await call.message.edit_text(
        f"⚠️ <b>Удалить НФТ #{tid}?</b>\n\nЭто действие необратимо.",
        reply_markup=kb, parse_mode="HTML",
    )
    await call.answer()


# ══════════════════════════════════════════════════════
# ЛОГИ
# ══════════════════════════════════════════════════════

@router.callback_query(F.data == "adm_logs")
async def adm_logs(call: CallbackQuery):
    if not await is_admin(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    perms = await get_admin_permissions(call.from_user.id)
    if not _has_perm(perms, "logs"):
        return await call.answer("❌ Нет прав", show_alert=True)
    await call.message.edit_text(
        "<b>📝 Логи</b>\n━━━━━━━━━━━━━━━━━━━\n\nВыберите тип:",
        reply_markup=admin_logs_kb(),
    )
    await call.answer()


@router.callback_query(F.data.startswith("alog:"))
async def adm_log_type(call: CallbackQuery, state: FSMContext):
    if not await is_admin(call.from_user.id):
        return await call.answer("❌", show_alert=True)
    parts = call.data.split(":")
    action = parts[1]
    if action == "search":
        await state.set_state(AdminStates.waiting_log_user_id)
        await call.message.edit_text("🔍 Введите ID участника:", reply_markup=admin_back_kb())
        return await call.answer()
    page = int(parts[2]) if len(parts) > 2 else 0
    logs = await get_activity_logs(action=action, page=page, per_page=10)
    total = await count_activity_logs(action=action)
    total_pages = max(1, math.ceil(total / 10))
    lines = [f"<b>📝 Логи: {action.upper()} ({total})</b>\n━━━━━━━━━━━━━━━━━━━\n"]
    for log in logs:
        lid, uid_l, act, det, dt = log[0], log[1], log[2], log[3] or "", log[4][:16] if log[4] else ""
        lines.append(f"#{lid} │ {uid_l} │ {det[:40]} │ {dt}")
    nav = []
    if total_pages > 1:
        if page > 0:
            nav.append(InlineKeyboardButton(text="◀️", callback_data=f"alog:{action}:{page-1}"))
        nav.append(InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="noop"))
        if page < total_pages - 1:
            nav.append(InlineKeyboardButton(text="▶️", callback_data=f"alog:{action}:{page+1}"))
    kb = []
    if nav:
        kb.append(nav)
    kb.append([InlineKeyboardButton(text="⬅️ Логи", callback_data="adm_logs")])
    await call.message.edit_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await call.answer()


@router.message(AdminStates.waiting_log_user_id)
async def adm_log_user(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    await state.clear()
    try:
        uid = int(message.text.strip())
    except (ValueError, TypeError):
        return await message.answer("❌ Число", reply_markup=admin_back_kb())
    logs = await get_activity_logs(user_id=uid, page=0, per_page=20)
    if not logs:
        return await message.answer(f"У {uid} нет логов.", reply_markup=admin_back_kb())
    lines = [f"<b>📝 Логи участника {uid}</b>\n━━━━━━━━━━━━━━━━━━━\n"]
    for log in logs:
        act = log[2]
        det = log[3] or ""
        dt = log[4][:16] if log[4] else ""
        lines.append(f"• {act}: {det[:50]} ({dt})")
    await message.answer("\n".join(lines), reply_markup=admin_back_kb())

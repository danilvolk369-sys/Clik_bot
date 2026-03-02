# ======================================================
# COMMON — /start, главное меню, профиль, доход
# ======================================================
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from config import (
    VERSION, RANKS_LIST, RANK_THRESHOLDS, BASE_CLICK_POWER,
    REFERRAL_BOT_USERNAME, PRIZE_CHANNEL_ID, PRIZE_CHANNEL_LINK,
    PRIZE_CHANNEL_NAME, PRIZE_CLICKS, PRIZE_POWER,
)
from database import (
    create_user, get_user, count_users, is_user_banned,
    add_referral, update_rank, claim_passive_income,
    count_user_nfts, get_user_nft_slots,
    get_prize_claim, set_prize_claim, deactivate_prize,
    update_clicks, update_bonus_click, set_user_online, get_online_count,
    add_nft_slot, remove_nft_slot,
    get_vip_multipliers,
    get_active_events, get_event, join_event, update_event_bid,
    get_event_participants, count_event_participants,
    get_user_event_bid, get_highest_bidder,
    create_nft_template, grant_nft_to_user,
    log_activity, get_user_likes_count,
)
from keyboards import start_kb, main_menu_kb, income_kb
from banners_util import send_msg, safe_edit

router = Router()


# ━━━━━━━━━━━━━━━━━━━ Утилиты ━━━━━━━━━━━━━━━━━━━
def fnum(n) -> str:
    if n is None:
        return "0"
    val = float(n)
    if val == 0:
        return "0"
    if abs(val) < 1:
        s = f"{val:.2f}"
        return s.rstrip('0').rstrip('.')
    int_part = int(val)
    frac = val - int_part
    formatted_int = f"{int_part:,}".replace(",", ".")
    if frac > 0:
        frac_str = f"{frac:.2f}"[1:]
        frac_str = frac_str.rstrip('0').rstrip('.')
        if frac_str:
            return formatted_int + frac_str
    return formatted_int


def _progress_bar(current: int, target: int) -> tuple[str, int]:
    if target <= 0:
        return "[██████████] MAX", 100
    pct = min(int(current / target * 100), 100)
    filled = pct // 10
    bar = "█" * filled + "░" * (10 - filled)
    return f"[{bar}] {pct}%", pct


async def _profile_text(user, total_users: int) -> str:
    rank_id = user["rank"] or 1
    rank_name = RANKS_LIST.get(rank_id, "🍼 Новичок")
    click_power = BASE_CLICK_POWER + user["bonus_click"]

    uid = user["user_id"]
    mc, mi = await get_vip_multipliers(uid)
    display_power = click_power * mc

    current_clicks = user["total_clicks"] or 0
    cur_thresh = RANK_THRESHOLDS[min(rank_id - 1, len(RANK_THRESHOLDS) - 1)]
    nxt_thresh = RANK_THRESHOLDS[min(rank_id, len(RANK_THRESHOLDS) - 1)]
    if rank_id >= len(RANK_THRESHOLDS):
        nxt_thresh = cur_thresh

    progress_cur = current_clicks - cur_thresh
    progress_max = nxt_thresh - cur_thresh
    bar, pct = _progress_bar(progress_cur, progress_max)

    uname = user["username"]
    name_line = f"@{uname}" if uname else "Аноним"

    nft_count = await count_user_nfts(uid)
    max_slots = await get_user_nft_slots(uid)
    likes = await get_user_likes_count(uid)

    # Доход
    total_income = float(user["passive_income"] or 0)
    try:
        capacity = float(user["income_capacity"]) if user["income_capacity"] else 150.0
    except (KeyError, IndexError):
        capacity = 150.0
    try:
        last_claim = user["last_income_claim"]
    except (KeyError, IndexError):
        last_claim = None

    accumulated = 0.0
    if last_claim and total_income > 0:
        from datetime import datetime as _dt
        try:
            last_dt = _dt.fromisoformat(last_claim)
            diff = (_dt.now() - last_dt).total_seconds()
            capped = min(diff, 600)  # макс 10 мин
            hours = capped / 3600.0
            accumulated = min(total_income * hours, capacity)
        except (ValueError, TypeError):
            accumulated = 0.0

    # VIP / Premium статус
    vip = user["vip_type"] if user else None
    if vip:
        exp = user["vip_expires"]
        emoji = "💎" if vip.lower() == "premium" else "⭐"
        bonuses = []
        if mc > 1:
            bonuses.append(f"×{mc:g} клик")
        if mi != 1:
            bonuses.append(f"×{mi:g} доход")
        bonus_str = ", ".join(bonuses) if bonuses else ""
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
            exp_str = ""
        vip_line = f"{emoji} Статус: {vip.upper()} ({bonus_str}) — {exp_str}"
    else:
        vip_line = "⭐ Статус: не активен"

    return (
        f"<b>💢 КликТохн</b> [ Главное меню ]\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 <b>{name_line}</b>  (ID: <code>{uid}</code>)\n"
        f"{vip_line}\n"
        f"\n\n"
        f"💢 Баланс: <b>{fnum(user['clicks'])}</b> Тохн\n"
        f"⚡ Клик: <b>+{fnum(display_power)}</b> Тохн\n\n"
        f"📈 Доход: <b>{fnum(total_income)}</b>/ч\n"
        f"📦 Емкость: {fnum(accumulated)} / {fnum(capacity)}\n"
        f"🎨 НФТ: {nft_count}/{max_slots}\n"
        f"\n\n"
        f"🪪 Ранг: {rank_name}\n"
        f"▸ Прогресс {bar}\n"
        f"\n\n"
        f"🔗 Рефералов: {user['referrals']}\n"
        f"❤️ Лайков: {likes}\n"
        f"👥 Участников: {total_users}\n"
        f"━━━━━━━━━━━━━━━━━━━"
    )


# ━━━━━━━━━━━━━━━━━━━ /start ━━━━━━━━━━━━━━━━━━━
@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    username = message.from_user.username or "Аноним"

    if await is_user_banned(user_id):
        return await message.answer("❌ Вы заблокированы.")

    await state.clear()
    await set_user_online(user_id)

    existing = await get_user(user_id)
    is_new = existing is None
    await create_user(user_id, username)

    args = message.text.split()
    if len(args) > 1 and is_new:
        try:
            ref_id = int(args[1])
            if ref_id != user_id:
                ref_user = await get_user(ref_id)
                if ref_user:
                    await add_referral(user_id, ref_id)
        except (ValueError, TypeError):
            pass

    total = await count_users()
    online = await get_online_count()
    user = await get_user(user_id)
    rank_name = RANKS_LIST.get(user["rank"] or 1, "🍼 Новичок")

    text = (
        f"<b>💢 КликТохн</b>  ·  v{VERSION}\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"👥 Игроков: <b>{total}</b>  ·  🟢 Онлайн: <b>{online}</b>\n\n"
        f"🏆 Ранг: {rank_name}\n"
        f"⚡ Клик: <b>+{fnum(BASE_CLICK_POWER + user['bonus_click'])}</b> Тохн\n\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"Нажмите <b>Начать</b> для входа"
    )

    await send_msg(message, text, reply_markup=start_kb())


@router.callback_query(F.data == "open_menu")
async def open_menu(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await set_user_online(call.from_user.id)
    user = await get_user(call.from_user.id)
    if not user:
        return await call.answer("❌ Используйте /start", show_alert=True)
    total = await count_users()
    await send_msg(
        call,
        await _profile_text(user, total),
        reply_markup=main_menu_kb(),
    )


# ━━━━━━━━━━━━━━━━━━━ Доход (информационный экран) ━━━━━━━━━━━━━━━━━━━
@router.callback_query(F.data == "claim_income")
async def claim_income(call: CallbackQuery):
    uid = call.from_user.id
    await set_user_online(uid)
    user = await get_user(uid)
    if not user:
        return await call.answer("❌ Используйте /start", show_alert=True)

    income_rate = float(user["passive_income"] or 0)
    capacity = float(user["income_capacity"]) if user["income_capacity"] else 150.0

    if income_rate <= 0:
        nft_count = await count_user_nfts(uid)
        max_slots = await get_user_nft_slots(uid)
        text = (
            "<b>💵 Пассивный доход</b>\n"
            "━━━━━━━━━━━━━━━━━━━\n\n"
            "⚠️ У вас пока нет пассивного дохода.\n\n"
            "Чтобы получать Тохн/час:\n"
            "  ▸ Купите улучшения 📈 в Магазине\n"
            "  ▸ Или приобретите НФТ 🎨\n\n"
            f"🎨 НФТ: {nft_count}/{max_slots}\n\n"
            "━━━━━━━━━━━━━━━━━━━"
        )
        await safe_edit(call.message, text, reply_markup=income_kb())
        return await call.answer()

    from datetime import datetime
    last_claim = user["last_income_claim"]
    if not last_claim:
        accumulated = 0.0
        time_str = "—"
    else:
        try:
            last_dt = datetime.fromisoformat(last_claim)
        except (ValueError, TypeError):
            last_dt = datetime.now()
        diff = (datetime.now() - last_dt).total_seconds()
        capped = min(diff, 600)  # макс 10 мин
        hours = capped / 3600.0
        accumulated = min(income_rate * hours, capacity)
        m = int(capped // 60)
        s = int(capped % 60)
        if m > 0:
            time_str = f"{m}м {s:02d}с"
        else:
            time_str = f"{s}с" if s > 0 else "&lt;1с"

    fill_pct = min(int(accumulated / capacity * 100), 100) if capacity > 0 else 0
    filled = fill_pct // 10
    bar = "█" * filled + "░" * (10 - filled)

    nft_count = await count_user_nfts(uid)
    max_slots = await get_user_nft_slots(uid)

    text = (
        "<b>💵 Пассивный доход</b>\n"
        "━━━━━━━━━━━━━━━━━━━\n\n"
        f"📈 Скорость: <b>{fnum(income_rate)}</b> Тохн/ч\n"
        f"📦 Копилка: {fnum(accumulated)}/{fnum(capacity)} Тохн\n"
        f"  [{bar}] {fill_pct}%\n\n"
        f"🎨 НФТ: {nft_count}/{max_slots}\n"
        f"⏱ Накоплено за: {time_str}\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "Нажмите «Собрать» чтобы получить."
    )
    await safe_edit(call.message, text, reply_markup=income_kb())
    await call.answer()


@router.callback_query(F.data == "do_claim_income")
async def do_claim_income(call: CallbackQuery):
    uid = call.from_user.id
    user = await get_user(uid)
    if not user:
        return await call.answer("❌ Используйте /start", show_alert=True)

    income_rate = float(user["passive_income"] or 0)
    capacity = float(user["income_capacity"]) if user["income_capacity"] else 150.0

    if income_rate <= 0:
        return await call.answer("📈 Нет пассивного дохода!", show_alert=True)

    earned, hours = await claim_passive_income(uid)

    if earned == -1.0:
        nft_count = await count_user_nfts(uid)
        max_slots = await get_user_nft_slots(uid)
        text = (
            "<b>💵 Пассивный доход</b>\n"
            "━━━━━━━━━━━━━━━━━━━\n\n"
            f"📈 Скорость: <b>{fnum(income_rate)}</b> Тохн/ч\n"
            f"📦 Копилка: 0/{fnum(capacity)} Тохн\n"
            f"🎨 НФТ: {nft_count}/{max_slots}\n\n"
            "✅ Таймер дохода запущен!\n"
            "Возвращайтесь позже за доходом.\n\n"
            "━━━━━━━━━━━━━━━━━━━"
        )
        await safe_edit(call.message, text, reply_markup=income_kb())
        return await call.answer("✅ Таймер запущен!", show_alert=False)

    if earned <= 0:
        remaining = int(hours)
        return await call.answer(f"⏳ Подождите ещё {remaining} сек.", show_alert=True)

    user = await get_user(uid)
    new_balance = float(user["clicks"]) if user else 0
    nft_count = await count_user_nfts(uid)
    max_slots = await get_user_nft_slots(uid)

    # hours уже ограничен 10 мин в claim_passive_income
    total_sec = hours * 3600
    m = int(total_sec // 60)
    s = int(total_sec % 60)
    if m > 0:
        time_str = f"{m}м {s:02d}с"
    else:
        time_str = f"{s}с" if s > 0 else "&lt;1с"

    text = (
        "<b>💵 Доход собран!</b>\n"
        "━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 Начислено: <b>+{fnum(earned)}</b> Тохн\n"
        f"📈 Скорость: {fnum(income_rate)}/ч\n"
        f"📦 Копилка: 0/{fnum(capacity)}\n"
        f"🎨 НФТ: {nft_count}/{max_slots}\n\n"
        f"⏱ Накоплено за: {time_str}\n\n"
        f"💢 Баланс: <b>{fnum(new_balance)}</b> Тохн\n\n"
        "━━━━━━━━━━━━━━━━━━━"
    )
    await safe_edit(call.message, text, reply_markup=income_kb())
    await call.answer(f"+{fnum(earned)} Тохн", show_alert=False)


# ━━━━━━━━━━━━━━━━━━━ Навигация ━━━━━━━━━━━━━━━━━━━
@router.callback_query(F.data == "menu")
async def back_to_menu(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await set_user_online(call.from_user.id)
    user = await get_user(call.from_user.id)
    if not user:
        return await call.answer("❌ Используйте /start", show_alert=True)
    total = await count_users()
    await send_msg(
        call,
        await _profile_text(user, total),
        reply_markup=main_menu_kb(),
    )


@router.callback_query(F.data.startswith("menu_page:"))
async def menu_page(call: CallbackQuery, state: FSMContext):
    await state.clear()
    user = await get_user(call.from_user.id)
    if not user:
        return await call.answer("❌ Используйте /start", show_alert=True)
    page = int(call.data.split(":")[1])
    total = await count_users()
    txt = await _profile_text(user, total)
    kb = main_menu_kb(page)
    try:
        # Если сообщение с фото — edit_caption
        if call.message.photo:
            await call.message.edit_caption(caption=txt, reply_markup=kb)
        else:
            await safe_edit(call.message, txt, reply_markup=kb)
    except Exception:
        pass
    await call.answer()


@router.callback_query(F.data == "noop")
async def noop_callback(call: CallbackQuery):
    await call.answer()


# ━━━━━━━━━━━━━━━━━━━ Мини-игры (точка входа) ━━━━━━━━━━━━━━━━━━━
@router.callback_query(F.data == "minigames_menu")
async def minigames_menu(call: CallbackQuery):
    from config import MINIGAMES_OPEN_CLICKS
    from keyboards import minigames_menu_kb
    user = await get_user(call.from_user.id)
    if not user:
        return await call.answer("❌ /start", show_alert=True)
    if (user["total_clicks"] or 0) < MINIGAMES_OPEN_CLICKS:
        return await call.answer(
            f"🔒 Нужно {MINIGAMES_OPEN_CLICKS} кликов чтобы открыть мини-игры!",
            show_alert=True,
        )
    text = (
        "<b>🎮 Мини-игры</b>\n"
        "━━━━━━━━━━━━━━━━━━━\n\n"
        "Выберите развлечение:"
    )
    await safe_edit(call.message, text, reply_markup=minigames_menu_kb())
    await call.answer()


# ━━━━━━━━━━━━━━━━━━━ Приз ━━━━━━━━━━━━━━━━━━━
@router.callback_query(F.data == "prize_menu")
async def prize_menu(call: CallbackQuery):
    uid = call.from_user.id
    user = await get_user(uid)
    if not user:
        return await call.answer("❌ /start", show_alert=True)

    subscribed = False
    try:
        member = await call.bot.get_chat_member(PRIZE_CHANNEL_ID, uid)
        subscribed = member.status in ("member", "administrator", "creator")
    except Exception:
        subscribed = False

    claim = await get_prize_claim(uid)

    if not subscribed:
        if claim and claim[3] == 1:
            await deactivate_prize(uid)
            await update_bonus_click(uid, -PRIZE_POWER)
            await remove_nft_slot(uid, 1)
            text = (
                "🎁 ПРИЗ\n══════════════════════\n\n"
                "⚠️ Вы отписались от канала!\n"
                f"❌ Клик-сила снижена на -{fnum(PRIZE_POWER)}\n"
                f"❌ -1 слот НФТ\n\n"
                f"📢 Подпишитесь снова на «{PRIZE_CHANNEL_NAME}»\n"
                "══════════════════════"
            )
        else:
            text = (
                "🎁 ПРИЗ\n══════════════════════\n\n"
                f"📢 Подпишитесь на «{PRIZE_CHANNEL_NAME}» и получите:\n\n"
                f"  💢 +{fnum(PRIZE_CLICKS)} тохн\n"
                f"  ⚡ +{fnum(PRIZE_POWER)} клик-сила\n"
                f"  🎨 +1 слот НФТ\n\n"
                "1️⃣ Подпишитесь на канал ниже\n"
                "2️⃣ Нажмите «Проверить»\n"
                "══════════════════════"
            )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📢 Подписаться", url=PRIZE_CHANNEL_LINK)],
            [InlineKeyboardButton(text="✅ Проверить подписку", callback_data="prize_check")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="ref_menu")],
        ])
    else:
        if not claim:
            await update_clicks(uid, PRIZE_CLICKS)
            await update_bonus_click(uid, PRIZE_POWER)
            await add_nft_slot(uid, 1)
            await set_prize_claim(uid)
            text = (
                "🎁 ПРИЗ ПОЛУЧЕН!\n══════════════════════\n\n"
                f"  💢 +{fnum(PRIZE_CLICKS)} тохн\n"
                f"  ⚡ +{fnum(PRIZE_POWER)} клик-сила\n"
                f"  🎨 +1 слот НФТ\n\n"
                "⚠️ Если отпишетесь от канала — потеряете клик-силу!\n"
                "══════════════════════"
            )
        elif claim[3] == 0:
            await update_bonus_click(uid, PRIZE_POWER)
            await add_nft_slot(uid, 1)
            await set_prize_claim(uid)
            text = (
                "🎁 С ВОЗВРАЩЕНИЕМ!\n══════════════════════\n\n"
                f"⚡ +{fnum(PRIZE_POWER)} клик-сила возвращена\n"
                f"🎨 +1 слот НФТ возвращён\n"
                "══════════════════════"
            )
        else:
            text = (
                "🎁 ПРИЗ\n══════════════════════\n\n"
                f"✅ Подписка активна! ⚡ +{fnum(PRIZE_POWER)} клик-сила\n"
                "══════════════════════"
            )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📢 Канал", url=PRIZE_CHANNEL_LINK)],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="ref_menu")],
        ])

    try:
        await safe_edit(call.message, text, reply_markup=kb)
    except Exception:
        await call.message.answer(text, reply_markup=kb)
    await call.answer()


@router.callback_query(F.data == "prize_check")
async def prize_check(call: CallbackQuery):
    uid = call.from_user.id
    user = await get_user(uid)
    if not user:
        return await call.answer("❌ /start", show_alert=True)

    subscribed = False
    try:
        member = await call.bot.get_chat_member(PRIZE_CHANNEL_ID, uid)
        subscribed = member.status in ("member", "administrator", "creator")
    except Exception:
        subscribed = False

    if not subscribed:
        return await call.answer("❌ Вы ещё не подписались!", show_alert=True)

    claim = await get_prize_claim(uid)
    if not claim:
        await update_clicks(uid, PRIZE_CLICKS)
        await update_bonus_click(uid, PRIZE_POWER)
        await add_nft_slot(uid, 1)
        await set_prize_claim(uid)
        await call.answer(f"🎉 +{fnum(PRIZE_CLICKS)} 💢, +{fnum(PRIZE_POWER)} сила, +1 слот НФТ!", show_alert=True)
    elif claim[3] == 0:
        await update_bonus_click(uid, PRIZE_POWER)
        await add_nft_slot(uid, 1)
        await set_prize_claim(uid)
        await call.answer(f"🔄 +{fnum(PRIZE_POWER)} клик-сила, +1 слот НФТ возвращены!", show_alert=True)
    else:
        await call.answer("✅ Приз уже активен!", show_alert=True)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Канал", url=PRIZE_CHANNEL_LINK)],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="ref_menu")],
    ])
    text = (
        "🎁 ПРИЗ\n══════════════════════\n\n"
        f"✅ Подписка активна! ⚡ +{fnum(PRIZE_POWER)}\n"
        "══════════════════════"
    )
    try:
        await safe_edit(call.message, text, reply_markup=kb)
    except Exception:
        pass


# ══════════════════════════════════════════
#  ДИАЛОГ С АДМИНИСТРАЦИЕЙ (ответ пользователя)
# ══════════════════════════════════════════
from states import DialogStates
from config import OWNER_ID


@router.callback_query(F.data.startswith("dialog_reply_"))
async def dialog_reply_start(call: CallbackQuery, state: FSMContext):
    """Пользователь нажал 'Ответить' на сообщение от админа/владельца."""
    parts = call.data.split("_")          # dialog_reply_{type}_{id}
    sender_type = parts[2]                # adm / owner
    sender_id = int(parts[3])
    await state.set_state(DialogStates.user_replying)
    await state.update_data(target_id=sender_id, target_type=sender_type)
    await call.message.answer(
        "💬 Введите ваш ответ администрации:\n\n"
        "Отправьте текст или /cancel для отмены."
    )
    await call.answer()


@router.message(DialogStates.user_replying)
async def dialog_reply_send(message: Message, state: FSMContext):
    """Пользователь отправил текст ответа."""
    if message.text and message.text.strip() == "/cancel":
        await state.clear()
        return await message.answer("❌ Отменено.")
    data = await state.get_data()
    target_id = data.get("target_id")
    target_type = data.get("target_type", "owner")
    if not target_id:
        await state.clear()
        return
    uid = message.from_user.id
    uname = message.from_user.username or "—"
    text_to_admin = (
        f"💬 <b>Ответ от пользователя</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"👤 ID: <code>{uid}</code> | @{uname}\n\n"
        f"{message.text or '(файл)'}\n\n"
        f"━━━━━━━━━━━━━━━━━━━"
    )
    try:
        from keyboards import dialog_incoming_reply_kb
        prefix = target_type  # adm / owner
        await message.bot.send_message(
            target_id, text_to_admin, parse_mode="HTML",
            reply_markup=dialog_incoming_reply_kb(prefix, uid),
        )
        await message.answer("✅ Ваш ответ отправлен администрации.")
    except Exception:
        await message.answer("❌ Не удалось отправить ответ.")
    await state.clear()


# ══════════════════════════════════════════
#  АУКЦИОН (broadcast-модель для участников)
# ══════════════════════════════════════════
from datetime import datetime as _dtm
from states import EventBidStates
from keyboards import auction_broadcast_kb, auction_joined_kb
from config import NFT_RARITIES, NFT_RARITY_EMOJI

_MEDALS = ["🥇", "🥈", "🥉"]


def _time_left_str(ends_at: str) -> str:
    """Человекочитаемый оставшийся таймер."""
    try:
        end = _dtm.fromisoformat(ends_at)
        delta = (end - _dtm.now()).total_seconds()
        if delta <= 0:
            return "⏰ Завершён"
        if delta < 60:
            return f"⏱ {int(delta)} сек"
        if delta < 3600:
            m = int(delta // 60)
            s = int(delta % 60)
            return f"⏱ {m} мин {s:02d} сек"
        h = int(delta // 3600)
        m = int((delta % 3600) // 60)
        return f"⏱ {h} ч {m:02d} мин"
    except Exception:
        return "⏱ ?"


def _build_auction_card(event, parts=None, my_bid=None) -> str:
    """Красивая карточка аукциона (для broadcast/обновления)."""
    p_count = len(parts) if parts else 0
    rn = event["nft_rarity"] if isinstance(event["nft_rarity"], str) else "Обычный"
    emoji = NFT_RARITY_EMOJI.get(rn, "🎨")
    timer = _time_left_str(event["ends_at"]) if event["ends_at"] else ""

    try:
        col = event['nft_collection'] or ''
    except (KeyError, IndexError):
        col = ''
    col_line = f"  📂 Коллекция: <b>{col}</b>\n" if col else ""

    # Список участников (отсортирован по ставке DESC из БД)
    p_lines = []
    if parts:
        for i, p in enumerate(parts[:10], 1):
            p_uid = p[0] if isinstance(p, tuple) else p["user_id"]
            p_bid = p[1] if isinstance(p, tuple) else p["bid_amount"]
            p_name = p[2] if isinstance(p, tuple) else (p["username"] if p["username"] else "?")
            medal = _MEDALS[i - 1] if i <= 3 else f"{i}."
            p_lines.append(f"  {medal} @{p_name or '???'} (<code>{p_uid}</code>) — {fnum(p_bid)} 💢")
    p_text = "\n".join(p_lines) if p_lines else "  Пока нет участников"

    warn = ""
    if p_count < 2:
        warn = "\n⚠️ <i>Нужно мин. 2 участника (иначе — отмена и возврат)</i>\n"

    bid_line = ""
    if my_bid is not None:
        bid_line = f"\n✅ <b>Ваша ставка:</b> {fnum(my_bid)} 💢"

    return (
        f"🎪 <b>НОВЫЙ АУКЦИОН!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"  📛 Название: <b>{event['nft_prize_name']}</b>\n"
        f"{col_line}"
        f"  ✨ Редкость: {emoji} <b>{rn}</b>\n"
        f"  💰 Доход: <b>{fnum(event['nft_income'])}</b>/ч\n\n"
        f"💵 Мин. ставка: <b>{fnum(event['bet_amount'])}</b> 💢\n"
        f"⏳ Длительность: {timer}\n"
        f"👥 Участников: <b>{p_count}/{event['max_participants']}</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🏆 <b>Соревнование:</b>\n{p_text}\n"
        f"━━━━━━━━━━━━━━━━━━━"
        f"{warn}{bid_line}\n\n"
        f"🏆 Победитель получает НФТ!\n"
        f"❌ Проигравшие теряют ставки"
    )


@router.callback_query(F.data.startswith("auc_ignore:"))
async def auc_ignore(call: CallbackQuery):
    """Пользователь нажал «Игнорировать» — удаляем сообщение."""
    try:
        await call.message.delete()
    except Exception:
        pass
    await call.answer()


@router.callback_query(F.data.startswith("auc_view:"))
async def auc_view(call: CallbackQuery):
    """Обновить карточку аукциона в broadcast-сообщении."""
    uid = call.from_user.id
    user = await get_user(uid)
    if not user:
        return await call.answer("❌ /start", show_alert=True)
    eid = int(call.data.split(":")[1])
    event = await get_event(eid)
    if not event or event["status"] != "active":
        return await call.answer("❌ Аукцион завершён или не найден", show_alert=True)

    parts = await get_event_participants(eid)
    my_bid = await get_user_event_bid(eid, uid)
    user_joined = my_bid is not None

    text = _build_auction_card(event, parts, my_bid)
    kb = auction_joined_kb(eid) if user_joined else auction_broadcast_kb(eid)
    await safe_edit(call.message, text, reply_markup=kb)
    await call.answer()


@router.callback_query(F.data.startswith("auc_join:"))
async def auc_join(call: CallbackQuery):
    uid = call.from_user.id
    user = await get_user(uid)
    if not user:
        return await call.answer("❌ /start", show_alert=True)
    eid = int(call.data.split(":")[1])
    event = await get_event(eid)
    if not event or event["status"] != "active":
        return await call.answer("❌ Аукцион завершён", show_alert=True)

    existing_bid = await get_user_event_bid(eid, uid)
    if existing_bid is not None:
        return await call.answer("✅ Вы уже участвуете!", show_alert=True)

    p_count = await count_event_participants(eid)
    if p_count >= event["max_participants"]:
        return await call.answer("❌ Максимум участников достигнут", show_alert=True)

    min_bet = float(event["bet_amount"])
    if float(user["clicks"]) < min_bet:
        return await call.answer(f"❌ Нужно {fnum(min_bet)} 💢", show_alert=True)

    ok = await join_event(eid, uid, min_bet)
    if not ok:
        return await call.answer("❌ Ошибка при участии", show_alert=True)

    await log_activity(uid, "auction_join", f"Аукцион #{eid}, ставка {fnum(min_bet)}")
    await call.answer(f"✅ Вы вступили! Ставка: {fnum(min_bet)} 💢", show_alert=True)

    # Обновить карточку — показать кнопку «Повысить ставку»
    parts = await get_event_participants(eid)
    text = _build_auction_card(event, parts, min_bet)
    try:
        await call.message.edit_text(text, reply_markup=auction_joined_kb(eid), parse_mode="HTML")
    except Exception:
        pass


@router.callback_query(F.data.startswith("auc_raise:"))
async def auc_raise(call: CallbackQuery, state: FSMContext):
    uid = call.from_user.id
    eid = int(call.data.split(":")[1])
    event = await get_event(eid)
    if not event or event["status"] != "active":
        return await call.answer("❌ Аукцион завершён", show_alert=True)

    my_bid = await get_user_event_bid(eid, uid)
    if my_bid is None:
        return await call.answer("❌ Вы не участвуете", show_alert=True)

    await state.set_state(EventBidStates.waiting_bid)
    await state.update_data(auc_event_id=eid, auc_current_bid=my_bid)
    await call.message.edit_text(
        f"<b>💰 Добавить сумму</b>\n"
        "━━━━━━━━━━━━━━━━━━━\n\n"
        f"Текущая ставка: <b>{fnum(my_bid)}</b> 💢\n\n"
        "Введите новую общую ставку\n"
        "(должна быть выше текущей):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data=f"auc_view:{eid}")],
        ]),
    )
    await call.answer()


@router.message(EventBidStates.waiting_bid)
async def auc_bid_input(message: Message, state: FSMContext):
    uid = message.from_user.id
    data = await state.get_data()
    eid = data.get("auc_event_id")
    current_bid = data.get("auc_current_bid", 0)
    await state.clear()

    if not eid:
        return await message.answer("❌ Ошибка")

    try:
        new_bid = float(message.text.strip())
    except (ValueError, TypeError):
        return await message.answer("❌ Введите число")

    if new_bid <= current_bid:
        return await message.answer(
            f"❌ Ставка должна быть выше {fnum(current_bid)} 💢",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Обновить", callback_data=f"auc_view:{eid}")],
            ]),
        )

    user = await get_user(uid)
    additional = new_bid - current_bid
    if float(user["clicks"]) < additional:
        return await message.answer(
            f"❌ Не хватает {fnum(additional)} 💢\n"
            f"У вас: {fnum(user['clicks'])} 💢",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Обновить", callback_data=f"auc_view:{eid}")],
            ]),
        )

    event = await get_event(eid)
    if not event or event["status"] != "active":
        return await message.answer("❌ Аукцион завершён")

    await update_event_bid(eid, uid, new_bid, additional)
    await log_activity(uid, "auction_raise", f"Аукцион #{eid}, ставка {fnum(new_bid)}")
    await message.answer(
        f"✅ Ставка повышена до <b>{fnum(new_bid)}</b> 💢!\n"
        f"Списано: {fnum(additional)} 💢",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить", callback_data=f"auc_view:{eid}")],
        ]),
    )

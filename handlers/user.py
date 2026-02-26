# ======================================================
# USER — Клик‑зона, Рефералы, Рейтинг
# ======================================================

import random
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from config import RANKS_LIST, BASE_CLICK_POWER, REFERRAL_BOT_USERNAME, RANK_THRESHOLDS
from database import get_user, update_clicks, update_rank, get_top_players, get_user_anonymous, set_user_anonymous
from keyboards import click_zone_kb, referral_kb, rating_kb, back_menu_kb
from handlers.common import fnum

router = Router()


# ══════════ 1. КЛИК ТОХН ══════════
@router.callback_query(F.data == "click_menu")
async def show_click_zone(call: CallbackQuery):
    user = await get_user(call.from_user.id)
    if not user:
        return await call.answer("❌ /start", show_alert=True)

    power = BASE_CLICK_POWER + user["bonus_click"]
    rank_id = user["rank"] or 1
    rank_name = RANKS_LIST.get(rank_id, "🍼 Новичок")

    # Прогресс
    total_clicks = user["total_clicks"] or 0
    cur_thresh = RANK_THRESHOLDS[min(rank_id - 1, len(RANK_THRESHOLDS) - 1)]
    nxt_thresh = RANK_THRESHOLDS[min(rank_id, len(RANK_THRESHOLDS) - 1)]
    if rank_id >= len(RANK_THRESHOLDS):
        nxt_thresh = cur_thresh
    progress = total_clicks - cur_thresh
    target = nxt_thresh - cur_thresh
    if target > 0:
        pct = min(int(progress / target * 100), 100)
    else:
        pct = 100
    filled = pct // 10
    bar = "█" * filled + "░" * (10 - filled)

    text = (
        f"🔘 ЗОНА МАЙНИНГА КЛИКТОХН\n"
        f"──────────────────\n"
        f"💰 Баланс: {fnum(user['clicks'])} 💢\n"
        f"⚡ Сила: +{fnum(power)} Тохн\n"
        f"🏆 Ранг: {rank_name}\n\n"
        f"🪫 Прогресс: [{bar}] {pct}%\n"
        f"   {fnum(total_clicks)} / {fnum(nxt_thresh)}\n"
        f"──────────────────\n"
        f"Жми на кнопку ниже, чтобы зарабатывать!"
    )

    await call.message.edit_text(text, reply_markup=click_zone_kb())
    await call.answer()


@router.callback_query(F.data == "tap")
async def process_tap(call: CallbackQuery):
    uid = call.from_user.id
    user = await get_user(uid)
    if not user:
        return

    power = BASE_CLICK_POWER + user["bonus_click"]

    # 5 % шанс крита × 5
    is_crit = random.random() < 0.05
    earn = power * (5 if is_crit else 1)

    await update_clicks(uid, earn)
    await update_rank(uid)

    # Перечитываем юзера — уже с новым балансом
    user = await get_user(uid)
    new_balance = user["clicks"] if user else 0
    rank_id = (user["rank"] or 1) if user else 1
    rank_name = RANKS_LIST.get(rank_id, "🍼 Новичок")

    # Прогресс до следующего ранга
    total_clicks = (user["total_clicks"] or 0) if user else 0
    cur_thresh = RANK_THRESHOLDS[min(rank_id - 1, len(RANK_THRESHOLDS) - 1)]
    nxt_thresh = RANK_THRESHOLDS[min(rank_id, len(RANK_THRESHOLDS) - 1)]
    if rank_id >= len(RANK_THRESHOLDS):
        nxt_thresh = cur_thresh
    progress = total_clicks - cur_thresh
    target = nxt_thresh - cur_thresh
    if target > 0:
        pct = min(int(progress / target * 100), 100)
    else:
        pct = 100
    filled = pct // 10
    bar = "█" * filled + "░" * (10 - filled)

    crit = "🔥 КРИТ! " if is_crit else ""

    # Обновляем текст сообщения — баланс в реал-тайме
    text = (
        f"🔘 ЗОНА МАЙНИНГА КЛИКТОХН\n"
        f"──────────────────\n"
        f"💰 Баланс: {fnum(new_balance)} 💢\n"
        f"⚡ Сила: +{fnum(power)} Тохн\n"
        f"🏆 Ранг: {rank_name}\n\n"
        f"🪫 Прогресс: [{bar}] {pct}%\n"
        f"   {fnum(total_clicks)} / {fnum(nxt_thresh)}\n"
        f"──────────────────\n"
        f"{crit}+{fnum(earn)} 💢"
    )

    try:
        await call.message.edit_text(text, reply_markup=click_zone_kb())
    except Exception:
        pass  # текст не изменился — Telegram бросает ошибку

    await call.answer(f"{crit}+{fnum(earn)} 💢", show_alert=False)


# ══════════ 2. ПРИГЛАСИТЬ ══════════
@router.callback_query(F.data == "ref_menu")
async def show_referral(call: CallbackQuery):
    uid = call.from_user.id
    user = await get_user(uid)
    if not user:
        return await call.answer("❌ /start", show_alert=True)

    ref_link = f"https://t.me/{REFERRAL_BOT_USERNAME}?start={uid}"
    ref_count = user["referrals"]
    bonus_clicks = ref_count * 100  # общая сумма бонусных кликов
    bonus_power = ref_count * 0.5

    text = (
        f"🔗 РЕФЕРАЛЬНАЯ ПРОГРАММА\n"
        f"══════════════════════\n\n"
        f"👥 Ваши рефералы: {ref_count} человек\n"
        f"💰 Бонус: +{fnum(bonus_clicks)} Тохн\n"
        f"💢 Клик: +{fnum(bonus_power)} 💢\n\n"
        f"🎁 НАГРАДЫ ЗА ПРИГЛАШЕНИЕ:\n"
        f"• За 1‑го реферала: +200 💢 + +0.5 силы\n"
        f"• За каждого реферала: +100 💢 + +0.5 силы\n\n"
        f"🔐 (Ссылка):\n"
        f"{ref_link}\n\n"
        f"Поделитесь своей ссылкой и получайте награды!\n"
        f"══════════════════════"
    )

    await call.message.edit_text(text, reply_markup=referral_kb(ref_link))
    await call.answer()


# ══════════ 4. РЕЙТИНГ ══════════
@router.callback_query(F.data == "rating_menu")
async def show_rating_menu(call: CallbackQuery):
    text = (
        "🏆 РЕЙТИНГ\n"
        "══════════════════════\n\n"
        "Посмотрите лучших игроков!"
    )
    await call.message.edit_text(text, reply_markup=rating_kb())
    await call.answer()


@router.callback_query(F.data == "top_50")
async def show_top50(call: CallbackQuery):
    uid = call.from_user.id
    players = await get_top_players(50)
    is_anon = await get_user_anonymous(uid)

    text = "🏆 ТОП‑50 ИГРОКОВ\n══════════════════════\n\n"

    if not players:
        text += "Пока нет игроков.\n"
    else:
        medals = {1: "🥇", 2: "🥈", 3: "🥉"}
        for i, p in enumerate(players, 1):
            p_uid, uname, clicks, bonus, passive, rank, anon = p
            medal = medals.get(i, f"#{i}")
            if anon:
                name = "Аноним"
            else:
                name = f"@{uname}" if uname else "Аноним"
            power = BASE_CLICK_POWER + (bonus or 0)
            text += (
                f"{medal} {name}\n"
                f"   💢 {fnum(clicks)}  ⚡ +{fnum(power)}  📈 {fnum(passive)}/ч\n\n"
            )

    status = "🟢 Вкл" if is_anon else "🔴 Выкл"
    text += f"══════════════════════\n🕶 Анонимность: {status}"

    anon_label = "🕶 Выключить анонимность" if is_anon else "🕶 Включить анонимность"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=anon_label, callback_data="toggle_anon")],
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="top_50")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="rating_menu")],
    ])

    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


@router.callback_query(F.data == "toggle_anon")
async def toggle_anon(call: CallbackQuery):
    uid = call.from_user.id
    current = await get_user_anonymous(uid)
    new_val = not current
    await set_user_anonymous(uid, new_val)

    status = "включена 🟢" if new_val else "выключена 🔴"
    await call.answer(f"🕶 Анонимность {status}", show_alert=True)

    # Обновляем экран топа
    players = await get_top_players(50)

    text = "🏆 ТОП‑50 ИГРОКОВ\n══════════════════════\n\n"

    if not players:
        text += "Пока нет игроков.\n"
    else:
        medals = {1: "🥇", 2: "🥈", 3: "🥉"}
        for i, p in enumerate(players, 1):
            p_uid, uname, clicks, bonus, passive, rank, anon = p
            medal = medals.get(i, f"#{i}")
            if anon:
                name = "Аноним"
            else:
                name = f"@{uname}" if uname else "Аноним"
            power = BASE_CLICK_POWER + (bonus or 0)
            text += (
                f"{medal} {name}\n"
                f"   💢 {fnum(clicks)}  ⚡ +{fnum(power)}  📈 {fnum(passive)}/ч\n\n"
            )

    status_icon = "🟢 Вкл" if new_val else "🔴 Выкл"
    text += f"══════════════════════\n🕶 Анонимность: {status_icon}"

    anon_label = "🕶 Выключить анонимность" if new_val else "🕶 Включить анонимность"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=anon_label, callback_data="toggle_anon")],
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="top_50")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="rating_menu")],
    ])

    try:
        await call.message.edit_text(text, reply_markup=kb)
    except Exception:
        pass

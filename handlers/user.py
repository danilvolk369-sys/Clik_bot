# ======================================================
# USER — Клик, Рефералы, Рейтинг
# ======================================================
import random
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from config import (
    RANKS_LIST, BASE_CLICK_POWER, REFERRAL_BOT_USERNAME, RANK_THRESHOLDS,
    RATING_TOP_COUNT, REF_FIRST_CLICKS, REF_FIRST_POWER, REF_EACH_CLICKS,
    REF_EACH_POWER, OWNER_ID, NFT_RARITY_EMOJI,
)
from database import (
    get_user, update_clicks, update_rank, get_top_players, count_top_players,
    get_user_anonymous, set_user_anonymous, set_user_online,
    get_user_hide_nft, set_user_hide_nft,
    count_user_nfts, get_user_nft_slots, get_online_count,
    count_users, count_user_complaints_received,
    get_vip_multipliers, is_admin, get_user_top_nfts,
    add_like, has_liked, get_user_likes_count,
    remove_like,
)
from keyboards import click_zone_kb, referral_kb, rating_kb
from banners_util import send_msg, safe_edit
from handlers.common import fnum, _progress_bar
fnum = fnum  # re-export

router = Router()


# ══════════ КЛИК / ДОХОД ══════════
@router.callback_query(F.data == "click_menu")
async def show_click_zone(call: CallbackQuery):
    user = await get_user(call.from_user.id)
    if not user:
        return await call.answer("❌ /start", show_alert=True)
    await set_user_online(call.from_user.id)

    power = BASE_CLICK_POWER + user["bonus_click"]

    # VIP-множитель в отображении
    mc, mi = await get_vip_multipliers(call.from_user.id)
    display_power = power * mc

    rank_id = user["rank"] or 1
    rank_name = RANKS_LIST.get(rank_id, "🍼 Новичок")

    total_clicks = user["total_clicks"] or 0
    cur_thresh = RANK_THRESHOLDS[min(rank_id - 1, len(RANK_THRESHOLDS) - 1)]
    nxt_thresh = RANK_THRESHOLDS[min(rank_id, len(RANK_THRESHOLDS) - 1)]
    if rank_id >= len(RANK_THRESHOLDS):
        nxt_thresh = cur_thresh
    bar, pct = _progress_bar(total_clicks - cur_thresh, nxt_thresh - cur_thresh)

    income_rate = float(user["passive_income"] or 0)
    vip_line = ""
    vip = user["vip_type"] if user else None
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
            exp_str = ""
        emoji = "💎" if vip.lower() == "premium" else "⭐"
        bonuses = []
        if mc > 1:
            bonuses.append(f"×{mc:g} клик")
        if mi != 1:
            bonuses.append(f"×{mi:g} доход")
        bonus_str = ", ".join(bonuses) if bonuses else ""
        vip_line = f"{emoji} {vip.upper()} ({bonus_str}) — {exp_str}\n"

    # Множитель клика
    click_mult = f" ({mc:.0f}x)" if mc > 1 else ""

    text = (
        f"<b>🔘 Зона майнинга</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💰 Баланс: <b>{fnum(user['clicks'])}</b> 💢\n"
        f"⚡ Клик: <b>+{fnum(display_power)}</b> Тохн{click_mult}\n"
        f"{vip_line}"
        f"🏆 Ранг: {rank_name}  ·  📈 {fnum(income_rate)}/ч\n\n"
        f"▸ {bar}\n"
        f"  {fnum(total_clicks)} / {fnum(nxt_thresh)}\n"
        f"━━━━━━━━━━━━━━━━━━"
    )

    await send_msg(call, text, reply_markup=click_zone_kb())


@router.callback_query(F.data == "tap")
async def process_tap(call: CallbackQuery):
    uid = call.from_user.id
    user = await get_user(uid)
    if not user:
        return


    power = BASE_CLICK_POWER + user["bonus_click"]
    # VIP-множитель клика
    mc, _ = await get_vip_multipliers(uid)
    power *= mc
    # Крит — максимум x2
    is_crit = random.random() < 0.05
    earn = power * (2 if is_crit else 1)

    await update_clicks(uid, earn)
    await update_rank(uid)

    user = await get_user(uid)
    new_balance = user["clicks"] if user else 0
    rank_id = (user["rank"] or 1) if user else 1
    rank_name = RANKS_LIST.get(rank_id, "🍼 Новичок")
    income_rate = float(user["passive_income"] or 0) if user else 0

    total_clicks = (user["total_clicks"] or 0) if user else 0
    cur_thresh = RANK_THRESHOLDS[min(rank_id - 1, len(RANK_THRESHOLDS) - 1)]
    nxt_thresh = RANK_THRESHOLDS[min(rank_id, len(RANK_THRESHOLDS) - 1)]
    if rank_id >= len(RANK_THRESHOLDS):
        nxt_thresh = cur_thresh
    bar, pct = _progress_bar(total_clicks - cur_thresh, nxt_thresh - cur_thresh)

    crit = "🔥 КРИТ! " if is_crit else ""
    click_mult = f" ({mc:.0f}x)" if mc > 1 else ""

    text = (
        f"<b>🔘 Зона майнинга</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💰 Баланс: <b>{fnum(new_balance)}</b> 💢\n"
        f"⚡ Клик: <b>+{fnum(power)}</b> Тохн{click_mult}\n"
        f"🏆 Ранг: {rank_name}  ·  📈 {fnum(income_rate)}/ч\n\n"
        f"▸ {bar}\n"
        f"  {fnum(total_clicks)} / {fnum(nxt_thresh)}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{crit}<b>+{fnum(earn)}</b> 💢"
    )

    try:
        await call.message.edit_caption(caption=text, reply_markup=click_zone_kb())
    except Exception:
        try:
            await call.message.edit_text(text, reply_markup=click_zone_kb())
        except Exception:
            pass
    await call.answer(f"{crit}+{fnum(earn)} 💢", show_alert=False)


# ══════════ ПРИГЛАСИТЬ ══════════
@router.callback_query(F.data == "ref_menu")
async def show_referral(call: CallbackQuery):
    uid = call.from_user.id
    user = await get_user(uid)
    if not user:
        return await call.answer("❌ /start", show_alert=True)

    ref_link = f"https://t.me/{REFERRAL_BOT_USERNAME}?start={uid}"
    ref_count = user["referrals"]
    click_power = BASE_CLICK_POWER + user["bonus_click"]

    # Подсчёт заработанных кликов от рефералов
    if ref_count >= 1:
        earned = REF_FIRST_CLICKS + REF_FIRST_POWER
        if ref_count > 1:
            earned += (ref_count - 1) * (REF_EACH_CLICKS + REF_EACH_POWER)
        ref_power = REF_FIRST_POWER + max(0, ref_count - 1) * REF_EACH_POWER
    else:
        earned = 0
        ref_power = 0

    text = (
        f"<b>🔗 Реферальная программа</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"👥 Приглашено: <b>{ref_count}</b>\n"
        f"💰 Заработано: <b>{fnum(earned)}</b> Тохн\n"
        f"⚡ Клик-сила от рефов: <b>+{fnum(ref_power)}</b>\n"
        f"⚡ Общий клик: <b>+{fnum(click_power)}</b> Тохн\n\n"
        f"🎁 <b>НАГРАДЫ:</b>\n"
        f"▸ Первый реферал:\n"
        f"  💢 +{REF_FIRST_CLICKS}  ·  ⚡ +{REF_FIRST_POWER}\n\n"
        f"▸ Каждый реферал:\n"
        f"  💢 +{REF_EACH_CLICKS}  ·  ⚡ +{REF_EACH_POWER}\n\n"
        f"🔐 Ваша ссылка:\n{ref_link}\n\n"
        f"━━━━━━━━━━━━━━━━━━━"
    )

    await send_msg(call, text, reply_markup=referral_kb(ref_link))


# ══════════ РЕЙТИНГ ══════════
@router.callback_query(F.data == "rating_menu")
async def show_rating_menu(call: CallbackQuery):
    text = (
        "<b>🏆 Рейтинг</b>\n"
        "━━━━━━━━━━━━━━━━━━━\n\n"
        "Лучшие игроки КликТохн!"
    )
    await send_msg(call, text, reply_markup=rating_kb())


RATING_PER_PAGE = 3


@router.callback_query(F.data == "top_15")
async def show_top15(call: CallbackQuery):
    await _show_rating_page(call, 0)


@router.callback_query(F.data.startswith("top_range:"))
async def show_top_range(call: CallbackQuery):
    page = int(call.data.split(":")[1])
    await _show_rating_page(call, page)


@router.callback_query(F.data.startswith("rating_pg:"))
async def rating_page(call: CallbackQuery):
    page = int(call.data.split(":")[1])
    await _show_rating_page(call, page)


async def _show_rating_page(call: CallbackQuery, page: int):
    uid = call.from_user.id
    viewer_is_staff = (uid == OWNER_ID) or await is_admin(uid)
    total_players = await count_top_players()
    import math
    total_pages = max(1, math.ceil(min(RATING_TOP_COUNT, max(total_players, 1)) / RATING_PER_PAGE))  # динамически по RATING_TOP_COUNT
    if page < 0:
        page = 0
    if page >= total_pages:
        page = total_pages - 1

    offset = page * RATING_PER_PAGE
    players = await get_top_players(RATING_PER_PAGE, offset)
    is_anon = await get_user_anonymous(uid)

    start_pos = offset + 1
    end_pos = offset + RATING_PER_PAGE
    text = f"<b>🏆 Топ {start_pos}—{end_pos}</b>\n━━━━━━━━━━━━━━━━━━━\n\n"

    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    kb_players = []
    if not players:
        text += "Пока нет игроков.\n"
    else:
        for i, p in enumerate(players, offset + 1):
            p_uid, uname, clicks, bonus, passive, rank, anon = p
            medal = medals.get(i, f"#{i}")
            if anon:
                name = "Аноним"
            else:
                name = f"@{uname}" if uname else "Аноним"
            # ID видно только админам/владельцу
            if viewer_is_staff:
                id_str = f" (ID: {p_uid})"
            elif anon:
                id_str = ""
            else:
                id_str = ""
            power = BASE_CLICK_POWER + (bonus or 0)
            p_likes = await get_user_likes_count(p_uid)
            text += (
                f"{medal} {name}{id_str}\n"
                f"   💢 {fnum(clicks)}  ⚡ +{fnum(power)}  ❤️ {p_likes}\n\n"
            )
            kb_players.append(InlineKeyboardButton(
                text=f"👤 {medal} {name[:15]}",
                callback_data=f"view_profile_{p_uid}",
            ))

    status = "🟢 Вкл" if is_anon else "🔴 Выкл"
    hide_nft = await get_user_hide_nft(uid)
    nft_status = "🟢 Скрыто" if hide_nft else "🔴 Видно"
    text += (
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🕶 Анонимность: {status}\n"
        f"🎨 НФТ в рейтинге: {nft_status}"
    )

    anon_label = "🕶 Выкл анонимность" if is_anon else "🕶 Вкл анонимность"
    nft_hide_label = "🎨 Показать НФТ" if hide_nft else "🎨 Скрыть НФТ"

    kb = []
    for btn in kb_players:
        kb.append([btn])
    kb.append([
        InlineKeyboardButton(text=anon_label, callback_data="toggle_anon"),
        InlineKeyboardButton(text=nft_hide_label, callback_data="toggle_hide_nft"),
    ])

    # Пагинация: ▶️⏭️ 📂 1/5 ⏮️◀️
    nav_row = []
    nav_row.append(InlineKeyboardButton(text="▶️", callback_data=f"top_range:{min(page + 1, total_pages - 1)}"))
    nav_row.append(InlineKeyboardButton(text="⏭️", callback_data=f"top_range:{total_pages - 1}"))
    nav_row.append(InlineKeyboardButton(text=f"📂 {page + 1}/{total_pages}", callback_data="noop"))
    nav_row.append(InlineKeyboardButton(text="⏮️", callback_data="top_range:0"))
    nav_row.append(InlineKeyboardButton(text="◀️", callback_data=f"top_range:{max(page - 1, 0)}"))
    kb.append(nav_row)

    kb.append([InlineKeyboardButton(text="⬅️ Рейтинг", callback_data="rating_menu")])

    try:
        await call.message.edit_caption(caption=text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    except Exception:
        try:
            await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
        except Exception:
            pass
    await call.answer()


@router.callback_query(F.data.startswith("view_profile_"))
async def view_player_profile(call: CallbackQuery):
    target_uid = int(call.data.split("_")[2])
    viewer_uid = call.from_user.id
    user = await get_user(target_uid)
    if not user:
        return await call.answer("❌ Игрок не найден", show_alert=True)

    is_anon = await get_user_anonymous(target_uid)
    viewer_is_staff = (viewer_uid == OWNER_ID) or await is_admin(viewer_uid)

    if is_anon:
        name = "🕶 Аноним"
    else:
        name = f"@{user['username']}" if user['username'] else "Аноним"

    # ID видно только админам/владельцу; для анонимных ID скрыт
    if viewer_is_staff:
        id_line = f"📌 {name} (ID: {target_uid})\n"
    elif is_anon:
        id_line = f"📌 {name}\n"
    else:
        id_line = f"📌 {name}\n"

    rank_name = RANKS_LIST.get(user["rank"] or 1, "🍼 Новичок")
    power = BASE_CLICK_POWER + user["bonus_click"]
    mc, mi = await get_vip_multipliers(target_uid)
    display_power = power * mc
    nft_count = await count_user_nfts(target_uid)
    max_slots = await get_user_nft_slots(target_uid)
    complaints = await count_user_complaints_received(target_uid)
    likes = await get_user_likes_count(target_uid)
    already_liked = await has_liked(viewer_uid, target_uid)

    # VIP/Premium строка
    vip = user["vip_type"]
    vip_line = ""
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
        vip_line = f"{emoji} {vip.upper()} ({bonus_str}) — {exp_str}\n"

    text = (
        f"<b>👤 Профиль игрока</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"{id_line}"
        f"🪪 Ранг: {rank_name}\n"
        f"{vip_line}\n"
        f"💢 Баланс: <b>{fnum(user['clicks'])}</b>\n"
        f"⚡ Клик: +{fnum(display_power)}\n"
        f"📈 Доход: {fnum(user['passive_income'] or 0)}/ч\n"
        f"🎨 НФТ: {nft_count}/{max_slots}\n"
        f"🔗 Рефералов: {user['referrals']}\n"
        f"❤️ Лайков: {likes}\n"
        f"⚠️ Жалоб: {complaints}\n\n"
        f"━━━━━━━━━━━━━━━━━━━"
    )

    kb_rows = []
    # Лайк / Анлайк (нельзя себя)
    if viewer_uid != target_uid:
        if already_liked:
            kb_rows.append([InlineKeyboardButton(
                text="💔 Убрать лайк",
                callback_data=f"rate_unlike_{target_uid}",
            )])
        else:
            kb_rows.append([InlineKeyboardButton(
                text="❤️ Поставить лайк",
                callback_data=f"rate_like_{target_uid}",
            )])
    # НФТ
    kb_rows.append([InlineKeyboardButton(
        text=f"🎨 Посмотреть НФТ ({nft_count})",
        callback_data=f"rating_nfts_{target_uid}",
    )])
    kb_rows.append([InlineKeyboardButton(text="⬅️ К рейтингу", callback_data="top_15")])

    await send_msg(call, text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))


@router.callback_query(F.data.startswith("rate_like_"))
async def rate_like(call: CallbackQuery):
    target_uid = int(call.data.replace("rate_like_", ""))
    viewer_uid = call.from_user.id
    if viewer_uid == target_uid:
        return await call.answer("❌ Нельзя лайкнуть себя", show_alert=True)
    ok = await add_like(viewer_uid, target_uid)
    if ok:
        await call.answer("❤️ Лайк поставлен!", show_alert=True)
    else:
        await call.answer("❤️ Вы уже лайкнули этого игрока", show_alert=True)
    # Обновляем профиль
    call.data = f"view_profile_{target_uid}"
    await view_player_profile(call)


@router.callback_query(F.data.startswith("rate_unlike_"))
async def rate_unlike(call: CallbackQuery):
    target_uid = int(call.data.replace("rate_unlike_", ""))
    viewer_uid = call.from_user.id
    if viewer_uid == target_uid:
        return await call.answer("❌", show_alert=True)
    ok = await remove_like(viewer_uid, target_uid)
    if ok:
        await call.answer("💔 Лайк убран!", show_alert=True)
    else:
        await call.answer("❌ Лайк не стоял", show_alert=True)
    call.data = f"view_profile_{target_uid}"
    await view_player_profile(call)


@router.callback_query(F.data.startswith("rating_nfts_"))
async def view_rating_nfts(call: CallbackQuery):
    """Показать топ-5 НФТ игрока из рейтинга."""
    target_uid = int(call.data.replace("rating_nfts_", ""))
    viewer_uid = call.from_user.id
    user = await get_user(target_uid)
    if not user:
        return await call.answer("❌ Игрок не найден", show_alert=True)

    viewer_is_staff = (viewer_uid == OWNER_ID) or await is_admin(viewer_uid)
    hide_nft = await get_user_hide_nft(target_uid)

    # Если НФТ скрыты и просматривающий не стафф — не показываем
    if hide_nft and not viewer_is_staff:
        return await call.answer("🎨 Игрок скрыл свои НФТ", show_alert=True)

    is_anon = await get_user_anonymous(target_uid)
    name = "🕶 Аноним" if is_anon else (f"@{user['username']}" if user['username'] else "Аноним")

    nfts = await get_user_top_nfts(target_uid, limit=5)
    lines = [f"<b>🎨 НФТ игрока {name}</b>\n━━━━━━━━━━━━━━━━━━━\n"]
    if nfts:
        for n in nfts:
            rarity_name = n[4] if len(n) > 4 else "Обычный"
            emoji = NFT_RARITY_EMOJI.get(rarity_name, "🟢")
            lines.append(f"{emoji} {n[1]} — {fnum(n[2])}/ч ({rarity_name})")
    else:
        lines.append("Нет НФТ.")
    lines.append("\n━━━━━━━━━━━━━━━━━━━")

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Профиль", callback_data=f"view_profile_{target_uid}")],
        [InlineKeyboardButton(text="⬅️ К рейтингу", callback_data="top_15")],
    ])
    await send_msg(call, "\n".join(lines), reply_markup=kb)


@router.callback_query(F.data == "toggle_anon")
async def toggle_anon(call: CallbackQuery):
    uid = call.from_user.id
    current = await get_user_anonymous(uid)
    new_val = not current
    await set_user_anonymous(uid, new_val)
    status = "включена 🟢" if new_val else "выключена 🔴"
    await call.answer(f"🕶 Анонимность {status}", show_alert=True)
    # Обновляем
    await show_top15(call)


@router.callback_query(F.data == "toggle_hide_nft")
async def toggle_hide_nft(call: CallbackQuery):
    uid = call.from_user.id
    current = await get_user_hide_nft(uid)
    new_val = not current
    await set_user_hide_nft(uid, new_val)
    status = "скрыты 🟢" if new_val else "видны 🔴"
    await call.answer(f"🎨 НФТ в рейтинге: {status}", show_alert=True)
    await show_top15(call)

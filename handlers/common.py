# ======================================================
# COMMON — /start, главное меню, профиль
# ======================================================

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from config import (
    VERSION, RANKS_LIST, RANK_THRESHOLDS, BASE_CLICK_POWER, MAX_NFT,
    REFERRAL_BOT_USERNAME, PRIZE_CHANNEL_ID, PRIZE_CHANNEL_LINK,
    PRIZE_CHANNEL_NAME, PRIZE_CLICKS, PRIZE_POWER,
)
from database import (
    create_user, get_user, count_users, is_user_banned,
    add_referral, update_rank, claim_passive_income,
    count_user_nfts, get_user_nfts,
    get_prize_claim, set_prize_claim, deactivate_prize,
    update_clicks, update_bonus_click,
)
from keyboards import start_kb, main_menu_kb, income_kb

router = Router()


# ─── Утилиты ───
def fnum(n) -> str:
    """Форматирует число с разделителями тысяч (точка).
    200 → '200',  1000 → '1.000',  1234567 → '1.234.567',
    0.5 → '0.5',  1.25 → '1.25'.
    """
    if n is None:
        return "0"
    val = float(n)
    if val == 0:
        return "0"
    # Мелкие значения < 1 (сила клика и т.д.) — до 2 знаков
    if abs(val) < 1:
        s = f"{val:.2f}"
        return s.rstrip('0').rstrip('.')
    # Дробная часть есть — показываем до 2 знаков + разделители
    int_part = int(val)
    frac = val - int_part
    formatted_int = f"{int_part:,}".replace(",", ".")
    if frac > 0:
        frac_str = f"{frac:.2f}"[1:]  # ".25"
        frac_str = frac_str.rstrip('0').rstrip('.')
        if frac_str:
            return formatted_int + frac_str
    return formatted_int


def _progress_bar(current: int, target: int) -> tuple[str, int]:
    """Возвращает (строку прогресс‑бара, процент)."""
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

    # Прогресс до следующего ранга
    current_clicks = user["total_clicks"] or 0
    cur_thresh = RANK_THRESHOLDS[min(rank_id - 1, len(RANK_THRESHOLDS) - 1)]
    nxt_thresh = RANK_THRESHOLDS[min(rank_id, len(RANK_THRESHOLDS) - 1)]
    if rank_id >= len(RANK_THRESHOLDS):
        nxt_thresh = cur_thresh  # макс ранг

    bar, pct = _progress_bar(current_clicks - cur_thresh, nxt_thresh - cur_thresh)

    # Имя пользователя и ID
    uname = user["username"]
    uid = user["user_id"]
    name_line = f"@{uname}" if uname else "Аноним"
    name_line += f"  (ID: {uid})"

    # Кол-во НФТ (точное)
    nft_count = await count_user_nfts(uid)

    # Накопленный доход прямо сейчас
    from datetime import datetime as _dt
    total_income = float(user["passive_income"] or 0)
    try:
        capacity = float(user["income_capacity"]) if user["income_capacity"] else 150.0
    except (KeyError, IndexError):
        capacity = 150.0
    try:
        last_claim = user["last_income_claim"]
    except (KeyError, IndexError):
        last_claim = None
    if last_claim and total_income > 0:
        try:
            last_dt = _dt.fromisoformat(last_claim)
            diff = (_dt.now() - last_dt).total_seconds()
            hours = min(diff / 3600.0, 1.0)
            accumulated = min(total_income * hours, capacity)
        except (ValueError, TypeError):
            accumulated = 0.0
    else:
        accumulated = 0.0

    return (
        f"📃 КликТохн [ ГЛАВНОЕ МЕНЮ ]\n"
        f"══════════════════════\n\n"
        f"📌 ПРОФИЛЬ: {name_line}\n"
        f"🪪 Ранг: {rank_name}\n"
        f"💢 Баланс: {fnum(user['clicks'])} Тохн\n"
        f"⚡ Сила клика: +{fnum(click_power)} Тохн\n\n"
        f"📈 Доход: {fnum(total_income)} Тохн/час\n"
        f"📦 Ёмкость: {fnum(accumulated)} / {fnum(capacity)} мест Тохн\n"
        f"🎨 Доступно НФТ: {nft_count} / {MAX_NFT}\n\n"
        f"🪫 ПРОГРЕСС:\n"
        f"{bar}\n"
        f"Кликов: {fnum(current_clicks)} / {fnum(nxt_thresh)}\n\n"
        f"🔗 РЕФЕРАЛЫ: {user['referrals']} человек\n\n"
        f"══════════════════════\n"
        f"ВЫБЕРИТЕ ДЕЙСТВИЕ НИЖЕ:"
    )


# ─── /start ───
@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    username = message.from_user.username or "Аноним"

    if await is_user_banned(user_id):
        return await message.answer("❌ Вы заблокированы.")

    await state.clear()

    existing = await get_user(user_id)
    is_new = existing is None
    await create_user(user_id, username)

    # Реферальная ссылка
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
    user = await get_user(user_id)
    rank_name = RANKS_LIST.get(user["rank"] or 1, "🍼 Новичок")

    text = (
        f"💢 ДОБРО ПОЖАЛОВАТЬ В КликТохн!\n"
        f"══════════════════════\n"
        f"Версия: {VERSION}\n"
        f"══════════════════════\n"
        f"📊 Статистика:\n"
        f"👥 Игроков в системе: {total}\n"
        f"🏆 Ваш ранг: {rank_name}\n"
        f"💢 Сила клика: +{fnum(BASE_CLICK_POWER + user['bonus_click'])} Тохн\n"
        f"══════════════════════\n"
        f"НАЖМИТЕ \"НАЧАТЬ\" ДЛЯ ВХОДА"
    )

    await message.answer(text, reply_markup=start_kb())


# ─── Кнопка «Начать» → главное меню ───
@router.callback_query(F.data == "open_menu")
async def open_menu(call: CallbackQuery, state: FSMContext):
    await state.clear()
    user = await get_user(call.from_user.id)
    if not user:
        return await call.answer("❌ Используйте /start", show_alert=True)

    total = await count_users()
    await call.message.edit_text(
        await _profile_text(user, total),
        reply_markup=main_menu_kb(),
    )
    await call.answer()


# ─── 💵 Взять доход — информационный экран ───
@router.callback_query(F.data == "claim_income")
async def claim_income(call: CallbackQuery):
    uid = call.from_user.id
    user = await get_user(uid)
    if not user:
        return await call.answer("❌ Используйте /start", show_alert=True)

    income_rate = float(user["passive_income"] or 0)
    capacity = float(user["income_capacity"]) if user["income_capacity"] else 150.0

    if income_rate <= 0:
        nft_count = await count_user_nfts(uid)
        text = (
            "💵 ПАССИВНЫЙ ДОХОД\n"
            "══════════════════════\n\n"
            "📈 У вас пока нет пассивного дохода.\n\n"
            "Чтобы получать Тохн/час:\n"
            "  • Купите улучшения 📈 в Магазине\n"
            "  • Или приобретите НФТ 🎨\n\n"
            f"🎨 Доступно НФТ: {nft_count} / {MAX_NFT}\n\n"
            "══════════════════════"
        )
        await call.message.edit_text(text, reply_markup=income_kb())
        return await call.answer()

    # Подсчёт накопленного (без списания)
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
        hours = min(diff / 3600.0, 1.0)  # макс 1 час
        accumulated = min(income_rate * hours, capacity)
        h = int(hours)
        m = int((hours - h) * 60)
        time_str = f"{h}ч {m}м" if h > 0 else (f"{m}м" if m > 0 else "<1м")

    fill_pct = min(int(accumulated / capacity * 100), 100) if capacity > 0 else 0
    filled = fill_pct // 10
    bar = "█" * filled + "░" * (10 - filled)

    nft_count = await count_user_nfts(uid)

    text = (
        "💵 ПАССИВНЫЙ ДОХОД\n"
        "══════════════════════\n\n"
        f"📈 Скорость: {fnum(income_rate)} Тохн/час\n"
        f"📦 Ёмкость: {fnum(accumulated)}/{fnum(capacity)} Тохн\n"
        f"[{bar}] {fill_pct}%\n\n"
        f"🎨 Доступно НФТ: {nft_count} / {MAX_NFT}\n\n"
        f"⏱ Накоплено за: {time_str}\n\n"
        "══════════════════════\n"
        "Нажмите «Взять» чтобы собрать доход."
    )
    await call.message.edit_text(text, reply_markup=income_kb())
    await call.answer()


# ─── 💰 Фактический сбор дохода ───
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

    # Первый вызов — таймер запущен
    if earned == -1.0:
        nft_count = await count_user_nfts(uid)
        text = (
            "💵 ПАССИВНЫЙ ДОХОД\n"
            "══════════════════════\n\n"
            f"📈 Скорость: {fnum(income_rate)} Тохн/час\n"
            f"📦 Ёмкость: 0/{fnum(capacity)} Тохн\n"
            f"🎨 Доступно НФТ: {nft_count} / {MAX_NFT}\n\n"
            "✅ Таймер дохода запущен!\n"
            "Возвращайтесь через некоторое время.\n\n"
            "══════════════════════"
        )
        await call.message.edit_text(text, reply_markup=income_kb())
        return await call.answer("✅ Таймер запущен!", show_alert=False)

    # Слишком рано
    if earned <= 0:
        remaining = int(hours)
        return await call.answer(f"⏳ Подождите ещё {remaining} сек.", show_alert=True)

    # Успешный сбор
    user = await get_user(uid)
    new_balance = float(user["clicks"]) if user else 0
    nft_count = await count_user_nfts(uid)

    h = int(hours)
    m = int((hours - h) * 60)
    time_str = f"{h}ч {m}м" if h > 0 else (f"{m}м" if m > 0 else "<1м")

    text = (
        "💵 ДОХОД СОБРАН!\n"
        "══════════════════════\n\n"
        f"💰 Начислено: +{fnum(earned)} Тохн\n"
        f"📈 Скорость: {fnum(income_rate)} Тохн/час\n"
        f"📦 Ёмкость: 0/{fnum(capacity)} Тохн\n"
        f"🎨 Доступно НФТ: {nft_count} / {MAX_NFT}\n\n"
        f"⏱ Накоплено за: {time_str}\n\n"
        f"💢 Новый баланс: {fnum(new_balance)} Тохн\n\n"
        "══════════════════════\n"
        "Возвращайтесь позже за новым доходом!"
    )
    await call.message.edit_text(text, reply_markup=income_kb())
    await call.answer(f"+{fnum(earned)} Тохн", show_alert=False)


# ─── Возврат в меню ───
@router.callback_query(F.data == "menu")
async def back_to_menu(call: CallbackQuery, state: FSMContext):
    await state.clear()
    user = await get_user(call.from_user.id)
    if not user:
        return await call.answer("❌ Используйте /start", show_alert=True)

    total = await count_users()
    await call.message.edit_text(
        await _profile_text(user, total),
        reply_markup=main_menu_kb(),
    )
    await call.answer()


# ─── Переключение страниц главного меню ───
@router.callback_query(F.data.startswith("menu_page:"))
async def menu_page(call: CallbackQuery, state: FSMContext):
    await state.clear()
    user = await get_user(call.from_user.id)
    if not user:
        return await call.answer("❌ Используйте /start", show_alert=True)

    page = int(call.data.split(":")[1])
    total = await count_users()
    try:
        await call.message.edit_text(
            await _profile_text(user, total),
            reply_markup=main_menu_kb(page),
        )
    except Exception:
        pass
    await call.answer()


# ─── Заглушка для пустых кнопок ───
@router.callback_query(F.data == "noop")
async def noop_callback(call: CallbackQuery):
    await call.answer()


# ═══════════════════════════════════════════════════════
#  🎁 ПРИЗ — подписка на канал
# ═══════════════════════════════════════════════════════
@router.callback_query(F.data == "prize_menu")
async def prize_menu(call: CallbackQuery):
    """Главное окно «Приз» — проверка подписки и выдача награды."""
    uid = call.from_user.id
    user = await get_user(uid)
    if not user:
        return await call.answer("❌ /start", show_alert=True)

    # Проверяем подписку на канал
    subscribed = False
    try:
        member = await call.bot.get_chat_member(PRIZE_CHANNEL_ID, uid)
        subscribed = member.status in ("member", "administrator", "creator")
    except Exception:
        subscribed = False

    claim = await get_prize_claim(uid)

    if not subscribed:
        # ─── Не подписан ───
        if claim and claim[3] == 1:
            # Был подписан, отписался → снимаем клик-силу
            await deactivate_prize(uid)
            await update_bonus_click(uid, -PRIZE_POWER)
            text = (
                "🎁 ПРИЗ\n"
                "══════════════════════\n\n"
                "⚠️ Вы отписались от канала!\n"
                f"❌ Клик-сила снижена на -{fnum(PRIZE_POWER)}\n"
                f"💰 Баланс сохранён.\n\n"
                "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
                f"📢 Подпишитесь снова на канал\n"
                f"«{PRIZE_CHANNEL_NAME}» чтобы вернуть\n"
                f"+{fnum(PRIZE_POWER)} к клик-силе!\n\n"
                "══════════════════════"
            )
        else:
            # Никогда не подписывался
            text = (
                "🎁 ПРИЗ\n"
                "══════════════════════\n\n"
                f"📢 Подпишитесь на канал\n"
                f"«{PRIZE_CHANNEL_NAME}» и получите:\n\n"
                f"  💢 +{fnum(PRIZE_CLICKS)} тохн\n"
                f"  ⚡ +{fnum(PRIZE_POWER)} клик-сила\n\n"
                "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
                "1️⃣ Подпишитесь на канал ниже\n"
                "2️⃣ Вернитесь и нажмите «Проверить»\n\n"
                "══════════════════════"
            )

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📢 Подписаться", url=PRIZE_CHANNEL_LINK)],
            [InlineKeyboardButton(text="✅ Проверить подписку", callback_data="prize_check")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="ref_menu")],
        ])
        try:
            await call.message.edit_text(text, reply_markup=kb)
        except Exception:
            await call.message.answer(text, reply_markup=kb)
        return await call.answer()

    # ─── Подписан ───
    if not claim:
        # Первый раз: дать баланс + клик-силу
        await update_clicks(uid, PRIZE_CLICKS)
        await update_bonus_click(uid, PRIZE_POWER)
        await set_prize_claim(uid)
        text = (
            "🎁 ПРИЗ ПОЛУЧЕН!\n"
            "══════════════════════\n\n"
            "🎉 Вы подписались на канал!\n\n"
            f"  💢 +{fnum(PRIZE_CLICKS)} тохн\n"
            f"  ⚡ +{fnum(PRIZE_POWER)} клик-сила\n\n"
            "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            "⚠️ Если отпишетесь — потеряете\n"
            f"клик-силу ({fnum(PRIZE_POWER)}), но баланс\n"
            "останется.\n\n"
            "══════════════════════"
        )
    elif claim[3] == 0:
        # Повторная подписка: только клик-сила
        await update_bonus_click(uid, PRIZE_POWER)
        await set_prize_claim(uid)
        text = (
            "🎁 С ВОЗВРАЩЕНИЕМ!\n"
            "══════════════════════\n\n"
            "🔄 Вы снова подписались!\n\n"
            f"  ⚡ +{fnum(PRIZE_POWER)} клик-сила возвращена\n"
            f"  💢 Баланс не начисляется повторно\n\n"
            "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            "Спасибо, что остаётесь с нами! ❤️\n\n"
            "══════════════════════"
        )
    else:
        # Уже подписан и приз активен
        text = (
            "🎁 ПРИЗ\n"
            "══════════════════════\n\n"
            "✅ Вы подписаны на канал!\n"
            f"⚡ Бонус +{fnum(PRIZE_POWER)} клик-сила активен\n\n"
            "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            "⚠️ Не отписывайтесь, иначе\n"
            "потеряете клик-силу!\n\n"
            "══════════════════════"
        )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Канал", url=PRIZE_CHANNEL_LINK)],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="ref_menu")],
    ])
    try:
        await call.message.edit_text(text, reply_markup=kb)
    except Exception:
        await call.message.answer(text, reply_markup=kb)
    await call.answer()


@router.callback_query(F.data == "prize_check")
async def prize_check(call: CallbackQuery):
    """Проверка подписки после нажатия кнопки."""
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
        return await call.answer("❌ Вы ещё не подписались на канал!", show_alert=True)

    # Подписан — логика та же, что в prize_menu
    claim = await get_prize_claim(uid)

    if not claim:
        await update_clicks(uid, PRIZE_CLICKS)
        await update_bonus_click(uid, PRIZE_POWER)
        await set_prize_claim(uid)
        await call.answer(f"🎉 +{fnum(PRIZE_CLICKS)} 💢 и +{fnum(PRIZE_POWER)} клик-сила!", show_alert=True)
    elif claim[3] == 0:
        await update_bonus_click(uid, PRIZE_POWER)
        await set_prize_claim(uid)
        await call.answer(f"🔄 +{fnum(PRIZE_POWER)} клик-сила возвращена!", show_alert=True)
    else:
        await call.answer("✅ Приз уже активен!", show_alert=True)

    # Обновляем экран
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Канал", url=PRIZE_CHANNEL_LINK)],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="ref_menu")],
    ])
    text = (
        "🎁 ПРИЗ\n"
        "══════════════════════\n\n"
        "✅ Вы подписаны на канал!\n"
        f"⚡ Бонус +{fnum(PRIZE_POWER)} клик-сила активен\n\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        "⚠️ Не отписывайтесь, иначе\n"
        "потеряете клик-силу!\n\n"
        "══════════════════════"
    )
    try:
        await call.message.edit_text(text, reply_markup=kb)
    except Exception:
        pass

# ======================================================
# SHOP — Магазин (требует 10 кликов)
# ======================================================
from aiogram import Router, F
from aiogram.types import (
    CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton,
)
from aiogram.fsm.context import FSMContext

from config import (
    SHOP_CLICK, SHOP_PASSIVE, SHOP_CAPACITY, SHOP_NFT_SLOT,
    SHOP_OPEN_CLICKS, CLICK_PACKAGES, VIP_PACKAGES,
    OWNER_ID, SBER_CARD, BASE_CLICK_POWER,
)
from states import PaymentStates
from database import (
    get_user, update_clicks, update_bonus_click,
    update_passive_income, update_income_capacity,
    add_nft_slot, get_user_nft_slots, count_user_nfts, create_transaction,
    log_activity, set_user_online,
    create_payment_order, get_user_orders,
    get_vip_multipliers,
    resolve_payment_order, set_user_vip,
    update_order_screenshot, is_payment_banned,
    get_setting,
)
from keyboards import (
    shop_menu_kb, shop_upg_kb, shop_pas_kb, shop_cap_kb,
    shop_nft_slot_kb, payment_menu_kb, back_menu_kb,
    pay_clicks_packages_kb, pay_vip_packages_kb,
    pay_order_pending_kb,
)
from handlers.common import fnum
from banners_util import send_msg, safe_edit

router = Router()


@router.callback_query(F.data == "shop_menu")
async def show_shop(call: CallbackQuery):
    user = await get_user(call.from_user.id)
    if not user:
        return await call.answer("❌ /start", show_alert=True)
    await set_user_online(call.from_user.id)

    if (user["total_clicks"] or 0) < SHOP_OPEN_CLICKS:
        return await call.answer(
            f"🔒 Нужно {SHOP_OPEN_CLICKS} кликов чтобы открыть магазин!",
            show_alert=True,
        )

    text = (
        "<b>💸 Магазин КликТохн</b>\n"
        "━━━━━━━━━━━━━━━━━━━\n\n"
        "🔨 <b>Клик</b> — усиль клик\n"
        "📈 <b>Доход</b> — пассивный заработок\n"
        "📦 <b>Ёмкость</b> — больше накоплений\n"
        "🔓 <b>Слоты</b> — доп. места для НФТ\n"
        "🏠 <b>Площадка</b> — купля/продажа\n"
        "💳 <b>Оплата</b> — Сбербанк\n\n"
        "━━━━━━━━━━━━━━━━━━━"
    )
    await send_msg(call, text, reply_markup=shop_menu_kb())


# ── Улучшение клика ──
@router.callback_query(F.data == "shop_upg")
async def shop_upg(call: CallbackQuery):
    user = await get_user(call.from_user.id)
    clicks = float(user["clicks"]) if user else 0
    power = BASE_CLICK_POWER + float(user["bonus_click"] or 0) if user else BASE_CLICK_POWER
    mc, _ = await get_vip_multipliers(call.from_user.id)
    text = (
        f"<b>🔨 Улучшение клика</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"💢 Баланс: <b>{fnum(clicks)}</b> Тохн\n"
        f"⚡ Текущий клик: <b>+{fnum(power * mc)}</b>\n\n"
        f"Выберите улучшение:"
    )
    await send_msg(call, text, reply_markup=shop_upg_kb(clicks))


@router.callback_query(F.data.startswith("buy_c_"))
async def buy_click_upgrade(call: CallbackQuery):
    key = call.data.replace("buy_c_", "")
    if key not in SHOP_CLICK:
        return await call.answer("❌ Не найдено", show_alert=True)
    bonus, price = SHOP_CLICK[key]
    user = await get_user(call.from_user.id)
    if float(user["clicks"]) < price:
        return await call.answer("❌ Недостаточно 💢", show_alert=True)
    await update_clicks(call.from_user.id, -price)
    await update_bonus_click(call.from_user.id, bonus)
    await create_transaction("shop", call.from_user.id, amount=price,
                             details=f"Улучшение клика +{bonus}")
    await log_activity(call.from_user.id, "shop", f"Купил улучшение клика +{bonus} за {price}")
    await call.answer(f"✅ +{bonus} к силе клика!", show_alert=True)
    # Обновить список с новым балансом
    await shop_upg(call)


# ── Пассивный доход ──
@router.callback_query(F.data == "shop_pas")
async def shop_pas(call: CallbackQuery):
    user = await get_user(call.from_user.id)
    clicks = float(user["clicks"]) if user else 0
    income = float(user["passive_income"] or 0) if user else 0
    _, mi = await get_vip_multipliers(call.from_user.id)
    text = (
        f"<b>📈 Пассивный доход</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"💢 Баланс: <b>{fnum(clicks)}</b> Тохн\n"
        f"📈 Текущий доход: <b>{fnum(income * mi)}</b>/ч\n\n"
        f"Выберите улучшение:"
    )
    await send_msg(call, text, reply_markup=shop_pas_kb(clicks))


@router.callback_query(F.data.startswith("buy_p_"))
async def buy_passive_upgrade(call: CallbackQuery):
    key = call.data.replace("buy_p_", "")
    if key not in SHOP_PASSIVE:
        return await call.answer("❌ Не найдено", show_alert=True)
    bonus, price = SHOP_PASSIVE[key]
    user = await get_user(call.from_user.id)
    if float(user["clicks"]) < price:
        return await call.answer("❌ Недостаточно 💢", show_alert=True)
    await update_clicks(call.from_user.id, -price)
    await update_passive_income(call.from_user.id, bonus)
    await create_transaction("shop", call.from_user.id, amount=price,
                             details=f"Пассивный доход +{bonus}/ч")
    await log_activity(call.from_user.id, "shop", f"Купил пассив +{bonus}/ч за {price}")
    await call.answer(f"✅ +{bonus} Тохн/час!", show_alert=True)
    # Обновить список с новым балансом
    await shop_pas(call)


# ── Ёмкость дохода ──
@router.callback_query(F.data == "shop_cap")
async def shop_cap(call: CallbackQuery):
    user = await get_user(call.from_user.id)
    clicks = float(user["clicks"]) if user else 0
    capacity = float(user["income_capacity"] or 150) if user else 150
    text = (
        f"<b>📦 Ёмкость дохода</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"💢 Баланс: <b>{fnum(clicks)}</b> Тохн\n"
        f"📦 Текущая ёмкость: <b>{fnum(capacity)}</b>\n\n"
        f"Выберите улучшение:"
    )
    await send_msg(call, text, reply_markup=shop_cap_kb(clicks))


@router.callback_query(F.data.startswith("buy_cap_"))
async def buy_cap_upgrade(call: CallbackQuery):
    key = call.data.replace("buy_cap_", "")
    if key not in SHOP_CAPACITY:
        return await call.answer("❌ Не найдено", show_alert=True)
    bonus, price = SHOP_CAPACITY[key]
    user = await get_user(call.from_user.id)
    if float(user["clicks"]) < price:
        return await call.answer("❌ Недостаточно 💢", show_alert=True)
    await update_clicks(call.from_user.id, -price)
    await update_income_capacity(call.from_user.id, bonus)
    await create_transaction("shop", call.from_user.id, amount=price,
                             details=f"Ёмкость +{bonus}")
    await log_activity(call.from_user.id, "shop", f"Купил ёмкость +{bonus} за {price}")
    await call.answer(f"✅ +{bonus} к ёмкости!", show_alert=True)
    # Обновить список с новым балансом
    await shop_cap(call)


# ── Освобождение мест НФТ ──
@router.callback_query(F.data == "shop_nft_slot")
async def shop_nft_slot(call: CallbackQuery):
    uid = call.from_user.id
    user = await get_user(uid)
    clicks = float(user["clicks"]) if user else 0
    slots = await get_user_nft_slots(uid)
    nft_count = await count_user_nfts(uid)
    text = (
        "<b>🔓 Слоты НФТ</b>\n"
        "━━━━━━━━━━━━━━━━━━━\n\n"
        f"💢 Баланс: <b>{fnum(clicks)}</b> Тохн\n"
        f"📦 Слотов: <b>{nft_count}/{slots}</b>\n\n"
        "Выберите покупку:"
    )
    await send_msg(call, text, reply_markup=shop_nft_slot_kb(clicks))


@router.callback_query(F.data.startswith("buy_slot_"))
async def buy_nft_slot(call: CallbackQuery):
    key = call.data.replace("buy_slot_", "")
    if key not in SHOP_NFT_SLOT:
        return await call.answer("❌ Не найдено", show_alert=True)
    bonus, price = SHOP_NFT_SLOT[key]
    user = await get_user(call.from_user.id)
    if float(user["clicks"]) < price:
        return await call.answer("❌ Недостаточно 💢", show_alert=True)
    await update_clicks(call.from_user.id, -price)
    await add_nft_slot(call.from_user.id, bonus)
    await create_transaction("shop", call.from_user.id, amount=price,
                             details=f"Слот НФТ +{bonus}")
    await log_activity(call.from_user.id, "shop", f"Купил слот НФТ +{bonus} за {price}")
    await call.answer(f"✅ +{bonus} слот НФТ!", show_alert=True)
    await shop_nft_slot(call)


# ══════════════════════════════════════════
#  ОПЛАТА (Сбербанк — скриншот)
# ══════════════════════════════════════════
@router.callback_query(F.data == "payment_menu")
async def payment_menu(call: CallbackQuery, state: FSMContext):
    await state.clear()
    uid = call.from_user.id

    # Проверка бана оплаты
    if await is_payment_banned(uid):
        return await call.answer(
            "🚫 Доступ к оплате заблокирован.", show_alert=True
        )

    mc, mi = await get_vip_multipliers(uid)
    user = await get_user(uid)
    vip = user["vip_type"] if user else None
    vip_line = ""
    if vip:
        exp = user["vip_expires"]
        if exp == "permanent":
            exp_str = "навсегда"
        elif exp:
            exp_str = exp[:10]
        else:
            exp_str = "—"
        vip_line = (
            f"\n⭐ Ваш статус: {vip.upper()}\n"
            f"   ×{mc:.0f} клик, ×{mi:.0f} доход\n"
            f"   До: {exp_str}\n"
        )

    text = (
        "<b>💳 Магазин оплаты</b>\n"
        "━━━━━━━━━━━━━━━━━━━\n\n"
        "Приобретайте Тохн или VIP/Premium\n"
        "за рубли — переводом на Сбербанк 🟢\n"
        f"{vip_line}\n"
        "━━━━━━━━━━━━━━━━━━━"
    )
    await send_msg(call, text, reply_markup=payment_menu_kb())


# ── Пакеты Тохн ──
@router.callback_query(F.data == "pay_clicks_menu")
async def pay_clicks_menu(call: CallbackQuery):
    if await is_payment_banned(call.from_user.id):
        return await call.answer("🚫 Доступ к оплате заблокирован.", show_alert=True)
    text = (
        "<b>💢 Пакеты Тохн</b>\n"
        "━━━━━━━━━━━━━━━━━━━\n\n"
        "Выберите пакет для покупки:"
    )
    await safe_edit(call.message, text, reply_markup=pay_clicks_packages_kb())
    await call.answer()


async def _get_pay_card() -> str:
    """Получить актуальные реквизиты из настроек или из config."""
    card = await get_setting("sber_card", "")
    return card or SBER_CARD


async def _get_pay_info() -> tuple:
    """Возвращает (card, fio, method)."""
    card = await _get_pay_card()
    fio = await get_setting("pay_fio", "")
    method = await get_setting("pay_method", "СБП")
    return card, fio, method


async def _build_order_text(order_id, label, price_rub, extra="") -> str:
    card, fio, method = await _get_pay_info()
    lines = [
        f"<b>📋 Заказ #{order_id}</b>",
        "━━━━━━━━━━━━━━━━━━━\n",
        f"📦 Пакет: <b>{label}</b>",
    ]
    if extra:
        lines.append(extra)
    lines.append(f"💰 Сумма: <b>{price_rub}₽</b>\n")
    lines.append(f"🏦 Способ: <b>{method}</b>")
    lines.append(f"💳 Реквизиты:\n<code>{card}</code>")
    if fio:
        lines.append(f"👤 Получатель: <b>{fio}</b>")
    lines.append("\n━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)


@router.callback_query(F.data.startswith("buy_pkg:"))
async def buy_pkg_select(call: CallbackQuery, state: FSMContext):
    if await is_payment_banned(call.from_user.id):
        return await call.answer("🚫 Доступ к оплате заблокирован.", show_alert=True)
    pkg_id = call.data.split(":")[1]
    if pkg_id not in CLICK_PACKAGES:
        return await call.answer("❌", show_alert=True)
    clicks, price_rub, label = CLICK_PACKAGES[pkg_id]

    card = await _get_pay_card()
    if not card:
        return await call.answer("⚠️ Реквизиты не настроены. Обратитесь к владельцу.", show_alert=True)

    # Проверка: оплата закрыта?
    if await get_setting("payment_closed", "false") in ("true", "1"):
        return await call.answer("🚫 Оплата временно закрыта.", show_alert=True)

    order_id = await create_payment_order(call.from_user.id, "clicks", pkg_id, "sber", price_rub)
    await state.update_data(order_id=order_id, pkg_type="clicks", pkg_id=pkg_id, amount=price_rub)

    order_text = await _build_order_text(order_id, label, price_rub)
    text = (
        f"{order_text}\n\n"
        "📝 <b>Шаг 1 из 2</b>\n"
        "Введите ваше <b>Имя Фамилия</b>\n"
        "(как в переводе) ⬇️"
    )
    await state.set_state(PaymentStates.waiting_fio)
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отменить заказ", callback_data=f"cancel_order:{order_id}")],
    ]))
    await call.answer()


# ── VIP/Premium ──
@router.callback_query(F.data == "pay_vip_menu")
async def pay_vip_menu(call: CallbackQuery):
    if await is_payment_banned(call.from_user.id):
        return await call.answer("🚫 Доступ к оплате заблокирован.", show_alert=True)
    text = (
        "<b>⭐ VIP / Premium</b>\n"
        "━━━━━━━━━━━━━━━━━━━\n\n"
        "▸ <b>VIP</b> — ×2 к силе клика\n"
        "▸ <b>Premium</b> — ×3 к клику И доходу\n\n"
        "Выберите пакет:"
    )
    await safe_edit(call.message, text, reply_markup=pay_vip_packages_kb())
    await call.answer()


@router.callback_query(F.data.startswith("buy_vip:"))
async def buy_vip_select(call: CallbackQuery, state: FSMContext):
    if await is_payment_banned(call.from_user.id):
        return await call.answer("🚫 Доступ к оплате заблокирован.", show_alert=True)
    pkg_id = call.data.split(":")[1]
    if pkg_id not in VIP_PACKAGES:
        return await call.answer("❌", show_alert=True)
    mc, mi, dur, price_rub, label = VIP_PACKAGES[pkg_id]

    card = await _get_pay_card()
    if not card:
        return await call.answer("⚠️ Реквизиты не настроены. Обратитесь к владельцу.", show_alert=True)

    if await get_setting("payment_closed", "false") in ("true", "1"):
        return await call.answer("🚫 Оплата временно закрыта.", show_alert=True)

    order_id = await create_payment_order(call.from_user.id, "vip", pkg_id, "sber", price_rub)
    dur_text = f"{dur} дней" if dur > 0 else "навсегда"
    await state.update_data(order_id=order_id, pkg_type="vip", pkg_id=pkg_id, amount=price_rub)

    order_text = await _build_order_text(order_id, label, price_rub, extra=f"⏱ Срок: <b>{dur_text}</b>")
    text = (
        f"{order_text}\n\n"
        "📝 <b>Шаг 1 из 2</b>\n"
        "Введите ваше <b>Имя Фамилия</b>\n"
        "(как в переводе) ⬇️"
    )
    await state.set_state(PaymentStates.waiting_fio)
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отменить заказ", callback_data=f"cancel_order:{order_id}")],
    ]))
    await call.answer()


# ── Шаг 1: Получение ФИО ──
@router.message(PaymentStates.waiting_fio)
async def receive_fio(message: Message, state: FSMContext):
    data = await state.get_data()
    order_id = data.get("order_id")
    if not order_id:
        await state.clear()
        return

    if not message.text or len(message.text.strip().split()) != 2:
        return await message.answer(
            "📝 Введите <b>Имя Фамилия</b> (2 слова, без отчества).\n"
            "Пример: <i>Иван Иванов</i>",
            parse_mode="HTML",
        )

    fio = message.text.strip()
    await state.update_data(sender_fio=fio)
    await state.set_state(PaymentStates.waiting_screenshot)

    text = (
        f"✅ <b>ФИО:</b> {fio}\n\n"
        f"📸 <b>Шаг 2 из 2</b>\n"
        f"Переведите сумму и отправьте\n"
        f"скриншот / чек оплаты ⬇️"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отменить заказ", callback_data=f"cancel_order:{order_id}")],
    ]))


# ── Шаг 2: Получение скриншота → превью ──
@router.message(PaymentStates.waiting_screenshot)
async def receive_screenshot(message: Message, state: FSMContext):
    data = await state.get_data()
    order_id = data.get("order_id")
    if not order_id:
        await state.clear()
        return

    # Принимаем фото или документ
    if not (message.photo or message.document):
        return await message.answer("📸 Отправьте скриншот оплаты (фото или файл).")

    # Сохраняем file_id в state для подтверждения
    file_id = None
    if message.photo:
        file_id = message.photo[-1].file_id
    elif message.document:
        file_id = message.document.file_id

    await state.update_data(screenshot_file_id=file_id, is_photo=bool(message.photo))
    await state.set_state(PaymentStates.confirming)

    sender_fio = data.get("sender_fio", "—")
    pkg_type = data.get('pkg_type', '?')
    pkg_id = data.get('pkg_id', '?')
    amount = data.get('amount', '?')

    if pkg_type == "clicks" and pkg_id in CLICK_PACKAGES:
        _, _, label = CLICK_PACKAGES[pkg_id]
    elif pkg_type == "vip" and pkg_id in VIP_PACKAGES:
        _, _, _, _, label = VIP_PACKAGES[pkg_id]
    else:
        label = f"{pkg_type}/{pkg_id}"

    preview = (
        f"📋 <b>Проверьте данные заказа #{order_id}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"📦 Пакет: <b>{label}</b>\n"
        f"💰 Сумма: <b>{amount}₽</b>\n"
        f"👤 ФИО: <b>{sender_fio}</b>\n"
        f"📸 Чек: прикреплён ✅\n\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"Всё верно? Нажмите <b>✅ Отправить</b>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Отправить", callback_data=f"pay_confirm:{order_id}")],
        [InlineKeyboardButton(text="✏️ Изменить ФИО", callback_data=f"pay_edit_fio:{order_id}"),
         InlineKeyboardButton(text="📸 Другой чек", callback_data=f"pay_edit_ss:{order_id}")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data=f"cancel_order:{order_id}")],
    ])
    await message.answer(preview, parse_mode="HTML", reply_markup=kb)


# ── Изменить ФИО ──
@router.callback_query(F.data.startswith("pay_edit_fio:"))
async def pay_edit_fio(call: CallbackQuery, state: FSMContext):
    order_id = int(call.data.split(":")[1])
    await state.set_state(PaymentStates.waiting_fio)
    await call.message.edit_text(
        f"📝 Заказ #{order_id}\n\nВведите новое <b>Имя Фамилия</b> ⬇️",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отменить заказ", callback_data=f"cancel_order:{order_id}")],
        ]),
    )
    await call.answer()


# ── Изменить скриншот ──
@router.callback_query(F.data.startswith("pay_edit_ss:"))
async def pay_edit_screenshot(call: CallbackQuery, state: FSMContext):
    order_id = int(call.data.split(":")[1])
    await state.set_state(PaymentStates.waiting_screenshot)
    await call.message.edit_text(
        f"📸 Заказ #{order_id}\n\nОтправьте новый скриншот / чек ⬇️",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отменить заказ", callback_data=f"cancel_order:{order_id}")],
        ]),
    )
    await call.answer()


# ── Подтверждение: отправить заказ ──
@router.callback_query(F.data.startswith("pay_confirm:"))
async def pay_confirm_send(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    order_id = int(call.data.split(":")[1])
    await state.clear()

    pkg_type = data.get('pkg_type', '?')
    pkg_id = data.get('pkg_id', '?')
    amount = data.get('amount', '?')
    sender_fio = data.get('sender_fio', '—')
    file_id = data.get('screenshot_file_id')
    is_photo = data.get('is_photo', True)

    if pkg_type == "clicks" and pkg_id in CLICK_PACKAGES:
        clicks, _, label = CLICK_PACKAGES[pkg_id]
        reward_desc = f"💢 Выдать {fnum(clicks)} Тохн"
        approve_text = f"💢 Выдать {fnum(clicks)} Тохн"
    elif pkg_type == "vip" and pkg_id in VIP_PACKAGES:
        mc, mi, dur, _, label = VIP_PACKAGES[pkg_id]
        vip_name = "VIP" if mc == 2 and mi == 1 else "Premium"
        dur_text = f"{dur} дн." if dur > 0 else "навсегда"
        reward_desc = f"⭐ {vip_name} (×{mc} клик, {dur_text})"
        approve_text = f"⭐ Выдать {vip_name}"
    else:
        reward_desc = f"{pkg_type}/{pkg_id}"
        approve_text = "✅ Одобрить"

    # Сохраняем скриншот в БД
    if file_id:
        await update_order_screenshot(order_id, file_id)

    # Пересылаем владельцу — фото + кнопки в ОДНОМ сообщении
    caption = (
        f"<b>💳 Новый платёж!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"📋 Заказ: <b>#{order_id}</b>\n"
        f"👤 {call.from_user.id} (@{call.from_user.username or 'anon'})\n"
        f"📝 ФИО отправителя: <b>{sender_fio}</b>\n"
        f"📦 {reward_desc}\n"
        f"💰 <b>{amount}₽</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"Нажмите кнопку ниже чтобы\n"
        f"выдать покупку игроку:"
    )
    action_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=approve_text, callback_data=f"order_approve:{order_id}")],
        [InlineKeyboardButton(text="❌ Отклонить", callback_data=f"order_reject:{order_id}")],
        [InlineKeyboardButton(text="💬 Написать", callback_data=f"order_msg:{order_id}"),
         InlineKeyboardButton(text="🚫 Фейк (бан)", callback_data=f"order_fake:{order_id}")],
    ])
    try:
        if file_id and is_photo:
            await call.bot.send_photo(
                OWNER_ID, file_id,
                caption=caption, reply_markup=action_kb,
            )
        elif file_id:
            await call.bot.send_document(
                OWNER_ID, file_id,
                caption=caption, reply_markup=action_kb,
            )
        else:
            await call.bot.send_message(
                OWNER_ID, caption, reply_markup=action_kb,
            )
    except Exception:
        pass

    await call.message.edit_text(
        f"✅ Заказ #{order_id} отправлен на проверку!\n\n"
        "Ожидайте подтверждения от администрации.\n"
        "Обычно это занимает до 24 часов.",
        reply_markup=pay_order_pending_kb(),
    )
    await call.answer()
    await log_activity(call.from_user.id, "payment",
                       f"Заказ #{order_id}: {pkg_type}/{pkg_id} {amount}₽ ФИО: {sender_fio}")


# ── Отмена заказа ──
@router.callback_query(F.data.startswith("cancel_order:"))
async def cancel_order(call: CallbackQuery, state: FSMContext):
    order_id = int(call.data.split(":")[1])
    await resolve_payment_order(order_id, 0, "cancelled")
    await state.clear()
    await call.message.edit_text(
        f"❌ Заказ #{order_id} отменён.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 К оплате", callback_data="payment_menu")],
            [InlineKeyboardButton(text="⬅️ Магазин", callback_data="shop_menu")],
        ]),
    )
    await call.answer()


# ── Мои заказы ──
@router.callback_query(F.data.startswith("my_orders:"))
async def my_orders(call: CallbackQuery):
    page = int(call.data.split(":")[1])
    uid = call.from_user.id
    orders = await get_user_orders(uid, page, 5)

    status_emoji = {"pending": "🟡", "approved": "✅", "rejected": "❌", "cancelled": "⚪"}

    lines = ["<b>📦 Мои заказы</b>\n━━━━━━━━━━━━━━━━━━━\n"]
    if not orders:
        lines.append("Нет заказов.")
    else:
        for o in orders:
            oid, ptype, pid, method, rub, status, dt = o
            emoji = status_emoji.get(status, "❓")
            dt_short = dt[:10] if dt else ""
            lines.append(f"{emoji} #{oid} | {rub}₽ | {status} | {dt_short}")

    kb = [[InlineKeyboardButton(text="⬅️ К оплате", callback_data="payment_menu")]]
    await call.message.edit_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await call.answer()


# ── Ответ пользователя владельцу по заказу ──
@router.callback_query(F.data.startswith("order_reply:"))
async def order_reply_start(call: CallbackQuery, state: FSMContext):
    order_id = int(call.data.split(":")[1])
    await state.set_state(PaymentStates.reply_to_owner)
    await state.update_data(reply_order_id=order_id)
    await call.message.answer(
        f"💬 Введите ваш ответ по заказу #{order_id}:\n\n"
        f"Отправьте текст или /cancel для отмены.",
    )
    await call.answer()


@router.message(PaymentStates.reply_to_owner)
async def order_reply_send(message: Message, state: FSMContext):
    if message.text and message.text.strip() == "/cancel":
        await state.clear()
        return await message.answer("❌ Отменено.")
    data = await state.get_data()
    order_id = data.get("reply_order_id")
    if not order_id:
        await state.clear()
        return

    uid = message.from_user.id
    uname = message.from_user.username or "anon"
    text_to_owner = (
        f"💬 <b>Ответ покупателя</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"📋 Заказ: #{order_id}\n"
        f"👤 {uid} (@{uname})\n\n"
        f"{message.text or '(фото/файл)'}\n\n"
        f"━━━━━━━━━━━━━━━━━━━"
    )
    reply_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Написать", callback_data=f"order_msg:{order_id}")],
        [InlineKeyboardButton(text="✅ Одобрить", callback_data=f"order_approve:{order_id}"),
         InlineKeyboardButton(text="❌ Отклонить", callback_data=f"order_reject:{order_id}")],
    ])
    try:
        await message.bot.send_message(OWNER_ID, text_to_owner, parse_mode="HTML",
                                        reply_markup=reply_kb)
        await message.answer(
            f"✅ Ваш ответ по заказу #{order_id} отправлен!\n"
            f"Ожидайте ответа администрации.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ В меню", callback_data="menu")],
            ]),
        )
    except Exception:
        await message.answer("❌ Не удалось отправить ответ.")
    await state.clear()

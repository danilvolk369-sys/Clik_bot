# ======================================================
# SHOP — Улучшение клика + Пассивный доход + Ёмкость
# ======================================================

from aiogram import Router, F
from aiogram.types import CallbackQuery

from config import SHOP_CLICK, SHOP_PASSIVE, SHOP_CAPACITY, DB_NAME, BASE_CLICK_POWER
from handlers.common import fnum
from database import get_user, spend_clicks, invalidate_cache, get_db, create_transaction
from keyboards import shop_menu_kb, shop_upg_kb, shop_pas_kb, shop_cap_kb

router = Router()


# ──── Главное меню магазина ────
@router.callback_query(F.data == "shop_menu")
async def show_shop(call: CallbackQuery):
    text = (
        "💸 МАГАЗИН КЛИКТОХН\n"
        "══════════════════════\n\n"
        "🔨 Улучшение клика — усиль силу\n"
        "📈 Пассивный доход — зарабатывай без кликов\n"
        "📦 Ёмкость дохода — больше накоплений\n\n"
        "══════════════════════"
    )
    await call.message.edit_text(text, reply_markup=shop_menu_kb())
    await call.answer()


# ──── Улучшение клика ────
@router.callback_query(F.data == "shop_upg")
async def show_upgrades(call: CallbackQuery):
    user = await get_user(call.from_user.id)
    power = BASE_CLICK_POWER + user["bonus_click"]

    text = (
        f"🔨 УЛУЧШЕНИЕ КЛИКА\n"
        f"══════════════════════\n"
        f"💰 Баланс: {fnum(user['clicks'])} 💢\n"
        f"⚡ Сила: +{fnum(power)}\n"
        f"══════════════════════\n"
    )
    for i, (k, (bonus, price)) in enumerate(SHOP_CLICK.items(), 1):
        ok = "✅" if user["clicks"] >= price else "❌"
        text += f"\n{ok} #{i}  +{bonus} к клику — {int(price):,} 💢"

    await call.message.edit_text(text, reply_markup=shop_upg_kb())
    await call.answer()


@router.callback_query(F.data.startswith("buy_c_"))
async def buy_click_upgrade(call: CallbackQuery):
    key = call.data.replace("buy_c_", "")
    if key not in SHOP_CLICK:
        return await call.answer("❌ Товар не найден", show_alert=True)

    bonus, price = SHOP_CLICK[key]

    if not await spend_clicks(call.from_user.id, price):
        return await call.answer("❌ Недостаточно 💢!", show_alert=True)

    db = await get_db()
    await db.execute(
        "UPDATE users SET bonus_click = bonus_click + ? WHERE user_id = ?",
        (bonus, call.from_user.id),
    )
    await db.commit()
    invalidate_cache(call.from_user.id)

    await create_transaction(
        "shop", call.from_user.id, 0, float(price),
        f"Клик +{bonus} ∙ {int(price):,}💢",
    )

    await call.answer(f"✅ +{bonus} к силе клика!", show_alert=True)
    await show_upgrades(call)


# ──── Пассивный доход ────
@router.callback_query(F.data == "shop_pas")
async def show_passive(call: CallbackQuery):
    user = await get_user(call.from_user.id)

    text = (
        f"📈 ПАССИВНЫЙ ДОХОД\n"
        f"══════════════════════\n"
        f"💰 Баланс: {fnum(user['clicks'])} 💢\n"
        f"📈 Доход: {fnum(user['passive_income'])} Тохн/час\n"
        f"══════════════════════\n"
    )
    for i, (k, (bonus, price)) in enumerate(SHOP_PASSIVE.items(), 1):
        ok = "✅" if user["clicks"] >= price else "❌"
        text += f"\n{ok} #{i}  +{bonus}/час — {int(price):,} 💢"

    await call.message.edit_text(text, reply_markup=shop_pas_kb())
    await call.answer()


@router.callback_query(F.data.startswith("buy_p_"))
async def buy_passive(call: CallbackQuery):
    key = call.data.replace("buy_p_", "")
    if key not in SHOP_PASSIVE:
        return await call.answer("❌ Товар не найден", show_alert=True)

    bonus, price = SHOP_PASSIVE[key]

    if not await spend_clicks(call.from_user.id, price):
        return await call.answer("❌ Недостаточно 💢!", show_alert=True)

    db = await get_db()
    await db.execute(
        "UPDATE users SET passive_income = passive_income + ? WHERE user_id = ?",
        (bonus, call.from_user.id),
    )
    await db.commit()
    invalidate_cache(call.from_user.id)

    await create_transaction(
        "shop", call.from_user.id, 0, float(price),
        f"Пассив +{bonus}/ч ∙ {int(price):,}💢",
    )

    await call.answer(f"✅ +{bonus} Тохн/час!", show_alert=True)
    await show_passive(call)


# ──── Ёмкость дохода ────
@router.callback_query(F.data == "shop_cap")
async def show_capacity(call: CallbackQuery):
    user = await get_user(call.from_user.id)
    capacity = float(user["income_capacity"]) if user["income_capacity"] else 150.0

    text = (
        f"📦 ЁМКОСТЬ ДОХОДА\n"
        f"══════════════════════\n"
        f"💰 Баланс: {fnum(user['clicks'])} 💢\n"
        f"📦 Ёмкость: {fnum(capacity)} Тохн\n"
        f"══════════════════════\n"
        f"Увеличьте ёмкость, чтобы\n"
        f"накапливать больше дохода!\n"
    )
    for i, (k, (bonus, price)) in enumerate(SHOP_CAPACITY.items(), 1):
        ok = "✅" if user["clicks"] >= price else "❌"
        text += f"\n{ok} #{i}  +{bonus} ёмкость — {int(price):,} 💢"

    await call.message.edit_text(text, reply_markup=shop_cap_kb())
    await call.answer()


@router.callback_query(F.data.startswith("buy_cap_"))
async def buy_capacity(call: CallbackQuery):
    key = call.data.replace("buy_cap_", "")
    if key not in SHOP_CAPACITY:
        return await call.answer("❌ Товар не найден", show_alert=True)

    bonus, price = SHOP_CAPACITY[key]

    if not await spend_clicks(call.from_user.id, price):
        return await call.answer("❌ Недостаточно 💢!", show_alert=True)

    db = await get_db()
    await db.execute(
        "UPDATE users SET income_capacity = income_capacity + ? WHERE user_id = ?",
        (bonus, call.from_user.id),
    )
    await db.commit()
    invalidate_cache(call.from_user.id)

    await create_transaction(
        "shop", call.from_user.id, 0, float(price),
        f"Ёмкость +{bonus} ∙ {int(price):,}💢",
    )

    await call.answer(f"✅ +{bonus} к ёмкости!", show_alert=True)
    await show_capacity(call)

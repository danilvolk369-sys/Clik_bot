# ======================================================
# NFT — Торговая площадка, Мои НФТ, Покупка, Продажа
# ======================================================

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from config import MAX_NFT
from handlers.common import fnum
from states import SellNFTStates
from database import (
    get_user,
    get_user_nfts,
    count_user_nfts,
    get_user_nft_by_id,
    get_nft_template,
    buy_nft_from_shop,
    buy_nft_from_market,
    list_nft_for_sale,
    is_nft_on_sale,
    get_nft_listing_by_user_nft,
    cancel_market_listing,
    get_combined_market_page,
    count_combined_market,
    create_transaction,
)
from keyboards import (
    my_nft_kb,
    nft_detail_kb,
    nft_sell_confirm_kb,
    nft_marketplace_kb,
    nft_buy_confirm_kb,
    market_menu_kb,
    back_menu_kb,
    main_menu_kb,
)

router = Router()


# ─── Утилиты ───
def _rarity_emoji(rarity: int) -> str:
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


# ══════════════════════════════════════════════
#  ТОРГОВАЯ ПЛОЩАДКА  (Магазин → Торговая площадка → НФТ продажи)
# ══════════════════════════════════════════════

@router.callback_query(F.data == "market_menu")
async def show_market_menu(call: CallbackQuery):
    text = (
        "🏪 МАГАЗИН КликТохн\n"
        "🏪 ТОРГОВАЯ ПЛОЩАДКА\n"
        "══════════════════════\n\n"
        "💰 Покупайте и продавайте НФТ!\n"
        "🎨 Редкие карточки с пассивным доходом\n\n"
        "══════════════════════"
    )
    await call.message.edit_text(text, reply_markup=market_menu_kb())
    await call.answer()


@router.callback_query(F.data.startswith("nftp_"))
async def show_nft_marketplace(call: CallbackQuery):
    """Список НФТ торговой площадки с пагинацией."""
    page = int(call.data.replace("nftp_", ""))
    per_page = 5

    total = await count_combined_market()
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(0, min(page, total_pages - 1))

    items = await get_combined_market_page(page, per_page)

    if not items:
        text = (
            "🛍 НФТ ТОРГОВАЯ ПЛОЩАДКА\n"
            "══════════════════════\n\n"
            "😔 Площадка пуста — НФТ ещё не созданы.\n\n"
            "══════════════════════"
        )
        await call.message.edit_text(text, reply_markup=market_menu_kb())
        return await call.answer()

    text = (
        "🛍 НФТ ТОРГОВАЯ ПЛОЩАДКА\n"
        "══════════════════════\n\n"
    )

    for idx, item in enumerate(items, start=page * per_page + 1):
        item_type, item_id, name, rarity, income, price, seller_id = item
        label = _rarity_emoji(rarity)
        icon = "🛒" if item_type == "tpl" else "👤"
        text += (
            f"══════════════\n\n"
            f"🌐 ID: #{item_id}\n\n"
            f"📋 ИНФОРМАЦИЯ NFT:\n"
            f"┠🪙 Название: {name}\n"
            f"┠✨ Редкость: {label}\n"
            f"┗📈 Доход/час: {fnum(income)} 💢\n\n"
            f"💵 Цена: {int(price):,} 💢\n\n"
        )

    text += f"══════════════════════\n📄 Страница {page + 1} / {total_pages}"

    await call.message.edit_text(
        text,
        reply_markup=nft_marketplace_kb(items, page, total_pages),
    )
    await call.answer()


# ─── Просмотр конкретного НФТ на площадке ───

@router.callback_query(F.data.startswith("nftv_"))
async def view_nft_item(call: CallbackQuery):
    """Просмотр НФТ перед покупкой."""
    parts = call.data.replace("nftv_", "").split("_")
    item_type = parts[0]  # tpl или lot
    item_id = int(parts[1])

    user = await get_user(call.from_user.id)
    if not user:
        return await call.answer("❌ /start", show_alert=True)

    nft_count = await count_user_nfts(call.from_user.id)

    if item_type == "tpl":
        tpl = await get_nft_template(item_id)
        if not tpl:
            return await call.answer("❌ НФТ не найден", show_alert=True)
        name = tpl["name"]
        rarity = tpl["rarity"]
        income = tpl["income_per_hour"]
        price = tpl["price"]
        seller_line = "🏪 Продавец: Магазин"
    else:
        from database import get_market_listing
        listing = await get_market_listing(item_id)
        if not listing:
            return await call.answer("❌ Лот не найден или продан", show_alert=True)
        _, seller_id, _, _, price, name, income, rarity = listing
        seller_line = f"👤 Продавец: игрок #{seller_id}"

    label = _rarity_emoji(rarity)
    can_buy = "✅" if user["clicks"] >= price and nft_count < MAX_NFT else "❌"

    text = (
        f"══════════════\n\n"
        f"🌐 ID: #{item_id}\n\n"
        f"📋 ИНФОРМАЦИЯ NFT:\n"
        f"┠🪙 Название: {name}\n"
        f"┠✨ Редкость: {label}\n"
        f"┗📈 Доход/час: {fnum(income)} 💢\n\n"
        f"💵 Цена: {int(price):,} 💢\n"
        f"{seller_line}\n\n"
        f"══════════════\n\n"
        f"💳 Ваш баланс: {fnum(user['clicks'])} 💢\n"
        f"🎨 Ваши НФТ: {nft_count} / {MAX_NFT}\n\n"
    )

    if nft_count >= MAX_NFT:
        text += "⚠️ У вас максимум НФТ! Продайте один из имеющихся."
    elif user["clicks"] < price:
        text += "⚠️ Недостаточно кликов для покупки."
    else:
        text += "Вы точно хотите купить этот НФТ?"

    await call.message.edit_text(
        text,
        reply_markup=nft_buy_confirm_kb(item_type, item_id),
    )
    await call.answer()


# ─── Покупка НФТ ───

@router.callback_query(F.data.startswith("nftb_"))
async def buy_nft(call: CallbackQuery):
    """Подтверждение покупки НФТ."""
    parts = call.data.replace("nftb_", "").split("_")
    item_type = parts[0]
    item_id = int(parts[1])

    uid = call.from_user.id
    nft_count = await count_user_nfts(uid)

    if nft_count >= MAX_NFT:
        return await call.answer(
            f"❌ Максимум {MAX_NFT} НФТ! Продайте один из имеющихся.",
            show_alert=True,
        )

    if item_type == "tpl":
        tpl = await get_nft_template(item_id)
        if not tpl:
            return await call.answer("❌ НФТ не найден", show_alert=True)
        price = tpl["price"]
        name = tpl["name"]
        success = await buy_nft_from_shop(uid, item_id, price)
    else:
        from database import get_market_listing
        listing = await get_market_listing(item_id)
        if not listing:
            return await call.answer("❌ Лот не найден или продан", show_alert=True)
        _, seller_id, _, _, price, name, income, rarity = listing
        if seller_id == uid:
            return await call.answer("❌ Нельзя купить свой НФТ!", show_alert=True)
        success = await buy_nft_from_market(uid, item_id)

    if not success:
        return await call.answer("❌ Недостаточно 💢 или ошибка!", show_alert=True)

    user = await get_user(uid)
    new_count = await count_user_nfts(uid)

    text = (
        f"✅ НФТ КУПЛЕН!\n"
        f"══════════════════════\n\n"
        f"📛 {name}\n"
        f"💰 Списано: {int(price):,} 💢\n"
        f"💳 Остаток: {fnum(user['clicks'])} 💢\n"
        f"🎨 Ваши НФТ: {new_count} / {MAX_NFT}\n\n"
        f"══════════════════════\n"
        f"НФТ добавлен в коллекцию! 🎉"
    )

    from keyboards import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎨 Мои НФТ", callback_data="my_nft")],
        [InlineKeyboardButton(text="🛍 Ещё покупки", callback_data="nftp_0")],
        [InlineKeyboardButton(text="⬅️ В меню", callback_data="menu")],
    ])

    await call.message.edit_text(text, reply_markup=kb)
    await call.answer("✅ Куплено!", show_alert=True)

    # Чек транзакции
    tx_type = "nft_buy" if item_type == "tpl" else "market_buy"
    seller = 0 if item_type == "tpl" else seller_id
    await create_transaction(
        tx_type, uid, seller, float(price),
        f"НФТ '{name}' ∙ {int(price):,}💢",
    )


# ══════════════════════════════════════════════
#  МОИ НФТ  (главное меню → Мои НФТ)
# ══════════════════════════════════════════════

@router.callback_query(F.data == "my_nft")
async def show_my_nfts(call: CallbackQuery, state: FSMContext):
    """Список НФТ пользователя."""
    await state.clear()
    uid = call.from_user.id
    user = await get_user(uid)
    if not user:
        return await call.answer("❌ /start", show_alert=True)

    nfts = await get_user_nfts(uid)
    count = len(nfts)

    text = (
        f"🎨 МОИ НФТ\n"
        f"══════════════════════\n\n"
        f"📦 Доступно: {count} / {MAX_NFT}\n\n"
    )

    if nfts:
        for idx, (un_id, name, income, rarity, bought, dt) in enumerate(nfts, 1):
            label = _rarity_emoji(rarity)
            text += (
                f"══════════════\n\n"
                f"🌐 ID: #{un_id}\n\n"
                f"📋 ИНФОРМАЦИЯ NFT:\n"
                f"┠🪙 Название: {name}\n"
                f"┠✨ Редкость: {label}\n"
                f"┗📈 Доход/час: {fnum(income)} 💢\n\n"
                f"💵 Куплен за: {int(bought):,} 💢\n\n"
            )
        text += "══════════════"
    else:
        text += (
            "😔 У вас пока нет НФТ.\n"
            "Купите в 🏪 Торговой площадке!\n\n"
            "══════════════════════"
        )

    await call.message.edit_text(text, reply_markup=my_nft_kb(nfts, MAX_NFT))
    await call.answer()


# ─── Детали конкретного НФТ пользователя ───

@router.callback_query(F.data.startswith("nft_info_"))
async def show_nft_detail(call: CallbackQuery):
    """Детали НФТ из коллекции пользователя."""
    user_nft_id = int(call.data.replace("nft_info_", ""))
    uid = call.from_user.id

    nft = await get_user_nft_by_id(user_nft_id)
    if not nft or nft[1] != uid:
        return await call.answer("❌ НФТ не найден", show_alert=True)

    un_id, owner_id, nft_id, name, income, rarity, bought = nft
    label = _rarity_emoji(rarity)
    on_sale = await is_nft_on_sale(user_nft_id)

    sale_status = "🟢 На продаже" if on_sale else "⚪ Не продаётся"

    text = (
        f"══════════════\n\n"
        f"🌐 ID: #{un_id}\n\n"
        f"📋 ИНФОРМАЦИЯ NFT:\n"
        f"┠🪙 Название: {name}\n"
        f"┠✨ Редкость: {label}\n"
        f"┠📈 Доход/час: {fnum(income)} 💢\n"
        f"┗💵 Куплен за: {int(bought):,} 💢\n\n"
        f"📊 Статус: {sale_status}\n\n"
        f"══════════════"
    )

    await call.message.edit_text(
        text,
        reply_markup=nft_detail_kb(user_nft_id, on_sale),
    )
    await call.answer()


# ─── Продажа НФТ — выбор цены ───

@router.callback_query(F.data.startswith("nft_sell_") & ~F.data.startswith("nft_sell_yes_"))
async def ask_sell_price(call: CallbackQuery, state: FSMContext):
    """Запросить цену для продажи НФТ."""
    user_nft_id = int(call.data.replace("nft_sell_", ""))
    uid = call.from_user.id

    nft = await get_user_nft_by_id(user_nft_id)
    if not nft or nft[1] != uid:
        return await call.answer("❌ НФТ не найден", show_alert=True)

    un_id, owner_id, nft_id, name, income, rarity, bought = nft
    label = _rarity_emoji(rarity)

    await state.set_state(SellNFTStates.waiting_price)
    await state.update_data(sell_nft_id=user_nft_id, sell_nft_name=name)

    text = (
        f"💰 ПРОДАЖА НФТ\n"
        f"══════════════\n\n"
        f"🌐 ID: #{un_id}\n\n"
        f"📋 ИНФОРМАЦИЯ NFT:\n"
        f"┠🪙 Название: {name}\n"
        f"┠✨ Редкость: {label}\n"
        f"┠📈 Доход/час: {fnum(income)} 💢\n"
        f"┗💵 Куплен за: {int(bought):,} 💢\n\n"
        f"══════════════\n\n"
        f"💵 Введите цену продажи (💢):"
    )

    await call.message.edit_text(text)
    await call.answer()


@router.message(SellNFTStates.waiting_price)
async def process_sell_price(message: Message, state: FSMContext):
    """Получена цена — показать подтверждение."""
    try:
        price = float(message.text.strip().replace(",", "."))
        assert price > 0
    except (ValueError, AssertionError, AttributeError):
        return await message.answer(
            "❌ Введите положительное число — цену в 💢:"
        )

    data = await state.get_data()
    user_nft_id = data.get("sell_nft_id")
    name = data.get("sell_nft_name", "НФТ")

    if not user_nft_id:
        await state.clear()
        return await message.answer("❌ Данные потеряны. Попробуйте снова.", reply_markup=back_menu_kb())

    await state.update_data(sell_price=price)

    nft = await get_user_nft_by_id(user_nft_id)
    if not nft or nft[1] != message.from_user.id:
        await state.clear()
        return await message.answer("❌ НФТ не найден.", reply_markup=back_menu_kb())

    text = (
        f"⚠️ ПОДТВЕРЖДЕНИЕ ПРОДАЖИ\n"
        f"══════════════════════\n\n"
        f"📛 {name}\n"
        f"💰 Цена: {int(price):,} 💢\n\n"
        f"══════════════════════\n\n"
        f"Вы уверены, что хотите выставить\n"
        f"НФТ на торговую площадку?"
    )

    await message.answer(text, reply_markup=nft_sell_confirm_kb(user_nft_id))


@router.callback_query(F.data.startswith("nft_sell_yes_"))
async def confirm_sell_nft(call: CallbackQuery, state: FSMContext):
    """Подтверждение — выставить на продажу."""
    user_nft_id = int(call.data.replace("nft_sell_yes_", ""))
    uid = call.from_user.id

    data = await state.get_data()
    price = data.get("sell_price")

    if not price:
        await state.clear()
        return await call.answer("❌ Цена не задана. Попробуйте снова.", show_alert=True)

    nft = await get_user_nft_by_id(user_nft_id)
    if not nft or nft[1] != uid:
        await state.clear()
        return await call.answer("❌ НФТ не найден", show_alert=True)

    on_sale = await is_nft_on_sale(user_nft_id)
    if on_sale:
        await state.clear()
        return await call.answer("❌ Этот НФТ уже на продаже!", show_alert=True)

    un_id, owner_id, nft_id, name, income, rarity, bought = nft

    listing_id = await list_nft_for_sale(uid, user_nft_id, nft_id, price)
    await state.clear()

    # Чек транзакции
    await create_transaction(
        "nft_sell", uid, 0, float(price),
        f"Выставлен '{name}' за {int(price):,}💢",
    )

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎨 Мои НФТ", callback_data="my_nft")],
        [InlineKeyboardButton(text="⬅️ В меню", callback_data="menu")],
    ])

    text = (
        f"✅ НФТ ВЫСТАВЛЕН НА ПРОДАЖУ!\n"
        f"══════════════════════\n\n"
        f"📛 {name}\n"
        f"💰 Цена: {int(price):,} 💢\n\n"
        f"НФТ доступен на торговой площадке.\n"
        f"══════════════════════"
    )

    await call.message.edit_text(text, reply_markup=kb)
    await call.answer("✅ Выставлено!", show_alert=True)


# ─── Снять с продажи ───

@router.callback_query(F.data.startswith("nft_unsell_"))
async def unsell_nft(call: CallbackQuery):
    """Снять НФТ с продажи."""
    user_nft_id = int(call.data.replace("nft_unsell_", ""))
    uid = call.from_user.id

    nft = await get_user_nft_by_id(user_nft_id)
    if not nft or nft[1] != uid:
        return await call.answer("❌ НФТ не найден", show_alert=True)

    listing_id = await get_nft_listing_by_user_nft(user_nft_id)
    if not listing_id:
        return await call.answer("❌ НФТ не на продаже", show_alert=True)

    ok = await cancel_market_listing(listing_id, uid)
    if not ok:
        return await call.answer("❌ Не удалось снять с продажи", show_alert=True)

    await call.answer("✅ Снято с продажи!", show_alert=True)

    # Показываем обновлённые детали
    nft = await get_user_nft_by_id(user_nft_id)
    un_id, owner_id, nft_id, name, income, rarity, bought = nft
    label = _rarity_emoji(rarity)

    text = (
        f"══════════════\n\n"
        f"🌐 ID: #{un_id}\n\n"
        f"📋 ИНФОРМАЦИЯ NFT:\n"
        f"┠🪙 Название: {name}\n"
        f"┠✨ Редкость: {label}\n"
        f"┠📈 Доход/час: {fnum(income)} 💢\n"
        f"┗💵 Куплен за: {int(bought):,} 💢\n\n"
        f"📊 Статус: ⚪ Не продаётся\n\n"
        f"══════════════"
    )

    await call.message.edit_text(
        text,
        reply_markup=nft_detail_kb(user_nft_id, False),
    )

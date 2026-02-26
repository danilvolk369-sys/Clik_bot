# ======================================================
# CHAT — Случайный анонимный чат (полная сборка)
# ======================================================

from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey

from config import CHAT_SEARCH_COST
from handlers.common import fnum
from states import ChatStates
from database import (
    get_user, chat_queue_add, chat_queue_remove,
    chat_queue_find_partner, chat_create, chat_get_active,
    chat_end, chat_log, chat_get_history_for_user,
    chat_count_for_user, spend_clicks, update_clicks,
    create_transaction,
)
from keyboards import (
    chat_menu_kb, chat_confirm_search_kb, chat_searching_kb,
    chat_active_kb, chat_ended_kb,
)

router = Router()


# ────────────────────────────────────────────────────────
#  Утилита: установить FSM-состояние партнёру
# ────────────────────────────────────────────────────────
async def _set_partner_state(bot: Bot, state: FSMContext,
                             partner_id: int, chat_id: int, my_id: int):
    """Устанавливаем состояние in_chat партнёру через его StorageKey."""
    key = StorageKey(
        bot_id=bot.id,
        chat_id=partner_id,
        user_id=partner_id,
    )
    partner_ctx = FSMContext(
        storage=state.storage,
        key=key,
    )
    await partner_ctx.set_state(ChatStates.in_chat)
    await partner_ctx.update_data(chat_id=chat_id, partner_id=my_id)


async def _clear_partner_state(bot: Bot, state: FSMContext, partner_id: int):
    """Очищаем FSM партнёра."""
    key = StorageKey(
        bot_id=bot.id,
        chat_id=partner_id,
        user_id=partner_id,
    )
    partner_ctx = FSMContext(
        storage=state.storage,
        key=key,
    )
    await partner_ctx.clear()


# ────────────────────────────────────────────────────────
#  Меню чата
# ────────────────────────────────────────────────────────
@router.callback_query(F.data == "chat_menu")
async def show_chat_menu(call: CallbackQuery, state: FSMContext):
    uid = call.from_user.id
    total = await chat_count_for_user(uid)
    active = await chat_get_active(uid)

    status = "🟢 В чате" if active else "⚪ Свободен"

    text = (
        "💬 АНОНИМНЫЙ ЧАТ\n"
        "══════════════════════\n\n"
        f"Статус: {status}\n"
        f"Всего диалогов: {total}\n\n"
        "🔍 Найти собеседника — случайный чат\n"
        "📋 Мои чаты — текущий диалог\n"
        "📜 История — прошлые диалоги\n\n"
        "══════════════════════"
    )

    # Если уже в чате — показать кнопки чата
    if active:
        await call.message.edit_text(text, reply_markup=chat_active_kb())
    else:
        await call.message.edit_text(text, reply_markup=chat_menu_kb())
    await call.answer()


# ────────────────────────────────────────────────────────
#  Начать поиск — предупреждение об оплате
# ────────────────────────────────────────────────────────
@router.callback_query(F.data == "chat_search")
async def chat_search_warning(call: CallbackQuery, state: FSMContext):
    uid = call.from_user.id

    active = await chat_get_active(uid)
    if active:
        await call.answer("💬 У вас уже есть активный чат!", show_alert=True)
        return

    user = await get_user(uid)
    if not user:
        return await call.answer("❌ /start", show_alert=True)

    balance = user["clicks"]
    cost = CHAT_SEARCH_COST
    enough = "✅" if balance >= cost else "❌"

    text = (
        "🔍 ПОИСК СОБЕСЕДНИКА\n"
        "══════════════════════\n\n"
        f"⚠️ Стоимость поиска: {cost} 💢\n"
        f"💳 Ваш баланс: {fnum(balance)} 💢 {enough}\n\n"
    )
    if balance < cost:
        text += "❌ Недостаточно кликов для поиска!\n"
    else:
        text += (
            "💡 Если собеседник не найден и вы\n"
            "отмените поиск — клики вернутся.\n"
        )
    text += "\n══════════════════════"

    await call.message.edit_text(text, reply_markup=chat_confirm_search_kb())
    await call.answer()


# ────────────────────────────────────────────────────────
#  Подтверждение оплаты → реальный поиск
# ────────────────────────────────────────────────────────
@router.callback_query(F.data == "chat_search_confirm")
async def chat_search_confirmed(call: CallbackQuery, state: FSMContext):
    uid = call.from_user.id

    active = await chat_get_active(uid)
    if active:
        await call.answer("💬 У вас уже есть активный чат!", show_alert=True)
        return

    # Списываем клики
    ok = await spend_clicks(uid, CHAT_SEARCH_COST)
    if not ok:
        return await call.answer("❌ Недостаточно 💢!", show_alert=True)

    # Ищем партнёра в очереди
    partner_id = await chat_queue_find_partner(uid)

    if partner_id:
        # ─── Партнёр найден! ───
        chat_id = await chat_create(uid, partner_id)

        await state.set_state(ChatStates.in_chat)
        await state.update_data(chat_id=chat_id, partner_id=partner_id)
        await _set_partner_state(call.bot, state, partner_id, chat_id, uid)

        found_text = (
            "💬 СОБЕСЕДНИК НАЙДЕН!\n"
            "══════════════════════\n\n"
            f"💰 Списано: {CHAT_SEARCH_COST} 💢\n"
            "👤 Аноним подключён.\n"
            "Просто пишите сообщение — оно уйдёт собеседнику.\n\n"
            "🔇 Завершить чат — выход\n"
            "🔍 Новый собеседник — следующий\n"
            "══════════════════════"
        )

        await call.message.edit_text(found_text, reply_markup=chat_active_kb())

        try:
            await call.bot.send_message(
                partner_id,
                "💬 СОБЕСЕДНИК НАЙДЕН!\n"
                "══════════════════════\n\n"
                "👤 Аноним подключён.\n"
                "Просто пишите сообщение — оно уйдёт собеседнику.\n\n"
                "🔇 Завершить чат — выход\n"
                "🔍 Новый собеседник — следующий",
                reply_markup=chat_active_kb(),
            )
        except Exception:
            pass
    else:
        # ─── Очередь пуста — встаём в ожидание ───
        await chat_queue_add(uid)
        await state.set_state(ChatStates.searching)
        await state.update_data(chat_paid=True)

        await call.message.edit_text(
            "🔍 ПОИСК СОБЕСЕДНИКА\n"
            "══════════════════════\n\n"
            f"💰 Списано: {CHAT_SEARCH_COST} 💢\n"
            "⏳ Ожидайте, ищем для вас пару...\n\n"
            "💡 Если отмените — клики вернутся.\n"
            "Нажмите «Остановить», чтобы отменить.",
            reply_markup=chat_searching_kb(),
        )

    await call.answer()


# ────────────────────────────────────────────────────────
#  Остановить поиск
# ────────────────────────────────────────────────────────
@router.callback_query(F.data == "chat_stop_search")
async def chat_stop_search(call: CallbackQuery, state: FSMContext):
    uid = call.from_user.id
    data = await state.get_data()
    await chat_queue_remove(uid)
    await state.clear()

    # Возвращаем клики, если оплата была
    if data.get("chat_paid"):
        await update_clicks(uid, CHAT_SEARCH_COST)
        refund_line = f"\n💰 Возвращено: {CHAT_SEARCH_COST} 💢"
    else:
        refund_line = ""

    await call.message.edit_text(
        "❌ Поиск остановлен.\n"
        f"{refund_line}\n"
        "Возвращайтесь, когда захотите пообщаться!",
        reply_markup=chat_menu_kb(),
    )
    await call.answer()


# ────────────────────────────────────────────────────────
#  Мои чаты (активный)
# ────────────────────────────────────────────────────────
@router.callback_query(F.data == "chat_list")
async def chat_list(call: CallbackQuery):
    uid = call.from_user.id
    active = await chat_get_active(uid)

    if active:
        text = (
            "📋 АКТИВНЫЙ ЧАТ\n"
            "══════════════════════\n\n"
            f"💬 Чат #{active['id']}\n"
            "Собеседник подключён — пишите!\n\n"
            "══════════════════════"
        )
        kb = chat_active_kb()
    else:
        text = (
            "📋 АКТИВНЫЙ ЧАТ\n"
            "══════════════════════\n\n"
            "У вас нет активного чата.\n"
            "Нажмите «Найти собеседника» для поиска."
        )
        kb = chat_menu_kb()

    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


# ────────────────────────────────────────────────────────
#  История чатов
# ────────────────────────────────────────────────────────
@router.callback_query(F.data == "chat_history")
async def chat_history(call: CallbackQuery):
    uid = call.from_user.id
    history = await chat_get_history_for_user(uid, limit=10)

    if not history:
        text = (
            "📜 ИСТОРИЯ ЧАТОВ\n"
            "══════════════════════\n\n"
            "Пока нет завершённых диалогов.\n"
            "Начните общение!"
        )
    else:
        lines = [
            "📜 ИСТОРИЯ ЧАТОВ\n"
            "══════════════════════\n"
        ]
        for i, row in enumerate(history, 1):
            cid = row[0]
            msgs = row[1]  # количество сообщений
            dt = row[2][:16].replace("T", " ") if row[2] else "?"
            lines.append(f"  {i}. Чат #{cid} — {msgs} сообщ. ({dt})")

        lines.append("\n══════════════════════")
        text = "\n".join(lines)

    await call.message.edit_text(text, reply_markup=chat_menu_kb())
    await call.answer()


# ────────────────────────────────────────────────────────
#  Сообщение во время поиска
# ────────────────────────────────────────────────────────
@router.message(ChatStates.searching)
async def msg_while_searching(message: Message, state: FSMContext):
    uid = message.from_user.id

    # Проверяем — может, партнёр уже нашёлся пока мы ждали
    active = await chat_get_active(uid)
    if active:
        # Переключаемся в чат
        partner = active["u2"] if active["u1"] == uid else active["u1"]
        await state.set_state(ChatStates.in_chat)
        await state.update_data(chat_id=active["id"], partner_id=partner)

        # Пересылаем это сообщение партнёру
        text = message.text or ""
        if text:
            await chat_log(active["id"], uid, text)
            try:
                await message.bot.send_message(partner, f"💬 {text}")
            except Exception:
                pass
        return

    await message.answer(
        "⏳ Ищем собеседника...\n"
        "Нажмите «Остановить» для отмены.",
        reply_markup=chat_searching_kb(),
    )


# ────────────────────────────────────────────────────────
#  Пересылка сообщений в чате
# ────────────────────────────────────────────────────────
@router.message(ChatStates.in_chat)
async def chat_relay(message: Message, state: FSMContext):
    uid = message.from_user.id
    active = await chat_get_active(uid)

    if not active:
        await state.clear()
        await message.answer(
            "❌ Чат завершён.\n"
            "Собеседник отключился.",
            reply_markup=chat_ended_kb(),
        )
        return

    partner = active["u2"] if active["u1"] == uid else active["u1"]
    text = message.text or ""

    if text:
        await chat_log(active["id"], uid, text)

    # Пересылаем партнёру (поддержка текста, стикеров, фото, голоса)
    try:
        if message.sticker:
            await message.bot.send_sticker(partner, message.sticker.file_id)
        elif message.photo:
            cap = message.caption or ""
            await message.bot.send_photo(
                partner, message.photo[-1].file_id,
                caption=f"💬 {cap}" if cap else None,
            )
        elif message.voice:
            await message.bot.send_voice(partner, message.voice.file_id)
        elif message.video_note:
            await message.bot.send_video_note(partner, message.video_note.file_id)
        elif message.video:
            cap = message.caption or ""
            await message.bot.send_video(
                partner, message.video.file_id,
                caption=f"💬 {cap}" if cap else None,
            )
        elif message.document:
            cap = message.caption or ""
            await message.bot.send_document(
                partner, message.document.file_id,
                caption=f"💬 {cap}" if cap else None,
            )
        elif message.animation:
            await message.bot.send_animation(partner, message.animation.file_id)
        elif text:
            await message.bot.send_message(partner, f"💬 {text}")
        else:
            await message.answer("⚠️ Этот тип сообщений не поддерживается.")
            return
    except Exception:
        await message.answer("⚠️ Не удалось доставить сообщение.")
        return

    # Без «✅ Отправлено» — чтобы не спамить (чат как чат)


# ────────────────────────────────────────────────────────
#  Завершить чат
# ────────────────────────────────────────────────────────
@router.callback_query(F.data == "chat_end")
async def end_chat(call: CallbackQuery, state: FSMContext):
    uid = call.from_user.id
    active = await chat_get_active(uid)

    if active:
        partner = active["u2"] if active["u1"] == uid else active["u1"]
        chat_id_val = active["id"]
        await chat_end(chat_id_val)

        # Чек транзакции
        await create_transaction(
            "chat", uid, partner, 0,
            f"Чат #{chat_id_val} ∙ завершён", ref_id=chat_id_val,
        )

        # Очищаем FSM партнёра
        await _clear_partner_state(call.bot, state, partner)

        try:
            await call.bot.send_message(
                partner,
                "❌ Собеседник завершил чат.\n\n"
                "Можете найти нового!",
                reply_markup=chat_ended_kb(),
            )
        except Exception:
            pass

    await state.clear()
    await call.message.edit_text(
        "✅ Чат завершён.\n"
        "══════════════════════\n\n"
        "Спасибо за общение! 🤝",
        reply_markup=chat_ended_kb(),
    )
    await call.answer()


# ────────────────────────────────────────────────────────
#  «Следующий» — завершить текущий + начать поиск нового
# ────────────────────────────────────────────────────────
@router.callback_query(F.data == "chat_next")
async def chat_next(call: CallbackQuery, state: FSMContext):
    uid = call.from_user.id
    active = await chat_get_active(uid)

    # Завершаем текущий чат
    if active:
        partner = active["u2"] if active["u1"] == uid else active["u1"]
        await chat_end(active["id"])
        await _clear_partner_state(call.bot, state, partner)

        try:
            await call.bot.send_message(
                partner,
                "❌ Собеседник перешёл к другому чату.\n\n"
                "Можете найти нового!",
                reply_markup=chat_ended_kb(),
            )
        except Exception:
            pass

    await state.clear()

    # Сразу ищем нового (тоже списываем)
    ok = await spend_clicks(uid, CHAT_SEARCH_COST)
    if not ok:
        await call.message.edit_text(
            f"❌ Недостаточно {CHAT_SEARCH_COST} 💢 для нового поиска.",
            reply_markup=chat_menu_kb(),
        )
        return await call.answer()

    partner_id = await chat_queue_find_partner(uid)

    if partner_id:
        chat_id = await chat_create(uid, partner_id)
        await state.set_state(ChatStates.in_chat)
        await state.update_data(chat_id=chat_id, partner_id=partner_id)
        await _set_partner_state(call.bot, state, partner_id, chat_id, uid)

        found_text = (
            "💬 НОВЫЙ СОБЕСЕДНИК НАЙДЕН!\n"
            "══════════════════════\n\n"
            "👤 Аноним подключён.\n"
            "Пишите — сообщение уйдёт собеседнику."
        )
        await call.message.edit_text(found_text, reply_markup=chat_active_kb())

        try:
            await call.bot.send_message(
                partner_id,
                "💬 СОБЕСЕДНИК НАЙДЕН!\n"
                "══════════════════════\n\n"
                "👤 Аноним подключён.\n"
                "Пишите — сообщение уйдёт собеседнику.",
                reply_markup=chat_active_kb(),
            )
        except Exception:
            pass
    else:
        await chat_queue_add(uid)
        await state.set_state(ChatStates.searching)
        await state.update_data(chat_paid=True)

        await call.message.edit_text(
            "🔍 ПОИСК НОВОГО СОБЕСЕДНИКА\n"
            "══════════════════════\n\n"
            f"💰 Списано: {CHAT_SEARCH_COST} 💢\n"
            "⏳ Ожидайте, ищем пару...\n\n"
            "💡 Если отмените — клики вернутся.\n"
            "Нажмите «Остановить», чтобы отменить.",
            reply_markup=chat_searching_kb(),
        )

    await call.answer()

# ======================================================
# CHAT — Случайный чат (в разделе Мини-игры)
# ======================================================
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from states import ChatStates
from database import (
    get_user, update_clicks, set_user_online,
    chat_queue_add, chat_queue_remove, chat_queue_find_partner,
    create_active_chat, get_active_chat, end_active_chat,
    add_chat_log, log_activity,
)
from keyboards import (
    chat_menu_kb, chat_confirm_search_kb, chat_searching_kb,
    chat_active_kb, chat_ended_kb,
)
from handlers.common import fnum
from banners_util import send_msg, safe_edit

router = Router()

CHAT_COST = 50  # стоимость поиска


# ── Меню чата ──
@router.callback_query(F.data == "chat_menu")
async def chat_menu(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await set_user_online(call.from_user.id)
    # Убираем из очереди если был
    await chat_queue_remove(call.from_user.id)
    await send_msg(
        call,
        "💬 СЛУЧАЙНЫЙ ЧАТ\n══════════════════════\n\n"
        "Общайтесь анонимно с другими игроками!\n"
        f"Поиск стоит {CHAT_COST} 💢.",
        reply_markup=chat_menu_kb(),
    )


# ── Подтверждение поиска ──
@router.callback_query(F.data == "chat_search")
async def chat_search(call: CallbackQuery, state: FSMContext):
    user = await get_user(call.from_user.id)
    if not user:
        return await call.answer("❌", show_alert=True)
    if user["is_banned"]:
        return await call.answer("🚫 Вы забанены", show_alert=True)

    # Проверяем, не в чате ли уже
    existing = await get_active_chat(call.from_user.id)
    if existing:
        return await call.answer("💬 Вы уже в чате!", show_alert=True)

    if user["clicks"] < CHAT_COST:
        return await call.answer(f"❌ Нужно {CHAT_COST} 💢 (у вас {fnum(user['clicks'])})", show_alert=True)

    await call.message.edit_text(
        f"🔍 Начать поиск за {CHAT_COST} 💢?\n"
        f"Ваши Тохн: {fnum(user['clicks'])} 💢",
        reply_markup=chat_confirm_search_kb(),
    )
    await call.answer()


# ── Начать поиск ──
@router.callback_query(F.data == "chat_search_confirm")
async def chat_search_confirm(call: CallbackQuery, state: FSMContext):
    uid = call.from_user.id
    user = await get_user(uid)
    if not user or user["clicks"] < CHAT_COST:
        return await call.answer("❌ Не хватает 💢", show_alert=True)

    # Списываем
    await update_clicks(uid, -CHAT_COST)

    # Ищем собеседника
    partner_id = await chat_queue_find_partner(uid)

    if partner_id:
        # Нашли пару!
        await chat_queue_remove(partner_id)
        await chat_queue_remove(uid)
        chat_id = await create_active_chat(uid, partner_id)

        await state.set_state(ChatStates.in_chat)
        await state.update_data(chat_id=chat_id, partner_id=partner_id)

        await call.message.edit_text(
            "💬 Собеседник найден!\n══════════════════════\n\n"
            "Пишите сообщения — они будут переданы анонимно.\n"
            "Используйте кнопки для управления.",
            reply_markup=chat_active_kb(),
        )

        # Уведомляем партнёра
        try:
            await call.bot.send_message(
                partner_id,
                "💬 Собеседник найден!\n══════════════════════\n\n"
                "Пишите сообщения — они будут переданы анонимно.",
                reply_markup=chat_active_kb(),
            )
        except Exception:
            pass

        await log_activity(uid, "chat_start", f"with partner, chat #{chat_id}")
    else:
        # Никого нет — ставим в очередь
        await chat_queue_add(uid)
        await state.set_state(ChatStates.searching)

        await call.message.edit_text(
            "🔍 Ищем собеседника...\n\n"
            "Ожидайте, вас подключат автоматически.",
            reply_markup=chat_searching_kb(),
        )

    await call.answer()


# ── Остановить поиск ──
@router.callback_query(F.data == "chat_stop_search")
async def chat_stop_search(call: CallbackQuery, state: FSMContext):
    uid = call.from_user.id
    await chat_queue_remove(uid)
    await state.clear()
    await call.message.edit_text(
        "⏹ Поиск остановлен.",
        reply_markup=chat_ended_kb(),
    )
    await call.answer()


# ── Завершить чат ──
@router.callback_query(F.data == "chat_end")
async def chat_end(call: CallbackQuery, state: FSMContext):
    uid = call.from_user.id
    chat = await get_active_chat(uid)
    if not chat:
        await state.clear()
        return await call.message.edit_text("ℹ️ Нет активного чата.", reply_markup=chat_ended_kb())

    chat_id, u1, u2 = chat[0], chat[1], chat[2]
    partner = u2 if u1 == uid else u1

    await end_active_chat(chat_id)
    await state.clear()

    await call.message.edit_text(
        "🔇 Чат завершён.",
        reply_markup=chat_ended_kb(),
    )

    # Уведомляем партнёра
    try:
        await call.bot.send_message(
            partner,
            "🔇 Собеседник покинул чат.",
            reply_markup=chat_ended_kb(),
        )
    except Exception:
        pass

    await log_activity(uid, "chat_end", f"chat #{chat_id}")
    await call.answer()


# ── Следующий собеседник (завершить текущий + найти нового) ──
@router.callback_query(F.data == "chat_next")
async def chat_next(call: CallbackQuery, state: FSMContext):
    uid = call.from_user.id
    user = await get_user(uid)
    if not user or user["clicks"] < CHAT_COST:
        return await call.answer(f"❌ Нужно {CHAT_COST} 💢", show_alert=True)

    # Завершаем текущий
    chat = await get_active_chat(uid)
    if chat:
        chat_id, u1, u2 = chat[0], chat[1], chat[2]
        partner = u2 if u1 == uid else u1
        await end_active_chat(chat_id)
        try:
            await call.bot.send_message(
                partner,
                "🔇 Собеседник покинул чат.",
                reply_markup=chat_ended_kb(),
            )
        except Exception:
            pass

    # Списываем
    await update_clicks(uid, -CHAT_COST)

    # Ищем нового
    partner_id = await chat_queue_find_partner(uid)
    if partner_id:
        await chat_queue_remove(partner_id)
        new_chat_id = await create_active_chat(uid, partner_id)
        await state.set_state(ChatStates.in_chat)
        await state.update_data(chat_id=new_chat_id, partner_id=partner_id)

        await call.message.edit_text(
            "💬 Новый собеседник найден!\n══════════════════════\n\n"
            "Пишите сообщения анонимно.",
            reply_markup=chat_active_kb(),
        )
        try:
            await call.bot.send_message(
                partner_id,
                "💬 Собеседник найден!\nПишите сообщения анонимно.",
                reply_markup=chat_active_kb(),
            )
        except Exception:
            pass
    else:
        await chat_queue_add(uid)
        await state.set_state(ChatStates.searching)
        await call.message.edit_text(
            "🔍 Ищем нового собеседника...",
            reply_markup=chat_searching_kb(),
        )

    await call.answer()


# ── Пересылка сообщений (основной обработчик) ──
@router.message(ChatStates.in_chat)
async def chat_relay(message: Message, state: FSMContext):
    uid = message.from_user.id
    chat = await get_active_chat(uid)
    if not chat:
        await state.clear()
        return await message.answer("ℹ️ Нет активного чата.", reply_markup=chat_ended_kb())

    chat_id, u1, u2 = chat[0], chat[1], chat[2]
    partner = u2 if u1 == uid else u1

    # Сохраняем лог
    text = message.text or "[медиа]"
    await add_chat_log(chat_id, uid, text[:500])

    # Пересылаем текст
    try:
        if message.text:
            await message.bot.send_message(partner, f"💬 {message.text}")
        elif message.sticker:
            await message.bot.send_sticker(partner, message.sticker.file_id)
        elif message.photo:
            await message.bot.send_photo(partner, message.photo[-1].file_id, caption=f"💬 {message.caption or ''}")
        elif message.voice:
            await message.bot.send_voice(partner, message.voice.file_id)
        elif message.video:
            await message.bot.send_video(partner, message.video.file_id, caption=f"💬 {message.caption or ''}")
        elif message.document:
            await message.bot.send_document(partner, message.document.file_id, caption=f"💬 {message.caption or ''}")
        elif message.animation:
            await message.bot.send_animation(partner, message.animation.file_id)
        else:
            await message.bot.send_message(partner, "💬 [неизвестный формат сообщения]")
    except Exception:
        await message.answer("⚠️ Не удалось доставить сообщение. Возможно, собеседник покинул чат.",
                             reply_markup=chat_ended_kb())
        await end_active_chat(chat_id)
        await state.clear()


# ── Ожидание: если пишут во время поиска ──
@router.message(ChatStates.searching)
async def chat_waiting_msg(message: Message):
    await message.answer("🔍 Поиск собеседника... Подождите.", reply_markup=chat_searching_kb())

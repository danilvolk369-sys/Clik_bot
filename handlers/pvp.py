# ======================================================
# PvP — мини-игры: КНБ, Кости, Монетка, Слоты
# Раунды: 1, 2, 3, 4
# ======================================================
import asyncio
import random

from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from config import MINIGAMES_OPEN_CLICKS
from states import PVPStates
from database import (
    get_user, create_pvp_game, get_open_pvp_games, get_pvp_game,
    join_pvp_game, set_pvp_move, finish_pvp_game, draw_pvp_game,
    cancel_pvp_game, update_pvp_round, get_user_pvp_history,
    set_user_online, create_transaction, log_activity,
)
from keyboards import (
    pvp_menu_kb, pvp_create_type_kb, pvp_rounds_kb, pvp_bet_kb,
    pvp_rps_kb, pvp_dice_kb, pvp_flip_kb, pvp_slots_kb, pvp_ttt_kb,
    minigames_menu_kb, back_menu_kb,
)
from handlers.common import fnum

from banners_util import send_msg, safe_edit

router = Router()

_pvp_ctx: dict = {}


def _check_minigames(user) -> bool:
    return (user["total_clicks"] or 0) >= MINIGAMES_OPEN_CLICKS


# ── Мини-игры меню ──
@router.callback_query(F.data == "minigames_menu")
async def minigames_menu(call: CallbackQuery):
    user = await get_user(call.from_user.id)
    if not user:
        return await call.answer("❌ /start", show_alert=True)
    await set_user_online(call.from_user.id)
    if not _check_minigames(user):
        return await call.answer(
            f"🔒 Нужно {MINIGAMES_OPEN_CLICKS} кликов для мини-игр!",
            show_alert=True,
        )
    text = (
        "🎮 МИНИ-ИГРЫ\n"
        "══════════════════════\n\n"
        "⚔️ PvP — сражайся с игроками\n"
        "💬 Чат — найди собеседника\n\n"
        "══════════════════════"
    )
    await call.message.edit_text(text, reply_markup=minigames_menu_kb())
    await call.answer()


# ── PvP Главное меню ──
@router.callback_query(F.data == "pvp_menu")
async def pvp_menu(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await set_user_online(call.from_user.id)
    text = (
        "⚔️ PvP АРЕНА\n"
        "══════════════════════\n\n"
        "Создай бой или вступи в чужой.\n"
        "Победитель получает ставки обоих.\n\n"
        "══════════════════════"
    )
    await send_msg(call, text, reply_markup=pvp_menu_kb())


# ── Создать ── Тип
@router.callback_query(F.data == "pvp_create")
async def pvp_create(call: CallbackQuery, state: FSMContext):
    await state.clear()
    text = "⚔️ СОЗДАТЬ БОЙ\n══════════════════════\n\nВыбери тип игры:"
    await call.message.edit_text(text, reply_markup=pvp_create_type_kb())
    await call.answer()


@router.callback_query(F.data.startswith("pvp_type_"))
async def pvp_set_type(call: CallbackQuery, state: FSMContext):
    game_type = call.data.replace("pvp_type_", "")
    _pvp_ctx[call.from_user.id] = {"type": game_type}
    # Крестики-нолики — всегда 1 раунд, сразу к ставке
    if game_type == "ttt":
        _pvp_ctx[call.from_user.id]["rounds"] = 1
        text = "💰 СТАВКА\n══════════════════════\n\n❌⭕ Крестики-Нолики (1 раунд)\nВыбери ставку:"
        await call.message.edit_text(text, reply_markup=pvp_bet_kb())
        return await call.answer()
    text = "⚔️ КОЛИЧЕСТВО РАУНДОВ\n══════════════════════\n\nВыбери количество раундов:"
    await call.message.edit_text(text, reply_markup=pvp_rounds_kb())
    await call.answer()


# ── Раунды
@router.callback_query(F.data.startswith("pvp_rounds_"))
async def pvp_set_rounds(call: CallbackQuery, state: FSMContext):
    rounds = int(call.data.replace("pvp_rounds_", ""))
    uid = call.from_user.id
    if uid not in _pvp_ctx:
        return await call.answer("❌ Начни создание заново", show_alert=True)
    _pvp_ctx[uid]["rounds"] = rounds
    text = f"💰 СТАВКА\n══════════════════════\n\nРаундов: {rounds}\nВыбери ставку:"
    await call.message.edit_text(text, reply_markup=pvp_bet_kb())
    await call.answer()


# ── Ставка
@router.callback_query(F.data.startswith("pvp_bet_"))
async def pvp_set_bet(call: CallbackQuery, state: FSMContext):
    uid = call.from_user.id
    if uid not in _pvp_ctx:
        return await call.answer("❌ Начни создание заново", show_alert=True)

    raw = call.data.replace("pvp_bet_", "")
    if raw == "custom":
        await state.set_state(PVPStates.waiting_bet)
        text = "✏️ Введи свою ставку (число):"
        await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="pvp_menu")]
        ]))
        return await call.answer()

    bet = float(raw)
    await _create_the_game(call, uid, bet)


@router.message(PVPStates.waiting_bet)
async def pvp_custom_bet(message: Message, state: FSMContext):
    await state.clear()
    uid = message.from_user.id
    try:
        bet = float(message.text.strip())
        if bet < 10:
            return await message.answer("❌ Минимум 10 💢", reply_markup=back_menu_kb())
    except (ValueError, TypeError):
        return await message.answer("❌ Введи число", reply_markup=back_menu_kb())
    # Отправим новое сообщение вместо edit
    user = await get_user(uid)
    if not user or float(user["clicks"]) < bet:
        return await message.answer("❌ Недостаточно 💢", reply_markup=back_menu_kb())
    if uid not in _pvp_ctx:
        return await message.answer("❌ Начни заново", reply_markup=back_menu_kb())
    ctx = _pvp_ctx[uid]
    game_type = ctx.get("type", "rps")
    rounds = ctx.get("rounds", 1)
    game_id = await create_pvp_game(uid, bet, game_type, rounds)
    _pvp_ctx.pop(uid, None)
    await log_activity(uid, "pvp", f"Создал PvP #{game_id}: {game_type} x{rounds} ставка {bet}")
    await create_transaction("pvp", uid, amount=bet, details=f"Создание PvP #{game_id}")
    text = (
        f"✅ Бой #{game_id} создан!\n\n"
        f"🎮 Тип: {_type_name(game_type)}\n"
        f"🔄 Раундов: {rounds}\n"
        f"💰 Ставка: {fnum(bet)} 💢\n\n"
        f"Ожидаем оппонента..."
    )
    await message.answer(text, reply_markup=pvp_menu_kb())


async def _create_the_game(call: CallbackQuery, uid: int, bet: float):
    user = await get_user(uid)
    if not user or float(user["clicks"]) < bet:
        return await call.answer("❌ Недостаточно 💢", show_alert=True)
    ctx = _pvp_ctx.get(uid, {})
    game_type = ctx.get("type", "rps")
    rounds = ctx.get("rounds", 1)
    game_id = await create_pvp_game(uid, bet, game_type, rounds)
    _pvp_ctx.pop(uid, None)
    await log_activity(uid, "pvp", f"Создал PvP #{game_id}: {game_type} x{rounds} ставка {bet}")
    await create_transaction("pvp", uid, amount=bet, details=f"Создание PvP #{game_id}")
    text = (
        f"✅ Бой #{game_id} создан!\n\n"
        f"🎮 Тип: {_type_name(game_type)}\n"
        f"🔄 Раундов: {rounds}\n"
        f"💰 Ставка: {fnum(bet)} 💢\n\n"
        f"Ожидаем оппонента..."
    )
    await call.message.edit_text(text, reply_markup=pvp_menu_kb())
    await call.answer()


def _type_name(t: str) -> str:
    return {"rps": "✂️ КНБ", "dice": "🎲 Кости", "flip": "🪙 Монетка", "slots": "🎰 Слоты", "ttt": "❌⭕ Крестики-Нолики"}.get(t, t)


# ── Найти бои ──
@router.callback_query(F.data == "pvp_find")
async def pvp_find(call: CallbackQuery):
    await set_user_online(call.from_user.id)
    games = await get_open_pvp_games()
    if not games:
        text = "⚔️ Нет открытых боёв.\n\nСоздай свой!"
        await call.message.edit_text(text, reply_markup=pvp_menu_kb())
        return await call.answer()

    kb = []
    for g in games[:10]:
        gid, creator_id, bet, gtype, rounds = g
        type_name = _type_name(gtype)
        kb.append([InlineKeyboardButton(
            text=f"⚔️ #{gid} │ {type_name} x{rounds} │ {fnum(bet)} 💢",
            callback_data=f"pvp_join_{gid}",
        )])
    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="pvp_menu")])
    await call.message.edit_text("⚔️ ОТКРЫТЫЕ БОИ\n══════════════════════\n\nВыбери бой:",
                                  reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await call.answer()


# ── Присоединиться ──
@router.callback_query(F.data.startswith("pvp_join_"))
async def pvp_join(call: CallbackQuery):
    game_id = int(call.data.replace("pvp_join_", ""))
    uid = call.from_user.id
    game = await get_pvp_game(game_id)
    if not game or game["status"] != "open":
        return await call.answer("❌ Бой уже начат или не найден", show_alert=True)
    if game["creator_id"] == uid:
        return await call.answer("❌ Нельзя играть с собой", show_alert=True)

    success = await join_pvp_game(game_id, uid)
    if not success:
        return await call.answer("❌ Недостаточно 💢", show_alert=True)

    await log_activity(uid, "pvp", f"Вступил в PvP #{game_id}")
    await create_transaction("pvp", uid, amount=float(game["bet"]), details=f"Вступление в PvP #{game_id}")

    game = await get_pvp_game(game_id)
    gtype = game["game_type"]

    # Крестики-нолики: инициализация доски
    if gtype == "ttt":
        board = "." * 9
        # creator_move хранит доску, opponent_move хранит чей ход ("X"=creator, "O"=opponent)
        await set_pvp_move(game_id, game["creator_id"], board)
        await set_pvp_move(game_id, uid, "X")  # opponent_move = "X" → ход создателя (❌)
        kb = pvp_ttt_kb(game_id, board)
        text = (
            f"❌⭕ БОЙ #{game_id} НАЧАЛСЯ!\n"
            f"══════════════════════\n\n"
            f"💰 Ставка: {fnum(game['bet'])} 💢\n\n"
            f"❌ ходит первым!\n"
            f"Создатель — ❌, Оппонент — ⭕"
        )
        await call.message.edit_text(text, reply_markup=kb)
        await call.answer()
        try:
            await call.bot.send_message(game["creator_id"], text, reply_markup=kb)
        except Exception:
            pass
        return

    text = (
        f"⚔️ БОЙ #{game_id} НАЧАЛСЯ!\n"
        f"══════════════════════\n\n"
        f"🎮 {_type_name(gtype)} │ Раунд 1/{game['rounds']}\n"
        f"💰 Ставка: {fnum(game['bet'])} 💢\n\n"
        f"Сделайте ход!"
    )
    kb = _game_kb(gtype, game_id)
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()

    # Уведомить создателя
    try:
        bot: Bot = call.bot
        await bot.send_message(
            game["creator_id"],
            f"⚔️ Оппонент найден! Бой #{game_id}\n\n{_type_name(gtype)} │ Раунд 1/{game['rounds']}\nСделайте ход!",
            reply_markup=kb,
        )
    except Exception:
        pass


def _game_kb(gtype: str, game_id: int):
    if gtype == "rps":
        return pvp_rps_kb(game_id)
    elif gtype == "dice":
        return pvp_dice_kb(game_id)
    elif gtype == "flip":
        return pvp_flip_kb(game_id)
    elif gtype == "slots":
        return pvp_slots_kb(game_id)
    elif gtype == "ttt":
        return pvp_ttt_kb(game_id, "." * 9)
    return pvp_rps_kb(game_id)


# ══════════════════════════════════════════
#  КНБ (Камень-Ножницы-Бумага)
# ══════════════════════════════════════════
@router.callback_query(F.data.regexp(r"^rps_(\d+)_(rock|scissors|paper)$"))
async def rps_move(call: CallbackQuery):
    parts = call.data.split("_")
    game_id = int(parts[1])
    move = parts[2]
    uid = call.from_user.id

    game = await get_pvp_game(game_id)
    if not game or game["status"] != "active":
        return await call.answer("❌ Бой не активен", show_alert=True)
    if uid not in (game["creator_id"], game["opponent_id"]):
        return await call.answer("❌ Это не ваш бой", show_alert=True)

    # Проверка что уже ходил
    is_creator = uid == game["creator_id"]
    if is_creator and game["creator_move"]:
        return await call.answer("⏳ Ожидаем ход оппонента", show_alert=True)
    if not is_creator and game["opponent_move"]:
        return await call.answer("⏳ Ожидаем ход оппонента", show_alert=True)

    await set_pvp_move(game_id, uid, move)
    await call.answer("✅ Ход принят!")

    game = await get_pvp_game(game_id)
    if game["creator_move"] and game["opponent_move"]:
        await _resolve_rps_round(call, game)
    else:
        await call.message.edit_text(
            f"⏳ Бой #{game_id}\n\nВаш ход: {_move_emoji(move)}\nОжидаем оппонента...",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[]),
        )


def _move_emoji(m: str) -> str:
    return {"rock": "🪨", "scissors": "✂️", "paper": "📄"}.get(m, m)


def _rps_winner(m1: str, m2: str) -> int:
    """0 = ничья, 1 = m1 wins, 2 = m2 wins"""
    if m1 == m2:
        return 0
    wins = {"rock": "scissors", "scissors": "paper", "paper": "rock"}
    return 1 if wins[m1] == m2 else 2


async def _resolve_rps_round(call: CallbackQuery, game):
    gid = game["id"]
    cm = game["creator_move"]
    om = game["opponent_move"]
    result = _rps_winner(cm, om)

    cs = game["creator_score"]
    os_ = game["opponent_score"]
    rnd = game["round_num"]
    total_rounds = game["rounds"]

    if result == 1:
        cs += 1
    elif result == 2:
        os_ += 1

    text = (
        f"⚔️ Бой #{gid} │ Раунд {rnd}/{total_rounds}\n"
        f"══════════════════════\n\n"
        f"Игрок 1: {_move_emoji(cm)}\n"
        f"Игрок 2: {_move_emoji(om)}\n\n"
    )

    if result == 0:
        text += "🤝 Ничья в раунде!\n"
    elif result == 1:
        text += "🏆 Раунд: Игрок 1!\n"
    else:
        text += "🏆 Раунд: Игрок 2!\n"

    text += f"\n📊 Счёт: {cs} — {os_}\n"

    if rnd >= total_rounds:
        await _finish_game(call, game, cs, os_, text)
    else:
        await update_pvp_round(gid, cs, os_, rnd + 1)
        text += f"\n▶️ Следующий раунд {rnd + 1}/{total_rounds}!"
        kb = pvp_rps_kb(gid)
        try:
            await call.message.edit_text(text, reply_markup=kb)
        except Exception:
            pass
        try:
            other_id = game["opponent_id"] if call.from_user.id == game["creator_id"] else game["creator_id"]
            await call.bot.send_message(other_id, text, reply_markup=kb)
        except Exception:
            pass


# ══════════════════════════════════════════
#  КОСТИ
# ══════════════════════════════════════════
@router.callback_query(F.data.regexp(r"^dice_(\d+)_roll$"))
async def dice_roll(call: CallbackQuery):
    game_id = int(call.data.split("_")[1])
    uid = call.from_user.id
    game = await get_pvp_game(game_id)
    if not game or game["status"] != "active":
        return await call.answer("❌ Бой не активен", show_alert=True)
    if uid not in (game["creator_id"], game["opponent_id"]):
        return await call.answer("❌ Это не ваш бой", show_alert=True)

    is_creator = uid == game["creator_id"]
    if is_creator and game["creator_move"]:
        return await call.answer("⏳ Ожидаем оппонента", show_alert=True)
    if not is_creator and game["opponent_move"]:
        return await call.answer("⏳ Ожидаем оппонента", show_alert=True)

    roll = str(random.randint(1, 6))
    await set_pvp_move(game_id, uid, roll)
    await call.answer(f"🎲 Вы выбросили: {roll}")

    game = await get_pvp_game(game_id)
    if game["creator_move"] and game["opponent_move"]:
        await _resolve_dice_round(call, game)
    else:
        await call.message.edit_text(
            f"🎲 Бой #{game_id}\n\nВы бросили: {roll}\nОжидаем оппонента...",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[]),
        )


async def _resolve_dice_round(call, game):
    gid = game["id"]
    cm = int(game["creator_move"])
    om = int(game["opponent_move"])
    cs = game["creator_score"]
    os_ = game["opponent_score"]
    rnd = game["round_num"]
    total = game["rounds"]

    if cm > om:
        cs += 1
        result_text = "🏆 Раунд: Игрок 1!"
    elif om > cm:
        os_ += 1
        result_text = "🏆 Раунд: Игрок 2!"
    else:
        result_text = "🤝 Ничья в раунде!"

    text = (
        f"🎲 Бой #{gid} │ Раунд {rnd}/{total}\n"
        f"══════════════════════\n\n"
        f"Игрок 1: 🎲 {cm}\nИгрок 2: 🎲 {om}\n\n"
        f"{result_text}\n📊 Счёт: {cs} — {os_}\n"
    )

    if rnd >= total:
        await _finish_game(call, game, cs, os_, text)
    else:
        await update_pvp_round(gid, cs, os_, rnd + 1)
        text += f"\n▶️ Следующий раунд {rnd + 1}/{total}!"
        kb = pvp_dice_kb(gid)
        try:
            await call.message.edit_text(text, reply_markup=kb)
        except Exception:
            pass
        try:
            other_id = game["opponent_id"] if call.from_user.id == game["creator_id"] else game["creator_id"]
            await call.bot.send_message(other_id, text, reply_markup=kb)
        except Exception:
            pass


# ══════════════════════════════════════════
#  МОНЕТКА
# ══════════════════════════════════════════
@router.callback_query(F.data.regexp(r"^flip_(\d+)_(eagle|tails)$"))
async def flip_move(call: CallbackQuery):
    parts = call.data.split("_")
    game_id = int(parts[1])
    move = parts[2]
    uid = call.from_user.id
    game = await get_pvp_game(game_id)
    if not game or game["status"] != "active":
        return await call.answer("❌ Не активен", show_alert=True)
    if uid not in (game["creator_id"], game["opponent_id"]):
        return await call.answer("❌ Не ваш бой", show_alert=True)

    is_creator = uid == game["creator_id"]
    if is_creator and game["creator_move"]:
        return await call.answer("⏳", show_alert=True)
    if not is_creator and game["opponent_move"]:
        return await call.answer("⏳", show_alert=True)

    await set_pvp_move(game_id, uid, move)
    await call.answer("✅ Ход принят!")
    game = await get_pvp_game(game_id)
    if game["creator_move"] and game["opponent_move"]:
        await _resolve_flip_round(call, game)
    else:
        e = "🌕 Орёл" if move == "eagle" else "🌑 Решка"
        await call.message.edit_text(
            f"🪙 Бой #{game_id}\n\nВы: {e}\nОжидаем оппонента...",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[]),
        )


async def _resolve_flip_round(call, game):
    gid = game["id"]
    cm = game["creator_move"]
    om = game["opponent_move"]
    flip_result = random.choice(["eagle", "tails"])
    cs = game["creator_score"]
    os_ = game["opponent_score"]
    rnd = game["round_num"]
    total = game["rounds"]

    if cm == flip_result:
        cs += 1
    if om == flip_result:
        os_ += 1

    f_name = "🌕 Орёл" if flip_result == "eagle" else "🌑 Решка"
    text = (
        f"🪙 Бой #{gid} │ Раунд {rnd}/{total}\n"
        f"══════════════════════\n\n"
        f"Монета выпала: {f_name}\n"
        f"Игрок 1: {'🌕 Орёл' if cm == 'eagle' else '🌑 Решка'}\n"
        f"Игрок 2: {'🌕 Орёл' if om == 'eagle' else '🌑 Решка'}\n\n"
        f"📊 Счёт: {cs} — {os_}\n"
    )

    if rnd >= total:
        await _finish_game(call, game, cs, os_, text)
    else:
        await update_pvp_round(gid, cs, os_, rnd + 1)
        text += f"\n▶️ Следующий раунд {rnd + 1}/{total}!"
        kb = pvp_flip_kb(gid)
        try:
            await call.message.edit_text(text, reply_markup=kb)
        except Exception:
            pass
        try:
            other_id = game["opponent_id"] if call.from_user.id == game["creator_id"] else game["creator_id"]
            await call.bot.send_message(other_id, text, reply_markup=kb)
        except Exception:
            pass


# ══════════════════════════════════════════
#  СЛОТЫ
# ══════════════════════════════════════════
_SLOT_SYMBOLS = ["🍒", "🍊", "🍋", "🔔", "⭐", "7️⃣"]


@router.callback_query(F.data.regexp(r"^slots_(\d+)_spin$"))
async def slots_spin(call: CallbackQuery):
    game_id = int(call.data.split("_")[1])
    uid = call.from_user.id
    game = await get_pvp_game(game_id)
    if not game or game["status"] != "active":
        return await call.answer("❌ Не активен", show_alert=True)
    if uid not in (game["creator_id"], game["opponent_id"]):
        return await call.answer("❌ Не ваш бой", show_alert=True)

    is_creator = uid == game["creator_id"]
    if is_creator and game["creator_move"]:
        return await call.answer("⏳", show_alert=True)
    if not is_creator and game["opponent_move"]:
        return await call.answer("⏳", show_alert=True)

    result = [random.choice(_SLOT_SYMBOLS) for _ in range(3)]
    score = _calc_slot_score(result)
    move = f"{','.join(result)}:{score}"
    await set_pvp_move(game_id, uid, move)
    await call.answer(f"🎰 {' '.join(result)} = {score} очков")

    game = await get_pvp_game(game_id)
    if game["creator_move"] and game["opponent_move"]:
        await _resolve_slots_round(call, game)
    else:
        await call.message.edit_text(
            f"🎰 Бой #{game_id}\n\n{' '.join(result)} = {score} очков\nОжидаем оппонента...",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[]),
        )


def _calc_slot_score(symbols: list) -> int:
    if len(set(symbols)) == 1:
        return 100 if symbols[0] == "7️⃣" else 50
    if len(set(symbols)) == 2:
        return 20
    return random.randint(1, 10)


async def _resolve_slots_round(call, game):
    gid = game["id"]
    cm_parts = game["creator_move"].split(":")
    om_parts = game["opponent_move"].split(":")
    c_score = int(cm_parts[1])
    o_score = int(om_parts[1])
    c_symbols = cm_parts[0]
    o_symbols = om_parts[0]

    cs = game["creator_score"]
    os_ = game["opponent_score"]
    rnd = game["round_num"]
    total = game["rounds"]

    if c_score > o_score:
        cs += 1
        rt = "🏆 Раунд: Игрок 1!"
    elif o_score > c_score:
        os_ += 1
        rt = "🏆 Раунд: Игрок 2!"
    else:
        rt = "🤝 Ничья!"

    text = (
        f"🎰 Бой #{gid} │ Раунд {rnd}/{total}\n"
        f"══════════════════════\n\n"
        f"Игрок 1: {c_symbols.replace(',', ' ')} = {c_score}\n"
        f"Игрок 2: {o_symbols.replace(',', ' ')} = {o_score}\n\n"
        f"{rt}\n📊 Счёт: {cs} — {os_}\n"
    )

    if rnd >= total:
        await _finish_game(call, game, cs, os_, text)
    else:
        await update_pvp_round(gid, cs, os_, rnd + 1)
        text += f"\n▶️ Следующий раунд {rnd + 1}/{total}!"
        kb = pvp_slots_kb(gid)
        try:
            await call.message.edit_text(text, reply_markup=kb)
        except Exception:
            pass
        try:
            other_id = game["opponent_id"] if call.from_user.id == game["creator_id"] else game["creator_id"]
            await call.bot.send_message(other_id, text, reply_markup=kb)
        except Exception:
            pass


# ══════════════════════════════════════════
#  КРЕСТИКИ-НОЛИКИ
# ══════════════════════════════════════════
_TTT_WIN_LINES = [
    (0, 1, 2), (3, 4, 5), (6, 7, 8),  # rows
    (0, 3, 6), (1, 4, 7), (2, 5, 8),  # cols
    (0, 4, 8), (2, 4, 6),             # diags
]


def _ttt_check_winner(board: str):
    """Возвращает 'X', 'O' или None. Если ничья (все заняты и нет победителя) — 'draw'."""
    for a, b, c in _TTT_WIN_LINES:
        if board[a] == board[b] == board[c] and board[a] != ".":
            return board[a]
    if "." not in board:
        return "draw"
    return None


def _ttt_board_text(board: str) -> str:
    _sym = {"X": "❌", "O": "⭕", ".": "⬜"}
    lines = []
    for r in range(3):
        lines.append(" ".join(_sym[board[r * 3 + c]] for c in range(3)))
    return "\n".join(lines)


@router.callback_query(F.data.regexp(r"^ttt_(\d+)_(\d)$"))
async def ttt_move(call: CallbackQuery):
    parts = call.data.split("_")
    game_id = int(parts[1])
    cell = int(parts[2])
    uid = call.from_user.id

    game = await get_pvp_game(game_id)
    if not game or game["status"] != "active":
        return await call.answer("❌ Бой не активен", show_alert=True)
    if uid not in (game["creator_id"], game["opponent_id"]):
        return await call.answer("❌ Это не ваш бой", show_alert=True)

    board = game["creator_move"] or "." * 9
    turn = game["opponent_move"] or "X"  # "X" = ход creator, "O" = ход opponent

    is_creator = uid == game["creator_id"]
    # Проверяем чей ход
    if is_creator and turn != "X":
        return await call.answer("⏳ Ход оппонента!", show_alert=True)
    if not is_creator and turn != "O":
        return await call.answer("⏳ Ход создателя!", show_alert=True)

    if cell < 0 or cell > 8 or board[cell] != ".":
        return await call.answer("❌ Клетка занята!", show_alert=True)

    # Ставим символ
    sym = "X" if is_creator else "O"
    board = board[:cell] + sym + board[cell + 1:]
    next_turn = "O" if sym == "X" else "X"

    # Сохраняем состояние
    await set_pvp_move(game_id, game["creator_id"], board)
    await set_pvp_move(game_id, game["opponent_id"], next_turn)
    await call.answer("✅ Ход принят!")

    winner = _ttt_check_winner(board)
    gid = game_id
    bet_str = fnum(game["bet"])

    if winner:
        # Игра окончена
        board_text = _ttt_board_text(board)
        if winner == "draw":
            text = (
                f"❌⭕ Бой #{gid}\n══════════════════════\n\n"
                f"{board_text}\n\n"
                f"🤝 НИЧЬЯ! Ставки возвращены.\n"
                f"💰 Ставка: {bet_str} 💢"
            )
            await draw_pvp_game(gid)
            await log_activity(game["creator_id"], "pvp", f"PvP #{gid} TTT ничья")
            await log_activity(game["opponent_id"], "pvp", f"PvP #{gid} TTT ничья")
            kb = pvp_menu_kb()
            try:
                await call.message.edit_text(text, reply_markup=kb)
            except Exception:
                pass
            try:
                other_id = game["opponent_id"] if uid == game["creator_id"] else game["creator_id"]
                await call.bot.send_message(other_id, text, reply_markup=kb)
            except Exception:
                pass
        else:
            # winner = "X" or "O"
            winner_id = game["creator_id"] if winner == "X" else game["opponent_id"]
            loser_id = game["opponent_id"] if winner == "X" else game["creator_id"]
            prize = float(game["bet"]) * 2
            await finish_pvp_game(gid, winner_id)
            w_sym = "❌" if winner == "X" else "⭕"
            text = (
                f"❌⭕ Бой #{gid}\n══════════════════════\n\n"
                f"{board_text}\n\n"
                f"🎊 ПОБЕДИТЕЛЬ: {w_sym}!\n"
                f"💰 Выигрыш: {fnum(prize)} 💢"
            )
            await log_activity(winner_id, "pvp", f"PvP #{gid} TTT победа +{prize}")
            await log_activity(loser_id, "pvp", f"PvP #{gid} TTT поражение -{game['bet']}")
            await create_transaction("pvp", winner_id, user2_id=loser_id, amount=prize,
                                     details=f"Победа в PvP TTT #{gid}")
            kb = pvp_menu_kb()
            try:
                await call.message.edit_text(text, reply_markup=kb)
            except Exception:
                pass
            try:
                other_id = game["opponent_id"] if uid == game["creator_id"] else game["creator_id"]
                await call.bot.send_message(other_id, text, reply_markup=kb)
            except Exception:
                pass
    else:
        # Игра продолжается
        turn_sym = "❌" if next_turn == "X" else "⭕"
        text = (
            f"❌⭕ Бой #{gid}\n══════════════════════\n\n"
            f"{_ttt_board_text(board)}\n\n"
            f"Ход: {turn_sym}\n"
            f"💰 Ставка: {bet_str} 💢"
        )
        kb = pvp_ttt_kb(gid, board)
        try:
            await call.message.edit_text(text, reply_markup=kb)
        except Exception:
            pass
        try:
            other_id = game["opponent_id"] if uid == game["creator_id"] else game["creator_id"]
            await call.bot.send_message(other_id, text, reply_markup=kb)
        except Exception:
            pass


# ══════════════════════════════════════════
#  Финиш матча
# ══════════════════════════════════════════
async def _finish_game(call, game, cs, os_, text_prefix):
    gid = game["id"]
    bet = float(game["bet"])
    creator_id = game["creator_id"]
    opponent_id = game["opponent_id"]

    if cs > os_:
        winner_id = creator_id
        loser_id = opponent_id
        text_prefix += "\n🎊 ПОБЕДИТЕЛЬ: Игрок 1!"
    elif os_ > cs:
        winner_id = opponent_id
        loser_id = creator_id
        text_prefix += "\n🎊 ПОБЕДИТЕЛЬ: Игрок 2!"
    else:
        await draw_pvp_game(gid)
        text_prefix += "\n🤝 ИТОГ: НИЧЬЯ! Ставки возвращены."
        await log_activity(creator_id, "pvp", f"PvP #{gid} ничья {cs}-{os_}")
        await log_activity(opponent_id, "pvp", f"PvP #{gid} ничья {cs}-{os_}")
        kb = pvp_menu_kb()
        try:
            await call.message.edit_text(text_prefix, reply_markup=kb)
        except Exception:
            pass
        try:
            other_id = opponent_id if call.from_user.id == creator_id else creator_id
            await call.bot.send_message(other_id, text_prefix, reply_markup=kb)
        except Exception:
            pass
        return

    await finish_pvp_game(gid, winner_id)
    prize = bet * 2
    text_prefix += f"\n💰 Выигрыш: {fnum(prize)} 💢"
    await log_activity(winner_id, "pvp", f"PvP #{gid} победа +{prize}")
    await log_activity(loser_id, "pvp", f"PvP #{gid} поражение -{bet}")
    await create_transaction("pvp", winner_id, user2_id=loser_id, amount=prize,
                             details=f"Победа в PvP #{gid}")
    kb = pvp_menu_kb()
    try:
        await call.message.edit_text(text_prefix, reply_markup=kb)
    except Exception:
        pass
    try:
        other_id = opponent_id if call.from_user.id == creator_id else creator_id
        await call.bot.send_message(other_id, text_prefix, reply_markup=kb)
    except Exception:
        pass


# ── История боёв ──
@router.callback_query(F.data == "pvp_history")
async def pvp_history(call: CallbackQuery):
    uid = call.from_user.id
    await set_user_online(uid)

    # Открытые бои пользователя (ожидают оппонента)
    all_open = await get_open_pvp_games()
    my_open = [g for g in all_open if g[1] == uid]  # creator_id == uid

    history = await get_user_pvp_history(uid)

    if not my_open and not history:
        text = "📊 У вас ещё нет боёв."
        await call.message.edit_text(text, reply_markup=pvp_menu_kb())
        return await call.answer()

    lines = ["📊 МОИ БОИ\n══════════════════════\n"]
    kb_rows = []

    # Открытые бои
    if my_open:
        lines.append("⏳ <b>Ожидают оппонента:</b>")
        for g in my_open[:5]:
            gid, cid, bet, gtype, rounds = g
            type_name = _type_name(gtype)
            lines.append(f"#{gid} │ {type_name} x{rounds} │ {fnum(bet)}💢")
            kb_rows.append([InlineKeyboardButton(
                text=f"❌ Отменить бой #{gid}",
                callback_data=f"pvp_cancel_{gid}",
            )])
        lines.append("")

    # Завершённые бои
    if history:
        lines.append("📋 <b>Завершённые:</b>")
        for g in history:
            gid, cid, oid, bet, gtype, status, winner, rounds = g
            type_name = _type_name(gtype)
            if status == "draw":
                result = "🤝 Ничья"
            elif winner == uid:
                result = "✅ Победа"
            else:
                result = "❌ Проигрыш"
            lines.append(f"#{gid} │ {type_name} x{rounds} │ {fnum(bet)}💢 │ {result}")

    # Кнопки отмены + меню PvP
    kb_rows.append([InlineKeyboardButton(text="🔍 Найти", callback_data="pvp_find"),
                     InlineKeyboardButton(text="⚔️ Создать", callback_data="pvp_create")])
    kb_rows.append([InlineKeyboardButton(text="⬅️ Мини-игры", callback_data="minigames_menu")])

    await call.message.edit_text("\n".join(lines), parse_mode="HTML",
                                  reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))
    await call.answer()


# ── Отмена боя ──
@router.callback_query(F.data.startswith("pvp_cancel_"))
async def pvp_cancel(call: CallbackQuery):
    uid = call.from_user.id
    game_id = int(call.data.split("_")[2])
    game = await get_pvp_game(game_id)
    if not game or game["creator_id"] != uid or game["status"] != "open":
        return await call.answer("⚠️ Бой не найден или уже начат.", show_alert=True)
    await cancel_pvp_game(game_id)
    await call.answer("✅ Бой отменён, ставка возвращена.", show_alert=True)
    # Обновить список
    await pvp_history(call)


# ── noop ──
@router.callback_query(F.data == "noop")
async def noop(call: CallbackQuery):
    await call.answer()

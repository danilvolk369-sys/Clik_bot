# ======================================================
# PVP — Бои 1 на 1 (ручные, Bo1 / Bo3)
# ======================================================

import random
import aiosqlite
from datetime import datetime

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from config import DB_NAME
from states import PVPStates
from database import get_user, spend_clicks, update_clicks, invalidate_cache, create_transaction
from keyboards import (
    pvp_menu_kb, pvp_create_type_kb, pvp_bet_kb, pvp_rps_kb,
    pvp_rounds_kb, pvp_dice_kb, pvp_flip_kb, pvp_slots_kb,
)
from handlers.common import fnum

router = Router()

# ─── Константы ───────────────────────────────────────────
_GAME_NAMES = {
    "rps":   "✂️ Камень-Ножницы-Бумага",
    "dice":  "🎲 Кости",
    "flip":  "🪙 Монетка",
    "slots": "🎰 Слоты",
}
_GAME_SHORT = {
    "rps": "✂️ КНБ", "dice": "🎲 Кости",
    "flip": "🪙 Монетка", "slots": "🎰 Слоты",
}
_MIN_BET = 100

_RPS_EMOJI = {"rock": "🪨 Камень", "scissors": "✂️ Ножницы", "paper": "📄 Бумага"}
_RPS_WINS  = {"rock": "scissors", "scissors": "paper", "paper": "rock"}
_DICE_FACE = {1: "⚀", 2: "⚁", 3: "⚂", 4: "⚃", 5: "⚄", 6: "⚅"}
_FLIP_EMOJI = {"eagle": "🌕 Орёл", "tails": "🌑 Решка"}
_SLOT_SYMBOLS = ["🍒", "🍋", "🍊", "🍇", "💎", "7️⃣", "🔔"]


def _round_text(r: int) -> str:
    return "Bo3 (до 2 побед)" if r == 3 else "Bo1 (1 раунд)"


# ════════════════════════════════════════════════════════════
#  МЕНЮ PvP
# ════════════════════════════════════════════════════════════
@router.callback_query(F.data == "pvp_menu")
async def show_pvp_menu(call: CallbackQuery, state: FSMContext = None):
    if state:
        await state.clear()
    async with aiosqlite.connect(DB_NAME) as db:
        row = await (await db.execute(
            "SELECT COUNT(*) FROM pvp_games WHERE status='open'"
        )).fetchone()
        open_cnt = row[0] if row else 0
    text = (
        "⚔️ PVP — БОИ 1 НА 1\n"
        "══════════════════════\n\n"
        "┠🔍 Найти бои — список открытых\n"
        "┠⚔️ Создать бой — бросить вызов\n"
        "┗📊 Мои бои — история сражений\n\n"
        f"🟢 Открытых боёв: {open_cnt}\n\n"
        "══════════════════════"
    )
    try:
        await call.message.edit_text(text, reply_markup=pvp_menu_kb())
    except Exception:
        await call.message.answer(text, reply_markup=pvp_menu_kb())
    await call.answer()


# ════════════════════════════════════════════════════════════
#  🔍 НАЙТИ БОИ
# ════════════════════════════════════════════════════════════
@router.callback_query(F.data == "pvp_find")
async def pvp_find(call: CallbackQuery):
    uid = call.from_user.id
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            "SELECT g.id, g.creator_id, g.bet, g.game_type, g.rounds, u.username "
            "FROM pvp_games g LEFT JOIN users u ON u.user_id=g.creator_id "
            "WHERE g.status='open' ORDER BY g.id DESC LIMIT 15"
        )
        games = await cur.fetchall()

    if not games:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⚔️ Создать бой", callback_data="pvp_create")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="pvp_menu")],
        ])
        await call.message.edit_text(
            "🔍 ОТКРЫТЫЕ БОИ\n"
            "══════════════════════\n\n"
            "😔 Нет открытых боёв.\n"
            "Создайте свой!\n\n"
            "══════════════════════",
            reply_markup=kb,
        )
        return await call.answer()

    text = "🔍 ОТКРЫТЫЕ БОИ\n══════════════════════\n\n"
    for gid, cid, bet, gt, rnds, uname in games:
        name = f"@{uname}" if uname else f"ID:{cid}"
        icon = _GAME_SHORT.get(gt, "❓")
        own = " (ваш)" if cid == uid else ""
        bo = "Bo3" if (rnds or 1) == 3 else "Bo1"
        text += f"┠{icon} │ {int(bet):,} 💢 │ {bo} │ {name}{own}\n"

    text += "\n══════════════════════\nНажмите, чтобы вступить:"

    kb = []
    for gid, cid, bet, gt, rnds, uname in games:
        icon = _GAME_SHORT.get(gt, "❓")
        bo = "Bo3" if (rnds or 1) == 3 else "Bo1"
        kb.append([InlineKeyboardButton(
            text=f"⚔️ {icon} │ {int(bet):,} 💢 │ {bo} │ #{gid}",
            callback_data=f"pvp_join_{gid}",
        )])
    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="pvp_menu")])

    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await call.answer()


# ════════════════════════════════════════════════════════════
#  ⚔️ СОЗДАТЬ — тип → раунды → ставка
# ════════════════════════════════════════════════════════════
@router.callback_query(F.data == "pvp_create")
async def pvp_create(call: CallbackQuery, state: FSMContext):
    await state.clear()
    user = await get_user(call.from_user.id)
    if not user:
        return await call.answer("❌ /start", show_alert=True)
    text = (
        "⚔️ СОЗДАТЬ БОЙ\n"
        "══════════════════════\n\n"
        "Выберите тип игры:\n\n"
        "┠✂️ КНБ — Камень-Ножницы-Бумага\n"
        "┠🎲 Кости — бросьте кости\n"
        "┠🪙 Монетка — орёл или решка\n"
        "┗🎰 Слоты — крутите барабан\n\n"
        "══════════════════════"
    )
    await call.message.edit_text(text, reply_markup=pvp_create_type_kb())
    await call.answer()


@router.callback_query(F.data.startswith("pvp_type_"))
async def pvp_type_chosen(call: CallbackQuery, state: FSMContext):
    gtype = call.data.replace("pvp_type_", "")
    await state.update_data(pvp_type=gtype)
    name = _GAME_NAMES.get(gtype, "❓")
    text = (
        "🔢 ФОРМАТ БОЯ\n"
        "══════════════════════\n\n"
        f"┠🎮 Игра: {name}\n\n"
        "Выберите количество раундов:\n\n"
        "┠1️⃣ Bo1 — один раунд решает\n"
        "┗3️⃣ Bo3 — до двух побед\n\n"
        "══════════════════════"
    )
    await call.message.edit_text(text, reply_markup=pvp_rounds_kb())
    await call.answer()


@router.callback_query(F.data.startswith("pvp_rounds_"))
async def pvp_rounds_chosen(call: CallbackQuery, state: FSMContext):
    rounds = int(call.data.replace("pvp_rounds_", ""))
    await state.update_data(pvp_rounds=rounds)
    data = await state.get_data()
    gtype = data.get("pvp_type", "rps")
    user = await get_user(call.from_user.id)
    balance = user["clicks"] if user else 0
    name = _GAME_NAMES.get(gtype, "❓")
    text = (
        "💰 СТАВКА\n"
        "══════════════════════\n\n"
        f"┠🎮 Игра: {name}\n"
        f"┠🔢 Формат: {_round_text(rounds)}\n"
        f"┗💳 Баланс: {fnum(balance)} 💢\n\n"
        f"Минимальная ставка: {_MIN_BET} 💢\n\n"
        "══════════════════════\n"
        "Выберите сумму или введите свою:"
    )
    await call.message.edit_text(text, reply_markup=pvp_bet_kb())
    await call.answer()


# ─── Быстрая ставка ───
@router.callback_query(F.data.regexp(r"^pvp_bet_\d+$"))
async def pvp_quick_bet(call: CallbackQuery, state: FSMContext):
    bet = int(call.data.replace("pvp_bet_", ""))
    await _create_game(call, state, bet)


# ─── Своя сумма ───
@router.callback_query(F.data == "pvp_bet_custom")
async def pvp_custom_bet(call: CallbackQuery, state: FSMContext):
    await state.set_state(PVPStates.waiting_bet)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="pvp_create")],
    ])
    await call.message.edit_text(
        f"✏️ СВОЯ СТАВКА\n"
        f"══════════════════════\n\n"
        f"Введите сумму (мин. {_MIN_BET} 💢):",
        reply_markup=kb,
    )
    await call.answer()


@router.message(PVPStates.waiting_bet)
async def pvp_manual_bet(message: Message, state: FSMContext):
    txt = (message.text or "").strip().replace(",", ".")
    try:
        bet = int(float(txt))
        assert bet >= _MIN_BET
    except (ValueError, AssertionError):
        return await message.answer(f"❌ Введите число не менее {_MIN_BET}:")
    await _create_game_msg(message, state, bet)


# ─── Создание (callback) ───
async def _create_game(call: CallbackQuery, state: FSMContext, bet: int):
    uid = call.from_user.id
    user = await get_user(uid)
    if not user or user["clicks"] < bet:
        return await call.answer("❌ Недостаточно 💢!", show_alert=True)
    data = await state.get_data()
    gtype = data.get("pvp_type", "rps")
    rounds = data.get("pvp_rounds", 1)
    if not await spend_clicks(uid, bet):
        return await call.answer("❌ Недостаточно 💢!", show_alert=True)
    gid = await _insert_game(uid, bet, gtype, rounds)
    await state.clear()
    name = _GAME_NAMES.get(gtype, "❓")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚫 Отменить бой", callback_data=f"pvp_cancel_{gid}")],
        [InlineKeyboardButton(text="🔍 Все бои", callback_data="pvp_find")],
        [InlineKeyboardButton(text="⬅️ В меню", callback_data="pvp_menu")],
    ])
    text = (
        "✅ БОЙ СОЗДАН!\n"
        "══════════════════════\n\n"
        f"┠🆔 Бой: #{gid}\n"
        f"┠🎮 Игра: {name}\n"
        f"┠🔢 Формат: {_round_text(rounds)}\n"
        f"┠💰 Ставка: {bet:,} 💢\n"
        f"┗⏳ Ожидание противника...\n\n"
        "══════════════════════"
    )
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer("✅ Бой создан!", show_alert=True)


# ─── Создание (message) ───
async def _create_game_msg(message: Message, state: FSMContext, bet: int):
    uid = message.from_user.id
    user = await get_user(uid)
    if not user or user["clicks"] < bet:
        return await message.answer("❌ Недостаточно 💢!")
    data = await state.get_data()
    gtype = data.get("pvp_type", "rps")
    rounds = data.get("pvp_rounds", 1)
    if not await spend_clicks(uid, bet):
        return await message.answer("❌ Недостаточно 💢!")
    gid = await _insert_game(uid, bet, gtype, rounds)
    await state.clear()
    name = _GAME_NAMES.get(gtype, "❓")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚫 Отменить бой", callback_data=f"pvp_cancel_{gid}")],
        [InlineKeyboardButton(text="🔍 Все бои", callback_data="pvp_find")],
        [InlineKeyboardButton(text="⬅️ В меню", callback_data="pvp_menu")],
    ])
    text = (
        "✅ БОЙ СОЗДАН!\n"
        "══════════════════════\n\n"
        f"┠🆔 Бой: #{gid}\n"
        f"┠🎮 Игра: {name}\n"
        f"┠🔢 Формат: {_round_text(rounds)}\n"
        f"┠💰 Ставка: {bet:,} 💢\n"
        f"┗⏳ Ожидание противника...\n\n"
        "══════════════════════"
    )
    await message.answer(text, reply_markup=kb)


async def _insert_game(creator_id: int, bet: int, gtype: str, rounds: int) -> int:
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            "INSERT INTO pvp_games "
            "(creator_id, bet, game_type, rounds, round_num, "
            "creator_score, opponent_score, status, created_at) "
            "VALUES (?,?,?,?,1,0,0,'open',?)",
            (creator_id, bet, gtype, rounds, datetime.now().isoformat()),
        )
        gid = cur.lastrowid
        await db.commit()
    return gid


# ════════════════════════════════════════════════════════════
#  🚫 ОТМЕНА БОЯ
# ════════════════════════════════════════════════════════════
@router.callback_query(F.data.startswith("pvp_cancel_"))
async def pvp_cancel(call: CallbackQuery):
    gid = int(call.data.split("_")[-1])
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            "SELECT creator_id, bet, status FROM pvp_games WHERE id=?", (gid,)
        )
        g = await cur.fetchone()
        if not g or g[0] != call.from_user.id or g[2] != "open":
            return await call.answer("❌ Нельзя отменить", show_alert=True)
        await db.execute("DELETE FROM pvp_games WHERE id=?", (gid,))
        await db.execute(
            "UPDATE users SET clicks=clicks+? WHERE user_id=?",
            (g[1], call.from_user.id),
        )
        await db.commit()
    invalidate_cache(call.from_user.id)
    await call.answer("✅ Ставка возвращена!", show_alert=True)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚔️ Создать бой", callback_data="pvp_create")],
        [InlineKeyboardButton(text="🔍 Все бои", callback_data="pvp_find")],
        [InlineKeyboardButton(text="⬅️ В меню", callback_data="pvp_menu")],
    ])
    await call.message.edit_text(
        "🚫 БОЙ ОТМЕНЁН\n"
        "══════════════════════\n\n"
        f"┠🆔 Бой: #{gid}\n"
        f"┗💰 Ставка {int(g[1]):,} 💢 возвращена\n\n"
        "══════════════════════",
        reply_markup=kb,
    )


# ════════════════════════════════════════════════════════════
#  ⚔️ ВСТУПИТЬ В БОЙ
# ════════════════════════════════════════════════════════════
@router.callback_query(F.data.startswith("pvp_join_"))
async def pvp_join(call: CallbackQuery):
    gid = int(call.data.split("_")[-1])
    uid = call.from_user.id

    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            "SELECT creator_id, bet, game_type, status, rounds "
            "FROM pvp_games WHERE id=?", (gid,),
        )
        g = await cur.fetchone()

    if not g or g[3] != "open":
        return await call.answer("❌ Бой недоступен", show_alert=True)
    if g[0] == uid:
        return await call.answer("❌ Нельзя играть с собой!", show_alert=True)

    creator_id, bet, gtype, _, rounds = g
    rounds = rounds or 1
    user = await get_user(uid)
    if not user or user["clicks"] < bet:
        return await call.answer(f"❌ Нужно {int(bet):,} 💢!", show_alert=True)
    if not await spend_clicks(uid, bet):
        return await call.answer("❌ Недостаточно 💢!", show_alert=True)

    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "UPDATE pvp_games SET opponent_id=?, status='playing' WHERE id=?",
            (uid, gid),
        )
        await db.commit()

    # Отправляем игровое поле обоим
    await _send_round_board(call.bot, gid, gtype, rounds,
                            creator_id, uid, bet, 1, 0, 0)
    await call.answer("⚔️ Бой начался!", show_alert=True)


# ════════════════════════════════════════════════════════════
#  📩 ИГРОВОЕ ПОЛЕ (отправка обоим)
# ════════════════════════════════════════════════════════════
async def _send_round_board(bot, gid, gtype, rounds, p1, p2, bet,
                            round_num, s1, s2):
    total = int(bet * 2)
    name = _GAME_NAMES.get(gtype, "❓")
    bo = _round_text(rounds)

    hdr = (
        f"⚔️ БОЙ #{gid}\n"
        f"══════════════════════\n\n"
        f"┠🎮 {name}\n"
        f"┠🔢 {bo}\n"
        f"┠💰 Банк: {total:,} 💢\n"
    )
    if rounds == 3:
        hdr += f"┠🏅 Счёт: {s1} : {s2}\n"
    hdr += f"┗🔄 Раунд {round_num}\n\n"

    tips = {
        "rps":   "Выберите ваш ход:",
        "dice":  "Нажмите, чтобы бросить кости:",
        "flip":  "Выберите сторону монетки:",
        "slots": "Нажмите, чтобы крутить барабан:",
    }
    hdr += tips.get(gtype, "") + "\n\n══════════════════════"

    kbs = {
        "rps":   pvp_rps_kb(gid),
        "dice":  pvp_dice_kb(gid),
        "flip":  pvp_flip_kb(gid),
        "slots": pvp_slots_kb(gid),
    }
    kb = kbs.get(gtype, pvp_rps_kb(gid))

    for pid in (p1, p2):
        try:
            await bot.send_message(pid, hdr, reply_markup=kb)
        except Exception:
            pass


# ════════════════════════════════════════════════════════════
#  ХОДЫ — все типы игр
# ════════════════════════════════════════════════════════════

# ✂️ КНБ
@router.callback_query(F.data.regexp(r"^rps_\d+_(rock|scissors|paper)$"))
async def rps_move(call: CallbackQuery):
    parts = call.data.split("_")
    await _process_move(call, int(parts[1]), parts[2])


# 🎲 Кости
@router.callback_query(F.data.regexp(r"^dice_\d+_roll$"))
async def dice_roll(call: CallbackQuery):
    gid = int(call.data.split("_")[1])
    await _process_move(call, gid, str(random.randint(1, 6)))


# 🪙 Монетка
@router.callback_query(F.data.regexp(r"^flip_\d+_(eagle|tails)$"))
async def flip_choice(call: CallbackQuery):
    parts = call.data.split("_")
    await _process_move(call, int(parts[1]), parts[2])


# 🎰 Слоты
@router.callback_query(F.data.regexp(r"^slots_\d+_spin$"))
async def slots_spin(call: CallbackQuery):
    gid = int(call.data.split("_")[1])
    syms = [random.choice(_SLOT_SYMBOLS) for _ in range(3)]
    await _process_move(call, gid, "|".join(syms))


# ════════════════════════════════════════════════════════════
#  🔄 ОБЩАЯ ЛОГИКА ХОДА
# ════════════════════════════════════════════════════════════
async def _process_move(call: CallbackQuery, game_id: int, move: str):
    uid = call.from_user.id

    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM pvp_games WHERE id=?", (game_id,))
        g = await cur.fetchone()

    if not g or g["status"] != "playing":
        return await call.answer("❌ Игра недоступна", show_alert=True)

    cid, oid = g["creator_id"], g["opponent_id"]

    if uid == cid:
        if g["creator_move"]:
            return await call.answer("⏳ Вы уже сделали ход!", show_alert=True)
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute(
                "UPDATE pvp_games SET creator_move=? WHERE id=?", (move, game_id)
            )
            await db.commit()
    elif uid == oid:
        if g["opponent_move"]:
            return await call.answer("⏳ Вы уже сделали ход!", show_alert=True)
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute(
                "UPDATE pvp_games SET opponent_move=? WHERE id=?", (move, game_id)
            )
            await db.commit()
    else:
        return await call.answer("❌ Вы не участник", show_alert=True)

    # Показываем подтверждение хода
    mt = _move_display(g["game_type"], move)
    await call.answer(f"✅ {mt}", show_alert=True)
    try:
        await call.message.edit_text(
            f"⏳ ХОД СДЕЛАН\n"
            f"══════════════════════\n\n"
            f"┠🆔 Бой: #{game_id}\n"
            f"┠✅ {mt}\n"
            f"┗⏳ Ожидание соперника...\n\n"
            f"══════════════════════"
        )
    except Exception:
        pass

    # Проверяем оба хода (перечитываем свежие данные)
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM pvp_games WHERE id=?", (game_id,))
        fresh = await cur.fetchone()

    if fresh["creator_move"] and fresh["opponent_move"]:
        await _resolve_round(call.bot, game_id)


def _move_display(gtype: str, move: str) -> str:
    if gtype == "rps":
        return _RPS_EMOJI.get(move, move)
    if gtype == "dice":
        n = int(move)
        return f"Вы выбросили {_DICE_FACE.get(n, '?')} {n}"
    if gtype == "flip":
        return f"Ваш выбор: {_FLIP_EMOJI.get(move, move)}"
    # slots
    return f"Ваши слоты: {' '.join(move.split('|'))}"


# ════════════════════════════════════════════════════════════
#  ⚖️ РЕЗУЛЬТАТ РАУНДА
# ════════════════════════════════════════════════════════════
async def _resolve_round(bot, game_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM pvp_games WHERE id=?", (game_id,))
        g = await cur.fetchone()

    if not g or g["status"] != "playing":
        return
    if not g["creator_move"] or not g["opponent_move"]:
        return

    cid      = g["creator_id"]
    oid      = g["opponent_id"]
    c_move   = g["creator_move"]
    o_move   = g["opponent_move"]
    bet      = g["bet"]
    gtype    = g["game_type"]
    rounds   = g["rounds"] or 1
    rnd      = g["round_num"] or 1
    s1       = g["creator_score"] or 0
    s2       = g["opponent_score"] or 0
    total    = int(bet * 2)
    need     = 2 if rounds == 3 else 1

    # Определяем победителя раунда + текст ходов
    winner, moves_text = _resolve_by_type(gtype, c_move, o_move)

    # Шапка
    name = _GAME_NAMES.get(gtype, "❓")
    hdr = (
        f"⚔️ БОЙ #{game_id} — РАУНД {rnd}\n"
        f"══════════════════════\n\n"
        f"┠🎮 {name}\n"
        f"┠💰 Банк: {total:,} 💢\n"
    )
    if rounds == 3:
        hdr += f"┠🏅 Счёт: {s1} : {s2}\n"
    hdr += f"┗🔄 Раунд {rnd}\n\n{moves_text}\n"

    # ──── НИЧЬЯ В РАУНДЕ → переигровка ────
    if winner == "draw":
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute(
                "UPDATE pvp_games SET creator_move=NULL, opponent_move=NULL "
                "WHERE id=?", (game_id,),
            )
            await db.commit()

        draw_txt = hdr + (
            "══════════════════════\n\n"
            "🤝 Ничья в раунде! Переигровка...\n\n"
            "══════════════════════"
        )
        for pid in (cid, oid):
            try:
                await bot.send_message(pid, draw_txt)
            except Exception:
                pass
        await _send_round_board(bot, game_id, gtype, rounds,
                                cid, oid, bet, rnd, s1, s2)
        return

    # ──── Есть победитель раунда ────
    if winner == "creator":
        s1 += 1
    else:
        s2 += 1

    game_over = (s1 >= need or s2 >= need)

    if game_over:
        # ──── МАТЧ ОКОНЧЕН ────
        if s1 > s2:
            match_winner = cid
        else:
            match_winner = oid

        await update_clicks(match_winner, total)

        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute(
                "UPDATE pvp_games SET status='done', winner_id=?, "
                "creator_score=?, opponent_score=?, "
                "creator_move=NULL, opponent_move=NULL WHERE id=?",
                (match_winner, s1, s2, game_id),
            )
            await db.commit()

        # Чек транзакции
        loser_id = oid if match_winner == cid else cid
        gname = _GAME_SHORT.get(gtype, gtype)
        await create_transaction(
            "pvp", match_winner, loser_id, float(total),
            f"{gname} ∙ {s1}:{s2} ∙ Победа", ref_id=game_id,
        )
        await create_transaction(
            "pvp", loser_id, match_winner, float(bet),
            f"{gname} ∙ {s2 if loser_id == oid else s1}:{s1 if loser_id == oid else s2} ∙ Поражение",
            ref_id=game_id,
        )

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⚔️ Ещё бой", callback_data="pvp_create")],
            [InlineKeyboardButton(text="⬅️ В меню", callback_data="pvp_menu")],
        ])

        for pid in (cid, oid):
            won = (pid == match_winner)
            role = f"🏆 Вы победили! +{total:,} 💢" if won else "😞 Вы проиграли."

            fin = hdr + "══════════════════════\n\n"
            if rounds == 3:
                fin += f"🏅 Итог: {s1} : {s2}\n"
            fin += f"{role}\n\n══════════════════════"

            try:
                await bot.send_message(pid, fin, reply_markup=kb)
            except Exception:
                pass
    else:
        # ──── СЛЕДУЮЩИЙ РАУНД ────
        new_rnd = rnd + 1
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute(
                "UPDATE pvp_games SET round_num=?, creator_score=?, "
                "opponent_score=?, creator_move=NULL, opponent_move=NULL "
                "WHERE id=?",
                (new_rnd, s1, s2, game_id),
            )
            await db.commit()

        rw = "Игрок 1 ✅" if winner == "creator" else "Игрок 2 ✅"
        mid = hdr + (
            "══════════════════════\n\n"
            f"✅ Раунд {rnd}: {rw}\n"
            f"🏅 Счёт: {s1} : {s2}\n\n"
            "Следующий раунд...\n\n"
            "══════════════════════"
        )
        for pid in (cid, oid):
            try:
                await bot.send_message(pid, mid)
            except Exception:
                pass

        await _send_round_board(bot, game_id, gtype, rounds,
                                cid, oid, bet, new_rnd, s1, s2)


# ─── Определение победителя раунда по типу ───
def _resolve_by_type(gtype: str, c_move: str, o_move: str):
    """Возвращает (winner: str, moves_text: str)"""

    if gtype == "rps":
        txt = (
            f"   Игрок 1: {_RPS_EMOJI[c_move]}\n"
            f"   Игрок 2: {_RPS_EMOJI[o_move]}\n\n"
        )
        if c_move == o_move:
            return "draw", txt
        return ("creator" if _RPS_WINS[c_move] == o_move else "opponent"), txt

    if gtype == "dice":
        cn, on = int(c_move), int(o_move)
        txt = (
            f"   Игрок 1: {_DICE_FACE[cn]} → {cn}\n"
            f"   Игрок 2: {_DICE_FACE[on]} → {on}\n\n"
        )
        if cn > on:
            return "creator", txt
        if on > cn:
            return "opponent", txt
        return "draw", txt

    if gtype == "flip":
        coin = random.choice(["eagle", "tails"])
        txt = (
            f"   Игрок 1: {_FLIP_EMOJI[c_move]}\n"
            f"   Игрок 2: {_FLIP_EMOJI[o_move]}\n"
            f"   🪙 Монета: {_FLIP_EMOJI[coin]}\n\n"
        )
        c_ok = (c_move == coin)
        o_ok = (o_move == coin)
        if c_ok and not o_ok:
            return "creator", txt
        if o_ok and not c_ok:
            return "opponent", txt
        return "draw", txt

    # slots
    c_disp = " ".join(c_move.split("|"))
    o_disp = " ".join(o_move.split("|"))
    c_sc = _slot_score(c_move)
    o_sc = _slot_score(o_move)
    txt = (
        f"   Игрок 1: {c_disp}\n"
        f"   Игрок 2: {o_disp}\n\n"
    )
    if c_sc > o_sc:
        return "creator", txt
    if o_sc > c_sc:
        return "opponent", txt
    return "draw", txt


def _slot_score(move: str) -> int:
    """3 одинаковых → 3, пара → 2, все разные → 1."""
    parts = move.split("|")
    unique = len(set(parts))
    if unique == 1:
        return 3
    if unique == 2:
        return 2
    return 1


# ════════════════════════════════════════════════════════════
#  📊 ИСТОРИЯ БОЁВ
# ════════════════════════════════════════════════════════════
@router.callback_query(F.data == "pvp_history")
async def pvp_history(call: CallbackQuery):
    uid = call.from_user.id

    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            "SELECT id, creator_id, opponent_id, bet, game_type, "
            "status, winner_id, rounds, creator_score, opponent_score "
            "FROM pvp_games "
            "WHERE (creator_id=? OR opponent_id=?) AND status IN ('done','draw') "
            "ORDER BY id DESC LIMIT 10",
            (uid, uid),
        )
        games = await cur.fetchall()

        cur2 = await db.execute(
            "SELECT "
            "COUNT(*), "
            "SUM(CASE WHEN winner_id=? THEN 1 ELSE 0 END), "
            "SUM(CASE WHEN status='draw' THEN 1 ELSE 0 END), "
            "SUM(CASE WHEN winner_id IS NOT NULL AND winner_id!=? "
            "AND status='done' THEN 1 ELSE 0 END) "
            "FROM pvp_games "
            "WHERE (creator_id=? OR opponent_id=?) AND status IN ('done','draw')",
            (uid, uid, uid, uid),
        )
        stats = await cur2.fetchone()

    total  = stats[0] or 0
    wins   = stats[1] or 0
    draws  = stats[2] or 0
    losses = stats[3] or 0
    wr = (wins / total * 100) if total > 0 else 0

    text = (
        "📊 МОИ БОИ\n"
        "══════════════════════\n\n"
        f"┠📈 Всего: {total}\n"
        f"┠🏆 Побед: {wins}\n"
        f"┠🤝 Ничьих: {draws}\n"
        f"┠😞 Поражений: {losses}\n"
        f"┗📊 Винрейт: {wr:.1f}%\n\n"
    )

    if games:
        text += "ПОСЛЕДНИЕ БОИ:\n══════════════════════\n\n"
        for gid, cid_g, oid_g, bet_g, gt, st, w, rnds, cs, os_ in games:
            icon = _GAME_SHORT.get(gt, "❓")
            if st == "draw":
                r = "🤝"
            elif w == uid:
                r = "🏆"
            else:
                r = "😞"
            bo = "Bo3" if (rnds or 1) == 3 else "Bo1"
            sc = f" ({cs or 0}:{os_ or 0})" if (rnds or 1) == 3 else ""
            text += f"┠{r} #{gid} │ {icon} │ {int(bet_g):,} 💢 │ {bo}{sc}\n"
        text += "\n"

    text += "══════════════════════"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚔️ Создать бой", callback_data="pvp_create")],
        [InlineKeyboardButton(text="🔍 Найти бои", callback_data="pvp_find")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="pvp_menu")],
    ])
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()

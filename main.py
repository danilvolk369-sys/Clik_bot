# ======================================================
# MAIN — Точка входа «КликТохн» v1.0.1
# ======================================================
import asyncio
import logging
import os
import random
import shutil
from datetime import datetime as _dtm

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import TOKEN, VERSION, OWNER_ID, NFT_RARITIES, NFT_RARITY_EMOJI, DB_NAME, SEED_DB
from database import (
    init_db, get_expired_active_events, finish_event_with_winner,
    get_event_participants, create_nft_template, grant_nft_to_user,
    get_event, get_active_events, cancel_event, count_event_participants,
    save_auction_message, get_auction_messages, delete_auction_messages,
    get_all_user_ids,
)
from handlers import all_routers

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Хранилище для уже отправленных оповещений таймера
_timer_alerts_sent: dict[int, set[str]] = {}


def _fmt_num(n) -> str:
    if n is None:
        return "0"
    val = float(n)
    if val == 0:
        return "0"
    if val >= 1_000_000:
        return f"{val/1_000_000:,.2f}M".replace(",", ".")
    if val >= 1_000:
        return f"{val:,.0f}".replace(",", ".")
    if val == int(val):
        return str(int(val))
    return f"{val:.2f}"


def _time_left_str(ends_at: str) -> str:
    try:
        end = _dtm.fromisoformat(ends_at)
        delta = (end - _dtm.now()).total_seconds()
        if delta <= 0:
            return "⏰ Завершён"
        if delta < 60:
            return f"⏱ {int(delta)} сек"
        m = int(delta // 60)
        s = int(delta % 60)
        return f"⏱ {m} мин {s:02d} сек"
    except Exception:
        return "⏱ ?"


async def _build_auction_text(ev, include_timer=True) -> str:
    """Генерирует текст аукциона для живого обновления."""
    eid = ev["id"]
    parts = await get_event_participants(eid)
    p_count = len(parts)
    rn = ev["nft_rarity"] if isinstance(ev["nft_rarity"], str) else "Обычный"
    emoji = NFT_RARITY_EMOJI.get(rn, "🎨")
    timer = _time_left_str(ev["ends_at"]) if include_timer and ev["ends_at"] else ""

    _medals = ["🥇", "🥈", "🥉"]
    top_lines = []
    for i, p in enumerate(parts[:10], 1):
        p_uid = p[0] if isinstance(p, tuple) else p["user_id"]
        p_bid = p[1] if isinstance(p, tuple) else p["bid_amount"]
        p_name = p[2] if isinstance(p, tuple) else (p["username"] if p["username"] else "?")
        medal = _medals[i - 1] if i <= 3 else f"{i}."
        top_lines.append(f"  {medal} @{p_name or '???'} (<code>{p_uid}</code>) — {_fmt_num(p_bid)} 💢")
    top_text = "\n".join(top_lines) if top_lines else "  Пока нет участников"

    warning = ""
    if p_count < 2:
        warning = "\n⚠️ <i>Нужно мин. 2 участника (иначе — отмена и возврат)</i>\n"

    try:
        col = ev['nft_collection'] or ''
    except (KeyError, IndexError):
        col = ''
    col_line = f"  📂 Коллекция: <b>{col}</b>\n" if col else ""

    return (
        f"🎪 <b>НОВЫЙ АУКЦИОН!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"  📛 Название: <b>{ev['nft_prize_name']}</b>\n"
        f"{col_line}"
        f"  ✨ Редкость: {emoji} <b>{rn}</b>\n"
        f"  💰 Доход: <b>{_fmt_num(ev['nft_income'])}</b>/ч\n\n"
        f"💵 Мин. ставка: <b>{_fmt_num(ev['bet_amount'])}</b> 💢\n"
        f"⏳ Длительность: {timer}\n"
        f"👥 Участников: <b>{p_count}/{ev['max_participants']}</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🏆 <b>Соревнование:</b>\n{top_text}\n"
        f"━━━━━━━━━━━━━━━━━━━"
        f"{warning}"
    )


async def _send_timer_alert(bot: Bot, ev, label: str):
    """Отправляет всем участникам аукциона оповещение о таймере."""
    eid = ev["id"]
    parts = await get_event_participants(eid)
    for p in parts:
        p_uid = p[0] if isinstance(p, tuple) else p["user_id"]
        try:
            await bot.send_message(
                p_uid,
                f"⏱ Аукцион «{ev['name']}» — <b>{label}</b>!\n"
                f"Успейте повысить ставку!",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="💰 Добавить сумму", callback_data=f"auc_raise:{eid}")],
                ]),
            )
        except Exception:
            pass


async def _delete_broadcast_messages(bot: Bot, eid: int):
    """Удалить все broadcast-сообщения аукциона."""
    msgs = await get_auction_messages(eid)
    for row in msgs:
        chat_id = row[0] if isinstance(row, tuple) else row["chat_id"]
        msg_id = row[1] if isinstance(row, tuple) else row["message_id"]
        try:
            await bot.delete_message(chat_id, msg_id)
        except Exception:
            pass
    await delete_auction_messages(eid)


async def auction_checker(bot: Bot):
    """Фоновая задача: каждые 5 сек проверяет аукционы (таймер + завершение)."""
    await asyncio.sleep(5)
    while True:
        try:
            # ── Живой таймер для активных аукционов ──
            active = await get_active_events()
            for ev in active:
                eid = ev["id"] if not isinstance(ev, tuple) else ev[0]
                if isinstance(ev, tuple):
                    continue  # нужен Row
                ends_at = ev["ends_at"]
                if not ends_at:
                    continue
                try:
                    end = _dtm.fromisoformat(ends_at)
                except (ValueError, TypeError):
                    continue
                remaining = (end - _dtm.now()).total_seconds()
                if remaining <= 0:
                    continue

                if eid not in _timer_alerts_sent:
                    _timer_alerts_sent[eid] = set()
                sent = _timer_alerts_sent[eid]

                # Вехи: 3мин, 2мин, 1мин, 30сек, 10сек
                milestones = [
                    (180, "3 минуты"),
                    (120, "2 минуты"),
                    (60, "1 минута"),
                    (30, "30 секунд"),
                    (10, "10 секунд"),
                ]
                for secs, label in milestones:
                    key = f"{secs}s"
                    if key not in sent and remaining <= secs and remaining > (secs - 6):
                        sent.add(key)
                        await _send_timer_alert(bot, ev, label)
                        break

            # ── Проверяем истёкшие аукционы ──
            expired = await get_expired_active_events()
            for ev in expired:
                eid = ev["id"]
                logger.info("Аукцион #%d истёк — завершаю…", eid)

                participants = await get_event_participants(eid)
                p_count = len(participants)

                # Удаляем все broadcast-сообщения аукциона
                await _delete_broadcast_messages(bot, eid)

                # ═══ Правило: меньше 2 участников → отмена и возврат ═══
                if p_count < 2:
                    await cancel_event(eid)
                    logger.info("Аукцион #%d: <2 участников — отменён, ставки возвращены", eid)

                    for p in participants:
                        p_uid = p[0] if isinstance(p, tuple) else p["user_id"]
                        p_bid = p[1] if isinstance(p, tuple) else p["bid_amount"]
                        try:
                            await bot.send_message(
                                p_uid,
                                f"🎪 Аукцион «{ev['name']}» отменён!\n\n"
                                f"👥 Участников: {p_count} (нужно мин. 2)\n"
                                f"💰 Ваша ставка <b>{_fmt_num(p_bid)} 💢</b> возвращена!",
                                parse_mode="HTML",
                                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                    [InlineKeyboardButton(text="⬅️ В меню", callback_data="menu")],
                                ]),
                            )
                        except Exception:
                            pass

                    try:
                        await bot.send_message(
                            OWNER_ID,
                            f"🎪 Аукцион #{eid} «{ev['name']}» отменён.\n"
                            f"👥 Участников: {p_count} (мин. 2)\n"
                            f"💰 Ставки возвращены.",
                        )
                    except Exception:
                        pass

                    _timer_alerts_sent.pop(eid, None)
                    continue

                # ═══ ≥2 участников → нормальное завершение ═══
                winner = await finish_event_with_winner(eid)
                if not winner:
                    logger.warning("Аукцион #%d: finish_event_with_winner вернул None", eid)
                    _timer_alerts_sent.pop(eid, None)
                    continue

                winner_uid = winner[0] if isinstance(winner, tuple) else winner["user_id"]
                winner_bid = winner[1] if isinstance(winner, tuple) else winner["bid_amount"]

                # Создать НФТ-приз с рандомным # и выдать победителю
                rarity_name = ev["nft_rarity"] if isinstance(ev["nft_rarity"], str) else "Обычный"
                rarity_pct = NFT_RARITIES.get(rarity_name, 10.0)
                income = float(ev["nft_income"])
                base_name = ev["nft_prize_name"] or "Аукцион-приз"
                rand_num = random.randint(1000, 9999)
                nft_name = f"{base_name} #{rand_num}"

                template_id = await create_nft_template(
                    nft_name, rarity_name, rarity_pct, income,
                    price=0, created_by=OWNER_ID,
                    collection_num=random.randint(1, 999),
                )
                await grant_nft_to_user(winner_uid, template_id, bought_price=0)

                emoji = NFT_RARITY_EMOJI.get(rarity_name, "🎨")

                # Уведомить победителя
                try:
                    win_col = ev['nft_collection'] or ''
                except (KeyError, IndexError):
                    win_col = ''
                win_col_line = f"  📂 Коллекция: <b>{win_col}</b>\n" if win_col else ""
                try:
                    await bot.send_message(
                        winner_uid,
                        f"🏆 <b>ПОБЕДА В АУКЦИОНЕ!</b>\n"
                        f"━━━━━━━━━━━━━━━━━━━\n"
                        f"  🎪 {ev['name']}\n"
                        f"━━━━━━━━━━━━━━━━━━━\n"
                        f"  📛 Вы получили: <b>{nft_name}</b>\n"
                        f"{win_col_line}"
                        f"  ✨ Редкость: {emoji} <b>{rarity_name}</b>\n"
                        f"  💰 Доход: <b>{_fmt_num(income)}</b> Тохн/ч\n"
                        f"  💵 Ваша ставка: <b>{_fmt_num(winner_bid)}</b> 💢\n"
                        f"  👥 Участников: <b>{p_count}</b>\n"
                        f"━━━━━━━━━━━━━━━━━━━\n\n"
                        f"🎉 НФТ добавлен в вашу коллекцию!",
                        parse_mode="HTML",
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="📦 Мои НФТ", callback_data="my_nft")],
                            [InlineKeyboardButton(text="⬅️ В меню", callback_data="menu")],
                        ]),
                    )
                except Exception:
                    pass

                # Уведомить проигравших — ставки НЕ возвращаются
                for p in participants:
                    p_uid = p[0] if isinstance(p, tuple) else p["user_id"]
                    p_bid = p[1] if isinstance(p, tuple) else p["bid_amount"]
                    if p_uid == winner_uid:
                        continue
                    try:
                        await bot.send_message(
                            p_uid,
                            f"🎪 Аукцион «{ev['name']}» завершён!\n\n"
                            f"❌ <b>Вы проиграли.</b>\n"
                            f"💸 Ваша ставка <b>{_fmt_num(p_bid)} 💢</b> списана.\n"
                            f"🏆 Победитель поставил {_fmt_num(winner_bid)} 💢",
                            parse_mode="HTML",
                            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                [InlineKeyboardButton(text="⬅️ В меню", callback_data="menu")],
                            ]),
                        )
                    except Exception:
                        pass

                # Уведомить владельца
                try:
                    await bot.send_message(
                        OWNER_ID,
                        f"🎪 Аукцион #{eid} «{ev['name']}» завершён!\n"
                        f"🏆 Победитель: {winner_uid} — {_fmt_num(winner_bid)} 💢\n"
                        f"👥 Участников: {p_count}\n"
                        f"🎨 НФТ: {nft_name}",
                    )
                except Exception:
                    pass

                logger.info("Аукцион #%d: победитель %d (%.0f 💢), участников %d, NFT: %s",
                            eid, winner_uid, winner_bid, p_count, nft_name)

                _timer_alerts_sent.pop(eid, None)

        except Exception as e:
            logger.error("auction_checker error: %s", e)

        await asyncio.sleep(5)


def _ensure_db():
    """Если DB_NAME не существует — копируем seed-БД из репозитория."""
    if not os.path.exists(DB_NAME):
        db_dir = os.path.dirname(DB_NAME)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        if os.path.exists(SEED_DB):
            shutil.copy2(SEED_DB, DB_NAME)
            logger.info("Скопирована seed-БД %s → %s", SEED_DB, DB_NAME)
        else:
            logger.info("Seed-БД не найдена, будет создана новая")
    else:
        logger.info("БД уже существует: %s", DB_NAME)


async def _db_backup_loop():
    """Каждые 5 минут делает WAL checkpoint — сохраняет все данные на диск."""
    while True:
        await asyncio.sleep(300)  # 5 минут
        try:
            from database import get_db
            db = await get_db()
            await db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            logger.info("💾 БД checkpoint выполнен — данные сохранены")
        except Exception as e:
            logger.error("Ошибка checkpoint БД: %s", e)


async def _shutdown_db():
    """Корректное закрытие БД при остановке — сохраняет все данные."""
    try:
        from database import get_db, _db_pool
        if _db_pool is not None:
            await _db_pool.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            await _db_pool.commit()
            await _db_pool.close()
            logger.info("💾 БД корректно закрыта, все данные сохранены")
    except Exception as e:
        logger.error("Ошибка при закрытии БД: %s", e)


async def main():
    logger.info("КликТохн v%s — запуск…", VERSION)

    # Копируем seed-БД, если нужно (для Railway Volume)
    _ensure_db()

    # Инициализация БД
    await init_db()

    # Бот
    bot = Bot(
        token=TOKEN,
        parse_mode=ParseMode.HTML,
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Регистрация роутеров
    for r in all_routers:
        dp.include_router(r)
        logger.info("  + роутер %s", r.name or r.__class__.__name__)

    # Удаляем webhook (если был установлен)
    await bot.delete_webhook(drop_pending_updates=True)

    # Запускаем фоновую проверку аукционов
    asyncio.create_task(auction_checker(bot))
    logger.info("  + auction_checker запущен")

    # Запускаем автосохранение БД каждые 5 минут
    asyncio.create_task(_db_backup_loop())
    logger.info("  + db_backup_loop запущен (каждые 5 мин)")

    logger.info("КликТохн v%s — polling запущен ✓", VERSION)
    try:
        await dp.start_polling(
            bot,
            allowed_updates=["message", "callback_query", "chat_member"],
        )
    finally:
        # При любом завершении — сохраняем БД
        await _shutdown_db()


if __name__ == "__main__":
    asyncio.run(main())

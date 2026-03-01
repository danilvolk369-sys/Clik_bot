# ======================================================
# BANNERS_UTIL — Утилиты для отправки/редактирования сообщений
# ======================================================
import logging
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup
from aiogram.exceptions import TelegramBadRequest

logger = logging.getLogger(__name__)


async def send_msg(
    target: Message | CallbackQuery,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    parse_mode: str = "HTML",
):
    """
    Универсальная отправка/редактирование сообщения.

    - Если target — CallbackQuery: пытается отредактировать сообщение,
      при неудаче — отправляет новое.
    - Если target — Message: отвечает новым сообщением.
    """
    if isinstance(target, CallbackQuery):
        try:
            await target.message.edit_text(
                text, reply_markup=reply_markup, parse_mode=parse_mode,
            )
        except TelegramBadRequest as e:
            if "message is not modified" in str(e):
                pass  # содержимое не изменилось — OK
            elif "message to edit not found" in str(e) or "message can't be edited" in str(e):
                await target.message.answer(
                    text, reply_markup=reply_markup, parse_mode=parse_mode,
                )
            else:
                logger.warning("send_msg edit failed: %s", e)
                try:
                    await target.message.answer(
                        text, reply_markup=reply_markup, parse_mode=parse_mode,
                    )
                except Exception:
                    pass
        except Exception as e:
            logger.warning("send_msg exception: %s", e)
            try:
                await target.message.answer(
                    text, reply_markup=reply_markup, parse_mode=parse_mode,
                )
            except Exception:
                pass
        try:
            await target.answer()
        except Exception:
            pass
    elif isinstance(target, Message):
        try:
            await target.answer(
                text, reply_markup=reply_markup, parse_mode=parse_mode,
            )
        except Exception as e:
            logger.warning("send_msg answer failed: %s", e)


async def safe_edit(
    message: Message,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    parse_mode: str = "HTML",
):
    """
    Безопасное редактирование сообщения.
    Если контент не изменился или сообщение уже удалено — не падаем.
    """
    try:
        await message.edit_text(
            text, reply_markup=reply_markup, parse_mode=parse_mode,
        )
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            pass  # ничего не изменилось — ОК
        else:
            logger.warning("safe_edit failed: %s", e)
    except Exception as e:
        logger.warning("safe_edit exception: %s", e)

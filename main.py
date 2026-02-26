# ======================================================
# MAIN — КликТохн v1.0.0  (оптимизация под слабый хостинг)
# ======================================================

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.fsm.storage.memory import MemoryStorage

from config import TOKEN
from database import init_db

from handlers import (
    common_router,
    user_router,
    shop_router,
    chat_router,
    pvp_router,
    owner_router,
    admin_router,
    nft_router,
    trade_router,
    history_router,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


async def main():
    logger.info("🤖 Инициализация КликТохн v1.0.0 ...")

    await init_db()
    logger.info("✅ База данных готова")

    # --- Прокси (только локально, на Railway не нужен) ---
    import os
    import urllib.request
    proxies = urllib.request.getproxies()
    proxy_url = proxies.get("https") or proxies.get("http") or None

    # На Railway прокси отключаем
    if os.getenv("RAILWAY_ENVIRONMENT"):
        proxy_url = None

    if proxy_url:
        logger.info(f"🌐 Прокси обнаружен: {proxy_url}")

    session = AiohttpSession(proxy=proxy_url)

    bot = Bot(token=TOKEN, session=session)
    dp = Dispatcher(storage=MemoryStorage())

    dp.include_router(common_router)
    dp.include_router(user_router)
    dp.include_router(shop_router)
    dp.include_router(chat_router)
    dp.include_router(pvp_router)
    dp.include_router(owner_router)
    dp.include_router(admin_router)
    dp.include_router(nft_router)
    dp.include_router(trade_router)
    dp.include_router(history_router)

    logger.info("🚀 Подключение к Telegram...")

    # Автоповтор при обрыве соединения
    while True:
        try:
            await dp.start_polling(
                bot,
                allowed_updates=["message", "callback_query"],
                drop_pending_updates=True,
                polling_timeout=30,
            )
            break  # Нормальное завершение
        except Exception as e:
            logger.warning(f"⚠️ Обрыв связи: {e}. Повтор через 5 сек...")
            await asyncio.sleep(5)

    await bot.session.close()
    logger.info("👋 Бот остановлен")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен")

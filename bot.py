import asyncio
import logging
import sys

from telegram import Update
from telegram.ext import Application

from config import BOT_TOKEN, DB_PATH
from db import init_db
from handlers import build_handlers

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)


def main() -> None:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    if not BOT_TOKEN:
        raise RuntimeError("Укажите BOT_TOKEN в .env или переменной окружения")

    init_db(DB_PATH)
    application = Application.builder().token(BOT_TOKEN).build()

    for handler in build_handlers():
        application.add_handler(handler)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(application.run_polling(allowed_updates=Update.ALL_TYPES))


if __name__ == "__main__":
    main()

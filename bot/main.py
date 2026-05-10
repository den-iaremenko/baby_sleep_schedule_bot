import logging

from telegram import BotCommand, BotCommandScopeAllPrivateChats, Update
from telegram.ext import Application, CommandHandler, ContextTypes

from db.engine import engine
from db.models import Base
from handlers.link import link_conv_handler
from handlers.schedule import cmd_morning_wake_up, schedule_conv_handler
from handlers.setup import cmd_profile, setup_conv_handler
from handlers.sleep import sleep_handlers
from handlers.stats import stats_handler
from keyboards import MAIN_KEYBOARD
from settings import settings

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


_COMMANDS = [
    BotCommand("morning_wake_up", "Зафіксувати ранковий підйом (опційно ГГ:ХХ)"),
    BotCommand("schedule", "Розклад сну на сьогодні"),
    BotCommand("profile",  "Переглянути профіль дитини"),
    BotCommand("setup",    "Налаштувати профіль дитини"),
    BotCommand("stats",    "Статистика сну (сьогодні або /stats ДД.ММ.РРРР)"),
    BotCommand("link",     "Підключитись до існуючого профілю за Baby ID"),
    BotCommand("cancel",   "Скасувати поточну дію"),
    BotCommand("start",    "Привітальне повідомлення"),
]


async def post_init(app: Application) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await app.bot.set_my_commands(_COMMANDS, scope=BotCommandScopeAllPrivateChats())
    logger.info("Database tables ready, bot commands registered")


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "👶 *Бот розкладу сну для малюка*\n\n"
        "Використовуйте кнопки нижче або команди:\n\n"
        "/setup — налаштувати профіль дитини\n"
        "/profile — переглянути поточний профіль\n"
        "/schedule — розклад сну на сьогодні\n"
        "/cancel — скасувати поточну дію",
        parse_mode="Markdown",
        reply_markup=MAIN_KEYBOARD,
    )


def main() -> None:
    app = Application.builder().token(settings.bot_token).post_init(post_init).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("morning_wake_up", cmd_morning_wake_up))
    app.add_handler(MessageHandler(filters.Regex("^☀️ Ранковий підйом$"), cmd_morning_wake_up))
    app.add_handler(schedule_conv_handler())
    app.add_handler(setup_conv_handler())
    app.add_handler(CommandHandler("profile", cmd_profile))
    app.add_handler(link_conv_handler())
    app.add_handler(stats_handler())
    for handler in sleep_handlers():
        app.add_handler(handler)
    logger.info("Bot is running")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()

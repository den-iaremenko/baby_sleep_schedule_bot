import logging

from telegram import BotCommand, BotCommandScopeAllPrivateChats, Update
from telegram.ext import Application, CommandHandler, ContextTypes

from sqlalchemy import text

from db.engine import engine
from db.models import Base
from handlers.schedule import schedule_conv_handler
from handlers.setup import cmd_profile, setup_conv_handler, timezone_conv_handler
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
    BotCommand("schedule", "Generate today's sleep schedule"),
    BotCommand("profile",  "View current baby profile"),
    BotCommand("setup",    "Set up or update baby profile"),
    BotCommand("slept",    "Record sleep start (optional HH:MM)"),
    BotCommand("woke",     "Record wake-up (optional HH:MM)"),
    BotCommand("stats",    "View sleep statistics (optional: DD.MM.YYYY)"),
    BotCommand("timezone", "Update your timezone (UTC offset)"),
    BotCommand("cancel",   "Cancel current action"),
    BotCommand("start",    "Welcome message"),
]


async def post_init(app: Application) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text(
            "ALTER TABLE baby_profiles ADD COLUMN IF NOT EXISTS utc_offset INTEGER NOT NULL DEFAULT 180"
        ))
    await app.bot.set_my_commands(_COMMANDS, scope=BotCommandScopeAllPrivateChats())
    logger.info("Database tables ready, bot commands registered")


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "👶 *Baby Sleep Schedule Bot*\n\n"
        "Use the buttons below or commands:\n\n"
        "/setup — set up baby profile\n"
        "/profile — view current profile\n"
        "/schedule — generate today's schedule\n"
        "/slept `[HH:MM]` — record sleep start\n"
        "/woke `[HH:MM]` — record wake-up\n"
        "/cancel — cancel current action",
        parse_mode="Markdown",
        reply_markup=MAIN_KEYBOARD,
    )


def main() -> None:
    app = Application.builder().token(settings.bot_token).post_init(post_init).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(schedule_conv_handler())
    app.add_handler(setup_conv_handler())
    app.add_handler(timezone_conv_handler())
    app.add_handler(CommandHandler("profile", cmd_profile))
    app.add_handler(stats_handler())
    for handler in sleep_handlers():
        app.add_handler(handler)
    logger.info("Bot is running")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()

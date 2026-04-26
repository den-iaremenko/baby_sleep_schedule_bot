import re

from telegram import Update
from telegram.ext import (
    CommandHandler,
    ConversationHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from db.engine import AsyncSessionLocal
from db import repository
from keyboards import MAIN_KEYBOARD, build_sleep_keyboard
from scheduler import build_schedule, DEFAULT_CONFIG, ScheduleConfig

ASK_WAKE_TIME = 0

_TIME_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")

_BUTTON_FILTER = filters.Regex(r"^(📅 Schedule|⚙️ Setup|😴 Slept|🌅 Woke up)$")


async def cmd_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "⏰ What time did the baby wake up this morning?\n"
        "Use HH:MM format, e.g. `07:30`",
        parse_mode="Markdown",
        reply_markup=MAIN_KEYBOARD,
    )
    return ASK_WAKE_TIME


async def receive_wake_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if not _TIME_RE.match(text):
        await update.message.reply_text(
            "Please use HH:MM format, e.g. `07:30`",
            parse_mode="Markdown",
        )
        return ASK_WAKE_TIME

    async with AsyncSessionLocal() as db:
        profile = await repository.get_baby_profile(db, update.effective_user.id)

    if profile:
        config = ScheduleConfig(
            wake_windows=tuple(profile.wake_windows),
            nap_durations=tuple(profile.nap_durations),
            active_ratio=profile.active_ratio,
        )
        header = f"📅 *{profile.name}'s Sleep Schedule*"
        keyboard = build_sleep_keyboard(1, len(profile.nap_durations))
    else:
        config = DEFAULT_CONFIG
        header = "📅 *Today's Sleep Schedule*"
        keyboard = build_sleep_keyboard(1, len(DEFAULT_CONFIG.nap_durations))

    schedule = build_schedule(text, config)
    await update.message.reply_text(
        f"{header}\n\n{schedule.format_message()}",
        parse_mode="Markdown",
        reply_markup=keyboard,
    )
    return ConversationHandler.END


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Cancelled.", reply_markup=MAIN_KEYBOARD)
    return ConversationHandler.END


def schedule_conv_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("schedule", cmd_schedule),
            MessageHandler(filters.Regex("^📅 Schedule$"), cmd_schedule),
        ],
        states={
            ASK_WAKE_TIME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~_BUTTON_FILTER, receive_wake_time),
            ],
        },
        fallbacks=[CommandHandler("cancel", cmd_cancel)],
    )

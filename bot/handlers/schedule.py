import re
from datetime import datetime

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
from keyboards import BUTTON_FILTER, MAIN_KEYBOARD, SLEEP_ACTIONS_KEYBOARD
from scheduler import build_schedule, DEFAULT_CONFIG, ScheduleConfig, schedule_to_db_blocks
from settings import KYIV_TZ

ASK_WAKE_TIME = 0

_TIME_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")


async def _build_and_save_schedule(update: Update, time_str: str) -> None:
    """Build the day schedule from wake time, persist it, and send it to the user."""
    today = datetime.now(KYIV_TZ).date()

    async with AsyncSessionLocal() as db:
        profile = await repository.get_baby_profile(db, update.effective_user.id)

    if profile:
        config = ScheduleConfig(
            wake_windows=tuple(profile.wake_windows),
            nap_durations=tuple(profile.nap_durations),
            active_ratio=profile.active_ratio,
        )
        header = f"📅 *Розклад сну {profile.name}*"
    else:
        config = DEFAULT_CONFIG
        header = "📅 *Розклад сну на сьогодні*"

    schedule = build_schedule(time_str, config)

    if profile:
        async with AsyncSessionLocal() as db:
            await repository.upsert_daily_schedule(
                db, profile.id, today, time_str, schedule_to_db_blocks(schedule)
            )

    await update.message.reply_text(
        f"{header}\n\n{schedule.format_message()}",
        parse_mode="Markdown",
        reply_markup=MAIN_KEYBOARD,
    )
    await update.message.reply_text("Записати сон:", reply_markup=SLEEP_ACTIONS_KEYBOARD)


async def cmd_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    today = datetime.now(KYIV_TZ).date()
    user_id = update.effective_user.id

    async with AsyncSessionLocal() as db:
        profile = await repository.get_baby_profile(db, user_id)
        daily = await repository.get_daily_schedule(db, profile.id, today) if profile else None

    if daily and profile:
        config = ScheduleConfig(
            wake_windows=tuple(profile.wake_windows),
            nap_durations=tuple(profile.nap_durations),
            active_ratio=profile.active_ratio,
        )
        schedule = build_schedule(daily.wake_time, config)
        await update.message.reply_text(
            f"📅 *Розклад сну {profile.name}*\n\n{schedule.format_message()}",
            parse_mode="Markdown",
            reply_markup=MAIN_KEYBOARD,
        )
        await update.message.reply_text("Записати сон:", reply_markup=SLEEP_ACTIONS_KEYBOARD)
        return ConversationHandler.END

    await update.message.reply_text(
        "⏰ О котрій годині дитина прокинулась сьогодні вранці?\n"
        "Формат: ГГ:ХХ, наприклад `07:30`",
        parse_mode="Markdown",
        reply_markup=MAIN_KEYBOARD,
    )
    return ASK_WAKE_TIME


async def receive_wake_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if not _TIME_RE.match(text):
        await update.message.reply_text(
            "Будь ласка, введіть час у форматі ГГ:ХХ, наприклад `07:30`",
            parse_mode="Markdown",
        )
        return ASK_WAKE_TIME

    await _build_and_save_schedule(update, text)
    return ConversationHandler.END


async def cmd_morning_wake_up(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.args:
        time_str = context.args[0].strip()
        if not _TIME_RE.match(time_str):
            await update.message.reply_text(
                "Невірний формат часу. Використовуйте ГГ:ХХ, наприклад `07:30`",
                parse_mode="Markdown",
                reply_markup=MAIN_KEYBOARD,
            )
            return
    else:
        time_str = datetime.now(KYIV_TZ).strftime("%H:%M")

    await update.message.reply_text(
        f"☀️ Ранковий підйом о *{time_str}* зафіксовано.",
        parse_mode="Markdown",
        reply_markup=MAIN_KEYBOARD,
    )
    await _build_and_save_schedule(update, time_str)


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Скасовано.", reply_markup=MAIN_KEYBOARD)
    return ConversationHandler.END


def schedule_conv_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("schedule", cmd_schedule),
            MessageHandler(filters.Regex("^📅 Розклад$"), cmd_schedule),
        ],
        states={
            ASK_WAKE_TIME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~BUTTON_FILTER, receive_wake_time),
            ],
        },
        fallbacks=[CommandHandler("cancel", cmd_cancel)],
    )

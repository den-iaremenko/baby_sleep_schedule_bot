import re
from datetime import datetime, timedelta, timezone

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from db.engine import AsyncSessionLocal
from db import repository
from keyboards import MAIN_KEYBOARD, build_sleep_keyboard
from scheduler import ScheduleConfig, rebuild_from_nap

_TIME_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")


def _nap_label(label: str) -> str:
    if label.startswith("nap_"):
        return f"Nap {label.split('_')[1]}"
    return "Night sleep" if label == "night" else label


def _label_to_nap_index(label: str) -> int | None:
    """'nap_1' → 0, 'nap_2' → 1. Returns None for 'night'."""
    if label.startswith("nap_"):
        return int(label.split("_")[1]) - 1
    return None


def _build_select_keyboard(action: str, num_naps: int) -> InlineKeyboardMarkup:
    nap_buttons = [
        InlineKeyboardButton(f"Nap {i}", callback_data=f"{action}:nap_{i}")
        for i in range(1, num_naps + 1)
    ]
    return InlineKeyboardMarkup([
        nap_buttons,
        [InlineKeyboardButton("Night", callback_data=f"{action}:night")],
    ])


def _local_now(utc_offset_minutes: int = 180) -> datetime:
    return datetime.now(timezone(timedelta(minutes=utc_offset_minutes)))


async def _num_naps(user_id: int) -> int:
    async with AsyncSessionLocal() as db:
        profile = await repository.get_baby_profile(db, user_id)
    return len(profile.nap_durations) if profile else 3


async def cmd_slept(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    num = await _num_naps(update.effective_user.id)
    await update.message.reply_text(
        "Which sleep?",
        reply_markup=_build_select_keyboard("sleep_start", num),
    )


async def cmd_woke(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    num = await _num_naps(update.effective_user.id)
    await update.message.reply_text(
        "Which sleep ended?",
        reply_markup=_build_select_keyboard("sleep_end", num),
    )


async def handle_sleep_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    action, label = query.data.split(":", 1)
    user_id = update.effective_user.id
    display = _nap_label(label)

    async with AsyncSessionLocal() as db:
        profile = await repository.get_baby_profile(db, user_id)

    now = _local_now(profile.utc_offset if profile else 0)

    if action == "sleep_start":
        async with AsyncSessionLocal() as db:
            await repository.start_session(db, user_id, now, label=label)
        await query.message.reply_text(
            f"😴 *{display}* started at *{now.strftime('%H:%M')}*",
            parse_mode="Markdown",
            reply_markup=MAIN_KEYBOARD,
        )
        return

    # sleep_end
    async with AsyncSessionLocal() as db:
        session = await repository.end_session(db, user_id, now, label=label)

    if not session:
        await query.message.reply_text(f"No active {display} session found.", reply_markup=MAIN_KEYBOARD)
        return

    actual_mins = int((now - session.started_at).total_seconds() / 60)
    h, m = divmod(actual_mins, 60)
    dur = f"{h}h {m:02d}m" if h else f"{m}m"

    await query.message.reply_text(
        f"🌅 *{display}* ended at *{now.strftime('%H:%M')}* — slept for *{dur}*",
        parse_mode="Markdown",
        reply_markup=MAIN_KEYBOARD,
    )

    # Recalculate remaining schedule after any nap ends
    nap_index = _label_to_nap_index(label)
    if nap_index is None or profile is None:
        return

    config = ScheduleConfig(
        wake_windows=tuple(profile.wake_windows),
        nap_durations=tuple(profile.nap_durations),
        active_ratio=profile.active_ratio,
    )

    # Deviation note
    planned_mins = config.nap_durations[nap_index] if nap_index < len(config.nap_durations) else None
    note = ""
    if planned_mins and abs(actual_mins - planned_mins) >= 10:
        direction = "longer" if actual_mins > planned_mins else "shorter"
        diff = abs(actual_mins - planned_mins)
        note = f"_Nap {nap_index + 1} was {diff}m {direction} than planned._\n\n"

    remaining = rebuild_from_nap(now.strftime("%H:%M"), nap_index, config)
    total_naps = len(profile.nap_durations)
    next_nap = nap_index + 2  # 1-based number of next nap

    keyboard = (
        build_sleep_keyboard(next_nap, total_naps)
        if next_nap <= total_naps
        else build_sleep_keyboard(total_naps + 1, total_naps)  # only night buttons
    )

    await query.message.reply_text(
        f"📅 *{profile.name}'s Updated Schedule*\n\n{note}"
        f"{remaining.format_message(wake_label=f'After Nap {nap_index + 1}')}",
        parse_mode="Markdown",
        reply_markup=keyboard,
    )


def sleep_handlers() -> list:
    return [
        CommandHandler("slept", cmd_slept),
        CommandHandler("woke", cmd_woke),
        MessageHandler(filters.Regex("^😴 Slept$"), cmd_slept),
        MessageHandler(filters.Regex("^🌅 Woke up$"), cmd_woke),
        CallbackQueryHandler(handle_sleep_callback, pattern=r"^sleep_(start|end):.+$"),
    ]

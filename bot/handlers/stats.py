from datetime import date, datetime

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

from db.engine import AsyncSessionLocal
from db import repository
from keyboards import MAIN_KEYBOARD


def _parse_date(text: str) -> date | None:
    for fmt in ("%d.%m.%Y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _fmt_minutes(mins: int) -> str:
    h, m = divmod(mins, 60)
    return f"{h}h {m:02d}m" if h and m else (f"{h}h" if h else f"{m}m")


def _nap_label(label: str | None) -> str:
    if not label:
        return "Sleep"
    if label.startswith("nap_"):
        return f"Nap {label.split('_')[1]}"
    return "Night sleep" if label == "night" else label


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    target_day: date | None = None

    if args:
        target_day = _parse_date(args[0])
        if not target_day:
            await update.message.reply_text(
                "Couldn't parse the date. Use DD.MM.YYYY, e.g. `/stats 24.04.2025`",
                parse_mode="Markdown",
                reply_markup=MAIN_KEYBOARD,
            )
            return

    user_id = update.effective_user.id

    async with AsyncSessionLocal() as db:
        profile = await repository.get_baby_profile(db, user_id)

    utc_offset = profile.utc_offset if profile else 180
    name = profile.name if profile else "Baby"

    if target_day is None:
        from datetime import timezone, timedelta
        tz = timezone(timedelta(minutes=utc_offset))
        target_day = datetime.now(tz).date()

    async with AsyncSessionLocal() as db:
        sessions = await repository.get_sessions_for_day(db, user_id, target_day, utc_offset)

    date_str = target_day.strftime("%d.%m.%Y")

    if not sessions:
        await update.message.reply_text(
            f"No sleep data found for *{name}* on {date_str}.",
            parse_mode="Markdown",
            reply_markup=MAIN_KEYBOARD,
        )
        return

    total_mins = 0
    lines = [f"📊 *{name}'s Sleep Stats — {date_str}*", ""]

    for s in sessions:
        label = _nap_label(s.label)
        start_str = s.started_at.strftime("%H:%M")

        if s.ended_at:
            dur_mins = int((s.ended_at - s.started_at).total_seconds() / 60)
            total_mins += dur_mins
            end_str = s.ended_at.strftime("%H:%M")
            lines.append(f"• {label}: {start_str}–{end_str} ({_fmt_minutes(dur_mins)})")
        else:
            lines.append(f"• {label}: {start_str}– _(ongoing)_")

    lines += ["", f"💤 *Total sleep: {_fmt_minutes(total_mins)}*"]

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=MAIN_KEYBOARD,
    )


def stats_handler() -> CommandHandler:
    return CommandHandler("stats", cmd_stats)

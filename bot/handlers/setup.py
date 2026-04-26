import re
from datetime import date, datetime

from telegram import Update
from telegram.ext import CommandHandler, ConversationHandler, ContextTypes, MessageHandler, filters

from db.engine import AsyncSessionLocal
from db import repository
from keyboards import MAIN_KEYBOARD


def _fmt_minutes(mins: int) -> str:
    h, m = divmod(mins, 60)
    return f"{h}h {m:02d}m" if h and m else (f"{h}h" if h else f"{m}m")


def _age_str(dob: date) -> str:
    today = date.today()
    months = (today.year - dob.year) * 12 + today.month - dob.month
    if today.day < dob.day:
        months -= 1
    if months < 1:
        days = (today - dob).days
        return f"{days} day{'s' if days != 1 else ''}"
    if months < 24:
        return f"{months} month{'s' if months != 1 else ''}"
    years = months // 12
    return f"{years} year{'s' if years != 1 else ''}"


def _fmt_offset(offset_minutes: int) -> str:
    sign = "+" if offset_minutes >= 0 else "-"
    h, m = divmod(abs(offset_minutes), 60)
    return f"UTC{sign}{h}:{m:02d}" if m else f"UTC{sign}{h}"


def _parse_utc_offset(text: str) -> int | None:
    """Parse UTC offset to minutes. Accepts: +2, -5, +5:30, 2, 0."""
    t = text.strip()
    m = re.fullmatch(r"([+-]?)(\d{1,2}):(\d{2})", t)
    if m:
        sign = -1 if m.group(1) == "-" else 1
        return sign * (int(m.group(2)) * 60 + int(m.group(3)))
    m = re.fullmatch(r"([+-]?)(\d{1,2})", t)
    if m:
        sign = -1 if m.group(1) == "-" else 1
        hours = int(m.group(2))
        if hours > 14:
            return None
        return sign * hours * 60
    return None


async def cmd_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async with AsyncSessionLocal() as db:
        profile = await repository.get_baby_profile(db, update.effective_user.id)

    if not profile:
        await update.message.reply_text(
            "No profile found. Use /setup or tap ⚙️ Setup to create one.",
            reply_markup=MAIN_KEYBOARD,
        )
        return

    ww = profile.wake_windows
    nd = profile.nap_durations
    num_naps = len(nd)
    age = _age_str(profile.date_of_birth)
    active_pct = int(profile.active_ratio * 100)
    chill_pct = 100 - active_pct

    lines = [
        f"👶 *{profile.name}'s Profile*",
        "",
        f"📅 Born: {profile.date_of_birth.strftime('%d.%m.%Y')} _{age}_",
        f"🕐 Timezone: {_fmt_offset(profile.utc_offset)}",
        f"😴 {num_naps} nap{'s' if num_naps != 1 else ''} per day",
        "",
    ]
    for i in range(num_naps):
        lines.append(f"Awake {_fmt_minutes(ww[i])} → Nap {i + 1} ({_fmt_minutes(nd[i])})")
    lines.append(f"Awake {_fmt_minutes(ww[-1])} → 🌙 Night sleep")
    lines += ["", f"⚡ Active / 😌 Wind-down split: {active_pct}% / {chill_pct}%"]

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=MAIN_KEYBOARD,
    )


ASK_NAME, ASK_DOB, ASK_TIMEZONE, ASK_NUM_NAPS, ASK_WAKE_WINDOW, ASK_NAP_DURATION, ASK_NEW_TIMEZONE = range(7)

_BUTTON_FILTER = filters.Regex(r"^(📅 Schedule|⚙️ Setup|😴 Slept|🌅 Woke up)$")


def _parse_duration(text: str) -> int | None:
    t = text.strip().lower().replace(" ", "")
    m = re.fullmatch(r"(\d+)h(\d+)m?", t)
    if m:
        return int(m.group(1)) * 60 + int(m.group(2))
    m = re.fullmatch(r"(\d+)h", t)
    if m:
        return int(m.group(1)) * 60
    m = re.fullmatch(r"(\d+)m", t)
    if m:
        return int(m.group(1))
    m = re.fullmatch(r"(\d+)", t)
    if m:
        return int(m.group(1))
    return None


def _parse_date(text: str) -> date | None:
    for fmt in ("%d.%m.%Y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text.strip(), fmt).date()
        except ValueError:
            continue
    return None


async def cmd_setup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("setup", None)
    await update.message.reply_text("👶 Let's set up your baby's profile!\n\nWhat's the baby's name?")
    return ASK_NAME


async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    name = update.message.text.strip()
    context.user_data["setup"] = {"name": name, "wake_windows": [], "nap_durations": []}
    await update.message.reply_text(
        f"When was *{name}* born?\nFormat: DD.MM.YYYY, e.g. `15.09.2024`",
        parse_mode="Markdown",
    )
    return ASK_DOB


async def receive_dob(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    dob = _parse_date(update.message.text)
    if not dob:
        await update.message.reply_text(
            "Couldn't parse the date. Please use DD.MM.YYYY, e.g. `15.09.2024`",
            parse_mode="Markdown",
        )
        return ASK_DOB

    context.user_data["setup"]["dob"] = dob.isoformat()
    await update.message.reply_text(
        "What's your UTC offset? Type `y` for default `+3`.\n"
        "e.g. `+3`, `-5` (Eastern US), `+5:30` (India)",
        parse_mode="Markdown",
    )
    return ASK_TIMEZONE


async def receive_timezone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if text.lower() == "y":
        offset = 180  # default: UTC+3
    else:
        offset = _parse_utc_offset(text)
    if offset is None:
        await update.message.reply_text(
            "Couldn't parse that. Try `+3`, `-5`, or `+5:30`. Type `y` for default `+3`.",
            parse_mode="Markdown",
        )
        return ASK_TIMEZONE

    setup = context.user_data["setup"]
    setup["utc_offset"] = offset
    await update.message.reply_text(
        f"How many naps does *{setup['name']}* have per day?",
        parse_mode="Markdown",
    )
    return ASK_NUM_NAPS


async def receive_num_naps(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if not text.isdigit() or not (1 <= int(text) <= 6):
        await update.message.reply_text("Please enter a number between 1 and 6.")
        return ASK_NUM_NAPS

    setup = context.user_data["setup"]
    setup["num_naps"] = int(text)
    setup["current_nap"] = 1

    await update.message.reply_text(
        f"How long is *{setup['name']}* awake before Nap 1?\n"
        "e.g. `2h10m` or `130` (minutes). Type `y` for default `170m`.",
        parse_mode="Markdown",
    )
    return ASK_WAKE_WINDOW


async def receive_wake_window(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    mins = 170 if text.lower() == "y" else _parse_duration(text)
    if not mins or mins <= 0:
        await update.message.reply_text(
            "Couldn't parse that. Try `2h10m`, `2h`, or `130`. Type `y` for default `170m`.",
            parse_mode="Markdown",
        )
        return ASK_WAKE_WINDOW

    setup = context.user_data["setup"]
    setup["wake_windows"].append(mins)
    current_nap = setup["current_nap"]
    num_naps = setup["num_naps"]
    name = setup["name"]

    if len(setup["wake_windows"]) <= num_naps:
        await update.message.reply_text(
            f"How long is *{name}'s* Nap {current_nap}?\n"
            "e.g. `1h` or `60` (minutes). Type `y` for default `60m`.",
            parse_mode="Markdown",
        )
        return ASK_NAP_DURATION

    return await _finish_setup(update, context)


async def receive_nap_duration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    mins = 60 if text.lower() == "y" else _parse_duration(text)
    if not mins or mins <= 0:
        await update.message.reply_text(
            "Couldn't parse that. Try `1h` or `60`. Type `y` for default `60m`.",
            parse_mode="Markdown",
        )
        return ASK_NAP_DURATION

    setup = context.user_data["setup"]
    setup["nap_durations"].append(mins)
    setup["current_nap"] += 1
    current_nap = setup["current_nap"]
    num_naps = setup["num_naps"]
    name = setup["name"]

    prompt = (
        f"How long is *{name}* awake before Nap {current_nap}?"
        if current_nap <= num_naps
        else f"How long is *{name}* awake before night sleep?"
    )
    await update.message.reply_text(
        f"{prompt}\ne.g. `2h50m` or `170` (minutes). Type `y` for default `170m`.",
        parse_mode="Markdown",
    )
    return ASK_WAKE_WINDOW


async def _finish_setup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    setup = context.user_data.pop("setup")
    dob = date.fromisoformat(setup["dob"])

    async with AsyncSessionLocal() as db:
        profile = await repository.save_baby_profile(
            db,
            user_id=update.effective_user.id,
            name=setup["name"],
            date_of_birth=dob,
            wake_windows=setup["wake_windows"],
            nap_durations=setup["nap_durations"],
            utc_offset=setup.get("utc_offset", 0),
        )

    ww = profile.wake_windows
    nd = profile.nap_durations
    num_naps = len(nd)

    lines = [f"✅ *{profile.name}'s profile saved!*", ""]
    for i in range(num_naps):
        lines.append(f"Awake {_fmt_minutes(ww[i])} → Nap {i + 1} ({_fmt_minutes(nd[i])})")
    lines.append(f"Awake {_fmt_minutes(ww[-1])} → 🌙 Night sleep")
    lines += ["", f"🕐 Timezone: {_fmt_offset(profile.utc_offset)}"]
    lines.append("")
    lines.append("Use /schedule to generate today's schedule.")

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=MAIN_KEYBOARD,
    )
    return ConversationHandler.END


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("setup", None)
    await update.message.reply_text("Setup cancelled.", reply_markup=MAIN_KEYBOARD)
    return ConversationHandler.END


async def cmd_timezone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    async with AsyncSessionLocal() as db:
        profile = await repository.get_baby_profile(db, update.effective_user.id)

    current = f" Current: {_fmt_offset(profile.utc_offset)}." if profile else ""
    await update.message.reply_text(
        f"Enter your UTC offset.{current}\n"
        "e.g. `+3`, `-5`, `+5:30`. Type `y` for default `+3`.",
        parse_mode="Markdown",
    )
    return ASK_NEW_TIMEZONE


async def receive_new_timezone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    offset = 180 if text.lower() == "y" else _parse_utc_offset(text)
    if offset is None:
        await update.message.reply_text(
            "Couldn't parse that. Try `+3`, `-5`, or `+5:30`. Type `y` for default `+3`.",
            parse_mode="Markdown",
        )
        return ASK_NEW_TIMEZONE

    async with AsyncSessionLocal() as db:
        saved = await repository.update_utc_offset(db, update.effective_user.id, offset)

    if saved:
        await update.message.reply_text(
            f"✅ Timezone updated to *{_fmt_offset(offset)}*.",
            parse_mode="Markdown",
            reply_markup=MAIN_KEYBOARD,
        )
    else:
        await update.message.reply_text(
            "No profile found. Use /setup to create one first.",
            reply_markup=MAIN_KEYBOARD,
        )
    return ConversationHandler.END


def timezone_conv_handler() -> ConversationHandler:
    text_only = filters.TEXT & ~filters.COMMAND & ~_BUTTON_FILTER
    return ConversationHandler(
        entry_points=[CommandHandler("timezone", cmd_timezone)],
        states={
            ASK_NEW_TIMEZONE: [MessageHandler(text_only, receive_new_timezone)],
        },
        fallbacks=[CommandHandler("cancel", cmd_cancel)],
    )


def setup_conv_handler() -> ConversationHandler:
    text_only = filters.TEXT & ~filters.COMMAND & ~_BUTTON_FILTER
    return ConversationHandler(
        entry_points=[
            CommandHandler("setup", cmd_setup),
            MessageHandler(filters.Regex("^⚙️ Setup$"), cmd_setup),
        ],
        states={
            ASK_NAME:         [MessageHandler(text_only, receive_name)],
            ASK_DOB:          [MessageHandler(text_only, receive_dob)],
            ASK_TIMEZONE:     [MessageHandler(text_only, receive_timezone)],
            ASK_NUM_NAPS:     [MessageHandler(text_only, receive_num_naps)],
            ASK_WAKE_WINDOW:  [MessageHandler(text_only, receive_wake_window)],
            ASK_NAP_DURATION: [MessageHandler(text_only, receive_nap_duration)],
        },
        fallbacks=[CommandHandler("cancel", cmd_cancel)],
    )

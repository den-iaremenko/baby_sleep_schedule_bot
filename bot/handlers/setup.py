import re
from datetime import date, datetime

from telegram import Update
from telegram.ext import CommandHandler, ConversationHandler, ContextTypes, MessageHandler, filters

from db.engine import AsyncSessionLocal
from db import repository
from keyboards import BUTTON_FILTER, MAIN_KEYBOARD


def _fmt_minutes(mins: int) -> str:
    h, m = divmod(mins, 60)
    return f"{h}г {m:02d}хв" if h and m else (f"{h}г" if h else f"{m}хв")


def _plural_uk(n: int, one: str, few: str, many: str) -> str:
    if 11 <= n % 100 <= 19:
        return many
    r = n % 10
    if r == 1:
        return one
    if 2 <= r <= 4:
        return few
    return many


def _age_str(dob: date) -> str:
    today = date.today()
    months = (today.year - dob.year) * 12 + today.month - dob.month
    if today.day < dob.day:
        months -= 1
    if months < 1:
        days = (today - dob).days
        return f"{days} {_plural_uk(days, 'день', 'дні', 'днів')}"
    if months < 24:
        return f"{months} {_plural_uk(months, 'місяць', 'місяці', 'місяців')}"
    years = months // 12
    return f"{years} {_plural_uk(years, 'рік', 'роки', 'років')}"


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


ASK_NAME, ASK_DOB, ASK_NUM_NAPS, ASK_WAKE_WINDOW, ASK_NAP_DURATION = range(5)



async def cmd_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async with AsyncSessionLocal() as db:
        profile = await repository.get_baby_profile(db, update.effective_user.id)

    if not profile:
        await update.message.reply_text(
            "Профіль не знайдено. Використайте /setup або натисніть ⚙️ Налаштування.",
            reply_markup=MAIN_KEYBOARD,
        )
        return

    ww = profile.wake_windows
    nd = profile.nap_durations
    num_naps = len(nd)
    age = _age_str(profile.date_of_birth)
    active_pct = int(profile.active_ratio * 100)
    chill_pct = 100 - active_pct
    nap_word = _plural_uk(num_naps, "сон", "сни", "снів")

    lines = [
        f"👶 *Профіль {profile.name}*",
        "",
        f"📅 Народження: {profile.date_of_birth.strftime('%d.%m.%Y')} _{age}_",
        f"😴 {num_naps} {nap_word} на день",
        "",
        f"🔑 Baby ID: `{profile.id}`",
        "_Поділіться цим ID щоб інший користувач міг підключитись через /link_",
        "",
    ]
    for i in range(num_naps):
        lines.append(f"Не спить {_fmt_minutes(ww[i])} → Сон {i + 1} ({_fmt_minutes(nd[i])})")
    lines.append(f"Не спить {_fmt_minutes(ww[-1])} → 🌙 Нічний сон")
    lines += ["", f"⚡ Активний / 😌 Заспокоєння: {active_pct}% / {chill_pct}%"]

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=MAIN_KEYBOARD,
    )


async def cmd_setup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("setup", None)
    await update.message.reply_text(
        "👶 Давайте налаштуємо профіль вашої дитини!\n\nЯк звати дитину?"
    )
    return ASK_NAME


async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    name = update.message.text.strip()
    context.user_data["setup"] = {"name": name, "wake_windows": [], "nap_durations": []}
    await update.message.reply_text(
        f"Коли народився(-лась) *{name}*?\nФормат: ДД.ММ.РРРР, наприклад `15.09.2024`",
        parse_mode="Markdown",
    )
    return ASK_DOB


async def receive_dob(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    dob = _parse_date(update.message.text)
    if not dob:
        await update.message.reply_text(
            "Не вдалося розпізнати дату. Використовуйте формат ДД.ММ.РРРР, наприклад `15.09.2024`",
            parse_mode="Markdown",
        )
        return ASK_DOB

    setup = context.user_data["setup"]
    setup["dob"] = dob.isoformat()
    await update.message.reply_text(
        f"Скільки денних снів має *{setup['name']}*?",
        parse_mode="Markdown",
    )
    return ASK_NUM_NAPS


async def receive_num_naps(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if not text.isdigit() or not (1 <= int(text) <= 6):
        await update.message.reply_text("Будь ласка, введіть число від 1 до 6.")
        return ASK_NUM_NAPS

    setup = context.user_data["setup"]
    setup["num_naps"] = int(text)
    setup["current_nap"] = 1

    await update.message.reply_text(
        f"Скільки часу *{setup['name']}* не спить перед Сном 1?\n"
        "Наприклад `2h10m` або `130` (хвилин). Введіть `y` для значення за замовчуванням `170хв`.",
        parse_mode="Markdown",
    )
    return ASK_WAKE_WINDOW


async def receive_wake_window(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    mins = 170 if text.lower() == "y" else _parse_duration(text)
    if not mins or mins <= 0:
        await update.message.reply_text(
            "Не вдалося розпізнати. Спробуйте `2h10m`, `2h` або `130`. Введіть `y` для значення за замовчуванням `170хв`.",
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
            f"Скільки триває Сон {current_nap} у *{name}*?\n"
            "Наприклад `1h` або `60` (хвилин). Введіть `y` для значення за замовчуванням `60хв`.",
            parse_mode="Markdown",
        )
        return ASK_NAP_DURATION

    return await _finish_setup(update, context)


async def receive_nap_duration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    mins = 60 if text.lower() == "y" else _parse_duration(text)
    if not mins or mins <= 0:
        await update.message.reply_text(
            "Не вдалося розпізнати. Спробуйте `1h` або `60`. Введіть `y` для значення за замовчуванням `60хв`.",
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
        f"Скільки часу *{name}* не спить перед Сном {current_nap}?"
        if current_nap <= num_naps
        else f"Скільки часу *{name}* не спить перед нічним сном?"
    )
    await update.message.reply_text(
        f"{prompt}\nНаприклад `2h50m` або `170` (хвилин). Введіть `y` для значення за замовчуванням `170хв`.",
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
        )

    ww = profile.wake_windows
    nd = profile.nap_durations
    num_naps = len(nd)

    lines = [f"✅ *Профіль {profile.name} збережено!*", ""]
    for i in range(num_naps):
        lines.append(f"Не спить {_fmt_minutes(ww[i])} → Сон {i + 1} ({_fmt_minutes(nd[i])})")
    lines.append(f"Не спить {_fmt_minutes(ww[-1])} → 🌙 Нічний сон")
    lines.append("")
    lines.append("Використайте /schedule для генерації розкладу на сьогодні.")

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=MAIN_KEYBOARD,
    )
    return ConversationHandler.END


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("setup", None)
    await update.message.reply_text("Налаштування скасовано.", reply_markup=MAIN_KEYBOARD)
    return ConversationHandler.END


def setup_conv_handler() -> ConversationHandler:
    text_only = filters.TEXT & ~filters.COMMAND & ~BUTTON_FILTER
    return ConversationHandler(
        entry_points=[
            CommandHandler("setup", cmd_setup),
            MessageHandler(filters.Regex("^⚙️ Налаштування$"), cmd_setup),
        ],
        states={
            ASK_NAME:         [MessageHandler(text_only, receive_name)],
            ASK_DOB:          [MessageHandler(text_only, receive_dob)],
            ASK_NUM_NAPS:     [MessageHandler(text_only, receive_num_naps)],
            ASK_WAKE_WINDOW:  [MessageHandler(text_only, receive_wake_window)],
            ASK_NAP_DURATION: [MessageHandler(text_only, receive_nap_duration)],
        },
        fallbacks=[CommandHandler("cancel", cmd_cancel)],
    )

from datetime import date, datetime, timedelta

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

from db.engine import AsyncSessionLocal
from db import repository
from keyboards import MAIN_KEYBOARD
from scheduler import ScheduleConfig, build_schedule
from settings import KYIV_TZ


def _parse_date(text: str) -> date | None:
    t = text.strip()
    current_year = datetime.now(KYIV_TZ).year
    try:
        return datetime.strptime(t, "%d.%m.%Y").date()
    except ValueError:
        pass
    try:
        return datetime.strptime(f"{t}.{current_year}", "%d.%m.%Y").date()
    except ValueError:
        pass
    return None


def _fmt_duration(mins: int) -> str:
    h, m = divmod(mins, 60)
    return f"{h}г {m:02d}хв" if h and m else (f"{h}г" if h else f"{m}хв")


def _label_display(label: str | None) -> str:
    if not label or label == "night":
        return "Нічний сон"
    if label.startswith("nap_"):
        return f"Сон {label.split('_')[1]}"
    return label


def _block_duration(start: str, end: str) -> int:
    s = datetime.strptime(start, "%H:%M")
    e = datetime.strptime(end, "%H:%M")
    return int((e - s).total_seconds() / 60)


def _schedule_lines(daily, profile) -> list[str]:
    config = ScheduleConfig(
        wake_windows=tuple(profile.wake_windows),
        nap_durations=tuple(profile.nap_durations),
        active_ratio=profile.active_ratio,
    )
    full = build_schedule(daily.wake_time, config)

    # Map db label → stored actual times
    actual: dict[str, dict] = {b["label"]: b for b in daily.blocks}

    lines = [f"🌅 *Підйом:* {daily.wake_time}", ""]

    for block in full.blocks:
        if block.label.startswith("Сон"):
            nap_num = int(block.label.split(" ")[1])
            db_label = f"nap_{nap_num}"
            planned = f"{block.start.strftime('%H:%M')}–{block.end.strftime('%H:%M')}"
            a = actual.get(db_label, {})
            a_start, a_end = a.get("actual_start"), a.get("actual_end")

            if a_start and a_end:
                dur = _fmt_duration(_block_duration(a_start, a_end))
                lines.append(f"😴 *{block.label}:* план {planned} | факт {a_start}–{a_end} ({dur})")
            elif a_start:
                lines.append(f"😴 *{block.label}:* план {planned} | розпочато {a_start} _(триває...)_")
            else:
                lines.append(f"😴 *{block.label}:* план {planned}")
            lines.append("")
        else:
            lines.append(block.format())

    night_planned = full.night_sleep.strftime("%H:%M")
    a = actual.get("night", {})
    a_start = a.get("actual_start")
    if a_start:
        lines.append(f"🌙 *Нічний сон:* план {night_planned} | розпочато {a_start}")
    else:
        lines.append(f"🌙 *Нічний сон:* план {night_planned}")

    return lines


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    now = datetime.now(KYIV_TZ)

    if context.args:
        target_day = _parse_date(context.args[0])
        if not target_day:
            await update.message.reply_text(
                "Невірний формат дати. Використовуйте ДД.ММ або ДД.ММ.РРРР\n"
                "Наприклад: `/stats 24.04` або `/stats 24.04.2025`",
                parse_mode="Markdown",
                reply_markup=MAIN_KEYBOARD,
            )
            return
    else:
        target_day = now.date()

    day_start = KYIV_TZ.localize(datetime(target_day.year, target_day.month, target_day.day))
    day_end = day_start + timedelta(days=1)
    date_str = target_day.strftime("%d.%m.%Y")

    async with AsyncSessionLocal() as db:
        profile = await repository.get_baby_profile(db, update.effective_user.id)
        if not profile:
            await update.message.reply_text(
                "Профіль не знайдено. Використайте /setup.",
                reply_markup=MAIN_KEYBOARD,
            )
            return
        daily = await repository.get_daily_schedule(db, profile.id, target_day)
        sessions = await repository.get_sessions_for_day(db, profile.id, day_start, day_end)

    lines = [f"📊 *Статистика {profile.name} — {date_str}*"]

    if not daily and not sessions:
        lines.append("\n_Немає даних за цей день._")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown", reply_markup=MAIN_KEYBOARD)
        return

    # ── Schedule ──────────────────────────────────────────────────────────────
    if daily:
        lines += ["", "📅 *Розклад*"] + _schedule_lines(daily, profile)

    # ── Sleep records ─────────────────────────────────────────────────────────
    if sessions:
        lines += ["", "😴 *Записи снів*"]
        total_mins = 0
        for s in sessions:
            label = _label_display(s.label)
            start_str = s.started_at.astimezone(KYIV_TZ).strftime("%H:%M")
            if s.ended_at:
                end_str = s.ended_at.astimezone(KYIV_TZ).strftime("%H:%M")
                dur_mins = int((s.ended_at - s.started_at).total_seconds() / 60)
                total_mins += dur_mins
                lines.append(f"• {label}: {start_str} – {end_str} ({_fmt_duration(dur_mins)})")
            else:
                lines.append(f"• {label}: {start_str} – _(триває...)_")

        lines += ["", f"💤 *Загальний час сну: {_fmt_duration(total_mins)}*"]

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=MAIN_KEYBOARD,
    )


def stats_handler() -> CommandHandler:
    return CommandHandler("stats", cmd_stats)

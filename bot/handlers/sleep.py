from datetime import datetime, timedelta

from telegram import Update
from telegram.ext import CallbackQueryHandler, ContextTypes, MessageHandler, filters

from db.engine import AsyncSessionLocal
from db import repository
from keyboards import MAIN_KEYBOARD, SLEEP_ACTIONS_KEYBOARD
from scheduler import ScheduleConfig, merge_with_rebuilt, rebuild_from_nap
from settings import KYIV_TZ


def _label_display(label: str | None) -> str:
    if not label or label == "night":
        return "Нічний сон"
    if label.startswith("nap_"):
        return f"Сон {label.split('_')[1]}"
    return label


def _nap_index(label: str) -> int | None:
    """'nap_1' → 0, 'nap_2' → 1. Returns None for night."""
    if label.startswith("nap_"):
        return int(label.split("_")[1]) - 1
    return None


def _fmt_duration(mins: int) -> str:
    h, m = divmod(mins, 60)
    return f"{h}г {m:02d}хв" if h and m else (f"{h}г" if h else f"{m}хв")


def _kyiv_now() -> datetime:
    return datetime.now(KYIV_TZ)


async def _handle_sleep_start(user_id: int, reply_fn) -> None:
    now = _kyiv_now()
    today = now.date()
    day_start = KYIV_TZ.localize(datetime(now.year, now.month, now.day))
    day_end = day_start + timedelta(days=1)

    async with AsyncSessionLocal() as db:
        profile = await repository.get_baby_profile(db, user_id)
        if not profile:
            await reply_fn(
                "Спочатку налаштуйте профіль дитини — /setup.",
                reply_markup=MAIN_KEYBOARD,
            )
            return

        baby_id = profile.id
        nap_durations = list(profile.nap_durations)

        active = await repository.get_active_session(db, baby_id)
        if active:
            await reply_fn(
                f"⚠️ *{_label_display(active.label)}* ще триває. "
                "Спочатку натисніть 🌅 *Прокинувся*.",
                parse_mode="Markdown",
                reply_markup=MAIN_KEYBOARD,
            )
            return

        finished = await repository.count_finished_today(db, baby_id, day_start, day_end)
        label = f"nap_{finished + 1}" if finished < len(nap_durations) else "night"
        await repository.start_session(db, baby_id, now, label)

    async with AsyncSessionLocal() as db:
        daily = await repository.get_daily_schedule(db, baby_id, today)
        if daily:
            blocks = [dict(b) for b in daily.blocks]
            for block in blocks:
                if block["label"] == label:
                    block["actual_start"] = now.strftime("%H:%M")
                    break
            await repository.update_schedule_blocks(db, baby_id, today, blocks)

    await reply_fn(
        f"😴 *{_label_display(label)}* розпочато о *{now.strftime('%H:%M')}*",
        parse_mode="Markdown",
        reply_markup=MAIN_KEYBOARD,
    )


async def _handle_sleep_end(user_id: int, reply_fn) -> None:
    now = _kyiv_now()

    async with AsyncSessionLocal() as db:
        profile = await repository.get_baby_profile(db, user_id)
        if not profile:
            await reply_fn(
                "Спочатку налаштуйте профіль дитини — /setup.",
                reply_markup=MAIN_KEYBOARD,
            )
            return

        baby_id = profile.id
        name = profile.name
        config = ScheduleConfig(
            wake_windows=tuple(profile.wake_windows),
            nap_durations=tuple(profile.nap_durations),
            active_ratio=profile.active_ratio,
        )

        session = await repository.end_session(db, baby_id, now)

    if not session:
        await reply_fn("⚠️ Немає активного сну.", reply_markup=MAIN_KEYBOARD)
        return

    display = _label_display(session.label)
    dur_mins = int((now - session.started_at).total_seconds() / 60)

    await reply_fn(
        f"🌅 *{display}* завершено о *{now.strftime('%H:%M')}* — тривав *{_fmt_duration(dur_mins)}*",
        parse_mode="Markdown",
        reply_markup=MAIN_KEYBOARD,
    )

    nap_idx = _nap_index(session.label or "")
    schedule_date = session.started_at.astimezone(KYIV_TZ).date()

    remaining = None
    if nap_idx is not None:
        remaining = rebuild_from_nap(now.strftime("%H:%M"), nap_idx, config)

    async with AsyncSessionLocal() as db:
        daily = await repository.get_daily_schedule(db, baby_id, schedule_date)
        if daily and session.label:
            blocks = [dict(b) for b in daily.blocks]
            for block in blocks:
                if block["label"] == session.label:
                    block["actual_end"] = now.strftime("%H:%M")
                    break
            if remaining:
                blocks = merge_with_rebuilt(blocks, remaining)
            await repository.update_schedule_blocks(db, baby_id, schedule_date, blocks)

    if nap_idx is None or remaining is None:
        return

    note = ""
    if nap_idx < len(config.nap_durations):
        planned = config.nap_durations[nap_idx]
        diff = abs(dur_mins - planned)
        if diff >= 10:
            direction = "довше" if dur_mins > planned else "коротше"
            note = f"_Сон {nap_idx + 1} тривав на {diff}хв {direction} ніж заплановано._\n\n"

    await reply_fn(
        f"📅 *Оновлений розклад {name}*\n\n{note}"
        f"{remaining.format_message(wake_label=f'Після Сону {nap_idx + 1}')}",
        parse_mode="Markdown",
        reply_markup=SLEEP_ACTIONS_KEYBOARD,
    )


async def cmd_sleep_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _handle_sleep_start(update.effective_user.id, update.message.reply_text)


async def cmd_sleep_end(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _handle_sleep_end(update.effective_user.id, update.message.reply_text)


async def cb_sleep(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    action = query.data.split(":")[1]
    if action == "start":
        await _handle_sleep_start(update.effective_user.id, query.message.reply_text)
    else:
        await _handle_sleep_end(update.effective_user.id, query.message.reply_text)


def sleep_handlers() -> list:
    return [
        MessageHandler(filters.Regex("^😴 Спить$"), cmd_sleep_start),
        MessageHandler(filters.Regex("^🌅 Прокинувся$"), cmd_sleep_end),
        CallbackQueryHandler(cb_sleep, pattern=r"^sleep:(start|end)$"),
    ]

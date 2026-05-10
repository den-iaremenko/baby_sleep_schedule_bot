from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True)
class ScheduleConfig:
    wake_windows: tuple[int, ...]  # awake minutes per period (must be len(nap_durations) + 1)
    nap_durations: tuple[int, ...]  # nap minutes per nap
    active_ratio: float = 0.70


DEFAULT_CONFIG = ScheduleConfig(
    wake_windows=(130, 170, 170, 180),
    nap_durations=(60, 60, 60),
)


@dataclass
class TimeBlock:
    label: str
    emoji: str
    start: datetime
    end: datetime

    def format(self) -> str:
        mins = int((self.end - self.start).total_seconds() / 60)
        h, m = divmod(mins, 60)
        dur = f"{h}г {m:02d}хв" if h and m else (f"{h}г" if h else f"{m}хв")
        return f"{self.emoji} *{self.label}:* {self.start.strftime('%H:%M')} – {self.end.strftime('%H:%M')} ({dur})"


@dataclass
class DaySchedule:
    wake_up: datetime
    blocks: list[TimeBlock]
    night_sleep: datetime

    def format_message(self, wake_label: str = "Підйом") -> str:
        lines = [f"🌅 *{wake_label}:* {self.wake_up.strftime('%H:%M')}", ""]
        for block in self.blocks:
            lines.append(block.format())
            if block.label.startswith("Сон"):
                lines.append("")
        lines.append(f"🌙 *Нічний сон:* {self.night_sleep.strftime('%H:%M')}")
        return "\n".join(lines)


def build_schedule(
    wake_time_str: str,
    config: ScheduleConfig = DEFAULT_CONFIG,
    nap_start_index: int = 1,
) -> DaySchedule:
    current = datetime.strptime(wake_time_str, "%H:%M")
    base = current
    blocks: list[TimeBlock] = []

    for i, wake_window in enumerate(config.wake_windows):
        active_mins = round(wake_window * config.active_ratio)
        chill_mins = wake_window - active_mins

        active_end = current + timedelta(minutes=active_mins)
        chill_end = active_end + timedelta(minutes=chill_mins)

        blocks.append(TimeBlock("Активний час", "⚡", current, active_end))
        blocks.append(TimeBlock("Заспокоєння", "😌", active_end, chill_end))
        current = chill_end

        if i < len(config.nap_durations):
            nap_end = current + timedelta(minutes=config.nap_durations[i])
            blocks.append(TimeBlock(f"Сон {nap_start_index + i}", "😴", current, nap_end))
            current = nap_end

    return DaySchedule(wake_up=base, blocks=blocks, night_sleep=current)


def schedule_to_db_blocks(schedule: DaySchedule) -> list[dict]:
    """Convert a DaySchedule to the list of sleep-block dicts stored in DailySchedule.blocks."""
    blocks = []
    for block in schedule.blocks:
        if block.label.startswith("Сон"):
            nap_num = int(block.label.split(" ")[1])
            blocks.append({
                "label": f"nap_{nap_num}",
                "planned_start": block.start.strftime("%H:%M"),
                "planned_end": block.end.strftime("%H:%M"),
                "actual_start": None,
                "actual_end": None,
            })
    blocks.append({
        "label": "night",
        "planned_start": schedule.night_sleep.strftime("%H:%M"),
        "planned_end": None,
        "actual_start": None,
        "actual_end": None,
    })
    return blocks


def merge_with_rebuilt(existing_blocks: list[dict], rebuilt: DaySchedule) -> list[dict]:
    """Replace planned times for remaining blocks from a rebuilt schedule, keeping actual times."""
    new_planned = {b["label"]: b for b in schedule_to_db_blocks(rebuilt)}
    result = []
    for block in existing_blocks:
        if block["label"] in new_planned:
            result.append({
                **block,
                "planned_start": new_planned[block["label"]]["planned_start"],
                "planned_end": new_planned[block["label"]]["planned_end"],
            })
        else:
            result.append(block)
    return result


def rebuild_from_nap(
    wake_time_str: str,
    completed_nap_index: int,
    config: ScheduleConfig,
) -> DaySchedule:
    """Recalculate the remaining day after a nap ends at an actual (possibly off-plan) time."""
    partial = ScheduleConfig(
        wake_windows=tuple(config.wake_windows[completed_nap_index + 1:]),
        nap_durations=tuple(config.nap_durations[completed_nap_index + 1:]),
        active_ratio=config.active_ratio,
    )
    return build_schedule(wake_time_str, partial, nap_start_index=completed_nap_index + 2)

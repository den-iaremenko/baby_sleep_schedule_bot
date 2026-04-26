from dataclasses import dataclass, field
from datetime import datetime, timedelta


@dataclass(frozen=True)
class ScheduleConfig:
    wake_windows: tuple[int, ...]  # awake minutes per period (must be len(nap_durations) + 1)
    nap_durations: tuple[int, ...]  # nap minutes per nap
    active_ratio: float = 0.70


# Wake → 2h10m → 1h nap → 2h50m → 1h nap → 2h50m → 1h nap → 3h → night sleep
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
        dur = f"{h}h {m:02d}m" if h and m else (f"{h}h" if h else f"{m}m")
        return f"{self.emoji} *{self.label}:* {self.start.strftime('%H:%M')} – {self.end.strftime('%H:%M')} ({dur})"


@dataclass
class DaySchedule:
    wake_up: datetime
    blocks: list[TimeBlock]
    night_sleep: datetime

    def format_message(self, wake_label: str = "Wake up") -> str:
        lines = [f"🌅 *{wake_label}:* {self.wake_up.strftime('%H:%M')}", ""]
        for block in self.blocks:
            lines.append(block.format())
            if block.label.startswith("Nap"):
                lines.append("")
        lines.append(f"🌙 *Night sleep:* {self.night_sleep.strftime('%H:%M')}")
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

        blocks.append(TimeBlock("Active", "⚡", current, active_end))
        blocks.append(TimeBlock("Wind down", "😌", active_end, chill_end))
        current = chill_end

        if i < len(config.nap_durations):
            nap_end = current + timedelta(minutes=config.nap_durations[i])
            blocks.append(TimeBlock(f"Nap {nap_start_index + i}", "😴", current, nap_end))
            current = nap_end

    return DaySchedule(wake_up=base, blocks=blocks, night_sleep=current)


def rebuild_from_nap(
    wake_time_str: str,
    completed_nap_index: int,
    config: ScheduleConfig,
) -> DaySchedule:
    """Rebuild the remaining day schedule after a nap ends at actual time.

    Keeps remaining wake windows and nap durations from the profile so total
    sleep stays close to the configured target.
    """
    remaining_ww = list(config.wake_windows[completed_nap_index + 1:])
    remaining_nd = list(config.nap_durations[completed_nap_index + 1:])

    partial = ScheduleConfig(
        wake_windows=tuple(remaining_ww),
        nap_durations=tuple(remaining_nd),
        active_ratio=config.active_ratio,
    )
    return build_schedule(wake_time_str, partial, nap_start_index=completed_nap_index + 2)

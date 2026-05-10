import uuid
from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import BabyProfile, DailySchedule, SleepSession, TelegramUser


# ── Baby profile ─────────────────────────────────────────────────────────────

async def get_baby_profile(db: AsyncSession, telegram_user_id: int) -> BabyProfile | None:
    result = await db.execute(
        select(BabyProfile)
        .join(TelegramUser, TelegramUser.baby_id == BabyProfile.id)
        .where(TelegramUser.telegram_user_id == telegram_user_id)
    )
    return result.scalar_one_or_none()


async def save_baby_profile(
    db: AsyncSession,
    telegram_user_id: int,
    name: str,
    date_of_birth: date,
    wake_windows: list[int],
    nap_durations: list[int],
    active_ratio: float = 0.70,
) -> BabyProfile:
    link_result = await db.execute(
        select(TelegramUser).where(TelegramUser.telegram_user_id == telegram_user_id)
    )
    link = link_result.scalar_one_or_none()

    if link:
        profile_result = await db.execute(
            select(BabyProfile).where(BabyProfile.id == link.baby_id)
        )
        profile = profile_result.scalar_one()
        profile.name = name
        profile.date_of_birth = date_of_birth
        profile.wake_windows = wake_windows
        profile.nap_durations = nap_durations
        profile.active_ratio = active_ratio
    else:
        profile = BabyProfile(
            id=uuid.uuid4(),
            name=name,
            date_of_birth=date_of_birth,
            wake_windows=wake_windows,
            nap_durations=nap_durations,
            active_ratio=active_ratio,
        )
        db.add(profile)
        await db.flush()
        db.add(TelegramUser(telegram_user_id=telegram_user_id, baby_id=profile.id))

    await db.commit()
    await db.refresh(profile)
    return profile


async def get_baby_profile_by_id(db: AsyncSession, baby_id: uuid.UUID) -> BabyProfile | None:
    result = await db.execute(select(BabyProfile).where(BabyProfile.id == baby_id))
    return result.scalar_one_or_none()


async def link_user_to_baby(
    db: AsyncSession,
    telegram_user_id: int,
    baby_id: uuid.UUID,
) -> str:
    """Create or update the telegram_user → baby link.

    Returns 'already_linked', 'updated', or 'created'.
    """
    result = await db.execute(
        select(TelegramUser).where(TelegramUser.telegram_user_id == telegram_user_id)
    )
    link = result.scalar_one_or_none()
    if link:
        if link.baby_id == baby_id:
            return "already_linked"
        link.baby_id = baby_id
        await db.commit()
        return "updated"
    db.add(TelegramUser(telegram_user_id=telegram_user_id, baby_id=baby_id))
    await db.commit()
    return "created"


# ── Sleep sessions ───────────────────────────────────────────────────────────

async def get_active_session(db: AsyncSession, baby_id: uuid.UUID) -> SleepSession | None:
    result = await db.execute(
        select(SleepSession)
        .where(SleepSession.baby_id == baby_id)
        .where(SleepSession.ended_at.is_(None))
        .order_by(SleepSession.started_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def count_finished_today(
    db: AsyncSession,
    baby_id: uuid.UUID,
    day_start: datetime,
    day_end: datetime,
) -> int:
    result = await db.execute(
        select(func.count()).select_from(SleepSession)
        .where(SleepSession.baby_id == baby_id)
        .where(SleepSession.started_at >= day_start)
        .where(SleepSession.started_at < day_end)
        .where(SleepSession.ended_at.isnot(None))
    )
    return result.scalar_one()


async def start_session(
    db: AsyncSession,
    baby_id: uuid.UUID,
    started_at: datetime,
    label: str,
) -> SleepSession:
    session = SleepSession(id=uuid.uuid4(), baby_id=baby_id, started_at=started_at, label=label)
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def end_session(
    db: AsyncSession,
    baby_id: uuid.UUID,
    ended_at: datetime,
) -> SleepSession | None:
    result = await db.execute(
        select(SleepSession)
        .where(SleepSession.baby_id == baby_id)
        .where(SleepSession.ended_at.is_(None))
        .order_by(SleepSession.started_at.desc())
        .limit(1)
    )
    session = result.scalar_one_or_none()
    if session:
        session.ended_at = ended_at
        await db.commit()
        await db.refresh(session)
    return session


async def get_sessions_for_day(
    db: AsyncSession,
    baby_id: uuid.UUID,
    day_start: datetime,
    day_end: datetime,
) -> list[SleepSession]:
    result = await db.execute(
        select(SleepSession)
        .where(SleepSession.baby_id == baby_id)
        .where(SleepSession.started_at >= day_start)
        .where(SleepSession.started_at < day_end)
        .order_by(SleepSession.started_at)
    )
    return list(result.scalars().all())


# ── Daily schedule ───────────────────────────────────────────────────────────

async def upsert_daily_schedule(
    db: AsyncSession,
    baby_id: uuid.UUID,
    schedule_date: date,
    wake_time: str,
    blocks: list[dict],
) -> DailySchedule:
    result = await db.execute(
        select(DailySchedule)
        .where(DailySchedule.baby_id == baby_id)
        .where(DailySchedule.date == schedule_date)
    )
    daily = result.scalar_one_or_none()
    if daily:
        daily.wake_time = wake_time
        daily.blocks = blocks
        flag_modified(daily, "blocks")
    else:
        daily = DailySchedule(
            id=uuid.uuid4(),
            baby_id=baby_id,
            date=schedule_date,
            wake_time=wake_time,
            blocks=blocks,
        )
        db.add(daily)
    await db.commit()
    await db.refresh(daily)
    return daily


async def get_daily_schedule(
    db: AsyncSession,
    baby_id: uuid.UUID,
    schedule_date: date,
) -> DailySchedule | None:
    result = await db.execute(
        select(DailySchedule)
        .where(DailySchedule.baby_id == baby_id)
        .where(DailySchedule.date == schedule_date)
    )
    return result.scalar_one_or_none()


async def update_schedule_blocks(
    db: AsyncSession,
    baby_id: uuid.UUID,
    schedule_date: date,
    blocks: list[dict],
) -> bool:
    result = await db.execute(
        select(DailySchedule)
        .where(DailySchedule.baby_id == baby_id)
        .where(DailySchedule.date == schedule_date)
    )
    daily = result.scalar_one_or_none()
    if not daily:
        return False
    daily.blocks = blocks
    flag_modified(daily, "blocks")
    await db.commit()
    return True

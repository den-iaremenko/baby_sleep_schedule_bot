from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import BabyProfile, SleepSession


async def save_baby_profile(
    db: AsyncSession,
    user_id: int,
    name: str,
    date_of_birth: date,
    wake_windows: list[int],
    nap_durations: list[int],
    active_ratio: float = 0.70,
    utc_offset: int = 0,
) -> BabyProfile:
    result = await db.execute(
        select(BabyProfile).where(BabyProfile.telegram_user_id == user_id)
    )
    profile = result.scalar_one_or_none()

    if profile:
        profile.name = name
        profile.date_of_birth = date_of_birth
        profile.wake_windows = wake_windows
        profile.nap_durations = nap_durations
        profile.active_ratio = active_ratio
        profile.utc_offset = utc_offset
    else:
        profile = BabyProfile(
            telegram_user_id=user_id,
            name=name,
            date_of_birth=date_of_birth,
            wake_windows=wake_windows,
            nap_durations=nap_durations,
            active_ratio=active_ratio,
            utc_offset=utc_offset,
        )
        db.add(profile)

    await db.commit()
    await db.refresh(profile)
    return profile


async def get_baby_profile(db: AsyncSession, user_id: int) -> BabyProfile | None:
    result = await db.execute(
        select(BabyProfile).where(BabyProfile.telegram_user_id == user_id)
    )
    return result.scalar_one_or_none()


async def start_session(
    db: AsyncSession,
    user_id: int,
    started_at: datetime,
    label: str | None = None,
) -> SleepSession:
    session = SleepSession(telegram_user_id=user_id, started_at=started_at, label=label)
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def end_session(
    db: AsyncSession,
    user_id: int,
    ended_at: datetime,
    label: str | None = None,
) -> SleepSession | None:
    stmt = (
        select(SleepSession)
        .where(SleepSession.telegram_user_id == user_id)
        .where(SleepSession.ended_at.is_(None))
        .order_by(SleepSession.started_at.desc())
        .limit(1)
    )
    if label:
        stmt = stmt.where(SleepSession.label == label)

    result = await db.execute(stmt)
    session = result.scalar_one_or_none()

    if session:
        session.ended_at = ended_at
        await db.commit()
        await db.refresh(session)

    return session


async def get_sessions_for_day(
    db: AsyncSession,
    user_id: int,
    day: date,
    utc_offset_minutes: int = 120,
) -> list[SleepSession]:
    tz = timezone(timedelta(minutes=utc_offset_minutes))
    local_start = datetime(day.year, day.month, day.day, tzinfo=tz)
    local_end = local_start + timedelta(days=1)
    result = await db.execute(
        select(SleepSession)
        .where(SleepSession.telegram_user_id == user_id)
        .where(SleepSession.started_at >= local_start)
        .where(SleepSession.started_at < local_end)
        .order_by(SleepSession.started_at)
    )
    return list(result.scalars().all())

import uuid
from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, Float, ForeignKey, JSON, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class BabyProfile(Base):
    __tablename__ = "baby_profiles"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(native_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    date_of_birth: Mapped[date] = mapped_column(Date, nullable=False)
    wake_windows: Mapped[list[int]] = mapped_column(JSON, nullable=False)   # len = num_naps + 1
    nap_durations: Mapped[list[int]] = mapped_column(JSON, nullable=False)  # len = num_naps
    active_ratio: Mapped[float] = mapped_column(Float, default=0.70, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class TelegramUser(Base):
    __tablename__ = "telegram_users"

    telegram_user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    baby_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(native_uuid=True), ForeignKey("baby_profiles.id"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SleepSession(Base):
    __tablename__ = "sleep_sessions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(native_uuid=True), primary_key=True, default=uuid.uuid4)
    baby_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(native_uuid=True), ForeignKey("baby_profiles.id"), nullable=False, index=True
    )
    label: Mapped[str | None] = mapped_column(String(20), nullable=True)  # nap_1, nap_2, ... , night
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DailySchedule(Base):
    __tablename__ = "daily_schedules"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(native_uuid=True), primary_key=True, default=uuid.uuid4)
    baby_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(native_uuid=True), ForeignKey("baby_profiles.id"), nullable=False, index=True
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    wake_time: Mapped[str] = mapped_column(String(5), nullable=False)  # HH:MM morning wake
    # Each entry: {label, planned_start, planned_end, actual_start, actual_end}
    blocks: Mapped[list] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (UniqueConstraint("baby_id", "date", name="uq_baby_date"),)

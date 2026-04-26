from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, Float, Integer, JSON, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class BabyProfile(Base):
    __tablename__ = "baby_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    date_of_birth: Mapped[date] = mapped_column(Date, nullable=False)
    wake_windows: Mapped[list[int]] = mapped_column(JSON, nullable=False)   # len = num_naps + 1
    nap_durations: Mapped[list[int]] = mapped_column(JSON, nullable=False)  # len = num_naps
    active_ratio: Mapped[float] = mapped_column(Float, default=0.70, nullable=False)
    utc_offset: Mapped[int] = mapped_column(Integer, default=180, server_default="180", nullable=False)  # UTC+3
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class SleepSession(Base):
    __tablename__ = "sleep_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    label: Mapped[str | None] = mapped_column(String(20), nullable=True)  # nap_1, nap_2, night
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

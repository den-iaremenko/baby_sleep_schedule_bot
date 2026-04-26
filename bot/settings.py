from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    bot_token: str = Field(alias="TELEGRAM_BOT_TOKEN")
    database_url: str = Field(alias="DATABASE_URL")

    # Wake window durations in minutes
    wake_window_1: int = Field(default=130, alias="WAKE_WINDOW_1")  # after morning wake-up (2h 10m)
    wake_window_2: int = Field(default=170, alias="WAKE_WINDOW_2")  # after nap 1           (2h 50m)
    wake_window_3: int = Field(default=170, alias="WAKE_WINDOW_3")  # after nap 2           (2h 50m)
    wake_window_4: int = Field(default=180, alias="WAKE_WINDOW_4")  # after nap 3           (3h)

    # Nap durations in minutes
    nap_1_duration: int = Field(default=60, alias="NAP_1_DURATION")
    nap_2_duration: int = Field(default=60, alias="NAP_2_DURATION")
    nap_3_duration: int = Field(default=60, alias="NAP_3_DURATION")

    # Fraction of each awake window spent on active play (remainder is wind-down)
    active_ratio: float = Field(default=0.70, alias="ACTIVE_RATIO")


settings = Settings()

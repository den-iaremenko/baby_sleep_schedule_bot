import pytz

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

KYIV_TZ = pytz.timezone("Europe/Kyiv")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    bot_token: str = Field(alias="TELEGRAM_BOT_TOKEN")
    database_url: str = Field(alias="DATABASE_URL")
    db_password: str = Field(alias="POSTGRES_PASSWORD")


settings = Settings()

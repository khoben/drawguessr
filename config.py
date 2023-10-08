from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    bot_token: SecretStr
    webhook_endpoint_secret: SecretStr
    telegram_bot_api_secret_token: SecretStr
    telegram_bot_web_app_url: str

    db_url: SecretStr

    host: str
    port: int


config = Settings()

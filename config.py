from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Переменные окружения приложения с валидацией."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    model: str = Field(default="llama3.2:latest", validation_alias="OLLAMA_MODEL")
    ollama_url: str = Field(default="http://localhost:11434", validation_alias="OLLAMA_URL")

    max_iter: int = Field(default=3, ge=1, validation_alias="MAX_ITER")
    max_retries: int = Field(default=3, ge=1, validation_alias="MAX_RETRIES")
    retry_delay: int = Field(default=1, ge=0, validation_alias="RETRY_DELAY")
    max_messages: int = Field(default=16, ge=1, validation_alias="MAX_MESSAGES")
    exec_timeout: int = Field(default=10, ge=1, validation_alias="EXEC_TIMEOUT")


settings = Settings()

# Обратная совместимость: те же имена констант, что и раньше.
MODEL = settings.model
OLLAMA_URL = settings.ollama_url
MAX_ITER = settings.max_iter
MAX_RETRIES = settings.max_retries
RETRY_DELAY = settings.retry_delay
MAX_MESSAGES = settings.max_messages
EXEC_TIMEOUT = settings.exec_timeout

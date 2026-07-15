from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    git_sha: str = "dev"

    database_url: str
    database_url_sync: str
    redis_url: str = "redis://localhost:6379/0"

    anthropic_api_key: str | None = None
    judge_model: str = "claude-sonnet-5"
    judge_sample_rate: float = 0.2


@lru_cache
def get_settings() -> Settings:
    return Settings()

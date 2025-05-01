from pydantic_settings import BaseSettings
from functools import lru_cache
import os


class Settings(BaseSettings):
    environment: str = "development"

    # PostgreSQL
    pguser: str
    pgpassword: str
    pghost: str
    pgdatabase: str
    pgport: int = 5432

    # Redis
    redis_host: str
    redis_port: int
    redis_password: str
    debug: bool = False

    class Config:
        env_file = ".env.dev" if os.getenv("ENVIRONMENT") == "development" else ".env.prod"
        env_file_encoding = 'utf-8'
        extra = 'ignore'  # Ignore undefined env vars


@lru_cache()
def get_settings():
    return Settings()
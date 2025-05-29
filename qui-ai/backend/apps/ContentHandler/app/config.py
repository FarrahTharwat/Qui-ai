from pydantic_settings import BaseSettings
from functools import lru_cache
import os

import logging
from logging.config import dictConfig

logging_config = dict(
    version=1,
    disable_existing_loggers=False,
    formatters={
        "standard": {
            "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S"
        }
    },
    handlers={
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
            "level": "INFO"
        }
    },
    loggers={
        "": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": True
        },
        "python_multipart.multipart": {
            "level": "WARNING",
            "propagate": False
        }
    }
)

def configure_logging():
    dictConfig(logging_config)
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
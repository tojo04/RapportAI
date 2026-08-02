from dataclasses import dataclass
from functools import lru_cache
import os

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    """Environment-backed application settings."""

    frontend_origin: str = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")


@lru_cache
def get_settings() -> Settings:
    return Settings()

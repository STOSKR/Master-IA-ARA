"""Application configuration and environment loading."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    """Typed runtime configuration for the extractor platform."""

    project_name: str = "cs2-price-trend-intelligence"
    environment: str = "dev"
    log_level: str = "INFO"
    data_dir: Path = Field(default=Path("data"))
    dump_dir: Path = Field(default=Path("data/dumps"))
    random_seed: int = 42

    model_config = SettingsConfigDict(
        env_prefix="CS2TREND_",
        env_file=".env",
        extra="ignore",
    )


def load_config() -> AppConfig:
    """Load configuration values from environment variables and defaults."""

    return AppConfig()


def ensure_runtime_directories(config: AppConfig) -> None:
    """Create required local directories in user-space if they do not exist."""

    config.data_dir.mkdir(parents=True, exist_ok=True)
    config.dump_dir.mkdir(parents=True, exist_ok=True)

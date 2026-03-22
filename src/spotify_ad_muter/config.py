from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import tomllib


DEFAULT_CONFIG_PATH = Path("~/.config/spotify-ad-muter/config.toml").expanduser()


@dataclass(slots=True)
class AppConfig:
    ad_volume_percent: int = 0
    unmute_delay_ms: int = 500
    poll_interval_ms: int = 1000
    log_level: str = "INFO"
    stream_match_mode: str = "relaxed"

    @classmethod
    def from_sources(
        cls,
        *,
        cli_values: dict[str, Any] | None = None,
        config_path: Path | None = None,
    ) -> "AppConfig":
        data: dict[str, Any] = {}

        source_path = config_path or DEFAULT_CONFIG_PATH
        if source_path.exists():
            with source_path.open("rb") as handle:
                loaded = tomllib.load(handle)
            if isinstance(loaded, dict):
                data.update(loaded)

        if cli_values:
            for key, value in cli_values.items():
                if value is not None:
                    data[key] = value

        config = cls(**data)
        config.validate()
        return config

    def validate(self) -> None:
        if not 0 <= self.ad_volume_percent <= 100:
            raise ValueError("ad_volume_percent must be between 0 and 100")
        if self.unmute_delay_ms < 0:
            raise ValueError("unmute_delay_ms must be >= 0")
        if self.poll_interval_ms <= 0:
            raise ValueError("poll_interval_ms must be > 0")
        if self.stream_match_mode not in {"strict", "relaxed"}:
            raise ValueError("stream_match_mode must be 'strict' or 'relaxed'")

from __future__ import annotations

from typing import Any


__all__ = ["AdMuterService", "AppConfig"]


def __getattr__(name: str) -> Any:
    if name == "AppConfig":
        from .config import AppConfig

        return AppConfig
    if name == "AdMuterService":
        from .service import AdMuterService

        return AdMuterService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

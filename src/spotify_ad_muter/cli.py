from __future__ import annotations

import argparse
import asyncio
import logging
import signal
from pathlib import Path

from .config import AppConfig, DEFAULT_CONFIG_PATH
from .service import AdMuterService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Mute Spotify ads using MPRIS and PulseAudio/PipeWire"
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="Path to a TOML config file",
    )
    parser.add_argument(
        "--ad-volume-percent",
        type=int,
        dest="ad_volume_percent",
        help="Volume percentage during ads",
    )
    parser.add_argument(
        "--unmute-delay-ms",
        type=int,
        dest="unmute_delay_ms",
        help="Delay before restoring volume",
    )
    parser.add_argument(
        "--poll-interval-ms",
        type=int,
        dest="poll_interval_ms",
        help="Polling interval for Spotify state",
    )
    parser.add_argument(
        "--stream-match-mode",
        choices=("strict", "relaxed"),
        dest="stream_match_mode",
        help="How aggressively to match Spotify sink inputs",
    )
    parser.add_argument(
        "--log-level", default=None, choices=("DEBUG", "INFO", "WARNING", "ERROR")
    )
    return parser


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


async def _run_service(config: AppConfig) -> None:
    service = AdMuterService(config)
    loop = asyncio.get_running_loop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(service.stop()))

    await service.run()


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    cli_values = {key: value for key, value in vars(args).items() if key != "config"}
    config = AppConfig.from_sources(cli_values=cli_values, config_path=args.config)
    configure_logging(config.log_level)
    asyncio.run(_run_service(config))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

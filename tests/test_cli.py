import argparse
import importlib
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

cli_module = importlib.import_module("spotify_ad_muter.cli")


class CliTests(unittest.TestCase):
    def test_build_parser_uses_expected_defaults(self) -> None:
        parser = cli_module.build_parser()
        args = parser.parse_args([])

        self.assertEqual(args.config, cli_module.DEFAULT_CONFIG_PATH)
        self.assertIsNone(args.ad_volume_percent)
        self.assertIsNone(args.unmute_delay_ms)
        self.assertIsNone(args.poll_interval_ms)
        self.assertIsNone(args.log_level)

    def test_configure_logging_passes_uppercase_level(self) -> None:
        with patch.object(cli_module.logging, "basicConfig") as basic_config:
            cli_module.configure_logging("debug")

        self.assertEqual(
            basic_config.call_args.kwargs["level"], cli_module.logging.DEBUG
        )

    def test_main_wires_config_and_runs_service(self) -> None:
        fake_config = Mock()
        fake_path = Path("/tmp/test-config.toml")
        parsed_args = argparse.Namespace(
            config=fake_path,
            ad_volume_percent=0,
            unmute_delay_ms=500,
            poll_interval_ms=1000,
            stream_match_mode="relaxed",
            log_level="INFO",
        )
        with (
            patch.object(
                cli_module,
                "build_parser",
                return_value=Mock(parse_args=Mock(return_value=parsed_args)),
            ),
            patch.object(
                cli_module.AppConfig, "from_sources", return_value=fake_config
            ) as from_sources,
            patch.object(cli_module, "configure_logging") as configure_logging,
            patch.object(cli_module.asyncio, "run") as asyncio_run,
            patch.object(
                cli_module,
                "_run_service",
                new=Mock(return_value="sentinel-coro"),
            ) as run_service,
        ):
            result = cli_module.main()

        self.assertEqual(result, 0)
        from_sources.assert_called_once_with(
            cli_values={
                "ad_volume_percent": 0,
                "unmute_delay_ms": 500,
                "poll_interval_ms": 1000,
                "stream_match_mode": "relaxed",
                "log_level": "INFO",
            },
            config_path=fake_path,
        )
        configure_logging.assert_called_once_with(fake_config.log_level)
        run_service.assert_called_once_with(fake_config)
        asyncio_run.assert_called_once_with("sentinel-coro")

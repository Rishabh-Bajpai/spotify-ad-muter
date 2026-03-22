import importlib
import tempfile
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

config_module = importlib.import_module("spotify_ad_muter.config")
AppConfig = config_module.AppConfig


class ConfigTests(unittest.TestCase):
    def test_cli_values_override_defaults(self) -> None:
        config = AppConfig.from_sources(
            cli_values={"ad_volume_percent": 10, "log_level": "DEBUG"},
            config_path=Path("/tmp/does-not-exist.toml"),
        )

        self.assertEqual(config.ad_volume_percent, 10)
        self.assertEqual(config.unmute_delay_ms, 500)
        self.assertEqual(config.log_level, "DEBUG")

    def test_config_file_loads_and_none_cli_values_are_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.toml"
            config_path.write_text(
                "ad_volume_percent = 15\n"
                "unmute_delay_ms = 750\n"
                'log_level = "WARNING"\n',
                encoding="utf-8",
            )

            config = AppConfig.from_sources(
                cli_values={"ad_volume_percent": None, "poll_interval_ms": 250},
                config_path=config_path,
            )

        self.assertEqual(config.ad_volume_percent, 15)
        self.assertEqual(config.unmute_delay_ms, 750)
        self.assertEqual(config.poll_interval_ms, 250)
        self.assertEqual(config.log_level, "WARNING")

    def test_validate_rejects_invalid_values(self) -> None:
        with self.assertRaisesRegex(ValueError, "ad_volume_percent"):
            AppConfig(ad_volume_percent=101).validate()

        with self.assertRaisesRegex(ValueError, "unmute_delay_ms"):
            AppConfig(unmute_delay_ms=-1).validate()

        with self.assertRaisesRegex(ValueError, "poll_interval_ms"):
            AppConfig(poll_interval_ms=0).validate()

        with self.assertRaisesRegex(ValueError, "stream_match_mode"):
            AppConfig(stream_match_mode="nope").validate()

    def test_package_init_uses_lazy_exports(self) -> None:
        package = importlib.import_module("spotify_ad_muter")

        self.assertIs(package.AppConfig, config_module.AppConfig)
        self.assertIn("AdMuterService", package.__all__)

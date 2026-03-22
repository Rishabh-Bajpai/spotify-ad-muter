import importlib
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

AppConfig = importlib.import_module("spotify_ad_muter.config").AppConfig


class ConfigTests(unittest.TestCase):
    def test_cli_values_override_defaults(self) -> None:
        config = AppConfig.from_sources(
            cli_values={"ad_volume_percent": 10, "log_level": "DEBUG"},
            config_path=Path("/tmp/does-not-exist.toml"),
        )

        self.assertEqual(config.ad_volume_percent, 10)
        self.assertEqual(config.unmute_delay_ms, 500)
        self.assertEqual(config.log_level, "DEBUG")

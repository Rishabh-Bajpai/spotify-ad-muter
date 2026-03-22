import importlib
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

is_ad_track = importlib.import_module("spotify_ad_muter.mpris").is_ad_track


class MprisTests(unittest.TestCase):
    def test_is_ad_track_matches_known_prefixes(self) -> None:
        self.assertTrue(is_ad_track("spotify:ad:123"))
        self.assertTrue(is_ad_track("/com/spotify/ad/123"))
        self.assertFalse(is_ad_track("spotify:track:123"))
        self.assertFalse(is_ad_track(None))

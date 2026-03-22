import importlib
from unittest.mock import AsyncMock, Mock
from pathlib import Path
import sys
import unittest

from dbus_next.errors import DBusError
from dbus_next.signature import Variant

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

mpris_module = importlib.import_module("spotify_ad_muter.mpris")
MprisWatcher = mpris_module.MprisWatcher
is_ad_track = mpris_module.is_ad_track
unwrap_variant = mpris_module.unwrap_variant


class MprisTests(unittest.TestCase):
    def test_is_ad_track_matches_known_prefixes(self) -> None:
        self.assertTrue(is_ad_track("spotify:ad:123"))
        self.assertTrue(is_ad_track("/com/spotify/ad/123"))
        self.assertFalse(is_ad_track("spotify:track:123"))
        self.assertFalse(is_ad_track(None))

    def test_unwrap_variant_handles_nested_structures(self) -> None:
        wrapped = Variant(
            "a{sv}",
            {
                "mpris:trackid": Variant("s", "spotify:ad:123"),
                "artists": Variant("as", ["one", "two"]),
                "nested": Variant("av", [Variant("s", "value")]),
            },
        )

        self.assertEqual(
            unwrap_variant(wrapped),
            {
                "mpris:trackid": "spotify:ad:123",
                "artists": ["one", "two"],
                "nested": ["value"],
            },
        )


class MprisWatcherTests(unittest.IsolatedAsyncioTestCase):
    async def test_fetch_track_id_reads_metadata(self) -> None:
        logger = Mock()
        watcher = MprisWatcher(logger, poll_interval_ms=1, on_state_change=AsyncMock())
        props = Mock()
        props.call_get = AsyncMock(
            return_value=Variant(
                "a{sv}", {"mpris:trackid": Variant("s", "spotify:track:123")}
            )
        )
        watcher._properties_interface = AsyncMock(return_value=props)

        track_id = await watcher._fetch_track_id()

        self.assertEqual(track_id, "spotify:track:123")

    async def test_fetch_track_id_resets_cached_properties_on_dbus_error(self) -> None:
        logger = Mock()
        watcher = MprisWatcher(logger, poll_interval_ms=1, on_state_change=AsyncMock())
        props = Mock()
        props.call_get = AsyncMock(
            side_effect=DBusError("org.test.Error", "something broke")
        )
        watcher._props = object()
        watcher._properties_interface = AsyncMock(return_value=props)

        track_id = await watcher._fetch_track_id()

        self.assertIsNone(track_id)
        self.assertIsNone(watcher._props)
        logger.debug.assert_called_once()

    async def test_run_deduplicates_repeated_state_changes(self) -> None:
        logger = Mock()
        callback = AsyncMock()
        watcher = MprisWatcher(logger, poll_interval_ms=1, on_state_change=callback)
        track_ids = iter(
            [
                "spotify:track:1",
                "spotify:track:1",
                "spotify:ad:2",
                "spotify:ad:2",
            ]
        )

        async def fake_fetch() -> str:
            value = next(track_ids)
            if value == "spotify:ad:2" and callback.await_count == 1:
                watcher._running = False
            return value

        watcher._fetch_track_id = fake_fetch  # type: ignore[method-assign]

        await watcher.run()

        self.assertEqual(callback.await_count, 2)
        self.assertEqual(callback.await_args_list[0].args, (False, "spotify:track:1"))
        self.assertEqual(callback.await_args_list[1].args, (True, "spotify:ad:2"))

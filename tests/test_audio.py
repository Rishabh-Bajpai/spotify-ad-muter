import importlib
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

audio_module = importlib.import_module("spotify_ad_muter.audio")
SpotifyAudioController = audio_module.SpotifyAudioController
StreamVolumeSnapshot = audio_module.StreamVolumeSnapshot
pulsectl = audio_module.pulsectl


class FakeVolume:
    def __init__(self, value_flat: float) -> None:
        self.value_flat = value_flat


class FakeStream:
    def __init__(
        self,
        index: int,
        name: str = "",
        proplist: dict[str, str] | None = None,
        volume: FakeVolume | None = None,
    ) -> None:
        self.index = index
        self.name = name
        self.proplist = proplist or {}
        self.volume = volume or FakeVolume(1.0)


class SpotifyAudioControllerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.logger = Mock()

    def test_strict_matching_requires_exact_spotify_identity(self) -> None:
        controller = SpotifyAudioController(self.logger, match_mode="strict")

        exact_stream = FakeStream(
            1,
            proplist={
                "application.name": "Spotify",
                "application.process.binary": "spotify",
            },
        )
        partial_stream = FakeStream(
            2,
            name="spotify helper",
            proplist={
                "application.name": "Spotify Helper",
                "application.process.binary": "spotifyd",
            },
        )

        self.assertTrue(controller._is_spotify_stream(exact_stream))
        self.assertFalse(controller._is_spotify_stream(partial_stream))

    def test_relaxed_matching_allows_partial_spotify_identity(self) -> None:
        controller = SpotifyAudioController(self.logger, match_mode="relaxed")

        partial_stream = FakeStream(
            2,
            name="spotify helper",
            proplist={
                "application.name": "Spotify Helper",
                "application.process.binary": "spotifyd",
            },
        )

        self.assertTrue(controller._is_spotify_stream(partial_stream))

    def test_apply_ad_volume_saves_original_volume_once_and_restore_recovers_it(self) -> None:
        controller = SpotifyAudioController(self.logger)
        spotify_stream = FakeStream(
            10,
            name="Spotify",
            proplist={"application.name": "Spotify"},
            volume=FakeVolume(0.7),
        )
        other_stream = FakeStream(
            20,
            name="Browser",
            proplist={"application.name": "Firefox"},
            volume=FakeVolume(0.9),
        )
        pulse = Mock()
        pulse.sink_input_list.return_value = [spotify_stream, other_stream]
        controller._pulse = pulse

        first_changed = controller.apply_ad_volume(20)
        second_changed = controller.apply_ad_volume(10)
        restored = controller.restore_volumes()

        self.assertEqual(first_changed, [10])
        self.assertEqual(second_changed, [10])
        self.assertEqual(restored, [10])
        self.assertEqual(pulse.sink_input_volume_set.call_count, 3)
        self.assertAlmostEqual(
            pulse.sink_input_volume_set.call_args_list[0].args[1].value_flat, 0.2
        )
        self.assertAlmostEqual(
            pulse.sink_input_volume_set.call_args_list[1].args[1].value_flat, 0.1
        )
        self.assertAlmostEqual(
            pulse.sink_input_volume_set.call_args_list[2].args[1].value_flat, 0.7
        )
        self.assertFalse(controller.has_saved_volumes)

    def test_restore_volumes_drops_missing_streams(self) -> None:
        controller = SpotifyAudioController(self.logger)
        pulse = Mock()
        controller._pulse = pulse
        controller._saved_volumes = {
            10: StreamVolumeSnapshot(index=10, volume=FakeVolume(0.4)),
            11: StreamVolumeSnapshot(index=11, volume=FakeVolume(0.6)),
        }

        def sink_input_info(index: int):
            if index == 11:
                raise pulsectl.PulseIndexError("missing stream")
            return object()

        pulse.sink_input_info.side_effect = sink_input_info

        restored = controller.restore_volumes()

        self.assertEqual(restored, [10])
        pulse.sink_input_volume_set.assert_called_once()
        self.assertEqual(pulse.sink_input_volume_set.call_args.args[0], 10)
        self.assertAlmostEqual(
            pulse.sink_input_volume_set.call_args.args[1].value_flat, 0.4
        )
        self.assertEqual(controller._saved_volumes, {})

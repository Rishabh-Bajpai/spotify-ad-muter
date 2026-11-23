import importlib
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

audio_module = importlib.import_module("spotify_ad_muter.audio")
SpotifyAudioController = audio_module.SpotifyAudioController
StreamMuteSnapshot = audio_module.StreamMuteSnapshot
pulsectl = audio_module.pulsectl


class FakeVolume:
    def __init__(self, value_flat: float = 1.0) -> None:
        self.value_flat = value_flat


class FakeStream:
    def __init__(
        self,
        index: int,
        name: str = "",
        proplist: dict[str, str] | None = None,
        mute: bool = False,
        client: int = 0,
        volume: FakeVolume | None = None,
    ) -> None:
        self.index = index
        self.name = name
        self.proplist = proplist or {}
        self.mute = mute
        self.client = client
        self.volume = volume or FakeVolume(1.0)


class FakeClientInfo:
    def __init__(self, name: str = "", proplist: dict[str, str] | None = None) -> None:
        self.name = name
        self.proplist = proplist or {}


class SpotifyAudioControllerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.logger = Mock()

    def test_strict_matching_requires_exact_spotify_identity(self) -> None:
        controller = SpotifyAudioController(self.logger, match_mode="strict")
        pulse = Mock()

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

        self.assertTrue(controller._is_spotify_stream(pulse, exact_stream))
        self.assertFalse(controller._is_spotify_stream(pulse, partial_stream))

    def test_relaxed_matching_allows_partial_spotify_identity(self) -> None:
        controller = SpotifyAudioController(self.logger, match_mode="relaxed")
        pulse = Mock()

        partial_stream = FakeStream(
            2,
            name="spotify helper",
            proplist={
                "application.name": "Spotify Helper",
                "application.process.binary": "spotifyd",
            },
        )

        self.assertTrue(controller._is_spotify_stream(pulse, partial_stream))

    def test_identifies_stream_through_client_info_fallback(self) -> None:
        controller = SpotifyAudioController(self.logger)
        pulse = Mock()

        bare_stream = FakeStream(
            10,
            name="audio-src",
            proplist={"media.role": "music"},
            client=133,
        )
        pulse.client_info.return_value = FakeClientInfo(
            name="spotify",
            proplist={
                "application.name": "spotify",
                "application.process.binary": "spotify",
            },
        )

        self.assertTrue(controller._is_spotify_stream(pulse, bare_stream))
        pulse.client_info.assert_called_once_with(133)

    def test_identifies_stream_through_client_fallback_without_proplist_matches(
        self,
    ) -> None:
        controller = SpotifyAudioController(self.logger)
        pulse = Mock()

        bare_stream = FakeStream(
            10,
            name="audio-src",
            proplist={"media.role": "music"},
            client=133,
        )
        pulse.client_info.return_value = FakeClientInfo(
            name="", proplist={"application.process.binary": "/usr/share/spotify/spotify"}
        )

        self.assertTrue(controller._is_spotify_stream(pulse, bare_stream))

    def test_apply_ad_volume_mutes_stream_and_restore_unmutes(self) -> None:
        controller = SpotifyAudioController(self.logger)
        spotify_stream = FakeStream(
            10,
            name="Spotify",
            proplist={"application.name": "Spotify"},
            mute=False,
        )
        other_stream = FakeStream(
            20,
            name="Browser",
            proplist={"application.name": "Firefox"},
        )
        pulse = Mock()
        pulse.sink_input_list.return_value = [spotify_stream, other_stream]
        pulse.sink_input_info.return_value = spotify_stream
        controller._pulse = pulse

        first_changed = controller.apply_ad_volume(0)
        restored = controller.restore_volumes()

        self.assertEqual(first_changed, [10])
        self.assertEqual(restored, [10])
        self.assertEqual(pulse.sink_input_mute.call_count, 2)
        pulse.sink_input_mute.assert_any_call(10, True)
        pulse.sink_input_mute.assert_any_call(10, False)
        # Muting never touched volume, so restore must not rewrite it.
        pulse.sink_input_volume_set.assert_not_called()
        self.assertFalse(controller.has_saved_volumes)

    def test_apply_ad_volume_skips_already_muted_streams(self) -> None:
        controller = SpotifyAudioController(self.logger)
        spotify_stream = FakeStream(
            10,
            name="Spotify",
            proplist={"application.name": "Spotify"},
            mute=True,
        )
        pulse = Mock()
        pulse.sink_input_list.return_value = [spotify_stream]
        controller._pulse = pulse

        changed = controller.apply_ad_volume(0)

        self.assertEqual(changed, [])
        # A stream muted while no ad is active is stuck, so it must be healed
        # rather than left silent.
        pulse.sink_input_mute.assert_called_once_with(10, False)

    def test_restore_volumes_preserves_originally_muted_streams(self) -> None:
        controller = SpotifyAudioController(self.logger)
        pulse = Mock()
        pulse.sink_input_list.return_value = []
        controller._pulse = pulse

        spotify_stream = FakeStream(
            10,
            name="Spotify",
            proplist={"application.name": "Spotify"},
            mute=True,
        )
        pulse.sink_input_list.return_value = [spotify_stream]

        controller.apply_ad_volume(0)
        pulse.sink_input_mute.reset_mock()
        pulse.sink_input_list.return_value = [spotify_stream]
        pulse.sink_input_info.return_value = spotify_stream

        restored = controller.restore_volumes()

        self.assertEqual(restored, [10])
        pulse.sink_input_volume_set.assert_not_called()
        self.assertFalse(controller.has_saved_volumes)

    def test_restore_volumes_drops_missing_streams(self) -> None:
        controller = SpotifyAudioController(self.logger)
        pulse = Mock()
        controller._pulse = pulse
        controller._saved_mute_states = {
            10: StreamMuteSnapshot(index=10, muted=False),
            11: StreamMuteSnapshot(index=11, muted=False),
        }

        def sink_input_info(index: int):
            if index == 11:
                raise pulsectl.PulseIndexError("missing stream")
            return FakeStream(10, volume=FakeVolume(0.4))

        pulse.sink_input_info.side_effect = sink_input_info

        restored = controller.restore_volumes()

        self.assertEqual(restored, [10])
        pulse.sink_input_mute.assert_called_once_with(10, False)
        self.assertEqual(controller._saved_mute_states, {})

    def test_recover_stuck_streams_unmutes_muted_spotify_streams(self) -> None:
        controller = SpotifyAudioController(self.logger)
        stuck = FakeStream(
            10,
            name="audio-src",
            proplist={"media.role": "music"},
            mute=True,
            client=133,
        )
        normal = FakeStream(
            20,
            name="Spotify",
            proplist={"application.name": "Spotify"},
            mute=False,
        )
        pulse = Mock()
        pulse.sink_input_list.return_value = [stuck, normal]
        pulse.client_info.return_value = FakeClientInfo(
            name="spotify",
            proplist={"application.name": "spotify", "application.process.binary": "spotify"},
        )
        controller._pulse = pulse

        recovered = controller.recover_stuck_streams()

        self.assertEqual(recovered, [10])
        pulse.sink_input_mute.assert_called_once_with(10, False)
        pulse.sink_input_volume_set.assert_not_called()

    def test_recover_skips_non_spotify_streams(self) -> None:
        controller = SpotifyAudioController(self.logger)
        firefox = FakeStream(
            20,
            name="Firefox",
            proplist={"application.name": "Firefox"},
            mute=True,
        )
        pulse = Mock()
        pulse.sink_input_list.return_value = [firefox]
        controller._pulse = pulse

        recovered = controller.recover_stuck_streams()

        self.assertEqual(recovered, [])
        pulse.sink_input_mute.assert_not_called()

    def test_stuck_stream_is_unmuted_even_when_volume_set_fails(self) -> None:
        controller = SpotifyAudioController(self.logger)
        stuck = FakeStream(
            10,
            name="Spotify",
            proplist={"application.name": "Spotify"},
            mute=True,
        )
        pulse = Mock()
        pulse.sink_input_list.return_value = [stuck]
        pulse.sink_input_volume_set.side_effect = pulsectl.PulseOperationFailed("aux map")
        controller._pulse = pulse

        recovered = controller.recover_stuck_streams()

        self.assertEqual(recovered, [10])
        pulse.sink_input_mute.assert_called_once_with(10, False)
        pulse.sink_input_volume_set.assert_not_called()

    def test_restore_continues_after_volume_error_on_one_stream(self) -> None:
        controller = SpotifyAudioController(self.logger)
        pulse = Mock()
        controller._pulse = pulse
        controller._saved_mute_states = {
            10: StreamMuteSnapshot(index=10, muted=False),
            11: StreamMuteSnapshot(index=11, muted=False),
        }
        pulse.sink_input_info.side_effect = lambda index: FakeStream(index)
        pulse.sink_input_volume_set.side_effect = pulsectl.PulseOperationFailed("aux map")

        restored = controller.restore_volumes()

        self.assertEqual(restored, [10, 11])
        pulse.sink_input_mute.assert_any_call(10, False)
        pulse.sink_input_mute.assert_any_call(11, False)
        self.assertFalse(controller.has_saved_volumes)

    def test_apply_ad_volume_drops_snapshots_for_vanished_streams(self) -> None:
        controller = SpotifyAudioController(self.logger)
        pulse = Mock()
        controller._pulse = pulse
        controller._saved_mute_states = {99: StreamMuteSnapshot(index=99, muted=False)}
        new_stream = FakeStream(
            10,
            name="Spotify",
            proplist={"application.name": "Spotify"},
            mute=False,
        )
        pulse.sink_input_list.return_value = [new_stream]

        controller.apply_ad_volume(0)
        restored = controller.restore_volumes()

        self.assertEqual(list(controller._saved_mute_states), [])
        self.assertEqual(restored, [10])
        pulse.sink_input_mute.assert_any_call(10, False)

    def test_apply_ad_volume_heals_stream_already_muted_by_stale_state(self) -> None:
        controller = SpotifyAudioController(self.logger)
        pulse = Mock()
        controller._pulse = pulse
        muted = FakeStream(
            10,
            name="Spotify",
            proplist={"application.name": "Spotify"},
            mute=True,
        )
        pulse.sink_input_list.return_value = [muted]

        changed = controller.apply_ad_volume(0)

        self.assertEqual(changed, [])
        pulse.sink_input_mute.assert_called_once_with(10, False)
        self.assertTrue(controller.has_saved_volumes)

    def test_release_all_unmutes_tracked_and_live_streams(self) -> None:
        controller = SpotifyAudioController(self.logger)
        pulse = Mock()
        controller._pulse = pulse
        controller._saved_mute_states = {42: StreamMuteSnapshot(index=42, muted=False)}
        live = FakeStream(
            10,
            name="Spotify",
            proplist={"application.name": "Spotify"},
            mute=True,
        )
        pulse.sink_input_list.return_value = [live]

        released = controller.release_all()

        self.assertEqual(sorted(released), [10, 42])
        pulse.sink_input_mute.assert_any_call(10, False)
        pulse.sink_input_mute.assert_any_call(42, False)
        self.assertFalse(controller.has_saved_volumes)

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

import pulsectl


@dataclass(slots=True)
class StreamMuteSnapshot:
    index: int
    muted: bool


class SpotifyAudioController:
    def __init__(self, logger: logging.Logger, *, match_mode: str = "relaxed") -> None:
        self._logger = logger
        self._match_mode = match_mode
        self._pulse: pulsectl.Pulse | None = None
        self._saved_mute_states: dict[int, StreamMuteSnapshot] = {}

    @property
    def has_saved_volumes(self) -> bool:
        return bool(self._saved_mute_states)

    def close(self) -> None:
        if self._pulse is not None:
            self._pulse.close()
            self._pulse = None

    def apply_ad_volume(self, percent: int) -> list[int]:
        pulse = self._pulse_client()
        streams = self._spotify_streams(pulse)
        live_indexes = {stream.index for stream in streams}

        # Drop snapshots for streams that disappeared (Spotify re-created its
        # audio stream, app restart, etc.) so a stale index cannot keep us from
        # tracking the live stream and restoring it later.
        for stale_index in set(self._saved_mute_states) - live_indexes:
            self._saved_mute_states.pop(stale_index, None)

        changed: list[int] = []
        for stream in streams:
            if stream.mute and stream.index not in self._saved_mute_states:
                # Muted but not by us, so it is stuck (likely from a previous
                # run that died before unmuting). Remember it as "should be
                # unmuted" and clear it now so the user is not left silent.
                self._saved_mute_states[stream.index] = StreamMuteSnapshot(
                    index=stream.index,
                    muted=False,
                )
                try:
                    self._set_mute(pulse, stream.index, False)
                except pulsectl.PulseOperationFailed:
                    pass
                continue
            if stream.index not in self._saved_mute_states:
                self._saved_mute_states[stream.index] = StreamMuteSnapshot(
                    index=stream.index,
                    muted=False,
                )
            if not stream.mute:
                self._set_mute(pulse, stream.index, True)
                changed.append(stream.index)
        return changed

    def restore_volumes(self) -> list[int]:
        pulse = self._pulse_client()
        restored: list[int] = []
        for index, snapshot in list(self._saved_mute_states.items()):
            try:
                stream_info = pulse.sink_input_info(index)
            except (pulsectl.PulseIndexError, pulsectl.PulseOperationFailed):
                self._saved_mute_states.pop(index, None)
                continue
            try:
                if not snapshot.muted:
                    self._set_mute(pulse, index, False)
                # Volume was never changed while muting, so there is nothing to
                # restore. Setting it anyway fails on streams with a channel
                # map pulsectl cannot parse (e.g. aux0,aux1) and aborted the
                # whole restore loop, leaving earlier streams muted.
                restored.append(index)
            finally:
                self._saved_mute_states.pop(index, None)
        return restored

    def recover_stuck_streams(self) -> list[int]:
        pulse = self._pulse_client()
        recovered: list[int] = []
        for stream in self._spotify_streams(pulse):
            if stream.mute:
                # Unmute first: the user must never be left silent because a
                # follow-up call failed.
                self._set_mute(pulse, stream.index, False)
                recovered.append(stream.index)
        if recovered:
            self._logger.info("Recovered %d stuck stream(s): %s", len(recovered), recovered)
        return recovered

    def release_all(self) -> list[int]:
        """Unmute every stream this controller muted, ignoring saved state."""
        pulse = self._pulse_client()
        released: list[int] = []
        for index in set(self._saved_mute_states) | set(self.current_stream_indexes()):
            try:
                self._set_mute(pulse, index, False)
                released.append(index)
            except (pulsectl.PulseIndexError, pulsectl.PulseOperationFailed):
                continue
        self._saved_mute_states.clear()
        return released

    def _set_mute(self, pulse: pulsectl.Pulse, index: int, muted: bool) -> None:
        pulse.sink_input_mute(index, muted)

    def current_stream_indexes(self) -> list[int]:
        return [stream.index for stream in self._spotify_streams(self._pulse_client())]

    def _pulse_client(self) -> pulsectl.Pulse:
        if self._pulse is None:
            self._pulse = pulsectl.Pulse("spotify-ad-muter")
        return self._pulse

    def _spotify_streams(self, pulse: pulsectl.Pulse) -> list[Any]:
        streams = pulse.sink_input_list()
        return [stream for stream in streams if self._is_spotify_stream(pulse, stream)]

    def _is_spotify_stream(self, pulse: pulsectl.Pulse, stream: Any) -> bool:
        stream_name = (getattr(stream, "name", "") or "").strip().lower()
        properties = {
            str(key).lower(): str(value).strip().lower()
            for key, value in dict(stream.proplist).items()
        }
        application_name = properties.get("application.name", "")
        binary_name = properties.get("application.process.binary", "")

        if application_name == "spotify" or stream_name == "spotify":
            return True
        if self._match_mode == "strict":
            return False
        if "spotify" in binary_name or "spotify" in application_name or "spotify" in stream_name:
            return True

        try:
            client_info = pulse.client_info(stream.client)
            client_props = {
                str(k).lower(): str(v).strip().lower()
                for k, v in dict(client_info.proplist).items()
            }
            client_name = (getattr(client_info, "name", "") or "").strip().lower()
            client_app = client_props.get("application.name", "")
            client_binary = client_props.get("application.process.binary", "")
            return (
                client_name == "spotify"
                or "spotify" in client_app
                or "spotify" in client_binary
            )
        except Exception:
            return False

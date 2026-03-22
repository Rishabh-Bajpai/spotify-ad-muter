from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import logging
from typing import Any

import pulsectl


@dataclass(slots=True)
class StreamVolumeSnapshot:
    index: int
    volume: pulsectl.PulseVolumeInfo


class SpotifyAudioController:
    def __init__(self, logger: logging.Logger, *, match_mode: str = "relaxed") -> None:
        self._logger = logger
        self._match_mode = match_mode
        self._pulse: pulsectl.Pulse | None = None
        self._saved_volumes: dict[int, StreamVolumeSnapshot] = {}

    @property
    def has_saved_volumes(self) -> bool:
        return bool(self._saved_volumes)

    def close(self) -> None:
        if self._pulse is not None:
            self._pulse.close()
            self._pulse = None

    def apply_ad_volume(self, percent: int) -> list[int]:
        pulse = self._pulse_client()
        streams = self._spotify_streams(pulse)

        changed: list[int] = []
        for stream in streams:
            if stream.index not in self._saved_volumes:
                self._saved_volumes[stream.index] = StreamVolumeSnapshot(
                    index=stream.index,
                    volume=deepcopy(stream.volume),
                )
            volume = deepcopy(stream.volume)
            volume.value_flat = percent / 100
            pulse.sink_input_volume_set(stream.index, volume)
            changed.append(stream.index)
        return changed

    def restore_volumes(self) -> list[int]:
        pulse = self._pulse_client()
        restored: list[int] = []
        for index, snapshot in list(self._saved_volumes.items()):
            try:
                pulse.sink_input_info(index)
            except (pulsectl.PulseIndexError, pulsectl.PulseOperationFailed):
                self._saved_volumes.pop(index, None)
                continue
            pulse.sink_input_volume_set(index, deepcopy(snapshot.volume))
            restored.append(index)
            self._saved_volumes.pop(index, None)
        return restored

    def current_stream_indexes(self) -> list[int]:
        return [stream.index for stream in self._spotify_streams(self._pulse_client())]

    def _pulse_client(self) -> pulsectl.Pulse:
        if self._pulse is None:
            self._pulse = pulsectl.Pulse("spotify-ad-muter")
        return self._pulse

    def _spotify_streams(self, pulse: pulsectl.Pulse) -> list[Any]:
        streams = pulse.sink_input_list()
        return [stream for stream in streams if self._is_spotify_stream(stream)]

    def _is_spotify_stream(self, stream: Any) -> bool:
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
        return (
            "spotify" in binary_name
            or "spotify" in application_name
            or "spotify" in stream_name
        )

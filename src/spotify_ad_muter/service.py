from __future__ import annotations

import asyncio
import contextlib
import logging

from .audio import SpotifyAudioController
from .config import AppConfig
from .mpris import MprisWatcher


class AdMuterService:
    def __init__(self, config: AppConfig, logger: logging.Logger | None = None) -> None:
        self._config = config
        self._logger = logger or logging.getLogger("spotify_ad_muter")
        self._audio = SpotifyAudioController(
            self._logger, match_mode=config.stream_match_mode
        )
        self._watcher = MprisWatcher(
            self._logger,
            poll_interval_ms=config.poll_interval_ms,
            on_state_change=self._handle_state_change,
        )
        self._ad_active = False
        self._audio_lock = asyncio.Lock()
        self._last_muted_streams: set[int] = set()
        self._restore_task: asyncio.Task[None] | None = None
        self._shutdown = asyncio.Event()

    async def run(self) -> None:
        watcher_task = asyncio.create_task(self._watcher.run(), name="mpris-watcher")
        reconcile_task = asyncio.create_task(
            self._reconcile_loop(), name="audio-reconcile"
        )

        try:
            await self._shutdown.wait()
        finally:
            await self._watcher.stop()
            watcher_task.cancel()
            reconcile_task.cancel()
            if self._restore_task is not None:
                self._restore_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self._restore_task
            with contextlib.suppress(asyncio.CancelledError):
                await watcher_task
            with contextlib.suppress(asyncio.CancelledError):
                await reconcile_task
            if self._ad_active or self._audio.has_saved_volumes:
                await self._restore_now()
            self._audio.close()

    async def stop(self) -> None:
        self._shutdown.set()

    async def _handle_state_change(self, is_ad: bool, track_id: str | None) -> None:
        if is_ad:
            if not self._ad_active:
                self._logger.info("Ad detected: %s", track_id or "unknown track")
            self._ad_active = True
            self._cancel_restore_task()
            await self._apply_ad_volume()
            return

        if self._ad_active:
            self._logger.info(
                "Ad finished, restoring volume in %sms", self._config.unmute_delay_ms
            )
            self._ad_active = False
            self._last_muted_streams.clear()
            self._schedule_restore()

    async def _reconcile_loop(self) -> None:
        interval = self._config.poll_interval_ms / 1000
        while True:
            await asyncio.sleep(interval)
            if self._ad_active:
                await self._apply_ad_volume()

    async def _apply_ad_volume(self) -> None:
        try:
            async with self._audio_lock:
                changed = await asyncio.to_thread(
                    self._audio.apply_ad_volume, self._config.ad_volume_percent
                )
            changed_set = set(changed)
            if changed and changed_set != self._last_muted_streams:
                self._logger.debug(
                    "Adjusted Spotify stream volume for %s",
                    ", ".join(map(str, changed)),
                )
            self._last_muted_streams = changed_set
        except Exception as error:
            self._logger.warning("Failed to change Spotify stream volume: %s", error)

    def _schedule_restore(self) -> None:
        self._cancel_restore_task()
        self._restore_task = asyncio.create_task(
            self._delayed_restore(), name="volume-restore"
        )

    def _cancel_restore_task(self) -> None:
        if self._restore_task is not None:
            self._restore_task.cancel()
            self._restore_task = None

    async def _delayed_restore(self) -> None:
        try:
            await asyncio.sleep(self._config.unmute_delay_ms / 1000)
            if not self._ad_active:
                await self._restore_now()
        except asyncio.CancelledError:
            raise
        finally:
            self._restore_task = None

    async def _restore_now(self) -> None:
        try:
            async with self._audio_lock:
                restored = await asyncio.to_thread(self._audio.restore_volumes)
            if restored:
                self._logger.info(
                    "Restored Spotify stream volume for %s",
                    ", ".join(map(str, restored)),
                )
            self._last_muted_streams.clear()
        except Exception as error:
            self._logger.warning("Failed to restore Spotify stream volume: %s", error)

from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable, cast

from dbus_next.aio.message_bus import MessageBus
from dbus_next.constants import BusType
from dbus_next.errors import DBusError
from dbus_next.signature import Variant


MPRIS_SERVICE = "org.mpris.MediaPlayer2.spotify"
MPRIS_PATH = "/org/mpris/MediaPlayer2"
MPRIS_PLAYER_INTERFACE = "org.mpris.MediaPlayer2.Player"
AD_PREFIXES = ("spotify:ad", "/com/spotify/ad/")


StateCallback = Callable[[bool, str | None], Awaitable[None]]


def unwrap_variant(value: Any) -> Any:
    if isinstance(value, Variant):
        return unwrap_variant(value.value)
    if isinstance(value, dict):
        return {key: unwrap_variant(item) for key, item in value.items()}
    if isinstance(value, list):
        return [unwrap_variant(item) for item in value]
    return value


def is_ad_track(track_id: str | None) -> bool:
    if not track_id:
        return False
    return any(track_id.startswith(prefix) for prefix in AD_PREFIXES)


class MprisWatcher:
    def __init__(
        self,
        logger: logging.Logger,
        *,
        poll_interval_ms: int,
        on_state_change: StateCallback,
    ) -> None:
        self._logger = logger
        self._poll_interval = poll_interval_ms / 1000
        self._on_state_change = on_state_change
        self._bus: MessageBus | None = None
        self._props = None
        self._last_state: bool | None = None
        self._last_track_id: str | None = None
        self._running = False

    async def run(self) -> None:
        self._running = True
        while self._running:
            track_id = await self._fetch_track_id()
            is_ad = is_ad_track(track_id)
            if is_ad != self._last_state or track_id != self._last_track_id:
                self._last_state = is_ad
                self._last_track_id = track_id
                await self._on_state_change(is_ad, track_id)
            await asyncio.sleep(self._poll_interval)

    async def stop(self) -> None:
        self._running = False
        if self._bus is not None:
            self._bus.disconnect()
            self._bus = None
        self._props = None

    async def _fetch_track_id(self) -> str | None:
        try:
            props = await self._properties_interface()
            if props is None:
                return None
            metadata_variant = await cast(Any, props).call_get(
                MPRIS_PLAYER_INTERFACE, "Metadata"
            )
            metadata = unwrap_variant(metadata_variant)
            track_id = metadata.get("mpris:trackid")
            if track_id is None:
                return None
            return str(track_id)
        except DBusError as error:
            if error.text not in {
                "The name is not activatable",
                "The name org.mpris.MediaPlayer2.spotify was not provided by any .service files",
            }:
                self._logger.debug("MPRIS query failed: %s", error)
            self._props = None
            return None
        except Exception as error:
            self._logger.debug("Unexpected MPRIS error: %s", error)
            self._props = None
            return None

    async def _properties_interface(self):
        if self._props is not None:
            return self._props
        if self._bus is None:
            self._bus = await MessageBus(bus_type=BusType.SESSION).connect()
        introspection = await self._bus.introspect(MPRIS_SERVICE, MPRIS_PATH)
        proxy_object = self._bus.get_proxy_object(
            MPRIS_SERVICE, MPRIS_PATH, introspection
        )
        self._props = proxy_object.get_interface("org.freedesktop.DBus.Properties")
        return self._props

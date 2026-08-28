"""Media player platform for SpinSense."""

import logging
from typing import Any

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .entity import SpinSenseEntity
from .play_clock import parse as parse_play_clock

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SpinSense media player."""
    entities = [SpinSenseMediaPlayer(hass, config_entry)]
    async_add_entities(entities)


class SpinSenseMediaPlayer(SpinSenseEntity, MediaPlayerEntity):
    """Representation of SpinSense as a media player.

    No supported features: a record player cannot be played, paused or seeked
    from Home Assistant, and claiming SEEK to get a draggable progress bar would
    be a lie. Duration and position render without any feature flag.
    """

    _attr_supported_features = MediaPlayerEntityFeature(0)

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the media player."""
        super().__init__(hass, config_entry, "Turn Table")

        self._attr_unique_id = f"{DOMAIN}_{config_entry.entry_id}"
        self._attr_name = "Turn Table"

        self._api = self.hass.data[DOMAIN][config_entry.entry_id]["api"]

        self._state = MediaPlayerState.IDLE
        self._title = None
        self._artist = None
        self._album = None
        self._album_art_url = None
        self._listener_remove = None
        self._media_duration = None
        self._media_position = None
        self._media_position_updated_at = None

        self._update_from_api()

    async def async_added_to_hass(self) -> None:
        """Subscribe to SpinSense state updates."""
        await super().async_added_to_hass()
        self._listener_remove = self._api.async_add_listener(
            self._async_handle_api_update
        )

    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe when removed."""
        if self._listener_remove:
            self._listener_remove()
        await super().async_will_remove_from_hass()

    async def _async_handle_api_update(self) -> None:
        self._update_from_api()
        self.async_write_ha_state()

    def _update_from_api(self) -> None:
        payload = self._api.state
        status = payload.get("status_msg", "").lower()
        engine_active = payload.get("engine_active", False)

        if not engine_active or status == "stopped":
            self._state = MediaPlayerState.OFF
        elif status == "playing":
            self._state = MediaPlayerState.PLAYING
        else:
            self._state = MediaPlayerState.IDLE

        track = payload.get("track", {}) or {}
        self._title = track.get("title") or None
        self._artist = track.get("artist") or None
        self._album = track.get("album") or None

        art_url = track.get("art_url") or None
        if art_url and art_url.startswith(("http://", "https://")):
            self._album_art_url = art_url
        else:
            self._album_art_url = None

        self._update_position(payload)

    def _update_position(self, payload: dict) -> None:
        """Anchor the progress bar, or clear it.

        The anchor is fixed for the length of the track (see play_clock.py), so
        these attributes change when the track does and not once a second —
        which matters, because the engine pushes a frame every second and each
        changed attribute is a state_changed event and a recorder row.
        """
        if self._state != MediaPlayerState.PLAYING:
            # Nothing on the platter: a frozen bar from the last track would be
            # worse than none.
            self._media_duration = None
            self._media_position = None
            self._media_position_updated_at = None
            return

        duration, position, valid_at = parse_play_clock(payload)
        self._media_duration = duration
        self._media_position = position
        self._media_position_updated_at = (
            dt_util.utc_from_timestamp(valid_at) if valid_at is not None else None
        )

    @property
    def available(self) -> bool:
        """Return True if the integration can reach the SpinSense service."""
        return self._api.is_available()

    @property
    def state(self) -> MediaPlayerState | None:
        """Return the state of the player."""
        return self._state

    @property
    def media_title(self) -> str | None:
        """Return the title of current playing media."""
        return self._title

    @property
    def media_artist(self) -> str | None:
        """Return the artist of current playing media."""
        return self._artist

    @property
    def media_album_name(self) -> str | None:
        """Return the album name of current playing media."""
        return self._album

    @property
    def media_content_type(self) -> str | None:
        """Return the content type of current playing media."""
        return MediaType.MUSIC if self._title else None

    @property
    def media_image_url(self) -> str | None:
        """Return the album art URL."""
        return self._album_art_url

    @property
    def media_duration(self) -> int | None:
        """Length of the current track, when SpinSense could resolve one."""
        return self._media_duration

    @property
    def media_position(self) -> int | None:
        """Playhead at `media_position_updated_at`, not right now.

        Home Assistant extrapolates the live value from this pair, so a template
        wanting the current position must do the same arithmetic — as with every
        media player. The number here is where the needle was when SpinSense
        identified the track, which for a mid-side needle drop is the offset it
        actually joined at rather than zero.
        """
        return self._media_position

    @property
    def media_position_updated_at(self):
        """The instant `media_position` was true."""
        return self._media_position_updated_at

    async def async_play_media(
        self, media_type: str, media_id: str, **kwargs: Any
    ) -> None:
        """Play a piece of media."""
        _LOGGER.debug("Play media called (not supported for vinyl)")

    async def async_media_play(self) -> None:
        """Send play command."""
        _LOGGER.debug("Play command called (not supported for vinyl)")

    async def async_media_pause(self) -> None:
        """Send pause command."""
        _LOGGER.debug("Pause command called (not supported for vinyl)")

    async def async_media_stop(self) -> None:
        """Send stop command."""
        _LOGGER.debug("Stop command called (not supported for vinyl)")

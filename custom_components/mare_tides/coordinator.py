"""Data coordinator for Mare."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import TideApiError, TideAuthError, TideData
from .const import (
    CONF_HILO_ONLY,
    CONF_PROVIDER,
    CONF_STATION_ID,
    DOMAIN,
    FETCH_INTERVAL,
    WINDOW_DAYS_AFTER,
    WINDOW_DAYS_BEFORE,
)
from .providers import PROVIDERS

_LOGGER = logging.getLogger(__name__)

type MareTidesConfigEntry = ConfigEntry[MareTidesCoordinator]


class MareTidesCoordinator(DataUpdateCoordinator[TideData]):
    """Fetches the tide window for one station once an hour."""

    config_entry: MareTidesConfigEntry

    def __init__(self, hass: HomeAssistant, entry: MareTidesConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {entry.title}",
            update_interval=FETCH_INTERVAL,
        )
        self.provider = PROVIDERS[entry.data[CONF_PROVIDER]]
        self.client = self.provider.client(async_get_clientsession(hass), entry.data.get(CONF_API_KEY))
        self.station_id: str = entry.data[CONF_STATION_ID]
        self.hilo_only: bool = entry.data.get(CONF_HILO_ONLY, False)

    async def _async_update_data(self) -> TideData:
        midnight = dt_util.start_of_local_day()
        start = midnight - timedelta(days=WINDOW_DAYS_BEFORE)
        end = midnight + timedelta(days=WINDOW_DAYS_AFTER)
        try:
            return await self.client.async_get_tides(self.station_id, start, end, self.hilo_only)
        except TideAuthError as err:
            # Home Assistant then asks for a new key (the reauth step of the config flow).
            raise ConfigEntryAuthFailed(str(err)) from err
        except TideApiError as err:
            raise UpdateFailed(str(err)) from err

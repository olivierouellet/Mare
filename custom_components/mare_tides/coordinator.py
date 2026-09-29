"""Data coordinator for DFO Tides."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import DfoApiError, DfoClient, TideData
from .const import CONF_STATION_ID, DOMAIN, FETCH_INTERVAL, WINDOW_DAYS_AFTER, WINDOW_DAYS_BEFORE

_LOGGER = logging.getLogger(__name__)

type DfoTidesConfigEntry = ConfigEntry[DfoTidesCoordinator]


class DfoTidesCoordinator(DataUpdateCoordinator[TideData]):
    """Fetches the tide window for one station once an hour."""

    config_entry: DfoTidesConfigEntry

    def __init__(self, hass: HomeAssistant, entry: DfoTidesConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {entry.title}",
            update_interval=FETCH_INTERVAL,
        )
        self.client = DfoClient(async_get_clientsession(hass))
        self.station_id: str = entry.data[CONF_STATION_ID]

    async def _async_update_data(self) -> TideData:
        midnight = dt_util.start_of_local_day()
        start = midnight - timedelta(days=WINDOW_DAYS_BEFORE)
        end = midnight + timedelta(days=WINDOW_DAYS_AFTER)
        try:
            return await self.client.async_get_tides(self.station_id, start, end)
        except DfoApiError as err:
            raise UpdateFailed(str(err)) from err

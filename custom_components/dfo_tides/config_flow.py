"""Config and options flows for DFO Tides: pick a station near a location or by name."""
from __future__ import annotations

import logging
import time
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_LOCATION, CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    BooleanSelector,
    LocationSelector,
    LocationSelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)
from homeassistant.util import slugify

from .api import DfoApiError, DfoClient, Station, nearest, search, station_label
from .const import (
    CONF_LATITUDE,
    CONF_LEGACY_OBJECT_ID,
    CONF_LONGITUDE,
    CONF_STATION_CODE,
    CONF_STATION_ID,
    CONF_STATION_NAME,
    CONF_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    MAX_UPDATE_INTERVAL,
    MIN_UPDATE_INTERVAL,
    NEAREST_COUNT,
    SEARCH_LIMIT,
)

_LOGGER = logging.getLogger(__name__)

STATIONS_CACHE_SECONDS = 24 * 3600
CONF_STATION = "station"
CONF_SEARCH = "search"
CONF_QUERY = "query"
CONF_CHANGE_STATION = "change_station"


async def async_get_stations(hass: HomeAssistant) -> list[Station]:
    """Station list, cached in memory for a day (it is ~1 MB and rarely changes)."""
    cache = hass.data.setdefault(DOMAIN, {})
    cached = cache.get("stations")
    if cached and time.monotonic() - cached[0] < STATIONS_CACHE_SECONDS:
        return cached[1]
    stations = await DfoClient(async_get_clientsession(hass)).async_get_stations()
    cache["stations"] = (time.monotonic(), stations)
    return stations


def station_data(station: Station) -> dict[str, Any]:
    return {
        CONF_STATION_ID: station.id,
        CONF_STATION_CODE: station.code,
        CONF_STATION_NAME: station.name,
        CONF_LATITUDE: station.latitude,
        CONF_LONGITUDE: station.longitude,
    }


def _station_selector(ranked: list[tuple[Station, float]]) -> SelectSelector:
    return SelectSelector(
        SelectSelectorConfig(
            options=[SelectOptionDict(value=s.id, label=station_label(s, d)) for s, d in ranked],
            mode=SelectSelectorMode.LIST,
        )
    )


class StationPickerMixin:
    """Shared location → nearest stations → search steps for both flows."""

    hass: HomeAssistant
    _stations: list[Station]
    _location: tuple[float, float]

    async def _async_station_chosen(self, station: Station) -> ConfigFlowResult:
        raise NotImplementedError

    async def _async_load_stations(self) -> str | None:
        """Load the station list; returns an error key on failure."""
        try:
            self._stations = await async_get_stations(self.hass)
        except DfoApiError as err:
            _LOGGER.warning("Could not load DFO stations: %s", err)
            return "cannot_connect"
        return None if self._stations else "no_stations"

    async def async_step_location(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Choose the reference point; defaults to the Home Assistant home location."""
        errors: dict[str, str] = {}
        if user_input is not None:
            loc = user_input[CONF_LOCATION]
            self._location = (loc[CONF_LATITUDE], loc[CONF_LONGITUDE])
            if (error := await self._async_load_stations()) is None:
                return await self.async_step_station()
            errors["base"] = error

        home = {CONF_LATITUDE: self.hass.config.latitude, CONF_LONGITUDE: self.hass.config.longitude}
        return self.async_show_form(  # type: ignore[attr-defined]
            step_id="location",
            data_schema=vol.Schema(
                {vol.Required(CONF_LOCATION, default=home): LocationSelector(LocationSelectorConfig(radius=False))}
            ),
            errors=errors,
        )

    async def async_step_station(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Pick one of the nearest stations, or go to search."""
        if user_input is not None:
            if user_input.get(CONF_SEARCH) or not user_input.get(CONF_STATION):
                return await self.async_step_search()
            return await self._async_station_chosen(self._by_id(user_input[CONF_STATION]))

        ranked = nearest(self._stations, *self._location, NEAREST_COUNT)
        return self.async_show_form(  # type: ignore[attr-defined]
            step_id="station",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_STATION, default=ranked[0][0].id): _station_selector(ranked),
                    vol.Optional(CONF_SEARCH, default=False): BooleanSelector(),
                }
            ),
        )

    async def async_step_search(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Search all stations by name or code, nearest first."""
        errors: dict[str, str] = {}
        query = ""
        ranked: list[tuple[Station, float]] = []
        if user_input is not None:
            query = user_input.get(CONF_QUERY, "").strip()
            ranked = search(self._stations, query, *self._location, SEARCH_LIMIT) if query else []
            chosen = user_input.get(CONF_STATION)
            if chosen and any(s.id == chosen for s, _ in ranked):
                return await self._async_station_chosen(self._by_id(chosen))
            if query and not ranked:
                errors[CONF_QUERY] = "no_match"

        schema: dict[Any, Any] = {vol.Required(CONF_QUERY, default=query): TextSelector()}
        if ranked:
            schema[vol.Optional(CONF_STATION)] = _station_selector(ranked)
        return self.async_show_form(  # type: ignore[attr-defined]
            step_id="search", data_schema=vol.Schema(schema), errors=errors
        )

    def _by_id(self, station_id: str) -> Station:
        return next(s for s in self._stations if s.id == station_id)


class DfoTidesConfigFlow(StationPickerMixin, ConfigFlow, domain=DOMAIN):
    """Add a tide station."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return await self.async_step_location(user_input)

    async def _async_station_chosen(self, station: Station) -> ConfigFlowResult:
        await self.async_set_unique_id(station.id)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title=station.name, data=station_data(station))

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import a legacy YAML sensor."""
        station_id = import_data[CONF_STATION_ID]
        await self.async_set_unique_id(station_id)
        self._abort_if_unique_id_configured()
        if await self._async_load_stations() is not None:
            return self.async_abort(reason="cannot_connect")
        station = next((s for s in self._stations if s.id == station_id), None)
        if station is None:
            return self.async_abort(reason="unknown_station")
        data = station_data(station)
        # The YAML sensor's entity ID was derived from its name (default "DFO Tides").
        data[CONF_LEGACY_OBJECT_ID] = slugify(import_data.get(CONF_NAME) or "DFO Tides")
        options = {}
        if interval := import_data.get(CONF_UPDATE_INTERVAL):
            options[CONF_UPDATE_INTERVAL] = min(max(interval, MIN_UPDATE_INTERVAL), MAX_UPDATE_INTERVAL)
        return self.async_create_entry(
            title=import_data.get(CONF_NAME) or station.name, data=data, options=options
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> DfoTidesOptionsFlow:
        return DfoTidesOptionsFlow()


class DfoTidesOptionsFlow(StationPickerMixin, OptionsFlow):
    """Change the station or the update interval."""

    def __init__(self) -> None:
        self._new_options: dict[str, Any] = {}

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        entry = self.config_entry
        if user_input is not None:
            self._new_options = {**entry.options, CONF_UPDATE_INTERVAL: int(user_input[CONF_UPDATE_INTERVAL])}
            if user_input.get(CONF_CHANGE_STATION):
                return await self.async_step_location()
            return self.async_create_entry(data=self._new_options)

        station = entry.data.get(CONF_STATION_NAME, entry.title)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_UPDATE_INTERVAL,
                        default=entry.options.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=MIN_UPDATE_INTERVAL,
                            max=MAX_UPDATE_INTERVAL,
                            step=30,
                            unit_of_measurement="s",
                            mode=NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Optional(CONF_CHANGE_STATION, default=False): BooleanSelector(),
                }
            ),
            description_placeholders={"station": f"{station} ({entry.data.get(CONF_STATION_CODE, '')})"},
        )

    async def _async_station_chosen(self, station: Station) -> ConfigFlowResult:
        entry = self.config_entry
        if station.id != entry.unique_id:
            for other in self.hass.config_entries.async_entries(DOMAIN):
                if other.entry_id != entry.entry_id and other.unique_id == station.id:
                    return self.async_abort(reason="already_configured")
        # Keep the legacy entity ID and a custom (imported) title across station changes.
        data = {**station_data(station), **{k: v for k, v in entry.data.items() if k == CONF_LEGACY_OBJECT_ID}}
        title = station.name if entry.title == entry.data.get(CONF_STATION_NAME) else entry.title
        # One update (and one reload); returning the same options below changes nothing more.
        self.hass.config_entries.async_update_entry(
            entry, data=data, title=title, unique_id=station.id, options=self._new_options
        )
        return self.async_create_entry(data=self._new_options)


"""Config and options flows for Mare: pick a source, then a station near a location or by name."""
from __future__ import annotations

import logging
import time
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_LOCATION
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

from .api import Station, TideApiError, nearest, search, station_label
from .const import (
    CONF_HILO_ONLY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_PROVIDER,
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
from .providers import PROVIDERS, provider_for_country

_LOGGER = logging.getLogger(__name__)

STATIONS_CACHE_SECONDS = 24 * 3600
CONF_STATION = "station"
CONF_SEARCH = "search"
CONF_QUERY = "query"
CONF_CHANGE_STATION = "change_station"


async def async_get_stations(hass: HomeAssistant, provider: str) -> list[Station]:
    """A provider's station list, cached in memory for a day (1-2 MB, rarely changes)."""
    cache = hass.data.setdefault(DOMAIN, {}).setdefault("stations", {})
    cached = cache.get(provider)
    if cached and time.monotonic() - cached[0] < STATIONS_CACHE_SECONDS:
        return cached[1]
    stations = await PROVIDERS[provider].client(async_get_clientsession(hass)).async_get_stations()
    cache[provider] = (time.monotonic(), stations)
    return stations


def station_unique_id(station: Station) -> str:
    """Station IDs are only unique within a provider."""
    return f"{station.provider}_{station.id}"


def station_data(station: Station) -> dict[str, Any]:
    return {
        CONF_PROVIDER: station.provider,
        CONF_STATION_ID: station.id,
        CONF_STATION_CODE: station.code,
        CONF_STATION_NAME: station.name,
        CONF_LATITUDE: station.latitude,
        CONF_LONGITUDE: station.longitude,
        CONF_HILO_ONLY: station.hilo_only,
    }


def _station_selector(ranked: list[tuple[Station, float]]) -> SelectSelector:
    return SelectSelector(
        SelectSelectorConfig(
            options=[SelectOptionDict(value=s.id, label=station_label(s, d)) for s, d in ranked],
            mode=SelectSelectorMode.LIST,
        )
    )


class StationPickerMixin:
    """Shared source → location → nearest stations → search steps for both flows."""

    hass: HomeAssistant
    _provider: str
    _stations: list[Station]
    _location: tuple[float, float]

    async def _async_station_chosen(self, station: Station) -> ConfigFlowResult:
        raise NotImplementedError

    def _default_provider(self) -> str:
        return provider_for_country(self.hass.config.country)

    async def _async_load_stations(self) -> str | None:
        """Load the chosen provider's station list; returns an error key on failure."""
        try:
            self._stations = await async_get_stations(self.hass, self._provider)
        except TideApiError as err:
            _LOGGER.warning("Could not load %s stations: %s", self._provider, err)
            return "cannot_connect"
        return None if self._stations else "no_stations"

    async def async_step_source(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Choose where the predictions come from (one service per country)."""
        if user_input is not None:
            self._provider = user_input[CONF_PROVIDER]
            return await self.async_step_location()

        return self.async_show_form(  # type: ignore[attr-defined]
            step_id="source",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PROVIDER, default=self._default_provider()): SelectSelector(
                        SelectSelectorConfig(
                            options=list(PROVIDERS), mode=SelectSelectorMode.LIST, translation_key=CONF_PROVIDER
                        )
                    )
                }
            ),
        )

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


class MareTidesConfigFlow(StationPickerMixin, ConfigFlow, domain=DOMAIN):
    """Add a tide station."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return await self.async_step_source(user_input)

    async def _async_station_chosen(self, station: Station) -> ConfigFlowResult:
        await self.async_set_unique_id(station_unique_id(station))
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title=station.name, data=station_data(station))

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> MareTidesOptionsFlow:
        return MareTidesOptionsFlow()


class MareTidesOptionsFlow(StationPickerMixin, OptionsFlow):
    """Change the station or the update interval."""

    def __init__(self) -> None:
        self._new_options: dict[str, Any] = {}

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        entry = self.config_entry
        if user_input is not None:
            self._new_options = {**entry.options, CONF_UPDATE_INTERVAL: int(user_input[CONF_UPDATE_INTERVAL])}
            if user_input.get(CONF_CHANGE_STATION):
                return await self.async_step_source()
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

    def _default_provider(self) -> str:
        return self.config_entry.data[CONF_PROVIDER]

    async def _async_station_chosen(self, station: Station) -> ConfigFlowResult:
        entry = self.config_entry
        unique_id = station_unique_id(station)
        if unique_id != entry.unique_id:
            for other in self.hass.config_entries.async_entries(DOMAIN):
                if other.entry_id != entry.entry_id and other.unique_id == unique_id:
                    return self.async_abort(reason="already_configured")
        # Keep a custom title across station changes.
        data = station_data(station)
        title = station.name if entry.title == entry.data.get(CONF_STATION_NAME) else entry.title
        # One update (and one reload); returning the same options below changes nothing more.
        self.hass.config_entries.async_update_entry(
            entry, data=data, title=title, unique_id=unique_id, options=self._new_options
        )
        return self.async_create_entry(data=self._new_options)


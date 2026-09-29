"""Sensors for Mare: current tide level, next high tide and next low tide."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfLength
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .api import interpolate, station_title
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
)
from .coordinator import MareTidesConfigEntry, MareTidesCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: MareTidesConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the sensors for one station."""
    coordinator = entry.runtime_data
    async_add_entities(
        [
            TideLevelSensor(coordinator),
            NextExtremeSensor(coordinator, "high"),
            NextExtremeSensor(coordinator, "low"),
        ]
    )


class MareTidesEntity(CoordinatorEntity[MareTidesCoordinator]):
    """Common base: device, attribution and periodic recalculation between fetches."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: MareTidesCoordinator, key: str) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        provider = coordinator.provider
        self._attr_attribution = provider.attribution
        # Tied to the entry, not the station, so entity IDs survive a station change.
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer=provider.attribution,
            model=station_title(entry.data.get(CONF_STATION_NAME, ""), entry.data.get(CONF_STATION_CODE, "")),
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=provider.station_url(entry.data[CONF_STATION_ID], entry.data.get(CONF_STATION_CODE, "")),
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        seconds = self.coordinator.config_entry.options.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
        self.async_on_remove(
            async_track_time_interval(self.hass, self._async_tick, timedelta(seconds=seconds))
        )

    @callback
    def _async_tick(self, _now: datetime) -> None:
        self.async_write_ha_state()


class TideLevelSensor(MareTidesEntity, SensorEntity):
    """Predicted water level right now, with the full curve and high/low points as attributes."""

    _attr_translation_key = "tide_level"
    _attr_native_unit_of_measurement = UnitOfLength.METERS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 2
    _attr_icon = "mdi:waves"
    # Large and fully predictable; keep them out of the recorder database.
    _unrecorded_attributes = frozenset({"tide_data", "tide_extremes"})

    def __init__(self, coordinator: MareTidesCoordinator) -> None:
        super().__init__(coordinator, "tide_level")

    @property
    def native_value(self) -> float | None:
        if self.coordinator.data is None:
            return None
        value = interpolate(self.coordinator.data.points, dt_util.utcnow())
        return round(value, 3) if value is not None else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data
        entry = self.coordinator.config_entry
        attrs: dict[str, Any] = {
            "station_id": entry.data[CONF_STATION_ID],
            "station_code": entry.data.get(CONF_STATION_CODE),
            "station_name": entry.data.get(CONF_STATION_NAME),
            "latitude": entry.data.get(CONF_LATITUDE),
            "longitude": entry.data.get(CONF_LONGITUDE),
            "provider": entry.data.get(CONF_PROVIDER),
            "datum": self.coordinator.provider.datum,
            # True when the curve is drawn through the highs and lows (stations with highs and lows only).
            "interpolated": entry.data.get(CONF_HILO_ONLY, False),
        }
        if data is None:
            return attrs
        now = dt_util.utcnow()
        # Heading to a high means rising; exact even right before a turn.
        upcoming = next((e for e in data.extremes if e[0] > now), None)
        if upcoming is not None:
            attrs["trend"] = "rising" if upcoming[2] == "high" else "falling"
        attrs["tide_data"] = [{"time": t.isoformat(), "value": v} for t, v in data.points]
        attrs["tide_extremes"] = [{"time": t.isoformat(), "value": v, "type": k} for t, v, k in data.extremes]
        return attrs


class NextExtremeSensor(MareTidesEntity, SensorEntity):
    """Time of the next high or low tide; its height is an attribute."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator: MareTidesCoordinator, kind: str) -> None:
        super().__init__(coordinator, f"next_{kind}")
        self._kind = kind
        self._attr_translation_key = f"next_{kind}"
        self._attr_icon = "mdi:arrow-collapse-up" if kind == "high" else "mdi:arrow-collapse-down"

    def _next(self) -> tuple[datetime, float, str] | None:
        if self.coordinator.data is None:
            return None
        now = dt_util.utcnow()
        return next((e for e in self.coordinator.data.extremes if e[2] == self._kind and e[0] > now), None)

    @property
    def native_value(self) -> datetime | None:
        nxt = self._next()
        return nxt[0] if nxt else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        nxt = self._next()
        return {"height": nxt[1], "height_unit": UnitOfLength.METERS} if nxt else {}

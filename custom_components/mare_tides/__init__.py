"""DFO Tides integration for Home Assistant."""
from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import DfoTidesConfigEntry, DfoTidesCoordinator

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: DfoTidesConfigEntry) -> bool:
    """Set up a tide station from a config entry."""
    coordinator = DfoTidesCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: DfoTidesConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload(hass: HomeAssistant, entry: DfoTidesConfigEntry) -> None:
    """Reload when the station or options change."""
    await hass.config_entries.async_reload(entry.entry_id)

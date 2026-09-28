"""DFO Tides integration for Home Assistant."""
import logging

_LOGGER = logging.getLogger(__name__)

DOMAIN = "dfo_tides"

async def async_setup(hass, config):
    """Set up the DFO Tides component."""
    return True
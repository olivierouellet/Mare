"""
Custom Home Assistant integration for DFO tide data
Place this file in: custom_components/dfo_tides/sensor.py
"""
import logging
import asyncio
from datetime import datetime, timedelta
import aiohttp
import async_timeout
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import CONF_NAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import async_load_platform

_LOGGER = logging.getLogger(__name__)

DOMAIN = "dfo_tides"
CONF_STATION_ID = "station_id"
CONF_TIME_SERIES_CODE = "time_series_code"
CONF_UPDATE_INTERVAL = "update_interval"

DEFAULT_NAME = "DFO Tides"
DEFAULT_TIME_SERIES_CODE = "wlp"
DEFAULT_UPDATE_INTERVAL = 300  # 5 minutes

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=5)

PLATFORM_SCHEMA = vol.Schema({
    vol.Required(CONF_STATION_ID): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_TIME_SERIES_CODE, default=DEFAULT_TIME_SERIES_CODE): cv.string,
    vol.Optional(CONF_UPDATE_INTERVAL, default=DEFAULT_UPDATE_INTERVAL): cv.positive_int,
})

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the DFO Tides sensor."""
    name = config.get(CONF_NAME)
    station_id = config.get(CONF_STATION_ID)
    time_series_code = config.get(CONF_TIME_SERIES_CODE)
    
    sensor = DFOTidesSensor(hass, name, station_id, time_series_code)
    
    async_add_entities([sensor], True)

class DFOTidesSensor(SensorEntity):
    """Implementation of DFO Tides sensor."""

    def __init__(self, hass, name, station_id, time_series_code):
        """Initialize the sensor."""
        self.hass = hass
        self._name = name
        self._station_id = station_id
        self._time_series_code = time_series_code
        self._state = None
        self._attributes = {}
        self._tide_data = []

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return "m"

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return "mdi:waves"

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self):
        """Fetch new state data for the sensor."""
        try:
            # Get today's date range
            now = datetime.now()
            from_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            to_date = from_date + timedelta(days=1) - timedelta(seconds=1)
            
            # Format dates for API
            from_str = from_date.strftime("%Y-%m-%dT%H:%M:%SZ")
            to_str = to_date.strftime("%Y-%m-%dT%H:%M:%SZ")
            
            # Build API URL
            url = f"https://api-iwls.dfo-mpo.gc.ca/api/v1/stations/{self._station_id}/data"
            params = {
                "time-series-code": self._time_series_code,
                "from": from_str,
                "to": to_str
            }
            
            session = async_get_clientsession(self.hass)
            
            with async_timeout.timeout(30):
                async with session.get(url, params=params) as response:
                    if response.status != 200:
                        _LOGGER.error(f"Error fetching tide data: {response.status}")
                        return
                    
                    data = await response.json()
                    
            # Process the data
            if "data" in data and data["data"]:
                tide_readings = data["data"]
                self._tide_data = []
                
                current_level = None
                for reading in tide_readings:
                    if "eventDate" in reading and "value" in reading:
                        timestamp = reading["eventDate"]
                        value = float(reading["value"])
                        
                        self._tide_data.append({
                            "time": timestamp,
                            "value": value
                        })
                        
                        # Set current level to most recent reading
                        current_level = value
                
                # Update state with current tide level
                self._state = current_level
                
                # Calculate tide statistics
                if self._tide_data:
                    values = [item["value"] for item in self._tide_data]
                    self._attributes = {
                        "tide_data": self._tide_data,
                        "max_tide": max(values),
                        "min_tide": min(values),
                        "readings_count": len(self._tide_data),
                        "station_id": self._station_id,
                        "last_updated": now.isoformat(),
                        "unit_of_measurement": "m"
                    }
                    
                    _LOGGER.info(f"Updated tide data: {len(self._tide_data)} readings")
                else:
                    _LOGGER.warning("No tide data received")
            else:
                _LOGGER.error("Invalid data format received from API")
                
        except asyncio.TimeoutError:
            _LOGGER.error("Timeout fetching tide data")
        except Exception as err:
            _LOGGER.error(f"Error fetching tide data: {err}")

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        await self.async_update()
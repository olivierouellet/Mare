"""Constants for the Mare integration."""
from datetime import timedelta

DOMAIN = "mare_tides"

CONF_PROVIDER = "provider"
CONF_STATION_ID = "station_id"
CONF_STATION_CODE = "station_code"
CONF_STATION_NAME = "station_name"
CONF_LATITUDE = "latitude"
CONF_LONGITUDE = "longitude"
CONF_HILO_ONLY = "hilo_only"
CONF_UPDATE_INTERVAL = "update_interval"

DEFAULT_UPDATE_INTERVAL = 300  # seconds between state recalculations
MIN_UPDATE_INTERVAL = 60
MAX_UPDATE_INTERVAL = 3600

# The API is only called this often; predictions do not change during the day.
FETCH_INTERVAL = timedelta(hours=1)

# Fetched window, relative to local midnight today. Covers a 72 h "day" span
# and a rolling span of up to 24 h back / 72 h ahead.
WINDOW_DAYS_BEFORE = 1
WINDOW_DAYS_AFTER = 4

NEAREST_COUNT = 5
SEARCH_LIMIT = 25

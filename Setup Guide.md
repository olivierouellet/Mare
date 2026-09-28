# DFO Tides Home Assistant Integration Setup Guide

This integration fetches tide data from the Fisheries and Oceans Canada (DFO) API and makes it available for use with ApexCharts cards in Home Assistant.

## Installation Steps

### 1. Create the Integration Directory Structure

Create the following directory structure in your Home Assistant configuration folder:

```
config/
└── custom_components/
    └── dfo_tides/
        ├── __init__.py
        ├── manifest.json
        └── sensor.py
```

### 2. Install the Files

1. **Copy the sensor code** from the first artifact into `custom_components/dfo_tides/sensor.py`

2. **Create `__init__.py`** with this content:
```python
"""DFO Tides integration for Home Assistant."""
import logging

_LOGGER = logging.getLogger(__name__)

DOMAIN = "dfo_tides"

async def async_setup(hass, config):
    """Set up the DFO Tides component."""
    return True
```

3. **Create `manifest.json`** with this content:
```json
{
  "domain": "dfo_tides",
  "name": "DFO Tides",
  "documentation": "https://github.com/yourusername/dfo-tides",
  "dependencies": [],
  "codeowners": ["@yourusername"],
  "requirements": [],
  "version": "1.0.0"
}
```

### 3. Configure the Sensor

Add this to your `configuration.yaml`:

```yaml
sensor:
  - platform: dfo_tides
    name: "Halifax Tides"
    station_id: "5cebf1e33d0f4a073c4bc2d8"  # Replace with your station ID
    time_series_code: "wlp"
    update_interval: 300  # Update every 5 minutes
```

### 4. Install ApexCharts Card

If you haven't already, install the ApexCharts card through HACS:
1. Go to HACS → Frontend
2. Search for "ApexCharts Card"
3. Install it
4. Add it to your Lovelace resources

### 5. Create the Dashboard Card

Add this card configuration to your Lovelace dashboard:

```yaml
type: custom:apexcharts-card
header:
  title: Today's Tide Levels
  show: true
graph_span: 24h
span:
  start: day
now:
  show: true
  label: Now
yaxis:
  - id: tide
    title:
      text: Water Level (m)
series:
  - entity: sensor.halifax_tides
    name: Tide Level
    type: line
    stroke_width: 2
    color: '#0066cc'
    data_generator: |
      return entity.attributes.tide_data.map((item) => {
        return [new Date(item.time).getTime(), item.value];
      });
apex_config:
  chart:
    height: 400
  xaxis:
    type: datetime
    labels:
      format: HH:mm
  tooltip:
    x:
      format: 'MMM dd, HH:mm'
  stroke:
    curve: smooth
```

## Finding Your Station ID

To find your station ID:

1. Visit the [DFO Station Search](https://api-iwls.dfo-mpo.gc.ca/swagger-ui/index.html)
2. Use the `/api/v1/stations` endpoint to search for stations near your location
3. Copy the station ID from the response

Example stations:
- Halifax: `5cebf1e33d0f4a073c4bc2d8`
- Vancouver: `5cebf1de3d0f4a073c4bbf55`
- Saint John: `5cebf1e23d0f4a073c4bc0ca`

## Configuration Options

| Parameter | Description | Default | Required |
|-----------|-------------|---------|----------|
| `name` | Friendly name for the sensor | "DFO Tides" | No |
| `station_id` | DFO station identifier | - | Yes |
| `time_series_code` | Data series code | "wlp" | No |
| `update_interval` | Update frequency (seconds) | 300 | No |

## Features

- **Automatic daily updates**: Fetches data for the current day automatically
- **Real-time current level**: Shows the most recent tide reading
- **Complete day data**: Provides all tide readings for ApexCharts visualization
- **Statistics**: Includes min/max tide levels in attributes
- **Error handling**: Robust error handling with logging
- **Throttled updates**: Prevents excessive API calls

## Troubleshooting

### Check the Logs

If the integration isn't working, check Home Assistant logs:
1. Go to Settings → System → Logs
2. Look for entries containing "dfo_tides"

### Common Issues

1. **No data appearing**: Verify your station ID is correct
2. **API errors**: Check if the DFO API is accessible from your network
3. **Card not updating**: Ensure the entity name matches in your card configuration

### Manual Testing

You can test the API directly by visiting:
```
https://api-iwls.dfo-mpo.gc.ca/api/v1/stations/YOUR_STATION_ID/data?time-series-code=wlp&from=2025-07-24T00:00:00Z&to=2025-07-24T23:59:00Z
```

Replace `YOUR_STATION_ID` with your actual station ID.

## Restart Home Assistant

After installation, restart Home Assistant to load the new integration. The sensor should appear as `sensor.halifax_tides` (or whatever name you configured) and the ApexCharts card should display the tide data for the current day.
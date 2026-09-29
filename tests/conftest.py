"""Fixtures for the Mare tests."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
    AiohttpClientMockResponse,
)

FIXTURES = Path(__file__).parent / "fixtures"

HALIFAX_ID = "5cebf1df3d0f4a073c4bbcbb"
BEDFORD_ID = "5cebf1e23d0f4a073c4bbfac"
SANDY_BEACH_ID = "5cebf1e33d0f4a073c4bc2d8"
BOSTON_ID = "8443970"  # NOAA reference station
HULL_ID = "8444351"  # NOAA subordinate station (highs and lows only)
NOW = "2026-09-27T15:00:00+00:00"  # 12:00 in Halifax, 11:00 in Boston


def load(name: str):
    return json.loads(load_text(name))


def load_text(name: str) -> str:
    return (FIXTURES / name).read_text()


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Load custom_components/ in every test."""
    yield


@pytest.fixture
async def halifax_home(hass):
    """Home Assistant located in Halifax, frozen at a known time."""
    await hass.config.async_set_time_zone("America/Halifax")
    hass.config.latitude = 44.6488
    hass.config.longitude = -63.5752
    return hass


@pytest.fixture
def dfo_api(aioclient_mock: AiohttpClientMocker) -> AiohttpClientMocker:
    """Serve recorded DFO API responses (tides are always Halifax's)."""
    aioclient_mock.get(re.compile(r"/api/v1/stations$"), json=load("stations.json"))
    aioclient_mock.get(re.compile(r"time-series-code=wlp-hilo"), json=load("halifax_hilo.json"))
    aioclient_mock.get(re.compile(r"time-series-code=wlp(&|$)"), json=load("halifax_wlp.json"))
    return aioclient_mock


@pytest.fixture
async def boston_home(hass):
    """Home Assistant located in Boston, frozen at a known time."""
    await hass.config.async_set_time_zone("America/New_York")
    hass.config.latitude = 42.3601
    hass.config.longitude = -71.0589
    hass.config.country = "US"
    return hass


@pytest.fixture
def noaa_api(aioclient_mock: AiohttpClientMocker) -> AiohttpClientMocker:
    """Serve recorded NOAA API responses (Boston, and Hull for a subordinate station)."""
    aioclient_mock.get(re.compile(r"/webapi/stations\.json"), json=load("noaa_stations.json"))
    aioclient_mock.get(re.compile(rf"station={BOSTON_ID}.*interval=15(&|$)"), json=load("boston_15.json"))
    aioclient_mock.get(re.compile(rf"station={BOSTON_ID}.*interval=hilo"), json=load("boston_hilo.json"))
    aioclient_mock.get(re.compile(rf"station={HULL_ID}.*interval=hilo"), json=load("hull_hilo.json"))
    return aioclient_mock


@pytest.fixture
def europe_api(aioclient_mock: AiohttpClientMocker) -> AiohttpClientMocker:
    """Serve recorded Kartverket (Bergen), Rijkswaterstaat (Hoek van Holland) and Marine Institute (Dublin) responses."""
    aioclient_mock.get(re.compile(r"tideapi\.php.*tide_request=stationlist"), text=load_text("kartverket_stations.xml"))
    aioclient_mock.get(re.compile(r"tideapi\.php.*datatype=pre"), text=load_text("bergen_pre.xml"))
    aioclient_mock.get(re.compile(r"tideapi\.php.*datatype=tab"), text=load_text("bergen_tab.xml"))

    async def rws_data(method, url, data):
        # Both requests share a URL; the body says whether the high/low waters are wanted.
        grouped = "Groepering" in data["AquoPlusWaarnemingMetadata"]["AquoMetadata"]
        return AiohttpClientMockResponse(method, url, json=load("hvh_extremes.json" if grouped else "hvh_curve.json"))

    aioclient_mock.post(re.compile(r"/OphalenCatalogus$"), json=load("rws_catalogue.json"))
    aioclient_mock.post(re.compile(r"/OphalenWaarnemingen$"), side_effect=rws_data)

    aioclient_mock.get(re.compile(r"/imiTidePrediction\.csv\?stationID"), text=load_text("marine_stations.csv"))
    aioclient_mock.get(re.compile(r"/imiTidePrediction\.csv\?time"), text=load_text("dublin_curve.csv"))
    aioclient_mock.get(re.compile(r"/IMI_TidePrediction_HighLow\.csv"), text=load_text("dublin_hilo.csv"))
    return aioclient_mock

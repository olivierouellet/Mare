"""Fixtures for the DFO Tides tests."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

FIXTURES = Path(__file__).parent / "fixtures"

HALIFAX_ID = "5cebf1df3d0f4a073c4bbcbb"
BEDFORD_ID = "5cebf1e23d0f4a073c4bbfac"
SANDY_BEACH_ID = "5cebf1e33d0f4a073c4bc2d8"
NOW = "2026-09-27T15:00:00+00:00"  # 12:00 in Halifax


def load(name: str):
    return json.loads((FIXTURES / name).read_text())


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

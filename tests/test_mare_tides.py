"""Tests for the Mare integration: flows, sensors and the NOAA client."""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from homeassistant import config_entries
from homeassistant.const import CONF_LOCATION
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er

from custom_components.mare_tides.api import TideClient, cosine_curve
from custom_components.mare_tides.const import DOMAIN
from custom_components.mare_tides.providers import PROVIDERS, provider_for_country

from .conftest import BEDFORD_ID, BOSTON_ID, HALIFAX_ID, HULL_ID, NOW, SANDY_BEACH_ID

HOME = {"latitude": 44.6488, "longitude": -63.5752}
BOSTON = {"latitude": 42.3601, "longitude": -71.0589}


async def _start(hass: HomeAssistant, provider: str = "dfo") -> dict:
    """Start the user flow and pick the source; returns the location step."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["step_id"] == "source"
    return await hass.config_entries.flow.async_configure(result["flow_id"], {"provider": provider})


async def _add_halifax(hass: HomeAssistant) -> config_entries.ConfigEntry:
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_LOCATION: HOME})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"station": HALIFAX_ID})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    return result["result"]


@pytest.mark.freeze_time(NOW)
async def test_user_flow_lists_nearest_stations(halifax_home, dfo_api) -> None:
    hass = halifax_home
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "source"
    assert result["data_schema"]({})["provider"] == "dfo"  # default outside the US
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"provider": "dfo"})
    assert result["step_id"] == "location"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_LOCATION: HOME})
    assert result["step_id"] == "station"
    options = result["data_schema"].schema["station"].config["options"]
    labels = [o["label"] for o in options]
    assert len(options) == 5
    assert labels[0].startswith("Halifax · 00490 · 1.3 km")
    assert labels[1].startswith("Bedford Institute")
    assert "Guysborough" not in " ".join(labels)  # no high/low predictions → filtered out

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"station": HALIFAX_ID})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Halifax"
    assert result["result"].unique_id == f"dfo_{HALIFAX_ID}"


@pytest.mark.freeze_time(NOW)
async def test_search_flow(halifax_home, dfo_api) -> None:
    hass = halifax_home
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_LOCATION: HOME})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"search": True})
    assert result["step_id"] == "search"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"query": "nothing-like-this"})
    assert result["errors"] == {"query": "no_match"}

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"query": "sandy"})
    assert [o["value"] for o in result["data_schema"].schema["station"].config["options"]] == [SANDY_BEACH_ID]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"query": "sandy", "station": SANDY_BEACH_ID}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Sandy Beach"


@pytest.mark.freeze_time(NOW)
async def test_duplicate_station_aborts(halifax_home, dfo_api) -> None:
    hass = halifax_home
    await _add_halifax(hass)
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_LOCATION: HOME})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"station": HALIFAX_ID})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.freeze_time(NOW)
async def test_sensors(halifax_home, dfo_api) -> None:
    hass = halifax_home
    await _add_halifax(hass)

    level = hass.states.get("sensor.halifax_tide_level")
    assert level is not None
    # 12:00 ADT on 2026-09-27 is between the 09:01 high (1.837 m) and the 15:28 low (0.181 m).
    assert float(level.state) == pytest.approx(1.039)
    assert level.attributes["unit_of_measurement"] == "m"
    assert level.attributes["provider"] == "dfo"
    assert level.attributes["interpolated"] is False
    assert level.attributes["attribution"] == "Fisheries and Oceans Canada / Pêches et Océans Canada"
    assert level.attributes["trend"] == "falling"
    assert len(level.attributes["tide_data"]) == 481
    kinds = [e["type"] for e in level.attributes["tide_extremes"]]
    assert all(a != b for a, b in zip(kinds, kinds[1:]))

    next_high = hass.states.get("sensor.halifax_next_high_tide")
    next_low = hass.states.get("sensor.halifax_next_low_tide")
    assert next_low.state == "2026-09-27T18:28:00+00:00"
    assert next_low.attributes["height"] == 0.181
    assert next_high.state.startswith("2026-09-28T")


@pytest.mark.freeze_time(NOW)
async def test_options_flow_changes_station_keeps_entity_ids(halifax_home, dfo_api) -> None:
    hass = halifax_home
    entry = await _add_halifax(hass)
    registry = er.async_get(hass)
    before = {e.unique_id: e.entity_id for e in er.async_entries_for_config_entry(registry, entry.entry_id)}

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["step_id"] == "init"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"update_interval": 120, "change_station": True}
    )
    assert result["step_id"] == "source"
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"provider": "dfo"})
    assert result["step_id"] == "location"
    result = await hass.config_entries.options.async_configure(result["flow_id"], {CONF_LOCATION: HOME})
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"station": BEDFORD_ID})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    assert entry.unique_id == f"dfo_{BEDFORD_ID}"
    assert entry.title == "Bedford Institute"
    assert entry.options["update_interval"] == 120
    after = {e.unique_id: e.entity_id for e in er.async_entries_for_config_entry(registry, entry.entry_id)}
    assert after == before
    assert hass.states.get("sensor.halifax_tide_level").attributes["station_name"] == "Bedford Institute"


@pytest.mark.freeze_time(NOW)
async def test_noaa_reference_station(boston_home, noaa_api) -> None:
    hass = boston_home
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["data_schema"]({})["provider"] == "noaa"  # default in the US
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"provider": "noaa"})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_LOCATION: BOSTON})
    labels = [o["label"] for o in result["data_schema"].schema["station"].config["options"]]
    assert labels[0] == "BOSTON, MA · 8443970 · 1.0 km"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"station": BOSTON_ID})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == f"noaa_{BOSTON_ID}"
    await hass.async_block_till_done()

    level = hass.states.get("sensor.boston_ma_tide_level")
    # 15:00 UTC is a recorded 15-minute point, between the 10:03 low and the 16:12 high.
    assert float(level.state) == pytest.approx(2.938)
    assert level.attributes["trend"] == "rising"
    assert level.attributes["provider"] == "noaa"
    assert level.attributes["interpolated"] is False
    assert level.attributes["attribution"] == "NOAA Tides and Currents"
    assert len(level.attributes["tide_data"]) == 481
    kinds = [e["type"] for e in level.attributes["tide_extremes"]]
    assert all(a != b for a, b in zip(kinds, kinds[1:]))

    next_high = hass.states.get("sensor.boston_ma_next_high_tide")
    next_low = hass.states.get("sensor.boston_ma_next_low_tide")
    assert next_high.state == "2026-09-27T16:12:00+00:00"
    assert next_high.attributes["height"] == 3.235
    assert next_low.state == "2026-09-27T22:27:00+00:00"
    assert next_low.attributes["height"] == -0.1


@pytest.mark.freeze_time(NOW)
async def test_noaa_subordinate_station(boston_home, noaa_api) -> None:
    hass = boston_home
    result = await _start(hass, "noaa")
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_LOCATION: BOSTON})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"search": True})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"query": "hull"})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"query": "hull", "station": HULL_ID})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].data["hilo_only"] is True
    await hass.async_block_till_done()

    level = hass.states.get("sensor.hull_ma_tide_level")
    assert level.attributes["interpolated"] is True
    # Cosine between the 10:10 low (0.023 m) and the 16:17 high (3.138 m), 290 of 367 minutes in.
    assert float(level.state) == pytest.approx(2.812, abs=0.001)
    assert level.attributes["trend"] == "rising"
    # The whole window is covered, even before the first and after the last extreme in it.
    assert len(level.attributes["tide_data"]) == 481
    heights = [e["value"] for e in level.attributes["tide_extremes"]]
    assert all(min(heights) - 0.2 <= p["value"] <= max(heights) + 0.2 for p in level.attributes["tide_data"])
    assert hass.states.get("sensor.hull_ma_next_high_tide").state == "2026-09-27T16:17:00+00:00"


@pytest.mark.freeze_time(NOW)
async def test_noaa_error_body(boston_home, aioclient_mock) -> None:
    """NOAA reports errors with HTTP 200 and an "error" object."""
    hass = boston_home
    aioclient_mock.get(re.compile(r"/webapi/stations\.json"), json={"error": {"message": "Service unavailable"}})
    result = await _start(hass, "noaa")
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_LOCATION: BOSTON})
    assert result["errors"] == {"base": "cannot_connect"}


def test_cosine_curve() -> None:
    t0 = datetime(2026, 9, 27, tzinfo=timezone.utc)
    extremes = [(t0, 1.0, "high"), (t0 + timedelta(hours=6), 0.0, "low"), (t0 + timedelta(hours=12), 1.0, "high")]
    curve = dict(cosine_curve(extremes, t0 - timedelta(hours=1), t0 + timedelta(hours=13), timedelta(hours=1)))
    assert min(curve) == t0 and max(curve) == t0 + timedelta(hours=12)  # nothing outside the extremes
    assert curve[t0] == pytest.approx(1.0)
    assert curve[t0 + timedelta(hours=3)] == pytest.approx(0.5)
    assert curve[t0 + timedelta(hours=6)] == pytest.approx(0.0)
    assert curve[t0 + timedelta(hours=9)] == pytest.approx(0.5)
    assert curve[t0 + timedelta(hours=12)] == pytest.approx(1.0)


def test_every_provider_is_complete() -> None:
    """A new provider needs a client, its countries and a label in every language."""
    component = Path(__file__).parent.parent / "custom_components" / DOMAIN
    for name in ("strings.json", "translations/en.json", "translations/fr.json"):
        options = json.loads((component / name).read_text())["selector"]["provider"]["options"]
        assert set(options) == set(PROVIDERS), name
    for provider in PROVIDERS.values():
        assert issubclass(provider.client, TideClient)
        assert provider.countries


def test_provider_for_country() -> None:
    assert provider_for_country("CA") == "dfo"
    assert provider_for_country("US") == "noaa"
    assert provider_for_country("PR") == "noaa"
    assert provider_for_country(None) == "dfo"


EUROPE = [
    # provider, time zone, home, station ID, entity prefix, level, next low, next high, datum
    (
        "kartverket", "Europe/Oslo", (60.3913, 5.3221), "BGO", "sensor.bergen",
        0.466, ("2026-09-27T16:04:00+00:00", 0.352), ("2026-09-27T22:18:00+00:00", 1.703), "Chart datum",
    ),
    (
        "rijkswaterstaat", "Europe/Amsterdam", (51.9769, 4.1198), "hoekvanholland", "sensor.hoek_van_holland",
        1.12, ("2026-09-27T19:07:00+00:00", -0.67), ("2026-09-28T02:29:00+00:00", 1.51), "NAP",
    ),
    (
        "marine_institute", "Europe/Dublin", (53.3457, -6.2217), "Dublin_Port", "sensor.dublin_port",
        -0.45, ("2026-09-27T17:15:00+00:00", -1.798), ("2026-09-27T23:55:00+00:00", 1.846), "OD Malin",
    ),
]


@pytest.mark.freeze_time(NOW)
@pytest.mark.parametrize(
    ("provider", "time_zone", "home", "station_id", "prefix", "level", "next_low", "next_high", "datum"),
    EUROPE,
    ids=[e[0] for e in EUROPE],
)
async def test_european_provider(
    hass: HomeAssistant, europe_api, provider, time_zone, home, station_id, prefix, level, next_low, next_high, datum
) -> None:
    await hass.config.async_set_time_zone(time_zone)
    result = await _start(hass, provider)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_LOCATION: {"latitude": home[0], "longitude": home[1]}}
    )
    options = result["data_schema"].schema["station"].config["options"]
    assert options[0]["value"] == station_id

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"station": station_id})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == f"{provider}_{station_id}"
    await hass.async_block_till_done()

    state = hass.states.get(f"{prefix}_tide_level")
    assert float(state.state) == pytest.approx(level)
    assert state.attributes["provider"] == provider
    assert state.attributes["datum"] == datum
    assert state.attributes["trend"] == "falling"
    kinds = [e["type"] for e in state.attributes["tide_extremes"]]
    assert kinds and all(a != b for a, b in zip(kinds, kinds[1:]))

    low = hass.states.get(f"{prefix}_next_low_tide")
    high = hass.states.get(f"{prefix}_next_high_tide")
    assert (low.state, low.attributes["height"]) == (next_low[0], pytest.approx(next_low[1]))
    assert (high.state, high.attributes["height"]) == (next_high[0], pytest.approx(next_high[1]))


@pytest.mark.freeze_time(NOW)
async def test_rijkswaterstaat_lists_only_locations_with_predictions(hass: HomeAssistant, europe_api) -> None:
    result = await _start(hass, "rijkswaterstaat")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_LOCATION: {"latitude": 51.9769, "longitude": 4.1198}}
    )
    values = [o["value"] for o in result["data_schema"].schema["station"].config["options"]]
    assert "hoekvanholland.splitsingsdam" not in values  # no astronomical series

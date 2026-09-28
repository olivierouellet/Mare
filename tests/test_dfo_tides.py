"""Tests for the DFO Tides integration: flows, YAML import and sensors."""
from __future__ import annotations

import pytest

from homeassistant import config_entries
from homeassistant.const import CONF_LOCATION
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from custom_components.dfo_tides.const import DOMAIN

from .conftest import BEDFORD_ID, HALIFAX_ID, NOW, SANDY_BEACH_ID

HOME = {"latitude": 44.6488, "longitude": -63.5752}


async def _add_halifax(hass: HomeAssistant) -> config_entries.ConfigEntry:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
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
    assert result["result"].unique_id == HALIFAX_ID


@pytest.mark.freeze_time(NOW)
async def test_search_flow(halifax_home, dfo_api) -> None:
    hass = halifax_home
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
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
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
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
    assert result["step_id"] == "location"
    result = await hass.config_entries.options.async_configure(result["flow_id"], {CONF_LOCATION: HOME})
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"station": BEDFORD_ID})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    assert entry.unique_id == BEDFORD_ID
    assert entry.title == "Bedford Institute"
    assert entry.options["update_interval"] == 120
    after = {e.unique_id: e.entity_id for e in er.async_entries_for_config_entry(registry, entry.entry_id)}
    assert after == before
    assert hass.states.get("sensor.halifax_tide_level").attributes["station_name"] == "Bedford Institute"


@pytest.mark.freeze_time(NOW)
async def test_yaml_import_keeps_entity_id(halifax_home, dfo_api) -> None:
    hass = halifax_home
    assert await async_setup_component(
        hass,
        "sensor",
        {"sensor": [{"platform": DOMAIN, "name": "Halifax Tides", "station_id": SANDY_BEACH_ID, "update_interval": 300}]},
    )
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].unique_id == SANDY_BEACH_ID
    assert entries[0].title == "Halifax Tides"
    assert hass.states.get("sensor.halifax_tides") is not None
    assert hass.states.get("sensor.halifax_tides_next_high_tide") is not None

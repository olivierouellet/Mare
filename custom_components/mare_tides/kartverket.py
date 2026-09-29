"""Client for the Kartverket (Norwegian Mapping Authority) tide API (Norway)."""
from __future__ import annotations

import asyncio
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from .api import Station, TideApiError, TideClient, parse_time

BASE_URL = "https://vannstand.kartverket.no/tideapi.php"


class KartverketClient(TideClient):
    """Predictions for Kartverket's permanent water level stations, in cm above chart datum."""

    async def _get(self, params: dict[str, str]) -> ET.Element:
        body = await self._fetch(BASE_URL, params={**params, "lang": "en"}, text=True)
        try:
            root = ET.fromstring(body)
        except ET.ParseError as err:
            raise TideApiError(f"Unexpected response from Kartverket: {err}") from err
        # Errors come back with HTTP 200 as <error>message</error>.
        if root.tag == "error":
            raise TideApiError(f"Kartverket error: {root.text}")
        return root

    async def async_get_stations(self) -> list[Station]:
        """Return the permanent stations (the ones Kartverket publishes predictions for)."""
        root = await self._get({"tide_request": "stationlist", "type": "perm"})
        stations = []
        for item in root.iter("location"):
            try:
                stations.append(
                    Station(
                        id=item.attrib["code"],
                        code=item.attrib["code"],
                        name=item.attrib["name"],
                        latitude=float(item.attrib["latitude"]),
                        longitude=float(item.attrib["longitude"]),
                        operating=True,
                        provider="kartverket",
                    )
                )
            except (KeyError, ValueError):
                continue
        return stations

    async def _async_get_predictions(
        self, station_id: str, start: datetime, end: datetime
    ) -> tuple[list[tuple[datetime, float]], list[tuple[datetime, float, str]]]:
        common = {
            "tide_request": "stationdata",
            "stationcode": station_id,
            "fromtime": _format_time(start),
            "totime": _format_time(end),
            "refcode": "cd",
            "tzone": "0",
            "dst": "0",
        }
        # Station data comes every 10 minutes at best; "tab" is the high/low table.
        curve, table = await asyncio.gather(
            self._get({**common, "datatype": "pre", "interval": "10"}),
            self._get({**common, "datatype": "tab"}),
        )
        points = [(when, value) for when, value, _ in _parse_levels(curve)]
        extremes = [(when, value, flag) for when, value, flag in _parse_levels(table) if flag in ("high", "low")]
        return points, extremes


def _format_time(value: datetime) -> str:
    """Format an aware datetime as Kartverket expects (UTC, with tzone=0)."""
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M")


def _parse_levels(root: ET.Element) -> list[tuple[datetime, float, str]]:
    """<waterlevel value="160.7" time="…" flag="pre"/> elements, in metres."""
    levels = []
    for item in root.iter("waterlevel"):
        try:
            levels.append((parse_time(item.attrib["time"]), float(item.attrib["value"]) / 100, item.attrib.get("flag", "")))
        except (KeyError, ValueError):
            continue
    levels.sort(key=lambda p: p[0])
    return levels

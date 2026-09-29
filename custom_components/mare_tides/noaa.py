"""Client for the NOAA CO-OPS Tides and Currents APIs (United States)."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from .api import Station, TideApiError, TideClient

STATIONS_URL = "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations.json"
DATA_URL = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"

KINDS = {"H": "high", "HH": "high", "L": "low", "LL": "low"}


class NoaaClient(TideClient):
    """Minimal async client for the endpoints this integration needs.

    Subordinate stations only publish highs and lows, so they are flagged `hilo_only`.
    """

    async def _get(self, url: str, params: dict[str, str]) -> dict[str, Any]:
        payload = await self._fetch(url, params=params)
        if not isinstance(payload, dict):
            raise TideApiError(f"Unexpected response format for {url}")
        # Errors come back with HTTP 200 and an "error" object.
        if error := payload.get("error"):
            message = error.get("message") if isinstance(error, dict) else error
            raise TideApiError(f"NOAA error: {message}")
        return payload

    async def async_get_stations(self) -> list[Station]:
        """Return all stations that publish tide predictions."""
        payload = await self._get(STATIONS_URL, {"type": "tidepredictions"})
        stations = []
        for item in payload.get("stations") or []:
            try:
                name = item["name"].strip()
                if state := (item.get("state") or "").strip():
                    name = f"{name}, {state}"
                stations.append(
                    Station(
                        id=str(item["id"]),
                        code=str(item["id"]),
                        name=name,
                        latitude=float(item["lat"]),
                        longitude=float(item["lng"]),
                        operating=True,
                        provider="noaa",
                        hilo_only=item.get("type") == "S",
                    )
                )
            except (KeyError, TypeError, ValueError, AttributeError):
                continue
        return stations

    async def _async_get_predictions(
        self, station_id: str, start: datetime, end: datetime
    ) -> tuple[list[tuple[datetime, float]], list[tuple[datetime, float, str]]]:
        raw_points, raw_hilo = await asyncio.gather(
            self._predictions(station_id, start, end, "15"),
            self._predictions(station_id, start, end, "hilo"),
        )
        return _parse_points(raw_points), _parse_extremes(raw_hilo)

    async def _async_get_extremes(
        self, station_id: str, start: datetime, end: datetime
    ) -> list[tuple[datetime, float, str]]:
        return _parse_extremes(await self._predictions(station_id, start, end, "hilo"))

    async def _predictions(self, station_id: str, start: datetime, end: datetime, interval: str) -> list[dict[str, Any]]:
        payload = await self._get(
            DATA_URL,
            {
                "product": "predictions",
                "application": "Mare",
                "station": station_id,
                "begin_date": _format_time(start),
                "end_date": _format_time(end),
                "datum": "MLLW",
                "time_zone": "gmt",
                "units": "metric",
                "interval": interval,
                "format": "json",
            },
        )
        predictions = payload.get("predictions")
        if not isinstance(predictions, list):
            raise TideApiError(f"Unexpected response format for station {station_id}")
        return predictions


def _format_time(value: datetime) -> str:
    """Format an aware datetime as NOAA expects (UTC, with time_zone=gmt)."""
    return value.astimezone(timezone.utc).strftime("%Y%m%d %H:%M")


def _parse_time(value: str) -> datetime:
    """Parse a NOAA timestamp such as "2026-09-27 03:54" (UTC with time_zone=gmt)."""
    return datetime.strptime(value, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)


def _parse_points(raw: list[dict[str, Any]]) -> list[tuple[datetime, float]]:
    points = []
    for item in raw:
        try:
            points.append((_parse_time(item["t"]), float(item["v"])))
        except (KeyError, TypeError, ValueError):
            continue
    points.sort(key=lambda p: p[0])
    return points


def _parse_extremes(raw: list[dict[str, Any]]) -> list[tuple[datetime, float, str]]:
    extremes = []
    for item in raw:
        try:
            extremes.append((_parse_time(item["t"]), float(item["v"]), KINDS[item["type"]]))
        except (KeyError, TypeError, ValueError):
            continue
    extremes.sort(key=lambda e: e[0])
    return extremes

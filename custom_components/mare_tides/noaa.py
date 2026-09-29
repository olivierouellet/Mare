"""Client for the NOAA CO-OPS Tides and Currents APIs (United States)."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

import aiohttp

from .api import TIMEOUT, Station, TideApiError, TideData, cosine_curve

STATIONS_URL = "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations.json"
DATA_URL = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"

# Subordinate stations only publish highs and lows. Fetching a day either side makes
# sure the curve has a high or low before the start and after the end of the window.
SUBORDINATE_MARGIN = timedelta(days=1)

KINDS = {"H": "high", "HH": "high", "L": "low", "LL": "low"}


class NoaaClient:
    """Minimal async client for the endpoints this integration needs."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session

    async def _get(self, url: str, params: dict[str, str]) -> dict[str, Any]:
        try:
            async with self._session.get(url, params=params, timeout=TIMEOUT) as resp:
                if resp.status != 200:
                    raise TideApiError(f"HTTP {resp.status} for {url}")
                payload = await resp.json(content_type=None)
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as err:
            raise TideApiError(f"Error requesting {url}: {err}") from err

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
                        subordinate=item.get("type") == "S",
                    )
                )
            except (KeyError, TypeError, ValueError, AttributeError):
                continue
        return stations

    async def async_get_tides(
        self, station_id: str, start: datetime, end: datetime, subordinate: bool = False
    ) -> TideData:
        """Fetch 15-minute predictions and official high/low points between start and end.

        Subordinate stations have no 15-minute predictions: their curve is drawn
        through their highs and lows.
        """
        if subordinate:
            raw = await self._predictions(station_id, start - SUBORDINATE_MARGIN, end + SUBORDINATE_MARGIN, "hilo")
            extremes = _parse_extremes(raw)
            points = cosine_curve(extremes, start, end)
            extremes = [e for e in extremes if start <= e[0] <= end]
        else:
            raw_points, raw_hilo = await asyncio.gather(
                self._predictions(station_id, start, end, "15"),
                self._predictions(station_id, start, end, "hilo"),
            )
            points = _parse_points(raw_points)
            extremes = _parse_extremes(raw_hilo)
        if not points:
            raise TideApiError(f"No predictions returned for station {station_id}")
        return TideData(points=points, extremes=extremes, start=start, end=end)

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

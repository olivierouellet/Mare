"""Client for the DFO / MPO Integrated Water Level System (IWLS) API.

Kept free of Home Assistant imports so it can be exercised on its own.
"""
from __future__ import annotations

import asyncio
import math
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

import aiohttp

BASE_URL = "https://api-iwls.dfo-mpo.gc.ca/api/v1"
TIMEOUT = aiohttp.ClientTimeout(total=30)

SERIES_PREDICTIONS = "wlp"
SERIES_HILO = "wlp-hilo"


class DfoApiError(Exception):
    """Raised when the DFO API cannot be reached or returns bad data."""


@dataclass(frozen=True)
class Station:
    """A tide station that has predictions and high/low predictions."""

    id: str
    code: str
    name: str
    latitude: float
    longitude: float
    operating: bool


@dataclass
class TideData:
    """Predicted water levels and high/low points for a time window."""

    points: list[tuple[datetime, float]] = field(default_factory=list)
    extremes: list[tuple[datetime, float, str]] = field(default_factory=list)
    start: datetime | None = None
    end: datetime | None = None


class DfoClient:
    """Minimal async client for the endpoints this integration needs."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session

    async def _get(self, path: str, params: dict[str, str] | None = None) -> list[dict[str, Any]]:
        try:
            async with self._session.get(f"{BASE_URL}{path}", params=params, timeout=TIMEOUT) as resp:
                if resp.status != 200:
                    raise DfoApiError(f"HTTP {resp.status} for {path}")
                payload = await resp.json()
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise DfoApiError(f"Error requesting {path}: {err}") from err

        # The API returns a bare list; older docs show a {"data": [...]} wrapper.
        if isinstance(payload, dict):
            payload = payload.get("data")
        if not isinstance(payload, list):
            raise DfoApiError(f"Unexpected response format for {path}")
        return payload

    async def async_get_stations(self) -> list[Station]:
        """Return all stations that publish both predictions and high/low predictions."""
        raw = await self._get("/stations")
        stations = []
        for item in raw:
            codes = {ts.get("code") for ts in item.get("timeSeries") or []}
            if SERIES_PREDICTIONS not in codes or SERIES_HILO not in codes:
                continue
            try:
                stations.append(
                    Station(
                        id=item["id"],
                        code=item.get("code", ""),
                        name=item.get("officialName") or item.get("code", item["id"]),
                        latitude=float(item["latitude"]),
                        longitude=float(item["longitude"]),
                        operating=bool(item.get("operating", True)),
                    )
                )
            except (KeyError, TypeError, ValueError):
                continue
        return stations

    async def async_get_tides(self, station_id: str, start: datetime, end: datetime) -> TideData:
        """Fetch 15-minute predictions and official high/low points between start and end."""
        common = {"from": format_utc(start), "to": format_utc(end)}
        raw_points, raw_hilo = await asyncio.gather(
            self._get(
                f"/stations/{station_id}/data",
                {**common, "time-series-code": SERIES_PREDICTIONS, "resolution": "FIFTEEN_MINUTES"},
            ),
            self._get(f"/stations/{station_id}/data", {**common, "time-series-code": SERIES_HILO}),
        )
        points = _parse_series(raw_points)
        if not points:
            raise DfoApiError(f"No predictions returned for station {station_id}")
        hilo = _parse_series(raw_hilo)
        return TideData(points=points, extremes=classify_extremes(hilo, points), start=start, end=end)


def _parse_series(raw: list[dict[str, Any]]) -> list[tuple[datetime, float]]:
    series = []
    for item in raw:
        try:
            series.append((parse_time(item["eventDate"]), float(item["value"])))
        except (KeyError, TypeError, ValueError):
            continue
    series.sort(key=lambda p: p[0])
    return series


def parse_time(value: str) -> datetime:
    """Parse an API timestamp such as 2026-09-27T00:41:00Z into an aware UTC datetime."""
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def format_utc(value: datetime) -> str:
    """Format an aware datetime as the API expects (UTC, Z suffix)."""
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def classify_extremes(
    hilo: list[tuple[datetime, float]], points: list[tuple[datetime, float]]
) -> list[tuple[datetime, float, str]]:
    """Label each high/low point as "high" or "low".

    The API does not say which is which. The prediction curve is the reference: a high
    sits above the curve two hours before and after it. Neighbouring points (highs and
    lows alternate) are only used when the curve does not cover the point.
    """
    extremes = []
    for i, (when, value) in enumerate(hilo):
        ref = [
            v
            for v in (interpolate(points, when - timedelta(hours=2)), interpolate(points, when + timedelta(hours=2)))
            if v is not None
        ]
        if not ref:
            ref = [hilo[j][1] for j in (i - 1, i + 1) if 0 <= j < len(hilo)]
        if not ref:
            continue
        extremes.append((when, value, "high" if value > sum(ref) / len(ref) else "low"))
    return extremes


def interpolate(points: list[tuple[datetime, float]], when: datetime) -> float | None:
    """Linear interpolation of the water level at a given time, None outside the data."""
    if not points or when < points[0][0] or when > points[-1][0]:
        return None
    lo, hi = 0, len(points) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if points[mid][0] <= when:
            lo = mid
        else:
            hi = mid
    (t0, v0), (t1, v1) = points[lo], points[hi]
    if t1 == t0:
        return v0
    ratio = (when - t0).total_seconds() / (t1 - t0).total_seconds()
    return v0 + (v1 - v0) * ratio


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometres."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def nearest(stations: list[Station], lat: float, lon: float, count: int) -> list[tuple[Station, float]]:
    """The `count` stations closest to a point, with their distance in km.

    Stations flagged as not operating still publish predictions, so they are kept.
    """
    ranked = sorted(((s, haversine_km(lat, lon, s.latitude, s.longitude)) for s in stations), key=lambda i: i[1])
    return ranked[:count]


def search(stations: list[Station], query: str, lat: float, lon: float, limit: int) -> list[tuple[Station, float]]:
    """Stations whose name or code contains `query` (case/accent-insensitive), nearest first."""
    needle = fold(query)
    matches = [s for s in stations if needle in fold(s.name) or needle in s.code]
    ranked = sorted(((s, haversine_km(lat, lon, s.latitude, s.longitude)) for s in matches), key=lambda i: i[1])
    return ranked[:limit]


def fold(text: str) -> str:
    """Lower-case and strip accents so "Riviere" matches "Rivière"."""
    return "".join(c for c in unicodedata.normalize("NFD", text.casefold()) if unicodedata.category(c) != "Mn")


def station_label(station: Station, distance_km: float | None = None) -> str:
    """Human label such as "Halifax · 00490 · 2.3 km"."""
    parts = [station.name, station.code]
    if distance_km is not None:
        parts.append(f"{distance_km:.0f} km" if distance_km >= 10 else f"{distance_km:.1f} km")
    return " · ".join(p for p in parts if p)

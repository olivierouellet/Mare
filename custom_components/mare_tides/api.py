"""Shared types and helpers for the tide prediction clients.

Kept free of Home Assistant imports so it can be exercised on its own.
"""
from __future__ import annotations

import asyncio
import math
import unicodedata
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

import aiohttp

TIMEOUT = aiohttp.ClientTimeout(total=30)

# Stations with highs and lows only: fetching a day either side makes sure the curve
# has a high or low before the start and after the end of the window.
HILO_MARGIN = timedelta(days=1)


class TideApiError(Exception):
    """Raised when a tide prediction service cannot be reached or returns bad data."""


@dataclass(frozen=True)
class Station:
    """A tide station that publishes predictions and high/low predictions."""

    id: str
    code: str
    name: str
    latitude: float
    longitude: float
    operating: bool
    provider: str
    # Some stations only publish highs and lows; their curve is drawn through them.
    hilo_only: bool = False


@dataclass
class TideData:
    """Predicted water levels and high/low points for a time window."""

    points: list[tuple[datetime, float]] = field(default_factory=list)
    extremes: list[tuple[datetime, float, str]] = field(default_factory=list)
    start: datetime | None = None
    end: datetime | None = None


class TideClient(ABC):
    """Base class for provider clients.

    A provider implements `async_get_stations` and `_async_get_predictions`, plus
    `_async_get_extremes` if some of its stations only publish highs and lows.
    """

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session

    async def _get_json(self, url: str, params: dict[str, str] | None = None) -> Any:
        """GET a JSON document; network errors and non-200 answers raise TideApiError."""
        try:
            async with self._session.get(url, params=params, timeout=TIMEOUT) as resp:
                if resp.status != 200:
                    raise TideApiError(f"HTTP {resp.status} for {url}")
                return await resp.json(content_type=None)
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as err:
            raise TideApiError(f"Error requesting {url}: {err}") from err

    @abstractmethod
    async def async_get_stations(self) -> list[Station]:
        """All stations that publish tide predictions."""

    @abstractmethod
    async def _async_get_predictions(
        self, station_id: str, start: datetime, end: datetime
    ) -> tuple[list[tuple[datetime, float]], list[tuple[datetime, float, str]]]:
        """The 15-minute curve and the labelled highs and lows between start and end."""

    async def _async_get_extremes(
        self, station_id: str, start: datetime, end: datetime
    ) -> list[tuple[datetime, float, str]]:
        """Labelled highs and lows between start and end, for stations without a curve."""
        raise NotImplementedError

    async def async_get_tides(
        self, station_id: str, start: datetime, end: datetime, hilo_only: bool = False
    ) -> TideData:
        """Predictions for one station; a curve is drawn for stations with highs and lows only."""
        if hilo_only:
            extremes = await self._async_get_extremes(station_id, start - HILO_MARGIN, end + HILO_MARGIN)
            points = cosine_curve(extremes, start, end)
            extremes = [e for e in extremes if start <= e[0] <= end]
        else:
            points, extremes = await self._async_get_predictions(station_id, start, end)
        if not points:
            raise TideApiError(f"No predictions returned for station {station_id}")
        return TideData(points=points, extremes=extremes, start=start, end=end)


def parse_time(value: str) -> datetime:
    """Parse an API timestamp such as 2026-09-27T00:41:00Z into an aware UTC datetime."""
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def format_utc(value: datetime) -> str:
    """Format an aware datetime as the API expects (UTC, Z suffix)."""
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


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


def cosine_curve(
    extremes: list[tuple[datetime, float, str]],
    start: datetime,
    end: datetime,
    step: timedelta = timedelta(minutes=15),
) -> list[tuple[datetime, float]]:
    """A water level curve through successive highs and lows, one point per `step`.

    Between two extremes the level follows half a cosine, the usual way to draw a tide
    from its highs and lows: it passes exactly through each of them and is flat at the
    turns. Times not between two extremes are left out.
    """
    points: list[tuple[datetime, float]] = []
    i = 0
    when = start
    while when <= end:
        while i + 1 < len(extremes) and extremes[i + 1][0] < when:
            i += 1
        if i + 1 < len(extremes) and extremes[i][0] <= when:
            (t0, h0, _), (t1, h1, _) = extremes[i], extremes[i + 1]
            phase = math.pi * (when - t0).total_seconds() / (t1 - t0).total_seconds()
            points.append((when, (h0 + h1) / 2 + (h0 - h1) / 2 * math.cos(phase)))
        when += step
    return points


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

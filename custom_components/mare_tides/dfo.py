"""Client for the DFO / MPO Integrated Water Level System (IWLS) API (Canada)."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any

import aiohttp

from .api import TIMEOUT, Station, TideApiError, TideData, format_utc, interpolate, parse_time

BASE_URL = "https://api-iwls.dfo-mpo.gc.ca/api/v1"

SERIES_PREDICTIONS = "wlp"
SERIES_HILO = "wlp-hilo"


class DfoClient:
    """Minimal async client for the endpoints this integration needs."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session

    async def _get(self, path: str, params: dict[str, str] | None = None) -> list[dict[str, Any]]:
        try:
            async with self._session.get(f"{BASE_URL}{path}", params=params, timeout=TIMEOUT) as resp:
                if resp.status != 200:
                    raise TideApiError(f"HTTP {resp.status} for {path}")
                payload = await resp.json()
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise TideApiError(f"Error requesting {path}: {err}") from err

        # The API returns a bare list; older docs show a {"data": [...]} wrapper.
        if isinstance(payload, dict):
            payload = payload.get("data")
        if not isinstance(payload, list):
            raise TideApiError(f"Unexpected response format for {path}")
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
                        provider="dfo",
                    )
                )
            except (KeyError, TypeError, ValueError):
                continue
        return stations

    async def async_get_tides(
        self, station_id: str, start: datetime, end: datetime, subordinate: bool = False
    ) -> TideData:
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
            raise TideApiError(f"No predictions returned for station {station_id}")
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

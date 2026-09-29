"""Client for the DFO / MPO Integrated Water Level System (IWLS) API (Canada)."""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from .api import Station, TideApiError, TideClient, classify_extremes, format_utc, parse_time

BASE_URL = "https://api-iwls.dfo-mpo.gc.ca/api/v1"

SERIES_PREDICTIONS = "wlp"
SERIES_HILO = "wlp-hilo"


class DfoClient(TideClient):
    """Minimal async client for the endpoints this integration needs."""

    async def _get(self, path: str, params: dict[str, str] | None = None) -> list[dict[str, Any]]:
        payload = await self._fetch(f"{BASE_URL}{path}", params=params)
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

    async def _async_get_predictions(
        self, station_id: str, start: datetime, end: datetime
    ) -> tuple[list[tuple[datetime, float]], list[tuple[datetime, float, str]]]:
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
        return points, classify_extremes(_parse_series(raw_hilo), points)


def _parse_series(raw: list[dict[str, Any]]) -> list[tuple[datetime, float]]:
    series = []
    for item in raw:
        try:
            series.append((parse_time(item["eventDate"]), float(item["value"])))
        except (KeyError, TypeError, ValueError):
            continue
    series.sort(key=lambda p: p[0])
    return series

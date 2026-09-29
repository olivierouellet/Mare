"""Client for the ADMIRALTY UK Tidal API, Discovery tier (United Kingdom)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import aiohttp

from .api import Station, TideApiError, TideClient

BASE_URL = "https://admiraltyapi.azure-api.net/uktidalapi/api/V1"

KINDS = {"HighWater": "high", "LowWater": "low"}


class AdmiraltyClient(TideClient):
    """High and low waters for UKHO tidal stations, in metres above chart datum.

    The free Discovery tier only publishes high and low waters, for today and the next
    six days, so every station is `hilo_only` and nothing before today is available.
    The client remembers the events it has seen, so the curve still covers the hours
    before today's first tide after it has been running for a day.
    """

    def __init__(self, session: aiohttp.ClientSession, api_key: str | None = None) -> None:
        super().__init__(session, api_key)
        self._seen: dict[str, dict[datetime, tuple[datetime, float, str]]] = {}

    async def _get(self, path: str, params: dict[str, str] | None = None) -> Any:
        return await self._fetch(
            f"{BASE_URL}{path}", params=params, headers={"Ocp-Apim-Subscription-Key": self._api_key or ""}
        )

    async def async_get_stations(self) -> list[Station]:
        """Return all tidal stations (a GeoJSON feature collection)."""
        payload = await self._get("/Stations")
        if not isinstance(payload, dict):
            raise TideApiError("Unexpected response from the ADMIRALTY stations list")
        stations = []
        for feature in payload.get("features") or []:
            try:
                props = feature["properties"]
                lon, lat = feature["geometry"]["coordinates"][:2]
                stations.append(
                    Station(
                        id=props["Id"],
                        code=props["Id"],
                        name=props["Name"].strip(),
                        latitude=float(lat),
                        longitude=float(lon),
                        operating=True,
                        provider="admiralty",
                        hilo_only=True,
                    )
                )
            except (KeyError, TypeError, ValueError, AttributeError):
                continue
        return stations

    async def _async_get_predictions(
        self, station_id: str, start: datetime, end: datetime
    ) -> tuple[list[tuple[datetime, float]], list[tuple[datetime, float, str]]]:
        raise TideApiError("ADMIRALTY Discovery only publishes high and low waters")

    async def _async_get_extremes(
        self, station_id: str, start: datetime, end: datetime
    ) -> list[tuple[datetime, float, str]]:
        """Today and the next six days (the most Discovery allows), plus events seen before."""
        payload = await self._get(f"/Stations/{station_id}/TidalEvents", {"duration": "7"})
        if not isinstance(payload, list):
            raise TideApiError(f"Unexpected response for station {station_id}")

        seen = self._seen.setdefault(station_id, {})
        for item in payload:
            try:
                when = _parse_time(item["DateTime"])
                seen[when] = (when, float(item["Height"]), KINDS[item["EventType"]])
            except (KeyError, TypeError, ValueError):
                continue
        for when in [w for w in seen if w < start]:
            del seen[when]
        return sorted(seen.values())


def _parse_time(value: str) -> datetime:
    """Parse "2026-09-29T05:12:00" (UTC, sometimes with fractions of a second)."""
    return datetime.fromisoformat(value.split(".")[0]).replace(tzinfo=timezone.utc)

"""Client for the Rijkswaterstaat Waterwebservices (the Netherlands)."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from .api import Station, TideApiError, TideClient, classify_extremes, parse_time

BASE_URL = "https://ddapi20-waterwebservices.rijkswaterstaat.nl"
CATALOGUE_URL = f"{BASE_URL}/METADATASERVICES/OphalenCatalogus"
DATA_URL = f"{BASE_URL}/ONLINEWAARNEMINGENSERVICES/OphalenWaarnemingen"

ASTRONOMICAL = "astronomisch"
WATER_HEIGHT = "WATHTE"
EXTREME_TYPE = "NVT"
# The computed high and low waters, as opposed to the regular curve (no grouping).
EXTREMES_GROUP = "GETETBRKD2"


class RijkswaterstaatClient(TideClient):
    """Astronomical tide predictions, in cm relative to NAP (Normaal Amsterdams Peil)."""

    async def async_get_stations(self) -> list[Station]:
        """Return the locations with an astronomical water height and high/low waters."""
        payload = await self._fetch(CATALOGUE_URL, json={"CatalogusFilter": {"Grootheden": True, "ProcesTypes": True}})
        if not isinstance(payload, dict) or not payload.get("Succesvol"):
            raise TideApiError("Unexpected response from the Rijkswaterstaat catalogue")

        wanted = {
            item["AquoMetadata_MessageID"]: item["Grootheid"]["Code"]
            for item in payload.get("AquoMetadataLijst") or []
            if item.get("ProcesType") == ASTRONOMICAL
            and item.get("Grootheid", {}).get("Code") in (WATER_HEIGHT, EXTREME_TYPE)
        }
        series: dict[int, set[str]] = {}
        for link in payload.get("AquoMetadataLocatieLijst") or []:
            if (code := wanted.get(link.get("AquoMetaData_MessageID"))) is not None:
                series.setdefault(link.get("Locatie_MessageID"), set()).add(code)

        stations = []
        for item in payload.get("LocatieLijst") or []:
            if series.get(item.get("Locatie_MessageID")) != {WATER_HEIGHT, EXTREME_TYPE}:
                continue
            try:
                stations.append(
                    Station(
                        id=item["Code"],
                        code=item["Code"],
                        name=item.get("Naam") or item["Code"],
                        latitude=float(item["Lat"]),
                        longitude=float(item["Lon"]),
                        operating=True,
                        provider="rijkswaterstaat",
                    )
                )
            except (KeyError, TypeError, ValueError):
                continue
        return stations

    async def _async_get_predictions(
        self, station_id: str, start: datetime, end: datetime
    ) -> tuple[list[tuple[datetime, float]], list[tuple[datetime, float, str]]]:
        curve, extremes = await asyncio.gather(
            self._series(station_id, start, end, None),
            self._series(station_id, start, end, EXTREMES_GROUP),
        )
        # The high and low waters are not labelled; the curve tells which is which.
        return curve, classify_extremes(extremes, curve)

    async def _series(
        self, station_id: str, start: datetime, end: datetime, group: str | None
    ) -> list[tuple[datetime, float]]:
        """Astronomical water heights in metres, either the curve or the high/low waters."""
        metadata: dict[str, Any] = {
            "Compartiment": {"Code": "OW"},
            "Grootheid": {"Code": WATER_HEIGHT},
            "ProcesType": ASTRONOMICAL,
        }
        if group:
            metadata["Groepering"] = {"Code": group}
        payload = await self._fetch(
            DATA_URL,
            json={
                "Locatie": {"Code": station_id},
                "AquoPlusWaarnemingMetadata": {"AquoMetadata": metadata},
                "Periode": {"Begindatumtijd": _format_time(start), "Einddatumtijd": _format_time(end)},
            },
            empty=frozenset({204}),  # no data in this period
        )
        if payload is None:
            return []
        if not isinstance(payload, dict) or not payload.get("Succesvol"):
            raise TideApiError(f"Unexpected response for station {station_id}")

        levels = []
        for item in payload.get("WaarnemingenLijst") or []:
            # Asking for the curve (no grouping) must not pick up grouped series.
            if (item.get("AquoMetadata", {}).get("Groepering", {}).get("Code") or None) != group:
                continue
            for value in item.get("MetingenLijst") or []:
                try:
                    levels.append((parse_time(value["Tijdstip"]), float(value["Meetwaarde"]["Waarde_Numeriek"]) / 100))
                except (KeyError, TypeError, ValueError):
                    continue
        levels.sort(key=lambda p: p[0])
        return levels


def _format_time(value: datetime) -> str:
    """Format an aware datetime as Rijkswaterstaat expects."""
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000+00:00")

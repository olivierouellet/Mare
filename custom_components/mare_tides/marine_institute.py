"""Client for the Marine Institute ERDDAP tide predictions (Ireland)."""
from __future__ import annotations

import asyncio
import csv
from datetime import datetime
from urllib.parse import quote

from yarl import URL

from .api import Station, TideApiError, TideClient, format_utc, parse_time

BASE_URL = "https://erddap.marine.ie/erddap/tabledap"
CURVE_DATASET = "imiTidePrediction"
HILO_DATASET = "IMI_TidePrediction_HighLow"

# Model-only stations carry this suffix in the curve dataset but not in the high/low one.
MODELLED_SUFFIX = "_MODELLED"
# The curve comes every 5 minutes; a point every 15 minutes is enough.
CURVE_MINUTES = 15

KINDS = {"HIGH": "high", "LOW": "low"}


class MarineInstituteClient(TideClient):
    """Predictions for the Irish National Tide Gauge Network, in metres relative to OD Malin."""

    async def _query(self, dataset: str, query: str) -> list[dict[str, str]]:
        """Rows of an ERDDAP tabledap CSV query; ERDDAP answers 404 when nothing matches."""
        # ERDDAP rejects unencoded quotes, commas and comparison signs, so encode it all here.
        url = URL(f"{BASE_URL}/{dataset}.csv?{quote(query, safe='=&')}", encoded=True)
        body = await self._fetch(url, text=True, empty=frozenset({404}))
        if body is None:
            return []
        rows = list(csv.DictReader(body.splitlines()))
        if not rows or not rows[0]:
            raise TideApiError(f"Unexpected response from {dataset}")
        return rows[1:]  # the first row holds the units

    async def async_get_stations(self) -> list[Station]:
        """Return all stations with a predicted curve."""
        rows = await self._query(CURVE_DATASET, "stationID,longitude,latitude&distinct()")
        stations = []
        for row in rows:
            try:
                station_id = row["stationID"]
                stations.append(
                    Station(
                        id=station_id,
                        code="",
                        name=station_id.removesuffix(MODELLED_SUFFIX).replace("_", " "),
                        latitude=float(row["latitude"]),
                        longitude=float(row["longitude"]),
                        operating=True,
                        provider="marine_institute",
                    )
                )
            except (KeyError, TypeError, ValueError):
                continue
        return stations

    async def _async_get_predictions(
        self, station_id: str, start: datetime, end: datetime
    ) -> tuple[list[tuple[datetime, float]], list[tuple[datetime, float, str]]]:
        window = f"&time>={format_utc(start)}&time<={format_utc(end)}"
        curve, hilo = await asyncio.gather(
            self._query(CURVE_DATASET, f'time,Water_Level_ODM{window}&stationID="{station_id}"'),
            self._query(
                HILO_DATASET,
                f'time,tide_time_category,Water_Level_ODMalin{window}'
                f'&stationID="{station_id.removesuffix(MODELLED_SUFFIX)}"',
            ),
        )
        points = []
        for row in curve:
            try:
                when = parse_time(row["time"])
                if when.minute % CURVE_MINUTES == 0:
                    points.append((when, float(row["Water_Level_ODM"])))
            except (KeyError, TypeError, ValueError):
                continue
        extremes = []
        for row in hilo:
            try:
                extremes.append(
                    (parse_time(row["time"]), float(row["Water_Level_ODMalin"]), KINDS[row["tide_time_category"]])
                )
            except (KeyError, TypeError, ValueError):
                continue
        points.sort(key=lambda p: p[0])
        extremes.sort(key=lambda e: e[0])
        return points, extremes

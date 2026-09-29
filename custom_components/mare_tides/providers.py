"""Tide prediction providers. Adding a country means adding a client and an entry here."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .api import TideClient
from .dfo import DfoClient
from .noaa import NoaaClient


@dataclass(frozen=True)
class Provider:
    """A tide prediction service and how to credit and link to it."""

    client: type[TideClient]
    attribution: str
    station_url: Callable[[str, str], str]  # (station id, station code) → web page


PROVIDERS: dict[str, Provider] = {
    "dfo": Provider(
        client=DfoClient,
        attribution="Fisheries and Oceans Canada / Pêches et Océans Canada",
        station_url=lambda _id, code: f"https://www.tides.gc.ca/en/stations/{code}",
    ),
    "noaa": Provider(
        client=NoaaClient,
        attribution="NOAA Tides and Currents",
        station_url=lambda station_id, _code: (
            f"https://tidesandcurrents.noaa.gov/noaatidepredictions.html?id={station_id}"
        ),
    ),
}

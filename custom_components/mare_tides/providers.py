"""Tide prediction providers. Adding a country means adding a client and an entry here."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .api import TideClient
from .dfo import DfoClient
from .kartverket import KartverketClient
from .marine_institute import MarineInstituteClient
from .noaa import NoaaClient
from .rijkswaterstaat import RijkswaterstaatClient


@dataclass(frozen=True)
class Provider:
    """A tide prediction service and how to credit and link to it."""

    client: type[TideClient]
    countries: tuple[str, ...]  # ISO 3166 codes; the setup flow suggests the provider for these
    attribution: str
    datum: str  # what heights are measured from
    station_url: Callable[[str, str], str]  # (station id, station code) → web page


PROVIDERS: dict[str, Provider] = {
    "dfo": Provider(
        client=DfoClient,
        countries=("CA",),
        attribution="Fisheries and Oceans Canada / Pêches et Océans Canada",
        datum="Chart datum",
        station_url=lambda _id, code: f"https://www.tides.gc.ca/en/stations/{code}",
    ),
    "noaa": Provider(
        client=NoaaClient,
        countries=("US", "PR", "VI", "GU", "AS", "MP"),
        attribution="NOAA Tides and Currents",
        datum="MLLW",
        station_url=lambda station_id, _code: (
            f"https://tidesandcurrents.noaa.gov/noaatidepredictions.html?id={station_id}"
        ),
    ),
    "kartverket": Provider(
        client=KartverketClient,
        countries=("NO", "SJ"),
        attribution="Kartverket (Norwegian Mapping Authority)",
        datum="Chart datum",
        station_url=lambda _id, _code: "https://www.kartverket.no/en/at-sea/se-havniva",
    ),
    "rijkswaterstaat": Provider(
        client=RijkswaterstaatClient,
        countries=("NL",),
        attribution="Rijkswaterstaat",
        datum="NAP",
        station_url=lambda _id, _code: "https://waterinfo.rws.nl/",
    ),
    "marine_institute": Provider(
        client=MarineInstituteClient,
        countries=("IE",),
        attribution="Marine Institute, Ireland",
        datum="OD Malin",
        station_url=lambda _id, _code: "https://erddap.marine.ie/erddap/tabledap/imiTidePrediction.html",
    ),
}


def provider_for_country(country: str | None) -> str:
    """The provider covering a country, or the first one."""
    return next((key for key, p in PROVIDERS.items() if country in p.countries), next(iter(PROVIDERS)))

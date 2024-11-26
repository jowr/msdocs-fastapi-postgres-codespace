import sys
import numpy as np
from enum import Enum
import requests
import openmeteo_requests
import requests_cache
from retry_requests import retry

from pydantic import BaseModel

from OSMPythonTools.nominatim import Nominatim
from OSMPythonTools.cachingStrategy import CachingStrategy, JSON

CachingStrategy.use(JSON, cacheDir=".cache-open-street-map")


class SortableEnum(Enum):
    def idx(self) -> int:
        order = list(self.__class__)
        return order.index(self)

    def __lt__(self, other) -> bool:
        if other is None:
            return False
        if not isinstance(other, self.__class__):
            return NotImplemented
        order = list(self.__class__)
        return order.index(self) < order.index(other)

    def __le__(self, other) -> bool:
        if other is None:
            return False
        return self < other or self == other

    def __gt__(self, other) -> bool:
        if other is None:
            return True
        return not self <= other

    def __ge__(self, other) -> bool:
        if other is None:
            return True
        return not self < other


class LocationData(BaseModel):
    name: str = ""
    country: str = ""
    lat: float = np.nan
    lon: float = np.nan

    def loc_str(self, delim=", ") -> str:
        lst = []
        if self.name:
            lst.append(self.name)
        if self.country:
            lst.append(self.country)
        return delim.join(lst)

    def __str__(self):
        return self.loc_str()


def _location_query_osm(loc: LocationData) -> None:
    nominatim = Nominatim()
    dct = nominatim.query(loc.loc_str()).toJSON()[0]
    loc.lat = float(dct["lat"])
    loc.lon = float(dct["lon"])
    return


def _location_query_om(loc: LocationData, apikey: str | None = None) -> None:
    params = {}
    params["count"] = 10
    params["language"] = "en"
    params["format"] = "json"
    # params["name"] = requests.utils.quote(loc.loc_str(delim=" "))
    # params["name"] = "+".join(loc.loc_str(delim=" ").split(" "))
    params["name"] = "+".join(loc.name.split(" "))
    URL = "https://geocoding-api.open-meteo.com/v1/search"

    if apikey is not None:
        params["apikey"] = apikey
        URL = "https://customer-geocoding-api.open-meteo.com/v1/search"

    url = URL + "?" + "&".join([f"{key}={value}" for key, value in params.items()])
    s = requests.Session()
    dct = s.get(url).json()
    item = dct["results"][0]
    loc.lat = float(item["latitude"])
    loc.lon = float(item["longitude"])
    return


def get_coordinates(city: str, country: str) -> LocationData:
    loc = LocationData(name=city, country=country)
    # _location_query_osm(loc)
    _location_query_om(loc)
    return loc


# Setup the Open-Meteo API client with a cache and retry mechanism
cache_session = requests_cache.CachedSession(".cache", expire_after=-1)
retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
om = openmeteo_requests.Client(session=retry_session)


class OmVariableEnum(str, SortableEnum):
    TempAir = "temperature_2m"
    RelHum = "relative_humidity_2m"
    DePoint = "dew_point_2m"
    Pressure = "surface_pressure"
    WindSpeed = "wind_speed_10m"
    TempSoil = "soil_temperature_54cm"
    Precipitation = "precipitation"
    Radiation = "direct_radiation"

    def get_idx(self, var: "OmVariableEnum") -> int:
        return


def prepare_om_params(lat: float, long: float) -> dict[str, str | float]:
    params = {
        "latitude": lat,
        "longitude": long,
        "hourly": [entry.value for entry in OmVariableEnum],
        # "current": ["temperature_2m", "relative_humidity_2m"],
        "forecast_days": 2,
        "tilt": 45,  # 0 degrees = horizontal
        "azimuth": -45,  # 0 deg = S, -90 deg = E, 90 deg = W
    }
    return params


def make_call(city, country):
    loc = get_coordinates(city, country)
    params = prepare_om_params(loc.lat, loc.lon)
    return loc, params


def main():
    for loc, params in [
        make_call("New York", "USA"),
        make_call("Copenhagen", "Denmark"),
        make_call("Zürich", "Switzerland"),
        make_call("Sydney", "Australia"),
    ]:

        print(f"Processing {loc}")

        responses = om.weather_api(
            "https://api.open-meteo.com/v1/forecast", params=params
        )
        response = responses[0]
        print(f"Coordinates {response.Latitude()}°N {response.Longitude()}°E")
        print(f"Elevation {response.Elevation()} m asl")

        hourly = response.Hourly()

        hourly_time = range(hourly.Time(), hourly.TimeEnd(), hourly.Interval())

        idx = OmVariableEnum.TempAir.idx()
        hourly_T_air = hourly.Variables(idx).ValuesAsNumpy()
        idx = OmVariableEnum.Radiation.idx()
        hourly_radiation = hourly.Variables(idx).ValuesAsNumpy()

        print(hourly_time)
        print(hourly_T_air)
        print(hourly_radiation)


if __name__ == "__main__":
    main()
    sys.exit(0)

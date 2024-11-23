import sys
import numpy as np
from enum import Enum

import openmeteo_requests
import requests_cache
from retry_requests import retry

from OSMPythonTools.nominatim import Nominatim
from OSMPythonTools.cachingStrategy import CachingStrategy, JSON

CachingStrategy.use(JSON, cacheDir=".cache-open-street-map")


# Converts a iterable of string City names to a list of lat lon stings
# Example: Input - "New York, NY, USA"
#          Output = "40.7127281,-74.0060152"
def _location_query(city: str) -> dict[str, str]:
    nominatim = Nominatim()
    return nominatim.query(city).toJSON()[0]


def get_coordinates(city: str, country: str) -> tuple[float, float]:
    # Converts a iterable of string City names to a list of lat lon stings
    # Example: Input - "New York", "USA"
    #          Output = 40.7127281, -74.0060152
    qry = f"{city}, {country}"
    jsn = _location_query(qry)
    return float(jsn["lat"]), float(jsn["lon"])


# Setup the Open-Meteo API client with a cache and retry mechanism
cache_session = requests_cache.CachedSession(".cache", expire_after=-1)
retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
om = openmeteo_requests.Client(session=retry_session)


class OmVariableEnum(Enum, str):
    TempAir = "temperature_2m"
    RelHum = "relative_humidity_2m"
    DePoint = "dew_point_2m"
    Pressure = "surface_pressure"
    WindSpeed = "wind_speed_10m"
    TempSoil = "soil_temperature_54cm"
    Precipitation = "precipitation"


def main():
    coord = get_coordinates("New York", "USA")
    print(f"{coord[0]},{coord[1]}")

    from openmeteo_sdk.Variable import Variable

    params = {
        "latitude": 52.54,
        "longitude": 13.41,
        "hourly": ["temperature_2m", "precipitation", "wind_speed_10m"],
        "current": ["temperature_2m", "relative_humidity_2m"],
    }

    responses = om.weather_api("https://api.open-meteo.com/v1/forecast", params=params)
    response = responses[0]
    print(f"Coordinates {response.Latitude()}°N {response.Longitude()}°E")
    print(f"Elevation {response.Elevation()} m asl")
    print(f"Timezone {response.Timezone()} {response.TimezoneAbbreviation()}")
    print(f"Timezone difference to GMT+0 {response.UtcOffsetSeconds()} s")

    # Current values
    current = response.Current()
    current_variables = list(
        map(lambda i: current.Variables(i), range(0, current.VariablesLength()))
    )
    current_temperature_2m = next(
        filter(
            lambda x: x.Variable() == Variable.temperature and x.Altitude() == 2,
            current_variables,
        )
    )
    current_relative_humidity_2m = next(
        filter(
            lambda x: x.Variable() == Variable.relative_humidity and x.Altitude() == 2,
            current_variables,
        )
    )

    print(f"Current time {current.Time()}")
    print(f"Current temperature_2m {current_temperature_2m.Value()}")
    print(f"Current relative_humidity_2m {current_relative_humidity_2m.Value()}")

    hourly = response.Hourly()
    hourly_time = range(hourly.Time(), hourly.TimeEnd(), hourly.Interval())
    hourly_variables = list(
        map(lambda i: hourly.Variables(i), range(0, hourly.VariablesLength()))
    )

    hourly_temperature_2m = next(
        filter(
            lambda x: x.Variable() == Variable.temperature and x.Altitude() == 2,
            hourly_variables,
        )
    ).ValuesAsNumpy()
    hourly_precipitation = next(
        filter(lambda x: x.Variable() == Variable.precipitation, hourly_variables)
    ).ValuesAsNumpy()
    hourly_wind_speed_10m = next(
        filter(
            lambda x: x.Variable() == Variable.wind_speed and x.Altitude() == 10,
            hourly_variables,
        )
    ).ValuesAsNumpy()

    vec = np.asarray(hourly_temperature_2m)
    print(vec)


if __name__ == "__main__":
    main()
    sys.exit(0)

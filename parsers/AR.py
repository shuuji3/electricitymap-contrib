#!/usr/bin/env python3

import datetime
import json
import logging
from typing import Dict, List

import arrow
import pandas as pd
import requests

from lib import web

# Useful links.
# https://en.wikipedia.org/wiki/Electricity_sector_in_Argentina
# https://en.wikipedia.org/wiki/List_of_power_stations_in_Argentina
# http://globalenergyobservatory.org/countryid/10#
# http://www.industcards.com/st-other-argentina.htm

# API Documentation: https://api.cammesa.com/demanda-svc/swagger-ui.html
CAMMESA_DEMANDA_ENDPOINT = (
    "https://api.cammesa.com/demanda-svc/generacion/ObtieneGeneracioEnergiaPorRegion/"
)
CAMMESA_RENEWABLES_ENDPOINT = "https://cdsrenovables.cammesa.com/exhisto/RenovablesService/GetChartTotalTRDataSource/"
CAMMESA_EXCHANGE_ENDPOINT = (
    "https://api.cammesa.com/demanda-svc/demanda/IntercambioCorredoresGeo"
)
CAMMESA_DEMAND_ENDPOINT = "https://api.cammesa.com/demanda-svc/demanda/ObtieneDemandaYTemperaturaRegion?id_region=1002"

TZ = "America/Argentina/Buenos_Aires"


def fetch_production(
    zone_key="AR",
    session=None,
    target_datetime: datetime.datetime = None,
    logger: logging.Logger = logging.getLogger(__name__),
) -> List[dict]:
    """Requests up to date list of production mixes (in MW) of a given country."""

    if target_datetime:
        raise NotImplementedError("This parser is not yet able to parse past dates")

    current_session = session or requests.session()

    non_renewables_production: Dict[str, dict] = non_renewables_production_mix(
        zone_key, current_session
    )
    renewables_production: Dict[str, dict] = renewables_production_mix(
        zone_key, current_session
    )

    full_production_list = [
        {
            "datetime": arrow.get(datetime_tz_ar).to("UTC").datetime,
            "zoneKey": zone_key,
            "production": merged_production_mix(
                non_renewables_production[datetime_tz_ar],
                renewables_production[datetime_tz_ar],
            ),
            "capacity": {},
            "storage": {},
            "source": "cammesaweb.cammesa.com",
        }
        for datetime_tz_ar in non_renewables_production
        if datetime_tz_ar in renewables_production
    ]

    return full_production_list


def merged_production_mix(non_renewables_mix: dict, renewables_mix: dict) -> dict:
    """Merges production mix data from different sources. Hydro comes from two
    different sources that are added up."""

    production_mix = {
        "biomass": renewables_mix["biomass"],
        "solar": renewables_mix["solar"],
        "wind": renewables_mix["wind"],
        "hydro": non_renewables_mix["hydro"] + renewables_mix["hydro"],
        "nuclear": non_renewables_mix["nuclear"],
        "unknown": non_renewables_mix["unknown"],
    }

    return production_mix


def renewables_production_mix(zone_key: str, session) -> Dict[str, dict]:
    """Retrieves production mix for renewables using CAMMESA's API"""

    today = arrow.now(tz="America/Argentina/Buenos Aires").format("DD-MM-YYYY")
    params = {"desde": today, "hasta": today}
    renewables_response = session.get(CAMMESA_RENEWABLES_ENDPOINT, params=params)
    assert renewables_response.status_code == 200, (
        "Exception when fetching production for "
        "{}: error when calling url={} with payload={}".format(
            zone_key, CAMMESA_RENEWABLES_ENDPOINT, params
        )
    )

    production_list = renewables_response.json()
    sorted_production_list = sorted(production_list, key=lambda d: d["momento"])

    renewables_production: Dict[str, dict] = {
        production_info["momento"]: {
            "biomass": production_info["biocombustible"],
            "hydro": production_info["hidraulica"],
            "solar": production_info["fotovoltaica"],
            "wind": production_info["eolica"],
        }
        for production_info in sorted_production_list
    }

    return renewables_production


def non_renewables_production_mix(zone_key: str, session) -> Dict[str, dict]:
    """Retrieves production mix for non renewables using CAMMESA's API"""

    params = {"id_region": 1002}
    api_cammesa_response = session.get(CAMMESA_DEMANDA_ENDPOINT, params=params)
    assert api_cammesa_response.status_code == 200, (
        "Exception when fetching production for "
        "{}: error when calling url={} with payload={}".format(
            zone_key, CAMMESA_DEMANDA_ENDPOINT, params
        )
    )

    production_list = api_cammesa_response.json()
    sorted_production_list = sorted(production_list, key=lambda d: d["fecha"])

    non_renewables_production: Dict[str, dict] = {
        production_info["fecha"]: {
            "hydro": production_info["hidraulico"],
            "nuclear": production_info["nuclear"],
            # As of 2022 thermal energy is mostly natural gas but
            # the data is not split. We put it into unknown for now.
            # More info: see page 21 in https://microfe.cammesa.com/static-content/CammesaWeb/download-manager-files/Sintesis%20Mensual/Informe%20Mensual_2021-12.pdf
            "unknown": production_info["termico"],
        }
        for production_info in sorted_production_list
    }

    return non_renewables_production


def fetch_consumption_forecast(
    zone_key="AR",
    session=None,
    target_datetime=None,
    logger=logging.getLogger(__name__),
) -> list:
    """Gets consumption forecast for specified zone."""

    df = pd.read_json(CAMMESA_DEMAND_ENDPOINT)
    df.index = df["fecha"]
    df = df[["demPrevista"]].dropna()

    data = []
    for datetime_str, demand_forcast in df.iterrows():
        data.append(
            {
                "zoneKey": zone_key,
                "datetime": arrow.get(datetime_str),
                "value": int(demand_forcast),
                "source": "https://cammesaweb.cammesa.com/",
            }
        )
    return data


def fetch_exchange(
    zone_key1, zone_key2, session=None, target_datetime=None, logger=None
) -> dict:
    """Requests the last known power exchange (in MW) between two zones."""
    sorted_zone_keys = "->".join(sorted([zone_key1, zone_key2]))

    data = json.loads(web.get_response_text("AR", CAMMESA_EXCHANGE_ENDPOINT))

    id_name_map = _make_id_name_map()

    exchange_data = {}
    for feature in data["features"]:
        if not feature["properties"]["internacional"]:
            continue

        feature_id = feature["properties"]["id"]
        name = id_name_map[feature_id]
        value = int(feature["properties"]["text"])
        arrow_direction = int(
            feature["properties"]["url"]
        )  # i.e. 'flecha45' (arrow image at 45 degree)

        # TODO: maybe this is wrong. the value might be always positive and arrow_direction might be changed...
        if name != "CL":
            # Chili's value is export (i.e. AR->CH) but others are import (i.e. BR->AR)
            value *= -1
        key = f"AR->{name}"
        exchange_data[key] = value

    if sorted_zone_keys not in exchange_data:
        return

    data = {
        "sortedZoneKeys": sorted_zone_keys,
        "datetime": arrow.now(TZ),
        "netFlow": exchange_data.get(sorted_zone_keys),
        "source": "cammesaweb.cammesa.com",
    }

    return data


def _make_id_name_map() -> dict:
    """Create a mapping from id to name for exchange data.

    example return value: {'1002055': 'BR', '1002056': 'CL-SEN', '1002598': 'UY', '1002595': 'PY'}
    """
    name_map = {
        "BRA": "BR",  # Brazil
        # TODO: confirm if correct?
        "CHI": "CL-SEN",  # Chili
        "URU": "UY",  # Uruguay
        "PAR": "PY",  # Paraguay
    }

    url = "https://microfe.cammesa.com/demandaregionchart/assets/data/regionesExternasPuntos.geojson.json"
    data = json.loads(web.get_response_text("AR", url))

    mapping = {}
    for feature in data["features"]:
        feature_id = feature["properties"]["id"]
        feature_name = feature["properties"]["name"]
        mapping[feature_id] = name_map[feature_name]

    return mapping


def fetch_price(
    zone_key="AR",
    session=None,
    target_datetime=None,
    logger=logging.getLogger(__name__),
) -> dict:
    """Requests the last known power price of a given country."""

    raise NotImplementedError("Fetching the price is not currently implemented")


if __name__ == "__main__":
    """Main method, never used by the Electricity Map backend, but handy for testing."""

    print("fetch_production() ->")
    print(fetch_production())

    print("fetch_price() ->")
    print(fetch_price())

    print("fetch_consumption_forecast() ->")
    print(fetch_consumption_forecast())

    print("fetch_exchange(AR, PY) ->")
    print(fetch_exchange("AR", "PY"))
    print("fetch_exchange(AR, BR) ->")
    print(fetch_exchange("AR", "BR"))
    print("fetch_exchange(AR, UY) ->")
    print(fetch_exchange("AR", "UY"))
    print("fetch_exchange(AR, CL-SEN) ->")
    print(fetch_exchange("AR", "CL-SEN"))

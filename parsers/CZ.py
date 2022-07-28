#!/usr/bin/env python3

import logging
import pytz

import arrow
import zeep


DOMAIN = "ceps.cz"
SOAP_WSDL_API = "https://www.ceps.cz/_layouts/CepsData.asmx?WSDL"
TZ = "Europe/Prague"


def fetch_production(
    zone_key="CZ",
    session=None,
    target_datetime=None,
    logger=logging.getLogger(__name__),
) -> list:
    """Gets production for specified zone."""
    if target_datetime is None:
        target_datetime = arrow.now(TZ)

    client = zeep.Client(wsdl=SOAP_WSDL_API)
    generation = client.service.Generation(
        target_datetime.shift(days=-1).isoformat(),
        target_datetime.isoformat(),
        # "QH",  # QH = quarter hour = 15 minute data
        "HR",  # debug
        "AVG",  # AVG = average
        "RT",  # RT = real time
        "all",  # all = all types of energy
    )

    # Generation type category:
    # - TPP = thermal power plants
    # - CCGT = combined-cycle gas turbine power plant
    # - NPP = nuclear
    # - HPP = hydro
    # - PsPP = pumped-storage
    # - AltPP = alternative
    # - ApPP = autoproducer
    # - PvPP = photovoltaic
    # - WPP = wind power plants
    production = []
    for item in _convert_soap_response(generation):
        data = {
            "zoneKey": zone_key,
            "datetime": item["date"],
            "production": {
                "biomass": None,
                "coal": item.get("TPP [MW]"),
                "gas": item.get("CCGT [MW]"),
                "hydro": item.get("HPP [MW]"),
                "nuclear": item.get("NPP [MW]"),
                "oil": None,
                "solar": item.get("PvPP [MW]"),
                "wind": item.get("WPP [MW]"),
                "geothermal": None,
                # FIXME: dict < int error
                # "storage": {
                #     "hydro": item.get("PsPP [MW]"),
                # },
                "unknown": round(
                    item.get("AltPP [MW]"),
                    1,
                ),
            },
            "source": DOMAIN,
        }
        production.append(data)

    return production


def _convert_soap_response(soap_response) -> list[dict]:
    ns = "{https://www.ceps.cz/CepsData/StructuredData/1.0}"

    # A mapping used to convert attribute names to make it readable
    # example:
    # {'date': '2022-07-26T01:00:00+02:00', 'value1': '6651'}
    # => {'date': '2022-07-26T01:00:00+02:00', 'Generation plan [MW]': '6651'}
    attrib_name_map = {
        i.attrib["id"]: i.attrib["name"] for i in soap_response.iter(f"{ns}serie")
    }

    data_list = []
    for item in soap_response.getiterator(f"{ns}item"):
        data = {}
        for k, v in item.attrib.items():
            if k == "date":
                v = arrow.get(v).datetime
            elif k in attrib_name_map:
                k = attrib_name_map[k]
                v = float(v)
            data[k] = v
        data_list.append(data)
    return data_list


if __name__ == "__main__":
    """Main method, never used by the Electricity Map backend, but handy for testing."""

    print("fetch_production() ->")
    print(fetch_production())

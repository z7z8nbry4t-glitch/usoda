#!/usr/bin/env python3
"""Fetch Police Force Area boundaries (England & Wales) from the ONS Open
Geography Portal (Open Government Licence) and write data/pfa.geojson.

Boundaries change rarely, so this is run manually / on schedule, not on every
ingest. Geometry is requested in WGS84 and generalised server-side.
Contains OS data (c) Crown copyright and database right.
"""
import json
import os
import sys
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(__file__))
from usoda_common import DATA_DIR, now_iso, write_json  # noqa: E402

SERVICE = ("https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services/"
           "Police_Force_Areas_December_2023_EW_BUC/FeatureServer/0/query")

# police.uk force slug -> ONS PFA name (only where the plain slug->title rule fails)
SLUG_OVERRIDES = {
    "metropolitan": "Metropolitan Police",
    "city-of-london": "London, City of",
}


def slugify(name):
    return name.lower().replace(",", "").replace("&", "and").replace(" ", "-")


def main():
    params = {"where": "1=1", "outFields": "PFA23CD,PFA23NM", "outSR": "4326",
              "maxAllowableOffset": "0.002", "geometryPrecision": "4", "f": "geojson"}
    url = SERVICE + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "USODA-boundaries"})
    with urllib.request.urlopen(req, timeout=120) as r:
        gj = json.load(r)
    rev = {v: k for k, v in SLUG_OVERRIDES.items()}
    for f in gj["features"]:
        p = f["properties"]
        name = p.pop("PFA23NM")
        code = p.pop("PFA23CD")
        f["properties"] = {"code": code, "name": name,
                           "slug": rev.get(name) or slugify(name)}
    gj["metadata"] = {"source": "ONS Open Geography Portal: Police Force Areas (December 2023) EW BUC",
                      "licence": "Open Government Licence v3.0", "fetched": now_iso()}
    write_json(os.path.join(DATA_DIR, "pfa.geojson"), gj)
    print(len(gj["features"]), "areas;", sorted(f["properties"]["slug"] for f in gj["features"]))


if __name__ == "__main__":
    main()

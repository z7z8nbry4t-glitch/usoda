#!/usr/bin/env python3
"""Build the Scotland council-area layer (aggregate only; no point data).

Sources (both Open Government Licence v3.0):
  * Scottish Government, "Recorded Crimes and Offences", from Police Scotland
    returns, council-area level, financial years (April to March):
    https://data.gov.scot/dataset/recorded_crimes_and_offences
  * ONS Open Geography Portal, Local Authority Districts (December 2024) UK BUC.
    Contains OS data (c) Crown copyright and database right.

Writes data/scotland_la.json (rows) and data/scotland_la.geojson (32 areas).
Scottish "sexual crimes" (Group 2) is a different definition from the
police.uk combined "Violence and sexual offences" category, so this layer
must never be summed or ranked against the England/Wales/NI hexagons.
"""
import csv
import io
import json
import os
import sys
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(__file__))
from usoda_common import DATA_DIR, now_iso, write_json  # noqa: E402

CSV_URL = ("https://data.gov.scot/dataset/recorded_crimes_and_offences/resource/"
           "3716a560-80b0-4860-b11f-6a53d24deb21/download")
LAD_URL = ("https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services/"
           "Local_Authority_Districts_December_2024_Boundaries_UK_BUC/FeatureServer/0/query")
YEARS = 10
GROUPS = {
    "All Group 2: Sexual crimes": "sexual",
    "Crimes: Group 2: Rape & attempted rape": "rape",
    "Crimes: Group 2: Sexual assault": "assault",
    "All Group 1: Non-sexual crimes of violence": "violence_nonsexual",
}


def get(url, timeout=180):
    req = urllib.request.Request(url, headers={"User-Agent": "USODA-scotland"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def build_rows(text):
    """Return ({code: name}, [financial years], {code: {year: {key: {count, rate}}}})."""
    rd = csv.DictReader(io.StringIO(text))
    names, data, years = {}, {}, set()
    for r in rd:
        if r["GeographyType"] != "Council Areas":
            continue
        key = GROUPS.get(r["Crime Or Offence"])
        if not key:
            continue
        try:
            v = float(r["Value"])
        except ValueError:
            continue
        code, yr = r["GeographyCode"], r["DateCode"]
        names[code] = r["GeographyName"]
        years.add(yr)
        cell = data.setdefault(code, {}).setdefault(yr, {}).setdefault(key, {})
        # "Ratio" rows hold the published rate per 10,000 population.
        cell["rate_per_10k" if r["Measurement"] == "Ratio" else "count"] = v
    return names, sorted(years)[-YEARS:], data


def main():
    text = get(CSV_URL).decode("utf-8-sig")
    names, years, data = build_rows(text)
    if len(names) != 32:
        sys.exit("expected 32 council areas, got %d" % len(names))
    out = {
        "source": "Scottish Government, Recorded Crimes and Offences (Police Scotland returns)",
        "source_url": "https://data.gov.scot/dataset/recorded_crimes_and_offences",
        "licence": "Open Government Licence v3.0",
        "definition": "Group 2 sexual crimes as recorded by Police Scotland. Not the same as the "
                      "police.uk category 'Violence and sexual offences'. Do not add or rank against it.",
        "period": "financial years (April to March)",
        "years": years,
        "fetched": now_iso(),
        "areas": {c: {"name": names[c], "years": {y: data[c].get(y, {}) for y in years}}
                  for c in sorted(names)},
    }
    write_json(os.path.join(DATA_DIR, "scotland_la.json"), out)

    params = {"where": "LAD24CD LIKE 'S%'", "outFields": "LAD24CD,LAD24NM", "outSR": "4326",
              "maxAllowableOffset": "0.002", "geometryPrecision": "4", "f": "geojson"}
    gj = json.loads(get(LAD_URL + "?" + urllib.parse.urlencode(params)))
    if len(gj["features"]) != 32:
        sys.exit("expected 32 boundary features, got %d" % len(gj["features"]))
    for f in gj["features"]:
        p = f["properties"]
        f["properties"] = {"code": p["LAD24CD"], "name": p["LAD24NM"]}
    missing = {f["properties"]["code"] for f in gj["features"]} ^ set(names)
    if missing:
        sys.exit("boundary/data code mismatch: %s" % sorted(missing))
    gj["metadata"] = {"source": "ONS Open Geography Portal: Local Authority Districts (December 2024) UK BUC",
                      "licence": "Open Government Licence v3.0", "fetched": now_iso()}
    write_json(os.path.join(DATA_DIR, "scotland_la.geojson"), gj)
    print("Scotland: %d areas, years %s..%s" % (len(names), years[0], years[-1]))


if __name__ == "__main__":
    main()

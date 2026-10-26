#!/usr/bin/env python3
"""Build population denominators for the hexagon grid (England and Wales).

Sources (Open Government Licence v3.0):
  * ONS Census 2021, TS001 usual residents, by LSOA (via Nomis).
  * ONS Census 2021, WD002 workday population, by LSOA (Nomis bulk download).
    Workday population counts people where they work (if employed) or live
    (if not), so city centres are not shown as nearly empty.
  * ONS population-weighted LSOA centroids (December 2021), Open Geography Portal.
  * Police force area polygons (data/pfa.geojson) to total people per force.

Each LSOA is placed in the hexagon that contains its centroid, so only area
totals are kept. Writes data/population.json. Census day is 21 March 2021: the
denominators are older than the crime counts and are not updated yearly.

Scotland and Northern Ireland are not included (different census bodies and
geographies); no rate is shown there.
"""
import csv
import io
import json
import os
import sys
import urllib.parse
import urllib.request
import zipfile
from collections import defaultdict

sys.path.insert(0, os.path.dirname(__file__))
from usoda_common import DATA_DIR, HEX_R, K, hex_of, now_iso, read_json, write_json  # noqa: E402

CENTROIDS = ("https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services/"
             "LSOA_PopCentroids_EW_2021_V4/FeatureServer/0/query")
NOMIS_TS001 = ("https://www.nomisweb.co.uk/api/v01/dataset/NM_2021_1.data.csv?date=latest&geography=TYPE151"
               "&c2021_restype_3=0&measures=20100&select=geography_code,obs_value")
WD002_URL = "https://www.nomisweb.co.uk/output/census/2021/wd002.zip"
MIN_LSOAS = 35000


def get(url, timeout=180):
    req = urllib.request.Request(url, headers={"User-Agent": "USODA-population"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception:
            if attempt == 3:
                raise


def fetch_centroids():
    out, off = {}, 0
    while True:
        q = {"where": "1=1", "outFields": "LSOA21CD", "outSR": "4326", "returnGeometry": "true",
             "resultOffset": off, "resultRecordCount": 2000, "orderByFields": "LSOA21CD", "f": "json"}
        d = json.loads(get(CENTROIDS + "?" + urllib.parse.urlencode(q)))
        feats = d.get("features", [])
        for f in feats:
            out[f["attributes"]["LSOA21CD"]] = (f["geometry"]["x"], f["geometry"]["y"])
        if len(feats) < 2000:
            return out
        off += 2000


def fetch_residents():
    out, off = {}, 0
    while True:
        text = get(NOMIS_TS001 + "&recordoffset=%d" % off).decode("utf-8-sig")
        rows = list(csv.DictReader(io.StringIO(text)))
        for r in rows:
            out[r["GEOGRAPHY_CODE"]] = int(float(r["OBS_VALUE"]))
        if len(rows) < 25000:
            return out
        off += 25000


def fetch_workday():
    z = zipfile.ZipFile(io.BytesIO(get(WD002_URL, 300)))
    out = defaultdict(int)
    with z.open("WD002_lsoa.csv") as f:
        for r in csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig")):
            out[r["Lower layer Super Output Areas Code"]] += int(float(r["Count"]))
    return out


def point_in_ring(lon, lat, ring):
    inside, j = False, len(ring) - 1
    for i in range(len(ring)):
        xi, yi, xj, yj = ring[i][0], ring[i][1], ring[j][0], ring[j][1]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def force_polygons(gj):
    out = []
    for f in gj["features"]:
        g = f["geometry"]
        polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        for poly in polys:
            xs = [p[0] for p in poly[0]]
            ys = [p[1] for p in poly[0]]
            out.append((f["properties"]["slug"], (min(xs), min(ys), max(xs), max(ys)), poly))
    return out


def force_of(lon, lat, polys):
    for slug, (x0, y0, x1, y1), poly in polys:
        if x0 <= lon <= x1 and y0 <= lat <= y1 and point_in_ring(lon, lat, poly[0]) \
                and not any(point_in_ring(lon, lat, h) for h in poly[1:]):
            return slug
    return None


def build(centroids, residents, workday, polys):
    cells = defaultdict(lambda: [0, 0])
    forces = defaultdict(lambda: [0, 0])
    unplaced = 0
    for code, (lon, lat) in centroids.items():
        res, wd = residents.get(code, 0), workday.get(code, 0)
        q, r = hex_of(lat, lon)
        cells[(q, r)][0] += res
        cells[(q, r)][1] += wd
        slug = force_of(lon, lat, polys)
        if slug:
            forces[slug][0] += res
            forces[slug][1] += wd
        else:
            unplaced += 1
    return cells, forces, unplaced


def main():
    centroids = fetch_centroids()
    residents = fetch_residents()
    workday = fetch_workday()
    common = set(centroids) & set(residents) & set(workday)
    if len(common) < MIN_LSOAS:
        sys.exit("only %d LSOAs matched across the three sources" % len(common))
    centroids = {c: centroids[c] for c in common}
    pfa = read_json(os.path.join(DATA_DIR, "pfa.geojson"))
    cells, forces, unplaced = build(centroids, residents, workday, force_polygons(pfa))
    write_json(os.path.join(DATA_DIR, "population.json"), {
        "source": "ONS Census 2021 (usual residents TS001; workday population WD002) with ONS "
                  "population-weighted LSOA centroids (Dec 2021)",
        "licence": "Open Government Licence v3.0",
        "census_day": "2021-03-21", "coverage": "England and Wales only",
        "hex": {"R": HEX_R, "K": K}, "lsoas": len(common),
        "lsoas_not_in_a_force_polygon": unplaced,
        "totals": {"residents": sum(v[0] for v in cells.values()), "workday": sum(v[1] for v in cells.values())},
        "forces": {s: {"residents": v[0], "workday": v[1]} for s, v in sorted(forces.items())},
        "cells": [[q, r, v[0], v[1]] for (q, r), v in sorted(cells.items())],
        "generated": now_iso(),
    })
    print("population: %d LSOAs, %d cells, %d forces, %d unplaced" % (len(common), len(cells), len(forces), unplaced))


if __name__ == "__main__":
    main()

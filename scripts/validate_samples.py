#!/usr/bin/env python3
"""Spot-check the archive pipeline against the live data.police.uk API.

For a few fixed sample rectangles and one month, count "Violence and sexual
offences" rows with coordinates inside the rectangle in the archive ZIP, and
compare with the API's crimes-street/violent-crime?poly=... result for the
same polygon and month. They come from the same source so should match
closely; a material difference indicates an ingest or filtering bug (or an
archive newer than the API's cache).

Usage: validate_samples.py ARCHIVE.zip YYYY-MM
Only aggregate counts are printed; no record-level detail is retained.
Exit code 1 if any sample differs by more than 2% (and more than 3 records).
"""
import csv
import io
import json
import re
import sys
import time
import urllib.request
import zipfile

CATEGORY = "Violence and sexual offences"
SAMPLES = {  # name: (south, west, north, east) in degrees; ~1 km boxes
    "Birmingham centre": (52.475, -1.910, 52.485, -1.890),
    "Leeds centre": (53.795, -1.555, 53.803, -1.538),
    "Cardiff centre": (51.476, -3.190, 51.485, -3.170),
    "Belfast centre": (54.592, -5.940, 54.600, -5.920),
}


def archive_count(zf, month, box):
    s, w, n, e = box
    total = 0
    for name in zf.namelist():
        if not re.match(rf"^{month}/{month}-.+-street\.csv$", name):
            continue
        with zf.open(name) as raw:
            text = io.TextIOWrapper(raw, encoding="utf-8", errors="replace", newline="")
            cols = next(csv.reader([text.readline()]))
            i_lon, i_lat, i_t = cols.index("Longitude"), cols.index("Latitude"), cols.index("Crime type")
            for line in text:
                if CATEGORY not in line:
                    continue
                f = next(csv.reader([line]))
                if f[i_t] != CATEGORY:
                    continue
                try:
                    lon, lat = float(f[i_lon]), float(f[i_lat])
                except ValueError:
                    continue
                if s <= lat <= n and w <= lon <= e:
                    total += 1
    return total


def api_count(month, box):
    s, w, n, e = box
    poly = f"{s},{w}:{s},{e}:{n},{e}:{n},{w}"
    url = f"https://data.police.uk/api/crimes-street/violent-crime?poly={poly}&date={month}"
    for i in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "USODA-validate"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return len(json.load(r))
        except Exception as ex:  # noqa: BLE001
            err = ex
            time.sleep(2 ** i)
    raise err


def main():
    zpath, month = sys.argv[1], sys.argv[2]
    zf = zipfile.ZipFile(zpath)
    bad = 0
    for name, box in SAMPLES.items():
        a, b = archive_count(zf, month, box), api_count(month, box)
        diff = abs(a - b)
        ok = diff <= 3 or diff <= 0.02 * max(a, b, 1)
        bad += not ok
        print(f"{name:20s} archive={a:5d} api={b:5d} diff={diff:3d} {'OK' if ok else 'MISMATCH'}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Ingest one data.police.uk monthly archive ZIP into per-month aggregates.

Usage:
  ingest_archive.py ARCHIVE.zip --from YYYY-MM --to YYYY-MM [--force]

For every *-street.csv for a month in [from, to] this keeps only rows whose
`Crime type` is "Violence and sexual offences" (API slug `violent-crime`) and
that carry a coordinate, bins them into the hex grid and writes
work/monthly/YYYY-MM.json:

  { "month": "2025-01",
    "forces": { "<slug>": {"rows": all street rows, "vso": category rows,
                           "vso_located": category rows with coordinates} },
    "cells": { "q,r": count } }

Individual rows, crime IDs, street names and LSOA names are NEVER retained.
Months already ingested are skipped unless --force is given (so newer
archives take precedence only when explicitly requested).
"""
import argparse
import csv
import io
import os
import re
import sys
import zipfile
from collections import defaultdict

sys.path.insert(0, os.path.dirname(__file__))
from usoda_common import CATEGORY, MONTHLY_DIR, hex_of, now_iso, write_json  # noqa: E402

MEMBER_RE = re.compile(r"^(\d{4}-\d{2})/\1-(.+)-street\.csv$")


def process_member(zf, name, month, slug, cells, forces):
    rows = vso = located = 0
    with zf.open(name) as raw:
        text = io.TextIOWrapper(raw, encoding="utf-8", errors="replace", newline="")
        header = text.readline()
        cols = next(csv.reader([header]))
        i_lon, i_lat, i_type = cols.index("Longitude"), cols.index("Latitude"), cols.index("Crime type")
        for line in text:
            rows += 1
            if CATEGORY not in line:
                continue
            f = next(csv.reader([line]))
            if len(f) <= i_type or f[i_type] != CATEGORY:
                continue
            vso += 1
            try:
                lon, lat = float(f[i_lon]), float(f[i_lat])
            except ValueError:
                continue
            if not (49.5 <= lat <= 61.0 and -8.7 <= lon <= 2.0):
                continue  # outside UK bounds: ignore rather than guess
            located += 1
            q, r = hex_of(lat, lon)
            cells[f"{q},{r}"] += 1
    forces[slug] = {"rows": rows, "vso": vso, "vso_located": located}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("zip")
    ap.add_argument("--from", dest="start", required=True)
    ap.add_argument("--to", dest="end", required=True)
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()

    zf = zipfile.ZipFile(a.zip)
    by_month = defaultdict(list)
    for n in zf.namelist():
        m = MEMBER_RE.match(n)
        if m and a.start <= m.group(1) <= a.end:
            by_month[m.group(1)].append((n, m.group(2)))

    for month in sorted(by_month):
        out = os.path.join(MONTHLY_DIR, f"{month}.json")
        if os.path.exists(out) and not a.force:
            print(f"{month}: already ingested, skipping")
            continue
        cells, forces = defaultdict(int), {}
        for name, slug in sorted(by_month[month]):
            process_member(zf, name, month, slug, cells, forces)
        write_json(out, {"month": month, "forces": forces, "cells": cells,
                         "source_archive": os.path.basename(a.zip), "ingested_at": now_iso()})
        tot = sum(f["vso"] for f in forces.values())
        print(f"{month}: {len(forces)} forces, {tot} category records, {len(cells)} cells", flush=True)


if __name__ == "__main__":
    main()

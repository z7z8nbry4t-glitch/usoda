#!/usr/bin/env python3
"""Build the static, pre-aggregated assets served to the browser.

Reads work/monthly/*.json (written by ingest_archive.py) and writes:

  data/meta.json            window, hex grid definition, quality metrics, notes
  data/windows/<id>.json    summed cell counts for 10y / 5y / 3y / 12m windows
  data/months/YYYY-MM.json  per-month cell counts (for the month selector)
  data/force_totals.json    per-force monthly category counts (absent month = gap)

The rolling window ends at the newest ingested month and is up to 120 months
long; if fewer months are available the maximum available span is used and
meta.json says so. Cells with fewer than MIN_CELL records are suppressed
(their total is reported in meta.json, never plotted).
"""
import glob
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(__file__))
from usoda_common import (CATEGORY, DATA_DIR, HEX_R, K, MIN_CELL, MONTHLY_DIR,  # noqa: E402
                          WINDOW_MONTHS, month_range, now_iso, read_json, write_json)

WINDOWS = {"10y": 120, "5y": 60, "3y": 36, "12m": 12}


def load_months():
    out = {}
    for p in sorted(glob.glob(os.path.join(MONTHLY_DIR, "*.json"))):
        d = read_json(p)
        out[d["month"]] = d
    return out


def sum_cells(months, ids):
    tot = defaultdict(int)
    for m in ids:
        for k, v in months[m]["cells"].items():
            tot[k] += v
    return tot


def publish_cells(tot):
    cells, suppressed, kept = [], 0, 0
    for k, v in tot.items():
        if v < MIN_CELL:
            suppressed += v
            continue
        q, r = k.split(",")
        cells.append([int(q), int(r), v])
        kept += v
    cells.sort()
    return cells, suppressed, kept


def main():
    months = load_months()
    if not months:
        sys.exit("No monthly aggregates found. Run ingest_archive.py first.")
    latest = max(months)
    want = month_range(latest, WINDOW_MONTHS)
    present = [m for m in want if m in months]
    missing = [m for m in want if m not in months]
    span_note = ("Full rolling 120-month window." if not missing else
                 f"Maximum available span: {len(present)} of {WINDOW_MONTHS} months "
                 f"({present[0]} to {present[-1]}).")

    # ---- windows --------------------------------------------------------
    win_meta = {}
    for wid, n in WINDOWS.items():
        ids = [m for m in month_range(latest, n) if m in months]
        if not ids:
            continue
        tot = sum_cells(months, ids)
        cells, suppressed, kept = publish_cells(tot)
        write_json(os.path.join(DATA_DIR, "windows", f"{wid}.json"),
                   {"id": wid, "from": ids[0], "to": ids[-1], "months": len(ids), "cells": cells})
        win_meta[wid] = {"from": ids[0], "to": ids[-1], "months": len(ids), "requested_months": n,
                         "cells": len(cells), "records_plotted": kept, "records_suppressed": suppressed}

    # ---- per-month files -----------------------------------------------
    month_index = []
    for m in present:
        cells, suppressed, kept = publish_cells(months[m]["cells"])
        write_json(os.path.join(DATA_DIR, "months", f"{m}.json"),
                   {"month": m, "cells": cells})
        month_index.append({"month": m, "records": sum(f["vso"] for f in months[m]["forces"].values()),
                            "cells": len(cells), "suppressed": suppressed})

    # ---- quality metrics ---------------------------------------------
    all_forces = sorted({s for m in present for s in months[m]["forces"]})
    expected = len(all_forces) * len(present)
    seen = sum(1 for m in present for s in all_forces
               if months[m]["forces"].get(s, {}).get("rows", 0) > 0)
    gaps = {}
    for s in all_forces:
        miss = [m for m in present if months[m]["forces"].get(s, {}).get("rows", 0) == 0]
        if miss:
            gaps[s] = {"missing_months": len(miss), "first": miss[0], "last": miss[-1]}
    recs = sum(months[m]["forces"][s]["vso"] for m in present for s in months[m]["forces"])
    located = sum(months[m]["forces"][s]["vso_located"] for m in present for s in months[m]["forces"])
    dups = sum(months[m]["forces"][s].get("dups_dropped", 0) for m in present for s in months[m]["forces"])
    scot_ex = sum(months[m]["forces"][s].get("btp_scotland_excluded", 0) for m in present for s in months[m]["forces"])
    prev = read_json(os.path.join(DATA_DIR, "meta.json"), {}) or {}

    meta = {
        "project": "UK Sexual Offence Density Atlas (USODA)",
        "category": CATEGORY,
        "category_slug": "violent-crime",
        "generated_at": now_iso(),
        "last_successful_ingest": now_iso(),
        "latest_month": latest,
        "window": {"from": present[0], "to": present[-1], "months": len(present),
                   "target_months": WINDOW_MONTHS, "note": span_note,
                   "missing_months_in_window": missing},
        "windows": win_meta,
        "hex": {"R": HEX_R, "K": K, "orientation": "pointy-top", "min_cell": MIN_CELL},
        "months_available": month_index,
        "quality": {
            "records_in_window": recs,
            "records_with_location": located,
            "duplicate_rows_dropped": dups,
            "btp_scotland_records_excluded": scot_ex,
            "location_share_pct": round(100.0 * located / recs, 2) if recs else None,
            "forces_seen": len(all_forces),
            "force_month_coverage_pct": round(100.0 * seen / expected, 2) if expected else None,
            "force_gaps": gaps,
        },
        "sources": [
            {"name": "data.police.uk street-level crime", "url": "https://data.police.uk/",
             "licence": "Open Government Licence v3.0"},
        ],
        "previous_latest_month": prev.get("latest_month"),
    }
    write_json(os.path.join(DATA_DIR, "meta.json"), meta, indent=1)
    # monthly[slug][month] = category records; a month is ABSENT when the force
    # published no street rows that month (a data gap, not a true zero).
    monthly = {s: {m: months[m]["forces"][s]["vso"] for m in present
                   if months[m]["forces"].get(s, {}).get("rows", 0) > 0} for s in all_forces}
    write_json(os.path.join(DATA_DIR, "force_totals.json"),
               {"latest": latest, "monthly": monthly})
    print(f"window {present[0]}..{present[-1]} ({len(present)} months); {recs} records; "
          f"coverage {meta['quality']['force_month_coverage_pct']}%")


if __name__ == "__main__":
    main()

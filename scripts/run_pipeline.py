#!/usr/bin/env python3
"""Stateless end-to-end build: download archives -> ingest -> aggregate.

Because each data.police.uk archive holds a rolling 36 months, a 120-month
window needs four archives: the newest month L, and L-36, L-72, L-108.
Archives are downloaded one at a time, ingested, and deleted, so peak disk use
is one archive (~2 GB) plus small aggregates. Nothing record-level is kept.

Usage:
  run_pipeline.py [--latest YYYY-MM] [--keep-archives] [--force]
If --latest is omitted the newest month from the availability endpoint is used.
If an older archive cannot be fetched, the build continues with the maximum
available span and meta.json records the shortfall.
"""
import argparse
import json
import os
import subprocess
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(__file__))
from usoda_common import ARCHIVE_DIR, WINDOW_MONTHS, month_range  # noqa: E402

ARCHIVE_URL = "https://data.police.uk/data/archive/{ym}.zip"
HERE = os.path.dirname(os.path.abspath(__file__))


def plan(latest, window=WINDOW_MONTHS):
    """Return [(archive_month, from_month, to_month), ...], newest first."""
    wanted = month_range(latest, window)
    start = wanted[0]
    out, a = [], latest
    while a >= start:
        span = month_range(a, 36)
        lo = max(span[0], start)
        out.append((a, lo, a))
        a = month_range(a, 37)[0]  # step back 36 months
    return out


def newest_upstream():
    req = urllib.request.Request("https://data.police.uk/api/crimes-street-dates",
                                 headers={"User-Agent": "USODA-pipeline"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return max(d["date"] for d in json.load(r))


def download(ym, dest):
    cmd = ["curl", "-sSfL", "--retry", "5", "--retry-delay", "10", "-C", "-", "-o", dest,
           ARCHIVE_URL.format(ym=ym)]
    return subprocess.run(cmd).returncode == 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--latest")
    ap.add_argument("--keep-archives", action="store_true")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    latest = a.latest or newest_upstream()
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    steps = plan(latest)
    print("plan:", steps, flush=True)
    for arch, lo, hi in steps:
        dest = os.path.join(ARCHIVE_DIR, f"{arch}.zip")
        if not os.path.exists(dest) and not download(arch, dest):
            print(f"WARNING: archive {arch} unavailable; continuing with a shorter span", file=sys.stderr)
            continue
        cmd = [sys.executable, os.path.join(HERE, "ingest_archive.py"), dest, "--from", lo, "--to", hi]
        if a.force:
            cmd.append("--force")
        subprocess.run(cmd, check=True)
        if not a.keep_archives:
            os.remove(dest)
    subprocess.run([sys.executable, os.path.join(HERE, "build_aggregates.py")], check=True)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Poll data.police.uk for the newest published month.

Exit code 0 always (so CI never fails on a transient outage); the result is
written to stdout as JSON and, when running in GitHub Actions, to
$GITHUB_OUTPUT as `new_month=true|false` and `latest=YYYY-MM`.
Only a month that is NEWER than data/meta.json's `latest_month` triggers
re-ingestion.
"""
import json
import os
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(__file__))
from usoda_common import DATA_DIR, read_json  # noqa: E402

URL = "https://data.police.uk/api/crimes-street-dates"


def fetch(retries=4):
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(URL, headers={"User-Agent": "USODA-poller (open-source)"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(2 ** i)
    raise last


def main():
    meta = read_json(os.path.join(DATA_DIR, "meta.json"), {}) or {}
    have = meta.get("latest_month")
    try:
        dates = fetch()
        upstream = max(d["date"] for d in dates)
        ok = True
    except Exception as e:  # noqa: BLE001
        print(f"poll failed: {e}", file=sys.stderr)
        upstream, ok = None, False
    new = bool(ok and (have is None or upstream > have))
    result = {"ok": ok, "upstream_latest": upstream, "ingested_latest": have, "new_month": new}
    print(json.dumps(result))
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a") as f:
            f.write(f"new_month={'true' if new else 'false'}\n")
            f.write(f"latest={upstream or ''}\n")


if __name__ == "__main__":
    main()

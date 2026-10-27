#!/usr/bin/env python3
"""Daily monitor: is the live atlas showing the newest month police.uk has published?

Exit code 1 (so the scheduled workflow fails and GitHub sends its alert) when:
  * the live site or its data files cannot be read, or
  * the newest month on police.uk is ahead of the month the atlas shows.
The partnership layer's dates are printed for information only (the Home Office publishes quarterly).

Usage: check_freshness.py [https://usoda.alphatedigital.co.uk]
"""
import json
import sys
import urllib.request


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "USODA-monitor"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def month_lag(atlas_latest, upstream_latest):
    """Whole months the atlas is behind police.uk (0 when level, negative if ahead)."""
    ay, am = map(int, atlas_latest.split("-"))
    uy, um = map(int, upstream_latest.split("-"))
    return (uy - ay) * 12 + (um - am)


def main():
    base = (sys.argv[1] if len(sys.argv) > 1 else "https://usoda.alphatedigital.co.uk").rstrip("/")
    problems = []
    try:
        meta = json.loads(get(base + "/data/meta.json"))
        csp = json.loads(get(base + "/data/csp.json"))
    except Exception as e:
        print("FAIL live site unreadable:", e)
        sys.exit(1)
    try:
        upstream = max(d["date"] for d in json.loads(get("https://data.police.uk/api/crimes-street-dates")))
        lag = month_lag(meta["latest_month"], upstream)
        print("atlas %s, police.uk %s, behind by %d month(s)" % (meta["latest_month"], upstream, lag))
        if lag > 0:
            problems.append("atlas is %d month(s) behind police.uk (%s vs %s): run the Update data workflow" % (lag, meta["latest_month"], upstream))
    except Exception as e:
        print("WARN could not read police.uk (not counted as a failure):", e)
    print("partnership layer: latest quarter %s, Home Office file updated %s, next update %s" % (csp["latest_quarter"], csp.get("updated"), csp.get("next_update")))
    if problems:
        print("FAIL " + "; ".join(problems))
        sys.exit(1)
    print("OK")


if __name__ == "__main__":
    main()

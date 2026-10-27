#!/usr/bin/env python3
"""Smoke-test a deployed USODA site. Usage: python3 scripts/verify_deploy.py https://usoda.pages.dev

Checks the pages and data files load, the data is fresh and consistent, and
(on Cloudflare) that the API proxy works. Exit code 1 if a required check fails.
"""
import json
import sys
import urllib.request


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "USODA-verify"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.status, dict(r.headers), r.read()


def main():
    base = (sys.argv[1] if len(sys.argv) > 1 else "https://usoda.pages.dev").rstrip("/")
    bad = 0

    def check(name, ok, detail="", required=True):
        nonlocal bad
        print(("PASS " if ok else ("FAIL " if required else "WARN ")) + name + (": " + detail if detail else ""))
        if not ok and required:
            bad += 1

    try:
        st, h, body = get(base + "/")
        check("home page", st == 200 and b"USODA" in body or b"Sexual Offence Density Atlas" in body)
        # HTTP header names are case-insensitive; Cloudflare sends them in lower case.
        check("CSP header", "content-security-policy" in {k.lower() for k in h}, required=False)
    except Exception as e:
        check("home page", False, str(e))
    try:
        st, h, body = get(base + "/atlas.html")
        check("map page", st == 200 and b'id="map"' in body)
    except Exception as e:
        check("map page", False, str(e))
    meta = None
    try:
        meta = json.loads(get(base + "/data/meta.json")[2])
        check("data/meta.json", True, "latest month " + meta.get("latest_month", "?"))
    except Exception as e:
        check("data/meta.json", False, str(e))
    for p in ("data/windows/10y.json", "data/pfa.geojson", "data/force_totals.json",
              "data/scotland_la.json", "data/scotland_la.geojson", "data/csp.json", "data/csp.geojson", "data/crossref.json",
              "data/population.json", "data/annotations.json", "data/national_context.json", "assets/app.js", "assets/style.css"):
        try:
            check(p, get(base + "/" + p)[0] == 200)
        except Exception as e:
            check(p, False, str(e))
    try:
        sc = json.loads(get(base + "/data/scotland_la.json")[2])
        check("Scotland: 32 council areas", len(sc["areas"]) == 32)
    except Exception as e:
        check("Scotland data", False, str(e))
    try:
        cs = json.loads(get(base + "/data/csp.json")[2])
        check("Partnerships: at least 280 areas", len(cs["areas"]) >= 280, "%d areas, latest %s" % (len(cs["areas"]), cs["latest_quarter"]))
    except Exception as e:
        check("Partnership data", False, str(e))
    try:
        dates = json.loads(get(base + "/api/crimes-street-dates")[2])
        newest = max(d["date"] for d in dates)
        check("API proxy (Cloudflare only)", True, "upstream newest " + newest, required=False)
        if meta:
            check("atlas up to date", meta.get("latest_month") == newest,
                  "atlas %s vs upstream %s" % (meta.get("latest_month"), newest), required=False)
    except Exception as e:
        check("API proxy (Cloudflare only)", False, str(e), required=False)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()

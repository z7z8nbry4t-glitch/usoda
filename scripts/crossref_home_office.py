#!/usr/bin/env python3
"""Cross-reference police.uk force totals with Home Office police recorded crime.

Source: Home Office, "Police recorded crime open data tables, Police Force Area"
(England and Wales, quarterly, Open Government Licence v3.0), found through the
gov.uk statistical data sets page. The police.uk category "Violence and sexual
offences" corresponds to Home Office offence groups "Violence against the person"
plus "Sexual offences", so the two are compared like for like per force and
financial year (April to March).

Writes data/crossref.json:
  * per force and financial year: Home Office violence, sexual offences, rape,
    the matching police.uk total, months present, ratio and an agreement band;
  * national totals and the sexual-offence share by force.

This file is for validation and context only. It never feeds the hexagons, and
Home Office counts are never added to police.uk counts.

Usage: crossref_home_office.py [--ods PATH]   (downloads the newest file if omitted)
"""
import argparse
import json
import os
import re
import sys
import tempfile
import urllib.request
import zipfile
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(__file__))
from usoda_common import DATA_DIR, now_iso, read_json, write_json  # noqa: E402

T = "{urn:oasis:names:tc:opendocument:xmlns:table:1.0}"
O = "{urn:oasis:names:tc:opendocument:xmlns:office:1.0}"
X = "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}"
PAGE_API = "https://www.gov.uk/api/content/government/statistical-data-sets/police-recorded-crime-and-outcomes-open-data-tables"
FILE_RE = re.compile(r"https://assets\.publishing\.service\.gov\.uk/media/[0-9a-f]+/prc-pfa-mar2013-onwards-tables-\d+\.ods")
SLUG_OVERRIDES = {"Metropolitan Police": "metropolitan", "London, City of": "city-of-london",
                  "British Transport Police": "btp"}
GROUPS = {"Violence against the person": "violence", "Sexual offences": "sexual"}
FIRST_FY = 2017        # first financial year compared (2017/18)
BAND_AGREE, BAND_MINOR = 0.05, 0.10


def slugify(name):
    return SLUG_OVERRIDES.get(name) or name.lower().replace(",", "").replace("&", "and").replace(" ", "-")


def find_ods_url():
    req = urllib.request.Request(PAGE_API, headers={"User-Agent": "USODA-crossref"})
    with urllib.request.urlopen(req, timeout=60) as r:
        text = r.read().decode("utf-8", "replace")
    urls = sorted(set(FILE_RE.findall(text.replace("\\/", "/"))))
    if not urls:
        raise RuntimeError("Home Office PFA file link not found on the gov.uk page")
    return urls[-1]


def iter_rows(path):
    """Stream (sheet_name, [cell strings]) from an ODS file without loading it all."""
    with zipfile.ZipFile(path) as z, z.open("content.xml") as f:
        sheet = None
        for ev, el in ET.iterparse(f, events=("start", "end")):
            if ev == "start" and el.tag == T + "table":
                sheet = el.get(T + "name")
            elif ev == "end" and el.tag == T + "table-row":
                row = []
                for c in el:
                    if c.tag not in (T + "table-cell", T + "covered-table-cell"):
                        continue
                    rep = min(int(c.get(T + "number-columns-repeated", "1")), 50)
                    vt = c.get(O + "value-type")
                    if vt in ("float", "percentage", "currency"):
                        v = c.get(O + "value")
                    elif vt == "string":
                        v = "".join("".join(p.itertext()) for p in c.findall(X + "p"))
                    else:
                        v = ""
                    row.extend([v] * rep)
                el.clear()
                yield sheet, row


def read_home_office(path):
    """Return {(slug, fy_start): {"violence", "sexual", "rape", "quarters": set}}."""
    out, cols = {}, None
    for sheet, row in iter_rows(path):
        if not re.match(r"^\d{4}_\d{2}$", sheet or ""):
            continue
        if row and row[0] == "Financial Year":
            cols = {n: i for i, n in enumerate(row)}
            continue
        if not cols or len(row) < len(cols):
            continue
        g = GROUPS.get(row[cols["Offence Group"]])
        if not g:
            continue
        fy = int(row[cols["Financial Year"]][:4])
        key = (slugify(row[cols["Force Name"]]), fy)
        d = out.setdefault(key, {"violence": 0, "sexual": 0, "rape": 0, "quarters": set()})
        n = int(float(row[cols["Number of Offences"]] or 0))
        d[g] += n
        d["quarters"].add(int(float(row[cols["Financial Quarter"]])))
        if row[cols["Offence Subgroup"]] == "Rape offences":
            d["rape"] += n
    return out


def fy_months(fy):
    return ["%d-%02d" % (fy, m) for m in range(4, 13)] + ["%d-%02d" % (fy + 1, m) for m in range(1, 4)]


def band(ratio, months_present):
    if months_present == 0:
        return "no_street_data"
    if months_present < 12:
        return "incomplete_months"
    d = abs(ratio - 1)
    return "agree" if d <= BAND_AGREE else ("minor_difference" if d <= BAND_MINOR else "differs")


def compare(ho, monthly):
    """Pure function: Home Office dict + police.uk monthly totals -> comparison rows."""
    rows = {}
    for (slug, fy), d in sorted(ho.items()):
        if fy < FIRST_FY or d["quarters"] != {1, 2, 3, 4}:
            continue
        ms = fy_months(fy)
        series = monthly.get(slug, {})
        present = [m for m in ms if m in series]
        pu = sum(series[m] for m in present)
        total = d["violence"] + d["sexual"]
        ratio = pu / total if total else 0.0
        rows.setdefault(slug, {})["%d/%02d" % (fy, (fy + 1) % 100)] = {
            "home_office_violence": d["violence"], "home_office_sexual": d["sexual"],
            "home_office_rape": d["rape"], "home_office_total": total,
            "sexual_share_pct": round(100.0 * d["sexual"] / total, 1) if total else None,
            "police_uk_total": pu, "police_uk_months": len(present),
            "ratio": round(ratio, 3), "agreement": band(ratio, len(present)),
        }
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ods")
    a = ap.parse_args()
    path, tmp = a.ods, None
    if not path:
        url = find_ods_url()
        tmp = tempfile.NamedTemporaryFile(suffix=".ods", delete=False)
        tmp.close()
        req = urllib.request.Request(url, headers={"User-Agent": "USODA-crossref"})
        with urllib.request.urlopen(req, timeout=300) as r, open(tmp.name, "wb") as f:
            while True:
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                f.write(chunk)
        path, src_url = tmp.name, url
    else:
        src_url = None
    try:
        ho = read_home_office(path)
    finally:
        if tmp:
            os.unlink(tmp.name)
    ft = read_json(os.path.join(DATA_DIR, "force_totals.json"))
    rows = compare(ho, ft["monthly"])
    counts = {}
    for fys in rows.values():
        for r in fys.values():
            counts[r["agreement"]] = counts.get(r["agreement"], 0) + 1
    write_json(os.path.join(DATA_DIR, "crossref.json"), {
        "source": "Home Office, Police recorded crime open data tables (Police Force Area), England and Wales",
        "source_url": src_url or "https://www.gov.uk/government/statistical-data-sets/police-recorded-crime-and-outcomes-open-data-tables",
        "licence": "Open Government Licence v3.0",
        "method": "police.uk 'Violence and sexual offences' compared with Home Office 'Violence against the person' "
                  "plus 'Sexual offences', per force and complete financial year (Apr to Mar). Validation only.",
        "bands": {"agree": "within 5%", "minor_difference": "within 10%", "differs": "more than 10%",
                  "incomplete_months": "fewer than 12 police.uk months", "no_street_data": "no police.uk rows"},
        "generated": now_iso(), "band_counts": counts, "forces": rows,
    }, indent=1)
    print("cross-reference:", counts)


if __name__ == "__main__":
    main()

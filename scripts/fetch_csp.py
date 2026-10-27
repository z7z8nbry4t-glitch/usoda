#!/usr/bin/env python3
"""Build the Home Office sexual-offences layer by community safety partnership (CSP).

Sources (all Open Government Licence v3.0):
  * Home Office, "Police recorded crime open data tables, Community Safety
    Partnership" (England and Wales, quarterly, found through the gov.uk
    statistical data sets page). Offence group "Sexual offences", with the
    subgroup "Rape offences" counted separately. British Transport Police is not
    in this table.
  * ONS Open Geography Portal, Local Authority Districts (December 2024) UK BUC,
    for the shapes. Contains OS data (c) Crown copyright and database right.
  * ONS Census 2021, TS001 usual residents by local authority (via Nomis), for
    rates per 1,000 residents.

A CSP is a local authority area, or a few of them together. Each CSP is matched
to its local authorities by name; the shape is those authorities' shapes joined.

Writes data/csp.json (counts by quarter) and data/csp.geojson (shapes).

This layer counts the Home Office offence group "Sexual offences" only. It is a
different measure from the police.uk category "Violence and sexual offences"
used by the hexagons, and from the Scottish Government's sexual crimes. It must
never be added to, ranked against or blended with either.

Usage: fetch_csp.py [--ods PATH]   (downloads the newest file if omitted)
"""
import argparse
import csv
import io
import json
import os
import re
import sys
import tempfile
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(__file__))
from crossref_home_office import iter_rows  # noqa: E402
from usoda_common import DATA_DIR, now_iso, write_json  # noqa: E402

PAGE_API = "https://www.gov.uk/api/content/government/statistical-data-sets/police-recorded-crime-and-outcomes-open-data-tables"
FILE_RE = re.compile(r"https://assets\.publishing\.service\.gov\.uk/media/[0-9a-f]+/"
                     r"prc-csp-mar(\d{2})-([a-z]{3})(\d{2})-tables-\d+\.ods")
MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
LAD_URL = ("https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services/"
           "Local_Authority_Districts_December_2024_Boundaries_UK_BUC/FeatureServer/0/query")
POP_URL = ("https://www.nomisweb.co.uk/api/v01/dataset/NM_2021_1.data.csv?date=latest&geography=TYPE424"
           "&c2021_restype_3=0&measures=20100&select=geography_code,geography_name,obs_value")
GROUP = "Sexual offences"
RAPE = "Rape offences"
MIN_AREAS = 280          # a build with fewer matched areas is refused
MAX_UNMATCHED = 8        # names with no shape that the build tolerates (listed in the data)


def get(url, timeout=180):
    req = urllib.request.Request(url, headers={"User-Agent": "USODA-csp"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def find_ods_url():
    text = get(PAGE_API, 60).decode("utf-8", "replace").replace("\\/", "/")
    best = None
    for m in FILE_RE.finditer(text):
        end = (int(m.group(3)), MONTHS.get(m.group(2), 0))
        if best is None or end > best[0]:
            best = (end, m.group(0))
    if not best:
        raise RuntimeError("Home Office CSP file link not found on the gov.uk page")
    return best[1]


# ---------------------------------------------------------------- reading the Home Office file
def quarter_key(fy, q):
    """('2025/26', '2') -> (2025, 2), so quarters sort in time order."""
    return int(fy[:4]), int(float(q))


def quarter_label(key):
    y, q = key
    return "%d/%02d Q%d" % (y, (y + 1) % 100, q)


def aggregate(rows):
    """rows: iterable of (sheet, [cells]) as from iter_rows.

    Returns (updated, next_update, {(force, csp): {quarter_key: [sexual, rape]}}).
    A quarter is present for a CSP once the table has any row for it, even if the
    counts are zero.
    """
    out, cols, updated, nxt = {}, None, None, None
    for sheet, row in rows:
        if sheet in ("Cover_sheet", "Notes"):
            if row and row[0].startswith("Updated:"):
                updated = row[0].split(":", 1)[1].strip()
            elif row and row[0].startswith("Next scheduled update:"):
                nxt = row[0].split(":", 1)[1].strip()
            continue
        if not re.match(r"^\d{4}_\d{2}$", sheet or ""):
            continue
        if row and row[0] == "Financial Year":
            cols = {n: i for i, n in enumerate(row) if n}
            continue
        if not cols or len(row) < len(cols) or not row[cols["Financial Year"]]:
            continue
        key = (row[cols["Police Force"]], row[cols["CSP Name"]])
        qk = quarter_key(row[cols["Financial Year"]], row[cols["Financial Quarter"]])
        cell = out.setdefault(key, {}).setdefault(qk, [0, 0])
        if row[cols["Offence Group"]] == GROUP:
            n = int(float(row[cols["Offence Count"]] or 0))
            cell[0] += n
            if row[cols["Offence Subgroup"]] == RAPE:
                cell[1] += n
    return updated, nxt, out


# ---------------------------------------------------------------- matching CSP names to local authorities
# Home Office CSP names that are not one current local authority. Each entry is
# (force, area name, [CSP names], [ONS local authority names]); the counts of the CSPs
# are added and the shape is the named authorities joined. Add an entry only where the
# grouping is known from the authorities' own names; the build prints every other
# name it cannot place, and those are left off the map and listed in the data.
GROUPS = [
    ("Cumbria", "Cumberland", ["Allerdale", "Carlisle", "Copeland"], ["Cumberland"]),
    ("Cumbria", "Westmorland and Furness", ["Barrow-in-Furness", "Eden", "South Lakeland"], ["Westmorland and Furness"]),
    ("Northamptonshire", "North Northamptonshire", ["Corby", "East Northamptonshire", "Kettering", "Wellingborough"], ["North Northamptonshire"]),
    ("Northamptonshire", "West Northamptonshire", ["Daventry and South Northamptonshire", "Northampton"], ["West Northamptonshire"]),
    ("Thames Valley", "Buckinghamshire", ["Aylesbury Vale", "Chiltern", "South Bucks", "Wycombe"], ["Buckinghamshire"]),
    ("Suffolk", "East Suffolk", ["Suffolk Coastal", "Waveney"], ["East Suffolk"]),
    ("Suffolk", "Western Suffolk", ["Western Suffolk"], ["Babergh", "Mid Suffolk", "West Suffolk"]),
    ("Dorset", "Bournemouth, Christchurch and Poole", ["Bournemouth", "Poole"], ["Bournemouth, Christchurch and Poole"]),
    ("Devon and Cornwall", "East and Mid Devon", ["East and Mid Devon"], ["East Devon", "Mid Devon"]),
    ("Devon and Cornwall", "Northern Devon", ["Northern Devon"], ["North Devon", "Torridge"]),
    ("Devon and Cornwall", "South Devon and Dartmoor", ["South Devon and Dartmoor"], ["South Hams", "Teignbridge", "West Devon"]),
    ("South Wales", "Cwm Taf", ["Cwm Taf"], ["Merthyr Tydfil", "Rhondda Cynon Taf"]),
    ("London, City of", "City of London", ["London, City of"], ["City of London"]),
]
# No area on the ground: not drawn.
NO_AREA = {"Manchester Airport"}


def norm(name):
    s = name.lower().replace("'", "").replace("\u2019", "").replace("&", " and ")
    s = re.sub(r",\s*(city|county) of\b", "", s)
    s = re.sub(r"^(city|county) of (?!london\b)", "", s)
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def match_lads(csp_name, lads):
    """lads: {normalised name: code}. Return a list of LAD codes, or None.

    Tries the whole name, then a split into authority names joined by
    'and' (for example 'Hackney and City of London' or 'Cornwall and Isles of Scilly').
    """
    n = norm(csp_name)
    if n in lads:
        return [lads[n]]
    words, memo = n.split(), {}

    def seg(i):
        if i == len(words):
            return []
        if i in memo:
            return memo[i]
        res = None
        for j in range(len(words), i, -1):
            phrase = " ".join(words[i:j])
            if phrase in lads:
                rest = seg(j)
                if rest is not None:
                    res = [lads[phrase]] + rest
                    break
        if res is None and words[i] == "and":
            res = seg(i + 1)
        memo[i] = res
        return res

    got = seg(0)
    return got if got else None


# ---------------------------------------------------------------- shapes and people
def read_populations(text):
    """Nomis CSV text -> {LAD code: usual residents}."""
    out = {}
    for r in csv.DictReader(io.StringIO(text)):
        try:
            out[r["GEOGRAPHY_CODE"]] = int(float(r["OBS_VALUE"]))
        except (KeyError, ValueError):
            pass
    return out


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower().replace("&", "and")).strip("-")


def build(agg, lad_gj, pops):
    """Pure: Home Office counts + LAD shapes + populations.

    Returns (quarters, areas, features, unmatched, unassigned, shared) where
    unassigned is {quarter label: offences} for the 'Unassigned <force>' rows,
    which have no place and are never drawn.
    """
    names = {}
    for f in lad_gj["features"]:
        p = f["properties"]
        names[norm(p["LAD24NM"])] = p["LAD24CD"]
    shapes = {f["properties"]["LAD24CD"]: f["geometry"] for f in lad_gj["features"]}
    quarters = sorted({q for v in agg.values() for q in v})
    grouped = {}
    for force, label, members, lad_names in GROUPS:
        grouped.update({(force, m): (label, lad_names) for m in members})
    # collect (force, area label) -> [csp names, lad names, summed counts]
    work, unmatched, unassigned = {}, [], {}
    for (force, csp), qs in sorted(agg.items()):
        if csp.startswith("Unassigned "):
            for q, c in qs.items():
                unassigned[quarter_label(q)] = unassigned.get(quarter_label(q), 0) + c[0]
            continue
        if csp in NO_AREA:
            continue
        if (force, csp) in grouped:
            label, lad_names = grouped[(force, csp)]
            codes = [names.get(norm(n)) for n in lad_names]
            codes = codes if all(codes) else None
        else:
            label, codes = csp, match_lads(csp, names)
        if not codes:
            unmatched.append("%s (%s)" % (csp, force))
            continue
        w = work.setdefault((force, label), {"codes": codes, "members": [], "q": {}})
        w["members"].append(csp)
        for q, c in qs.items():
            t = w["q"].setdefault(q, [0, 0])
            t[0] += c[0]
            t[1] += c[1]
    areas, feats, used = {}, [], {}
    for (force, label), w in sorted(work.items()):
        k = slug(label)
        if k in areas:
            k = k + "-" + slug(force)
        pop = sum(pops.get(c, 0) for c in w["codes"])
        for c in w["codes"]:
            used.setdefault(c, []).append(k)
        areas[k] = {
            "name": label, "force": force, "lads": w["codes"], "population": pop,
            "sexual": [w["q"][q][0] if q in w["q"] else None for q in quarters],
            "rape": [w["q"][q][1] if q in w["q"] else None for q in quarters],
        }
        polys = []
        for c in w["codes"]:
            g = shapes.get(c)
            if not g:
                continue
            polys.extend([g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"])
        feats.append({"type": "Feature", "properties": {"key": k, "name": label},
                      "geometry": {"type": "MultiPolygon", "coordinates": polys}})
    shared = {c: ks for c, ks in used.items() if len(ks) > 1}
    return quarters, areas, feats, unmatched, unassigned, shared


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ods")
    a = ap.parse_args()
    url = None
    path = a.ods
    if not path:
        url = find_ods_url()
        path = os.path.join(tempfile.mkdtemp(), "csp.ods")
        with open(path, "wb") as f:
            f.write(get(url, 600))
    updated, nxt, agg = aggregate(iter_rows(path))
    params = {"where": "LAD24CD LIKE 'E%' OR LAD24CD LIKE 'W%'", "outFields": "LAD24CD,LAD24NM",
              "outSR": "4326", "maxAllowableOffset": "0.002", "geometryPrecision": "4", "f": "geojson"}
    lad_gj = json.loads(get(LAD_URL + "?" + urllib.parse.urlencode(params)))
    pops = read_populations(get(POP_URL).decode("utf-8-sig"))
    quarters, areas, feats, unmatched, unassigned, shared = build(agg, lad_gj, pops)
    if len(areas) < MIN_AREAS or len(unmatched) > MAX_UNMATCHED:
        sys.exit("CSP match failed: %d areas, %d unmatched: %s" % (len(areas), len(unmatched), unmatched))
    if shared:
        sys.exit("local authorities used by more than one CSP: %s" % shared)
    out = {
        "source": "Home Office, Police recorded crime open data tables, Community Safety Partnership (England and Wales)",
        "source_url": "https://www.gov.uk/government/statistical-data-sets/police-recorded-crime-and-outcomes-open-data-tables",
        "file": url,
        "licence": "Open Government Licence v3.0",
        "definition": "Home Office offence group 'Sexual offences'. Not the same as the police.uk category "
                      "'Violence and sexual offences' or the Scottish definition. Do not add or rank against either. "
                      "British Transport Police is not in this table.",
        "population_source": "ONS Census 2021, usual residents (TS001), by local authority",
        "updated": updated, "next_update": nxt, "fetched": now_iso(),
        "quarters": [quarter_label(q) for q in quarters],
        "latest_quarter": quarter_label(quarters[-1]),
        "not_drawn": unmatched,
        "unassigned_by_quarter": unassigned,
        "areas": areas,
    }
    write_json(os.path.join(DATA_DIR, "csp.json"), out)
    gj = {"type": "FeatureCollection", "features": feats,
          "metadata": {"source": "ONS Open Geography Portal: Local Authority Districts (December 2024) UK BUC",
                       "licence": "Open Government Licence v3.0. Contains OS data (c) Crown copyright and database right.",
                       "fetched": now_iso()}}
    write_json(os.path.join(DATA_DIR, "csp.geojson"), gj)
    print("CSP: %d areas, quarters %s to %s, %d unmatched %s" %
          (len(areas), out["quarters"][0], out["quarters"][-1], len(unmatched), unmatched))


if __name__ == "__main__":
    main()

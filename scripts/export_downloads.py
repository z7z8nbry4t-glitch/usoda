#!/usr/bin/env python3
"""Write plain CSV copies of the aggregates the atlas already publishes, to data/downloads/.

Nothing new is derived here: each file is a flat copy of a published JSON file, so a reader can open
it in a spreadsheet. Sources are kept in separate files and are never added together.
"""
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from usoda_common import DATA_DIR, hex_center  # noqa: E402

OUT = os.path.join(DATA_DIR, "downloads")


def load(name):
    with open(os.path.join(DATA_DIR, name), encoding="utf-8") as f:
        return json.load(f)


def write(name, header, rows):
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, name), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    return len(rows)


def force_monthly(ft):
    return [(slug, m, n) for slug, mm in sorted(ft["monthly"].items()) for m, n in sorted(mm.items())]


def force_annual(xref):
    rows = []
    for slug, years in sorted(xref["forces"].items()):
        for fy, d in sorted(years.items()):
            rows.append((slug, fy, d.get("home_office_sexual"), d.get("home_office_rape"), d.get("home_office_violence"),
                         d.get("police_uk_total"), d.get("police_uk_months")))
    return rows


def csp_quarterly(csp):
    rows = []
    for key, a in sorted(csp["areas"].items()):
        for i, q in enumerate(csp["quarters"]):
            if a["sexual"][i] is not None:
                rows.append((a["name"], a["force"], q, a["sexual"][i], a["rape"][i], a["population"]))
    return rows


def scotland_annual(sc):
    rows = []
    for code, a in sorted(sc["areas"].items()):
        for y, d in sorted(a["years"].items()):
            g = lambda k, f="count": (d.get(k) or {}).get(f)
            rows.append((code, a["name"], y, g("sexual"), g("rape"), g("assault"), g("sexual", "rate_per_10k")))
    return rows


def cells(window):
    rows = []
    for q, r, n in window["cells"]:
        lat, lon = hex_center(q, r)
        rows.append((q, r, round(lat, 4), round(lon, 4), n))
    return rows


README = """USODA downloads
================

Flat copies of the aggregates published on the atlas. Each file is one source and one definition.
Never add files together or rank one against another: their definitions, areas and periods differ.

force_monthly_police_uk.csv    police.uk records of Violence and sexual offences by force and month
                                (England, Wales, Northern Ireland, British Transport Police). A month
                                missing for a force means the force published nothing.
force_annual_home_office.csv   Home Office sexual offences, rape and violence by force and financial year,
                                with the police.uk total for comparison (England and Wales).
partnership_quarterly_home_office.csv
                                Home Office Sexual offences by community safety partnership and quarter
                                (England and Wales, no British Transport Police), with Census 2021 residents.
scotland_annual.csv            Scottish Government recorded sexual crimes by council area and financial year.
cells_10y.csv                  Hexagon cells of about 4 km (axial q, r), centre point, and the count of
                                police.uk records in the rolling ten-year window. Cells under 3 are absent.

Licence: Open Government Licence v3.0 (see DATA-LICENCE.md). Processed by USODA; not the publishers' own
statistics. Reports are not prevalence: most sexual offences are never reported.
"""


def main():
    n = {}
    n["force_monthly"] = write("force_monthly_police_uk.csv", ["force", "month", "records"], force_monthly(load("force_totals.json")))
    n["force_annual"] = write("force_annual_home_office.csv", ["force", "financial_year", "sexual_offences", "rape", "violence_against_the_person", "police_uk_records", "police_uk_months"], force_annual(load("crossref.json")))
    n["csp"] = write("partnership_quarterly_home_office.csv", ["partnership", "force", "quarter", "sexual_offences", "rape", "residents_census_2021"], csp_quarterly(load("csp.json")))
    n["scotland"] = write("scotland_annual.csv", ["code", "council_area", "financial_year", "sexual_crimes", "rape_and_attempted_rape", "sexual_assault", "rate_per_10000"], scotland_annual(load("scotland_la.json")))
    n["cells"] = write("cells_10y.csv", ["q", "r", "latitude", "longitude", "records"], cells(load(os.path.join("windows", "10y.json"))))
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "README.txt"), "w", encoding="utf-8") as f:
        f.write(README)
    print("downloads:", n)


if __name__ == "__main__":
    main()

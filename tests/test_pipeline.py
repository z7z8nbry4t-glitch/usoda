"""Offline tests for the USODA pipeline using a tiny synthetic archive.

Run:  python3 -m unittest discover -s tests -v
No network access and no real police data are used.
"""
import importlib
import json
import os
import random
import sys
import tempfile
import unittest
import zipfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

HEADER = ("Crime ID,Month,Reported by,Falls within,Longitude,Latitude,Location,"
          "LSOA code,LSOA name,Crime type,Last outcome category,Context\n")
VSO = "Violence and sexual offences"


def row(month, lon, lat, ctype, street="On or near Secret Street"):
    return f"abc123,{month},F,F,{lon},{lat},{street},E01000001,Somewhere 001A,{ctype},,\n"


def make_zip(path, months, forces):
    rnd = random.Random(1)
    with zipfile.ZipFile(path, "w") as z:
        for m in months:
            for slug, gap_months in forces.items():
                if m in gap_months:
                    continue
                body = HEADER
                for _ in range(40):  # 40 category rows clustered in one place
                    body += row(m, -1.9000 + rnd.uniform(-0.001, 0.001),
                                52.4800 + rnd.uniform(-0.001, 0.001), VSO)
                body += row(m, -1.9, 52.48, "Burglary")           # other category: must be ignored
                body += row(m, "", "", VSO)                         # no coordinate: counted, not plotted
                body += row(m, 10.0, 80.0, VSO)                     # outside UK bounds: ignored
                body += row(m, -4.0, 56.0, VSO)                     # 1 isolated record: below MIN_CELL
                z.writestr(f"{m}/{m}-{slug}-street.csv", body)


class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        os.environ["USODA_WORK"] = os.path.join(cls.tmp, "work")
        import usoda_common
        importlib.reload(usoda_common)
        cls.common = usoda_common
        # redirect published output into the temp dir
        usoda_common.DATA_DIR = os.path.join(cls.tmp, "data")
        import ingest_archive, build_aggregates
        importlib.reload(ingest_archive)
        importlib.reload(build_aggregates)
        build_aggregates.DATA_DIR = usoda_common.DATA_DIR
        cls.ing, cls.build = ingest_archive, build_aggregates
        cls.months = usoda_common.month_range("2024-06", 14)
        cls.gap = set(cls.months[4:9])  # force "beta" misses 5 months
        zpath = os.path.join(cls.tmp, "a.zip")
        make_zip(zpath, cls.months, {"alpha": set(), "beta": cls.gap})
        sys.argv = ["ingest", zpath, "--from", cls.months[0], "--to", cls.months[-1]]
        cls.ing.main()
        cls.build.main()
        cls.out = usoda_common.DATA_DIR

    def load(self, rel):
        with open(os.path.join(self.out, rel)) as f:
            return json.load(f)

    def test_hex_roundtrip(self):
        c = self.common
        for lat, lng in [(52.48, -1.9), (51.5, -0.12), (57.1, -2.1), (54.6, -5.9)]:
            q, r = c.hex_of(lat, lng)
            clat, clng = c.hex_center(q, r)
            self.assertEqual(c.hex_of(clat, clng), (q, r))
            # point is within one circumradius of its hex centre (lat/lng-scaled space)
            d = ((lat - clat) ** 2 + ((lng - clng) * c.K) ** 2) ** 0.5
            self.assertLessEqual(d, c.HEX_R + 1e-9)

    def test_month_range(self):
        c = self.common
        self.assertEqual(c.month_range("2024-02", 3), ["2023-12", "2024-01", "2024-02"])

    def test_category_filter_and_counts(self):
        m = self.load("meta.json")
        # per month: alpha 40+1+1(no coord)... category rows = 40 + no-coord + outside + isolated = 43
        with open(os.path.join(self.common.MONTHLY_DIR, f"{self.months[0]}.json")) as fh:
            monthly = json.load(fh)
        self.assertEqual(monthly["forces"]["alpha"]["vso"], 43)
        self.assertEqual(monthly["forces"]["alpha"]["vso_located"], 41)  # excludes no-coord + outside-UK
        self.assertEqual(sum(monthly["cells"].values()), 82)  # alpha+beta located rows

    def test_small_cells_suppressed(self):
        w = self.load("windows/12m.json")
        counts = [c[2] for c in w["cells"]]
        self.assertTrue(all(n >= self.common.MIN_CELL for n in counts))
        # the isolated Scottish-border point has 2 records/month (< MIN_CELL): hidden but reported
        first = self.load("meta.json")["months_available"][0]
        self.assertGreater(first["suppressed"], 0)
        month_cells = self.load(f"months/{first['month']}.json")["cells"]
        self.assertTrue(all(c[2] >= self.common.MIN_CELL for c in month_cells))

    def test_window_falls_back_to_available_span(self):
        m = self.load("meta.json")
        self.assertEqual(m["window"]["months"], 14)
        self.assertIn("Maximum available span", m["window"]["note"])
        self.assertEqual(m["windows"]["10y"]["months"], 14)

    def test_gap_detection(self):
        m = self.load("meta.json")
        gaps = m["quality"]["force_gaps"]
        self.assertEqual(gaps["beta"]["missing_months"], 5)
        self.assertNotIn("alpha", gaps)
        ft = self.load("force_totals.json")["monthly"]
        self.assertEqual(len(ft["beta"]), 9)          # gap months absent, not zero
        self.assertEqual(len(ft["alpha"]), 14)
        self.assertAlmostEqual(m["quality"]["force_month_coverage_pct"], 100 * (28 - 5) / 28, places=2)

    def test_no_record_level_or_street_detail_published(self):
        for root, _, files in os.walk(self.out):
            for fn in files:
                with open(os.path.join(root, fn)) as fh:
                    text = fh.read()
                self.assertNotIn("Secret Street", text)
                self.assertNotIn("abc123", text)
                self.assertNotIn("Somewhere 001A", text)

    def test_run_pipeline_plan(self):
        import run_pipeline
        self.assertEqual(run_pipeline.plan("2026-08"),
                         [("2026-08", "2023-09", "2026-08"), ("2023-08", "2020-09", "2023-08"),
                          ("2020-08", "2017-09", "2020-08"), ("2017-08", "2016-09", "2017-08")])



class ScotlandParserTest(unittest.TestCase):
    def test_build_rows(self):
        import fetch_scotland as fs
        hdr = "GeographyCode,GeographyName,GeographyType,DateCode,Measurement,Units,Value,Crime Or Offence\n"
        rows = ("S12000049,Glasgow City,Council Areas,2024/2025,Count,Crimes Or Offences Recorded,100,All Group 2: Sexual crimes\n"
                "S12000049,Glasgow City,Council Areas,2024/2025,Ratio,Crimes Or Offences Recorded,12,All Group 2: Sexual crimes\n"
                "S92000003,Scotland,Country,2024/2025,Count,Crimes Or Offences Recorded,999,All Group 2: Sexual crimes\n"
                "S12000049,Glasgow City,Council Areas,2024/2025,Count,Crimes Or Offences Recorded,5,All Crimes\n")
        names, years, data = fs.build_rows(hdr + rows)
        self.assertEqual(names, {"S12000049": "Glasgow City"})
        self.assertEqual(years, ["2024/2025"])
        self.assertEqual(data["S12000049"]["2024/2025"]["sexual"], {"count": 100.0, "rate_per_10k": 12.0})


class CrossReferenceTests(unittest.TestCase):
    def setUp(self):
        import ingest_archive
        self.ing = ingest_archive
        self.ing._SCOT = [((-5.0, 55.0, -3.0, 57.0), [[-5, 55], [-3, 55], [-3, 57], [-5, 57], [-5, 55]])]

    def _member(self, rows):
        import io as _io
        buf = _io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("2025-01/2025-01-x-street.csv", HEADER + "".join(rows))
        return zipfile.ZipFile(buf)

    def test_exact_duplicates_counted_once(self):
        def r(cid, lon):
            return f"{cid},2025-01,F,F,{lon},52.48,St,E01,N,{VSO},,\n"
        zf = self._member([r("A", -1.9), r("A", -1.9), r("A", -1.8), r("B", -1.9)])
        cells, forces = {}, {}
        from collections import defaultdict
        cells = defaultdict(int)
        self.ing.process_member(zf, "2025-01/2025-01-x-street.csv", "2025-01", "x", cells, forces)
        # second "A" at identical coordinates is dropped; "A" at a different place and "B" are kept
        self.assertEqual(forces["x"]["vso"], 3)
        self.assertEqual(forces["x"]["dups_dropped"], 1)

    def test_northern_ireland_ids_not_deduplicated(self):
        rows = [f"X,2025-01,F,F,-5.9,54.6,St,N01,N,{VSO},,\n"] * 3
        zf = self._member(rows)
        from collections import defaultdict
        forces = {}
        self.ing.process_member(zf, "2025-01/2025-01-x-street.csv", "2025-01", "northern-ireland", defaultdict(int), forces)
        self.assertEqual(forces["northern-ireland"]["vso"], 3)

    def test_btp_points_in_scotland_are_excluded(self):
        rows = [f"{i},2025-01,F,F,-4.0,56.0,Stn,S01,N,{VSO},,\n" for i in range(3)] + \
               [f"9,2025-01,F,F,-1.9,52.48,Stn,E01,N,{VSO},,\n"]
        zf = self._member(rows)
        from collections import defaultdict
        forces, cells = {}, defaultdict(int)
        self.ing.process_member(zf, "2025-01/2025-01-x-street.csv", "2025-01", "btp", cells, forces)
        self.assertEqual(forces["btp"]["btp_scotland_excluded"], 3)
        self.assertEqual(forces["btp"]["vso_located"], 1)
        self.assertEqual(sum(cells.values()), 1)

    def test_compare_bands(self):
        import crossref_home_office as cr
        ho = {("a", 2024): {"violence": 900, "sexual": 100, "rape": 30, "quarters": {1, 2, 3, 4}},
              ("b", 2024): {"violence": 900, "sexual": 100, "rape": 30, "quarters": {1, 2, 3, 4}},
              ("c", 2024): {"violence": 900, "sexual": 100, "rape": 30, "quarters": {1, 2, 3, 4}},
              ("d", 2024): {"violence": 900, "sexual": 100, "rape": 30, "quarters": {1, 2}}}
        ms = cr.fy_months(2024)
        monthly = {"a": {m: 1000 / 12 for m in ms}, "b": {m: 800 / 12 for m in ms}, "c": {m: 10 for m in ms[:6]}}
        out = cr.compare(ho, monthly)
        self.assertEqual(out["a"]["2024/25"]["agreement"], "agree")
        self.assertEqual(out["b"]["2024/25"]["agreement"], "differs")
        self.assertEqual(out["c"]["2024/25"]["agreement"], "incomplete_months")
        self.assertNotIn("d", out)  # part-year Home Office data is not compared
        self.assertEqual(out["a"]["2024/25"]["sexual_share_pct"], 10.0)
        self.assertEqual(cr.band(0.0, 0), "no_street_data")


class PopulationTests(unittest.TestCase):
    def test_build_places_people_in_hexes_and_forces(self):
        import fetch_population as fp
        from usoda_common import hex_of
        sq = [[[-1.0, 52.0], [-0.5, 52.0], [-0.5, 52.5], [-1.0, 52.5], [-1.0, 52.0]]]
        polys = [("box", (-1.0, 52.0, -0.5, 52.5), sq)]
        cents = {"A": (-0.75, 52.25), "B": (-0.76, 52.26), "C": (5.0, 60.0)}
        cells, forces, unplaced = fp.build(cents, {"A": 100, "B": 50, "C": 7}, {"A": 300, "B": 20, "C": 1}, polys)
        self.assertEqual(forces["box"], [150, 320])
        self.assertEqual(unplaced, 1)
        self.assertEqual(sum(v[0] for v in cells.values()), 157)
        q, r = hex_of(52.25, -0.75)
        self.assertGreaterEqual(cells[(q, r)][0], 100)

    def test_point_in_ring_with_hole(self):
        import fetch_population as fp
        outer = [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]
        hole = [[4, 4], [6, 4], [6, 6], [4, 6], [4, 4]]
        polys = [("p", (0, 0, 10, 10), [outer, hole])]
        self.assertEqual(fp.force_of(1, 1, polys), "p")
        self.assertIsNone(fp.force_of(5, 5, polys))



class CspTests(unittest.TestCase):
    """Home Office community safety partnership layer (scripts/fetch_csp.py)."""

    def setUp(self):
        import fetch_csp
        self.f = fetch_csp
        sq = lambda x: {"type": "Polygon", "coordinates": [[[x, 0], [x + 1, 0], [x + 1, 1], [x, 1], [x, 0]]]}
        self.gj = {"features": [
            {"properties": {"LAD24CD": "E1", "LAD24NM": "Kings Lynn and West Norfolk"}, "geometry": sq(0)},
            {"properties": {"LAD24CD": "E2", "LAD24NM": "Cumberland"}, "geometry": sq(2)},
            {"properties": {"LAD24CD": "E3", "LAD24NM": "Hackney"}, "geometry": sq(4)},
            {"properties": {"LAD24CD": "E4", "LAD24NM": "Cornwall"}, "geometry": sq(6)},
            {"properties": {"LAD24CD": "E5", "LAD24NM": "Isles of Scilly"}, "geometry": sq(8)}]}
        self.pops = {"E1": 1000, "E2": 2000, "E3": 3000, "E4": 4000, "E5": 50}

    def test_norm_ignores_apostrophes_and_case(self):
        self.assertEqual(self.f.norm("King\u2019s Lynn & West Norfolk"), "kings lynn and west norfolk")

    def test_match_splits_joined_names(self):
        lads = {"cornwall": "E4", "isles of scilly": "E5"}
        self.assertEqual(self.f.match_lads("Cornwall and Isles of Scilly", lads), ["E4", "E5"])
        self.assertIsNone(self.f.match_lads("Nowhere", lads))

    def test_aggregate_counts_only_sexual_offences_and_splits_rape(self):
        hdr = ["Financial Year", "Financial Quarter", "Police Force", "CSP Name", "Offence Description",
               "Offence Group", "Offence Subgroup", "Offence Code", "Offence Count"]
        mk = lambda g, sg, n: ["2025/26", "1", "F", "Hackney", "x", g, sg, "1", str(n)]
        rows = [("Cover_sheet", ["Updated: 22 October 2026"]), ("Cover_sheet", ["Next scheduled update: January 2027"]),
                ("2025_26", hdr), ("2025_26", mk("Sexual offences", "Rape offences", 4)),
                ("2025_26", mk("Sexual offences", "Other sexual offences", 6)),
                ("2025_26", mk("Violence against the person", "Stalking", 99)),
                ("2025_26", [""] * 9)]
        updated, nxt, agg = self.f.aggregate(rows)
        self.assertEqual((updated, nxt), ("22 October 2026", "January 2027"))
        self.assertEqual(agg[("F", "Hackney")][(2025, 1)], [10, 4])

    def test_build_groups_sums_and_never_draws_unassigned(self):
        q = (2025, 1)
        agg = {("Cumbria", "Allerdale"): {q: [5, 1]}, ("Cumbria", "Carlisle"): {q: [7, 2]},
               ("Cumbria", "Unassigned Cumbria"): {q: [50, 9]}, ("Met", "Hackney"): {q: [20, 3]},
               ("Met", "Mystery"): {q: [1, 0]}, ("Greater Manchester", "Manchester Airport"): {q: [2, 0]}}
        quarters, areas, feats, unmatched, unassigned, shared = self.f.build(agg, self.gj, self.pops)
        self.assertEqual(areas["cumberland"]["sexual"], [12]) 
        self.assertEqual(areas["cumberland"]["rape"], [3])
        self.assertEqual(areas["hackney"]["population"], 3000)
        self.assertEqual(unmatched, ["Mystery (Met)"])
        self.assertEqual(unassigned, {"2025/26 Q1": 50})
        self.assertEqual(sorted(a["name"] for a in areas.values()), ["Cumberland", "Hackney"])
        self.assertEqual(len(feats), 2)
        self.assertFalse(shared)

    def test_quarter_labels_sort_in_time_order(self):
        ks = sorted([self.f.quarter_key("2025/26", "2"), self.f.quarter_key("2024/25", "4"), self.f.quarter_key("2025/26", "1")])
        self.assertEqual([self.f.quarter_label(k) for k in ks], ["2024/25 Q4", "2025/26 Q1", "2025/26 Q2"])


class MonitorAndDownloadTests(unittest.TestCase):
    def test_month_lag(self):
        import check_freshness
        self.assertEqual(check_freshness.month_lag("2026-08", "2026-08"), 0)
        self.assertEqual(check_freshness.month_lag("2026-08", "2026-09"), 1)
        self.assertEqual(check_freshness.month_lag("2025-12", "2026-02"), 2)
        self.assertEqual(check_freshness.month_lag("2026-09", "2026-08"), -1)

    def test_every_force_page_slug_has_monthly_data_and_a_name(self):
        ft = json.load(open(os.path.join(ROOT, "data", "force_totals.json")))["monthly"]
        pfa = {f["properties"]["slug"] for f in json.load(open(os.path.join(ROOT, "data", "pfa.geojson")))["features"]}
        self.assertTrue(pfa <= set(ft), pfa - set(ft))
        html = open(os.path.join(ROOT, "force.html")).read()
        self.assertIn("assets/charts.js", html)
        self.assertNotIn("<script>", html)  # no inline script, to keep the content security policy

    def test_downloads_match_published_json_and_hide_small_cells(self):
        import csv
        d = os.path.join(ROOT, "data", "downloads")
        rows = list(csv.DictReader(open(os.path.join(d, "cells_10y.csv"))))
        win = json.load(open(os.path.join(ROOT, "data", "windows", "10y.json")))
        self.assertEqual(len(rows), len(win["cells"]))
        self.assertEqual(sum(int(r["records"]) for r in rows), sum(c[2] for c in win["cells"]))
        self.assertGreaterEqual(min(int(r["records"]) for r in rows), 3)
        csp = list(csv.DictReader(open(os.path.join(d, "partnership_quarterly_home_office.csv"))))
        self.assertTrue(all(r["partnership"] and r["quarter"] for r in csp))
        self.assertTrue(os.path.exists(os.path.join(d, "README.txt")))


class PublishedDataConsistencyTests(unittest.TestCase):
    """Checks the committed data against official totals read from source pages."""

    def test_scotland_matches_published_2024_25(self):
        d = json.load(open(os.path.join(ROOT, "data", "scotland_la.json")))
        tot = lambda k: sum(a["years"]["2024/2025"][k]["count"] for a in d["areas"].values())
        self.assertEqual((tot("sexual"), tot("rape"), tot("assault")), (14892, 2897, 5124))

    def test_scotland_keeps_full_history_for_trend_charts(self):
        d = json.load(open(os.path.join(ROOT, "data", "scotland_la.json")))
        self.assertEqual(d["years"][0], "1996/1997")
        self.assertGreaterEqual(len(d["years"]), 29)

    def test_home_office_sexual_total_matches_ons_2025_26(self):
        d = json.load(open(os.path.join(ROOT, "data", "crossref.json")))
        total = sum(f["2025/26"]["home_office_sexual"] for f in d["forces"].values() if "2025/26" in f)
        self.assertLess(abs(total - 217567) / 217567, 0.01)  # ONS bulletin: 217,567

    def test_csp_layer_reconciles_to_home_office_force_totals(self):
        d = json.load(open(os.path.join(ROOT, "data", "csp.json")))
        idx = [i for i, q in enumerate(d["quarters"]) if q.startswith("2025/26")]
        self.assertEqual(len(idx), 4)
        drawn = sum(a["sexual"][i] or 0 for a in d["areas"].values() for i in idx)
        unassigned = sum(v for k, v in d["unassigned_by_quarter"].items() if k.startswith("2025/26"))
        # the table has no British Transport Police and five partnership names are not drawn, so the
        # drawn total sits a little under the force-table total of 217,271 and must not exceed it
        self.assertLessEqual(drawn + unassigned, 217271)
        self.assertGreater((drawn + unassigned) / 217271, 0.95)
        self.assertLessEqual(len(d["not_drawn"]), 8)
        self.assertEqual(len(d["areas"]), len(json.load(open(os.path.join(ROOT, "data", "csp.geojson")))["features"]))

    def test_northern_ireland_police_uk_agrees_with_psni_within_5_percent(self):
        d = json.load(open(os.path.join(ROOT, "data", "ni_validation.json")))
        self.assertEqual(d["psni_violence_plus_sexual"], d["psni"]["violence_against_the_person"] + d["psni"]["sexual_offences"])
        self.assertEqual(d["police_uk_months"], 12)
        self.assertLess(abs(d["ratio"] - 1), 0.05)
        f = json.load(open(os.path.join(ROOT, "data", "force_totals.json")))["monthly"]["northern-ireland"]
        self.assertEqual(sum(v for m, v in f.items() if "2025-04" <= m <= "2026-03"), d["police_uk_violence_and_sexual"])

    def test_force_rates_have_denominators(self):
        pop = json.load(open(os.path.join(ROOT, "data", "population.json")))["forces"]
        x = json.load(open(os.path.join(ROOT, "data", "crossref.json")))["forces"]
        rates = [x[s]["2025/26"]["home_office_sexual"] / pop[s]["residents"] * 1000
                 for s in x if s in pop and "2025/26" in x[s] and s != "city-of-london"]
        self.assertGreater(len(rates), 35)
        self.assertTrue(all(1 < r < 8 for r in rates), sorted(rates)[-3:])

    def test_context_items_have_sources(self):
        d = json.load(open(os.path.join(ROOT, "data", "national_context.json")))
        for it in d["items"]:
            self.assertTrue(it["url"].startswith("https://"))
            self.assertTrue(it["text"])


if __name__ == "__main__":
    unittest.main()

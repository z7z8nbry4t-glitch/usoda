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


if __name__ == "__main__":
    unittest.main()

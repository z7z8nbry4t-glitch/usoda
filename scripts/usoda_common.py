"""Shared helpers for the USODA pipeline.

Hex grid definition (documented in README, mirrored in assets/app.js):
  * Work in a locally scaled plane: x = longitude * K, y = latitude,
    where K = cos(54.5 deg) (a single constant for the whole UK).
  * Pointy-top hexagons, circumradius HEX_R (in y/latitude degrees).
  * Cells are addressed by axial coordinates (q, r).
The grid is an analysis device only. It is deliberately coarse (~2 km) so
that it never resolves individual streets or addresses.
"""
import json
import math
import os
from datetime import datetime, timezone

K = math.cos(math.radians(54.5))
HEX_R = 0.02  # degrees of latitude (~2.2 km circumradius)
SQRT3 = math.sqrt(3.0)

CATEGORY = "Violence and sexual offences"
WINDOW_MONTHS = 120  # rolling ten-year window
MIN_CELL = 3         # cells with fewer reported records than this are suppressed

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(ROOT, "data")
WORK_DIR = os.environ.get("USODA_WORK", os.path.join(ROOT, "work"))
MONTHLY_DIR = os.path.join(WORK_DIR, "monthly")
ARCHIVE_DIR = os.path.join(WORK_DIR, "archives")


def hex_of(lat, lng):
    """Return axial (q, r) of the hex containing the point."""
    x = lng * K
    y = lat
    qf = (SQRT3 / 3.0 * x - y / 3.0) / HEX_R
    rf = (2.0 / 3.0 * y) / HEX_R
    return cube_round(qf, rf)


def cube_round(qf, rf):
    sf = -qf - rf
    q, r, s = round(qf), round(rf), round(sf)
    dq, dr, ds = abs(q - qf), abs(r - rf), abs(s - sf)
    if dq > dr and dq > ds:
        q = -r - s
    elif dr > ds:
        r = -q - s
    return int(q), int(r)


def hex_center(q, r):
    """Return (lat, lng) of the hex centre."""
    x = HEX_R * SQRT3 * (q + r / 2.0)
    y = HEX_R * 1.5 * r
    return y, x / K


def hex_polygon(q, r):
    """Return list of (lng, lat) vertices (closed ring) for GeoJSON."""
    lat0, lng0 = hex_center(q, r)
    x0, y0 = lng0 * K, lat0
    ring = []
    for i in range(6):
        ang = math.radians(60 * i + 30)
        ring.append(((x0 + HEX_R * math.cos(ang)) / K, y0 + HEX_R * math.sin(ang)))
    ring.append(ring[0])
    return ring


def month_range(end_ym, n):
    """Return the n months ending at end_ym (inclusive), oldest first."""
    y, m = int(end_ym[:4]), int(end_ym[5:7])
    out = []
    for _ in range(n):
        out.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return out[::-1]


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_json(path, obj, indent=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, separators=(",", ":") if indent is None else None, indent=indent,
                  sort_keys=True)
    os.replace(tmp, path)


def read_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default

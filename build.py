#!/usr/bin/env python3
"""
Africa's Demographic Expansion (2000-2300) — dashboard build script.

Builds a fully self-contained index.html by injecting a compact data payload
into template.html.

Data sources:
  - UN World Population Prospects 2024 (medium variant), via Our World in Data
    population-with-un-projections / population-regions-with-projections
  - UN WPP 2024 median age, via Our World in Data
  - UN WPP 2024 fertility, via Our World in Data
  - Natural Earth 110m admin-0 country boundaries (GeoJSON)

Horizon handling (important):
  Official UN projections end in 2100. For 2105-2300 this script applies an
  H Heuristics extended scenario: each UN region is eased from its 2100 value
  toward a 2300 anchor (Africa ~half of humanity), and countries are scaled by
  their region's factor. Every post-2100 value is flagged as EXTENDED in the UI.
"""

import csv
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"

SOURCES = {
    "population-countries.csv": "https://ourworldindata.org/grapher/population-with-un-projections.csv",
    "population-regions.csv":   "https://ourworldindata.org/grapher/population-regions-with-projections.csv",
    "median-age.csv":           "https://ourworldindata.org/grapher/median-age.csv",
    "fertility.csv":            "https://ourworldindata.org/grapher/children-per-woman-un.csv",
    "world-countries.geojson":  "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_admin_0_countries.geojson",
}

REGIONS = {
    "UN_AFR": {"name": "Africa",                      "short": "Africa",        "color": "#f0a04b"},
    "UN_ASI": {"name": "Asia",                        "short": "Asia",          "color": "#7aa6d6"},
    "UN_EUR": {"name": "Europe",                      "short": "Europe",        "color": "#8f9bb3"},
    "UN_LAC": {"name": "Latin America & Caribbean",   "short": "LatAm & Carib", "color": "#d98c6a"},
    "UN_NAM": {"name": "Northern America",            "short": "N. America",    "color": "#6aa0a8"},
    "UN_OCE": {"name": "Oceania",                     "short": "Oceania",       "color": "#9c8bd9"},
}

# 5-year steps 2000..2300 inclusive = 61 points
YEARS5 = list(range(2000, 2301, 5))
IDX_2100 = YEARS5.index(2100)
IDX_2020 = 4   # 5-year steps: idx 0=2000 ... idx 4=2020, idx 5=2025
IDX_2025 = 5


def interp2024(v2020, v2025):
    """2024 = 0.2*2020 + 0.8*2025 (2024 is 4/5 of the way from 2020 to 2025)."""
    if v2020 is None or v2025 is None:
        return None
    return round(0.2 * v2020 + 0.8 * v2025)

# Post-2100 extended-scenario anchors (absolute persons), H Heuristics scenario.
# Anchored to UN WPP 2024 medium 2100 values; 2300 targets keep Africa near
# half of a roughly stable world, consistent with the report's "beyond 2100" note.
TARGETS_2300 = {
    "UN_AFR": 5_300_000_000,
    "UN_ASI": 3_750_000_000,
    "UN_EUR": 500_000_000,
    "UN_LAC": 600_000_000,
    "UN_NAM": 440_000_000,
    "UN_OCE": 85_000_000,
}

# Median-age 2300 anchors (years), extended from UN WPP 2024 2100 values.
MEDIAN_2300 = {
    "UN_AFR": 44.0, "UN_ASI": 46.0, "UN_EUR": 48.0,
    "UN_LAC": 47.0, "UN_NAM": 46.0, "UN_OCE": 43.0, "WLD": 46.0,
}

# Africa fertility (births per woman): UN historical/projected anchors from the
# H Heuristics report (3.9 in 2024 -> 2.8 in 2050 -> 2.0 in 2100), extended.
AFRICA_TFR_ANCHORS = [
    [2000, 5.10], [2024, 3.90], [2050, 2.80], [2100, 2.00], [2200, 1.88], [2300, 1.82],
]

# Illustrative diaspora / ancestry scenario anchors (H Heuristics synthesis).
# - bornOutside: Africa-born people living outside Africa under 3 mobility
#   scenarios, expressed as a ratio of Africa's population (report §5).
# - broadAncestry: people outside Africa with any African ancestry
#   (genealogical/admixture definition) — directional scenario only.
# - under25Share: Africa's share of the world's under-25 population (%).
DIASPORA_RATIOS = [0.0147, 0.02, 0.03]
INTRA_RATIO = 0.0155  # Africa-born living in another African country (2020 = 20.8M)
BROAD_ANCESTRY_ANCHORS = [
    [2000, 0.36], [2025, 0.44], [2050, 0.62], [2100, 1.05], [2200, 1.62], [2300, 2.10],  # billions
]
UNDER25_ANCHORS = [[2000, 24.0], [2024, 28.0], [2100, 46.0], [2300, 47.0]]  # %


def fetch():
    DATA.mkdir(exist_ok=True)
    for fname, url in SOURCES.items():
        dest = DATA / fname
        if dest.exists() and dest.stat().st_size > 1000:
            continue
        print(f"  downloading {fname}")
        urllib.request.urlretrieve(url, dest)
    print("  data present")


def read_csv(fname):
    with open(DATA / fname, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def to_num(s):
    if s is None or s == "":
        return None
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def pop1000(v):
    if v is None:
        return None
    return int(round(v / 1000.0))


def smoothstep(t):
    # ease in-out sine-ish on [0,1]
    import math
    return 0.5 - 0.5 * math.cos(math.pi * min(1.0, max(0.0, t)))


def extend_series(vals_to_2100, target_2300, idx2100=IDX_2100, n=len(YEARS5)):
    """Extend a 2000..2100 series to 2000..2300 using a smooth ease to target."""
    out = list(vals_to_2100)
    v2100 = vals_to_2100[idx2100]
    for i in range(idx2100 + 1, n):
        t = (YEARS5[i] - 2100) / 200.0
        f = smoothstep(t)
        out.append(v2100 + (target_2300 - v2100) * f)
    return out


def build_region_series(rows):
    """Region population (thousands) for 2000..2300."""
    table = {}
    for r in rows:
        code = (r.get("Code") or "").strip()
        if code not in REGIONS:
            continue
        y = int(float(r["Year"]))
        if y < 2000 or y > 2100:
            continue
        p = to_num(r.get("Population"))
        if p is None:
            continue
        table.setdefault(code, {})[y] = pop1000(p)

    out = {}
    for code, d in table.items():
        base = [d.get(y) for y in YEARS5 if y <= 2100]
        if len(base) != IDX_2100 + 1:
            print(f"  WARN region {code}: incomplete 2000-2100 series ({len(base)} pts)")
            continue
        target_k = pop1000(TARGETS_2300[code])
        v5 = extend_series(base, target_k)
        out[code] = {
            "name": REGIONS[code]["name"],
            "short": REGIONS[code]["short"],
            "color": REGIONS[code]["color"],
            "v5": v5,
            "p2000": base[0],
            "p2024": interp2024(base[IDX_2020], base[IDX_2025]),
            "p2100": base[IDX_2100],
            "p2300": v5[-1],
        }
    return out


def build_world(regions):
    """World = sum of the 6 UN regions (consistent across the whole horizon)."""
    n = len(YEARS5)
    v5 = [0] * n
    for code in REGIONS:
        s = regions.get(code)
        if not s:
            continue
        for i in range(n):
            v = s["v5"][i]
            if v is not None:
                v5[i] += v
    return v5


def build_median_series(rows, regions):
    """Median age (1 decimal) for world + regions, 2000..2300."""
    table = {}
    for r in rows:
        code = (r.get("Code") or "").strip()
        key = code if code in REGIONS else ("WLD" if r.get("Entity") == "World" else None)
        if key is None:
            continue
        y = int(float(r["Year"]))
        if y < 2000 or y > 2100:
            continue
        hist = to_num(r.get("Median age"))
        proj = to_num(r.get("Median age (Projected)"))
        v = proj if proj is not None else hist
        if v is None:
            continue
        table.setdefault(key, {})[y] = round(v, 1)

    result = {}
    for key, d in table.items():
        base = [d.get(y) for y in YEARS5 if y <= 2100]
        if len(base) != IDX_2100 + 1:
            continue
        target = MEDIAN_2300.get(key, base[IDX_2100])
        v5 = extend_series(base, target)
        result[key] = {"v5": v5, "p2000": base[0], "p2100": base[IDX_2100], "p2300": v5[-1]}
    # ensure Africa exists even if data quirks
    if "UN_AFR" not in result and regions.get("UN_AFR"):
        result["UN_AFR"] = {"v5": [19.0] * (IDX_2100 + 1), "p2000": 19.0, "p2100": 35.0, "p2300": 44.0}
    return result


def build_africa_tfr(rows):
    """Africa fertility 2000..2300 from UN data (to 2100) + extended anchors."""
    vals = {}
    for r in rows:
        code = (r.get("Code") or "").strip()
        if code != "UN_AFR":
            continue
        y = int(float(r["Year"]))
        if y < 2000 or y > 2100:
            continue
        v = to_num(r.get("Fertility rate"))
        if v is not None:
            vals[y] = round(v, 2)
    anchors = AFRICA_TFR_ANCHORS
    out_years, out_vals = [], []
    for y in YEARS5:
        # prefer real UN data; blend into anchors for the extension
        if y in vals:
            out_years.append(y)
            out_vals.append(vals[y])
        else:
            # interpolate between nearest anchors
            a = anchors[0]
            b = anchors[-1]
            for i in range(len(anchors) - 1):
                if anchors[i][0] <= y <= anchors[i + 1][0]:
                    a, b = anchors[i], anchors[i + 1]
                    break
            t = (y - a[0]) / (b[0] - a[0]) if b[0] != a[0] else 0
            out_years.append(y)
            out_vals.append(round(a[1] + (b[1] - a[1]) * t, 2))
    return {"years": out_years, "v": out_vals}


def build_countries(rows, geojson_lookup, regions):
    """Country population (thousands) 2000..2300, extended by region factor."""
    import re
    iso3_re = re.compile(r"^[A-Z]{3}$")
    series, names = {}, {}
    for r in rows:
        code = (r.get("Code") or "").strip()
        if not iso3_re.match(code):
            continue
        y = int(float(r["Year"]))
        if y < 2000 or y > 2100:
            continue
        hist = to_num(r.get("Population"))
        proj = to_num(r.get("Population (Projected)"))
        v = proj if proj is not None else hist
        if v is None:
            continue
        series.setdefault(code, {})[y] = v
        names.setdefault(code, r.get("Entity", code))

    out = {}
    for code, d in series.items():
        g = geojson_lookup.get(code)
        region = g["region"] if g else None
        base = [pop1000(d.get(y)) for y in YEARS5 if y <= 2100]
        if len(base) != IDX_2100 + 1 or region is None:
            continue
        # extend past 2100 using the region's trajectory
        reg = regions.get(region)
        v5 = list(base)
        if reg:
            for i in range(IDX_2100 + 1, len(YEARS5)):
                f = reg["v5"][i] / reg["v5"][IDX_2100] if reg["v5"][IDX_2100] else 1.0
                v5.append(int(round(base[IDX_2100] * f)))
        else:
            v5 += [base[IDX_2100]] * (len(YEARS5) - IDX_2100 - 1)

        p2000, p2024, p2100 = base[0], interp2024(base[IDX_2020], base[IDX_2025]), base[IDX_2100]
        grow2000 = round((p2100 - p2000) / p2000 * 100.0, 1) if p2000 else None
        out[code] = {
            "name": names.get(code, code),
            "region": region,
            "v5": v5,
            "p2000": p2000,
            "p2024": p2024,
            "p2100": p2100,
            "grow2000": grow2000,
        }
    return out


def load_geojson():
    g = json.load(open(DATA / "world-countries.geojson"))
    lookup, feats = {}, []
    for f in g["features"]:
        p = f.get("properties", {})
        iso = (p.get("ISO_A3_EH") or p.get("ISO_A3") or "").strip()
        if not iso or iso == "-99":
            continue
        name = p.get("NAME") or p.get("ADMIN") or iso
        region = region_from_ne(p.get("REGION_UN"), p.get("SUBREGION"))
        geom = slim_geometry(f.get("geometry"))
        feats.append({"type": "Feature", "properties": {"iso": iso, "name": name, "region": region}, "geometry": geom})
        lookup[iso] = {"name": name, "region": region}
    return feats, lookup


def region_from_ne(region_un, subregion):
    if region_un == "Africa":
        return "UN_AFR"
    if region_un == "Asia":
        return "UN_ASI"
    if region_un == "Europe":
        return "UN_EUR"
    if region_un == "Oceania":
        return "UN_OCE"
    if region_un == "Americas":
        return "UN_NAM" if (subregion or "") == "Northern America" else "UN_LAC"
    return None


def slim_geometry(geom):
    if geom is None:
        return None
    t = geom.get("type")
    if t == "Polygon":
        return {"type": t, "coordinates": [[[round(c[0], 2), round(c[1], 2)] for c in ring] for ring in geom["coordinates"]]}
    if t == "MultiPolygon":
        return {"type": t, "coordinates": [[[[round(c[0], 2), round(c[1], 2)] for c in ring] for ring in poly] for poly in geom["coordinates"]]}
    return geom


def main():
    fetch()
    print("Reading CSVs...")
    region_rows = read_csv("population-regions.csv")
    country_rows = read_csv("population-countries.csv")
    median_rows = read_csv("median-age.csv")
    tfr_rows = read_csv("fertility.csv")

    print("Processing GeoJSON...")
    geojson_feats, geojson_lookup = load_geojson()

    print("Building series...")
    regions = build_region_series(region_rows)
    world = build_world(regions)
    median = build_median_series(median_rows, regions)
    tfr = build_africa_tfr(tfr_rows)
    countries = build_countries(country_rows, geojson_lookup, regions)

    afr = regions.get("UN_AFR", {})
    meta = {
        "years5": YEARS5,
        "idx2100": IDX_2100,
        "title": "Africa's Demographic Expansion",
        "subtitle": "Population, diaspora & mixed ancestry · 2000-2300",
        "source": "UN WPP 2024 (to 2100) · H Heuristics extended scenario (2105-2300)",
        "africa": {
            "p2000": afr.get("p2000"),
            "p2024": afr.get("p2024"),
            "p2100": afr.get("p2100"),
            "p2300": afr.get("p2300"),
        },
        "regions": [{"code": c, "name": REGIONS[c]["name"], "short": REGIONS[c]["short"], "color": REGIONS[c]["color"]} for c in REGIONS],
        "diaspora": {
            "ratios": DIASPORA_RATIOS,
            "intraRatio": INTRA_RATIO,
            "base2020M": 19.7,
            "broadAncestry": BROAD_ANCESTRY_ANCHORS,
            "under25": UNDER25_ANCHORS,
        },
        "tfrAnchors": AFRICA_TFR_ANCHORS,
        "hubs": [
            {"name": "Brazil", "lat": -10.3, "lng": -53.2, "w": 1.00},
            {"name": "United States", "lat": 37.8, "lng": -96.0, "w": 0.62},
            {"name": "Caribbean", "lat": 19.5, "lng": -72.0, "w": 0.34},
            {"name": "Colombia", "lat": 4.5, "lng": -74.0, "w": 0.12},
            {"name": "France", "lat": 46.6, "lng": 2.5, "w": 0.07},
            {"name": "United Kingdom", "lat": 52.5, "lng": -1.5, "w": 0.05},
            {"name": "Canada", "lat": 56.0, "lng": -96.0, "w": 0.04},
            {"name": "Saudi Arabia", "lat": 23.5, "lng": 44.5, "w": 0.04},
            {"name": "UAE", "lat": 24.0, "lng": 54.0, "w": 0.03},
            {"name": "Spain", "lat": 40.0, "lng": -3.5, "w": 0.03},
            {"name": "Italy", "lat": 42.5, "lng": 12.0, "w": 0.03},
            {"name": "Germany", "lat": 51.0, "lng": 10.5, "w": 0.03},
            {"name": "Netherlands", "lat": 52.3, "lng": 5.5, "w": 0.02},
            {"name": "Portugal", "lat": 39.5, "lng": -8.0, "w": 0.02},
            {"name": "Mexico", "lat": 23.6, "lng": -102.5, "w": 0.02},
        ],
    }

    payload = {
        "meta": meta,
        "regions": regions,
        "world": world,
        "median": median,
        "tfr": tfr,
        "countries": countries,
        "geo": geojson_feats,
    }

    (DATA / "payload.json").write_text(json.dumps(payload, separators=(",", ":")))
    print(f"  countries: {len(countries)} | geo features: {len(geojson_feats)}")
    print(f"  Africa: 2000={afr.get('p2000')}k 2024={afr.get('p2024')}k 2100={afr.get('p2100')}k 2300={afr.get('p2300')}k")
    print(f"  Africa share: 2024={afr['p2024']/world[4]*100:.1f}% 2100={afr['p2100']/world[IDX_2100]*100:.1f}% 2300={afr['p2300']/world[-1]*100:.1f}%")

    tpl = (ROOT / "template.html").read_text(encoding="utf-8")
    marker = "/*__PAYLOAD__*/"
    if marker not in tpl:
        print("ERROR: template.html missing marker", marker)
        sys.exit(1)
    injected = json.dumps(payload, separators=(",", ":"))
    out_html = tpl.replace(marker, injected, 1)
    (ROOT / "index.html").write_text(out_html, encoding="utf-8")
    print(f"  wrote index.html ({len(out_html):,} bytes)")


if __name__ == "__main__":
    main()

"""
Jawa.gg PC Market Trends — React+Chart.js dashboard (Flask)
Run:  python dashboard.py
Open: http://localhost:8050
"""

import csv
import json
import math
import os
from pathlib import Path

from flask import Flask, Response, send_file

CSV_PATH  = Path(__file__).parent / "jawa_listings.csv"
HTML_PATH = Path(__file__).parent / "dashboard.html"

# Part cost estimates used by the Recommendations engine (client-side)
PART_COSTS = {
    # ── GPUs ──────────────────────────────────────────────────────────────────
    "RTX 5090": 1800, "RTX 5080": 1100, "RTX 5070 Ti": 700,  "RTX 5070": 550,
    "RTX 5060 Ti": 380, "RTX 5060": 300,
    "RTX 4090": 1200, "RTX 4080 Super": 800, "RTX 4080": 750,
    "RTX 4070 Ti Super": 580, "RTX 4070 Ti": 520, "RTX 4070 Super": 420,
    "RTX 4070": 340, "RTX 4060 Ti": 270, "RTX 4060": 220, "RTX 4050": 170,
    "RTX 3090 Ti": 580, "RTX 3090": 500, "RTX 3080 Ti": 400,
    "RTX 3080 12GB": 320, "RTX 3080": 280, "RTX 3070 Ti": 260,
    "RTX 3070": 220, "RTX 3060 Ti": 180, "RTX 3060": 140, "RTX 3050": 110,
    "RTX 2080 Ti": 280, "RTX 2080 Super": 200, "RTX 2080": 180,
    "RTX 2070 Super": 160, "RTX 2070": 140, "RTX 2060 Super": 130, "RTX 2060": 110,
    "GTX 1080 Ti": 140, "GTX 1080": 110, "GTX 1070 Ti": 90,  "GTX 1070": 75,
    "GTX 1660 Ti": 80,  "GTX 1660 Super": 75, "GTX 1660": 65,
    "RX 9070 XT": 480, "RX 9070": 420,
    "RX 7900 XTX": 600, "RX 7900 XT": 480, "RX 7900 GRE": 380,
    "RX 7800 XT": 280,  "RX 7700 XT": 230, "RX 7600 XT": 190, "RX 7600": 160,
    "RX 6950 XT": 380,  "RX 6900 XT": 330, "RX 6800 XT": 280, "RX 6800": 240,
    "RX 6750 XT": 200,  "RX 6700 XT": 175, "RX 6700": 150,
    "RX 6650 XT": 140,  "RX 6600 XT": 125, "RX 6600": 110,
    "Arc B580": 200, "Arc A770": 180, "Arc A750": 150,
    # ── CPUs ──────────────────────────────────────────────────────────────────
    "Ryzen 9 9950X3D": 700, "Ryzen 9 9900X": 400,  "Ryzen 7 9800X3D": 380,
    "Ryzen 7 9700X": 280,   "Ryzen 5 9600X": 220,  "Ryzen 5 9600": 180,
    "Ryzen 9 7950X3D": 650, "Ryzen 9 7900X3D": 480,"Ryzen 9 7900X": 350,
    "Ryzen 7 7800X3D": 300, "Ryzen 7 7700X": 200,  "Ryzen 7 7700": 170,
    "Ryzen 5 7600X": 170,   "Ryzen 5 7600": 150,
    "Ryzen 9 5950X": 250,   "Ryzen 9 5900X": 180,  "Ryzen 7 5800X3D": 180,
    "Ryzen 7 5800X": 120,   "Ryzen 7 5700X": 100,  "Ryzen 5 5600X": 80,
    "Ryzen 5 5600": 70,     "Ryzen 5 5500": 60,
    "Ryzen 7 3700X": 80,    "Ryzen 5 3600": 60,
    "i9-14900KS": 420, "i9-14900K": 380, "i7-14700K": 320, "i7-14700KF": 300,
    "i5-14600K": 220,  "i5-14600KF": 210,
    "i9-13900KS": 380, "i9-13900K": 340, "i7-13700K": 280, "i7-13700KF": 260,
    "i5-13600K": 200,  "i5-13600KF": 190,
    "i9-12900K": 260,  "i7-12700K": 200, "i7-12700KF": 190,
    "i5-12600K": 160,  "i5-12400F": 100, "i5-12400": 110,
    "i7-11700K": 140,  "i5-11600K": 110, "i7-10700K": 120,
    "i5-10600K": 90,   "i5-10400F": 70,
    "Core Ultra 9 285K": 480, "Core Ultra 7 265K": 360, "Core Ultra 5 245K": 260,
}

app = Flask(__name__)


def _clean(val: str) -> str | None:
    if not val:
        return None
    v = val.strip()
    return None if v.lower() in ("", "nan", "none") else v


def load_data() -> list[dict]:
    """Read CSV and return a JSON-safe list of listing dicts."""
    if not CSV_PATH.exists():
        return []
    rows = []
    try:
        with open(CSV_PATH, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                price = None
                try:
                    p = float(row.get("price") or "")
                    if not math.isnan(p):
                        price = p
                except (ValueError, TypeError):
                    pass

                ram_gb = None
                try:
                    r = float(row.get("ram_gb") or "")
                    if not math.isnan(r):
                        ram_gb = int(r)
                except (ValueError, TypeError):
                    pass

                rows.append({
                    "title":       _clean(row.get("title", "")),
                    "price":       price,
                    "gpu":         _clean(row.get("gpu", "")),
                    "cpu":         _clean(row.get("cpu", "")),
                    "ram_gb":      ram_gb,
                    "storage":     _clean(row.get("storage", "")),
                    "color":       _clean(row.get("color", "")),
                    "status":      _clean(row.get("status", "")),
                    "url":         _clean(row.get("url", "")),
                    "date_listed": _clean(row.get("date_listed", "")),
                    "date_sold":   _clean(row.get("date_sold", "")),
                })
    except Exception as exc:
        print(f"[dashboard] CSV read error: {exc}")
    return rows


@app.route("/")
def index():
    return send_file(HTML_PATH)


@app.route("/api/data.js")
def data_js():
    rows = load_data()
    js = (
        f"window.JAWA_DATA = {json.dumps(rows)};\n"
        f"window.PART_COSTS = {json.dumps(PART_COSTS)};\n"
    )
    return Response(js, mimetype="application/javascript",
                    headers={"Cache-Control": "no-store"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8050))
    print(f"\n  Dashboard  →  http://localhost:{port}\n")
    app.run(debug=False, host="0.0.0.0", port=port)

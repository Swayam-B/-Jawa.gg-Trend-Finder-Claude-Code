"""
Jawa.gg PC Market Trends — AstroLabPCs Research Dashboard
Run:  python dashboard.py
Open: http://localhost:8050
"""

import math
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import dash
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, State, dash_table, dcc, html

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CSV_PATH = Path(__file__).parent / "jawa_listings.csv"

# Jawa-inspired dark palette: near-black surfaces with a mint/teal accent
COLORS = {
    "bg":       "#0a0c10",
    "card":     "#14171c",
    "card_alt": "#1c2128",
    "border":   "#2d333b",
    "accent":   "#14d991",   # jawa mint / brand-ish teal-green
    "accent_2": "#2dd4bf",
    "sold":     "#14d991",   # successful sale
    "active":   "#f59e0b",   # amber: still on market
    "gold":     "#fbbf24",
    "danger":   "#f87171",
    "text":     "#e6edf3",
    "muted":    "#7d8590",
}

# Hardware brand colors (applied to GPU/CPU charts so the same brand is
# always the same color across the dashboard).
BRAND_COLORS = {
    "nvidia": "#76b900",   # NVIDIA green
    "amd":    "#ed1c24",   # AMD red
    "intel":  "#0071c5",   # Intel blue
    "other":  "#7d8590",
}


def gpu_generation(name: str | None) -> str | None:
    """Return a generation label like 'RTX 40 series' for a canonical GPU name."""
    if not name:
        return None
    n = str(name)
    checks = [
        (r"RTX\s*5\d{3}", "RTX 50 series"),
        (r"RTX\s*4\d{3}", "RTX 40 series"),
        (r"RTX\s*3\d{3}", "RTX 30 series"),
        (r"RTX\s*2\d{3}", "RTX 20 series"),
        (r"GTX\s*1[6-9]\d{2}", "GTX 16 series"),
        (r"GTX\s*1[0-5]\d{2}", "GTX 10 series"),
        (r"RX\s*9\d{3}", "RX 9000 series"),
        (r"RX\s*7\d{3}", "RX 7000 series"),
        (r"RX\s*6\d{3}", "RX 6000 series"),
        (r"RX\s*5[5-9]\d{2}", "RX 5000 series"),
        (r"RX\s*5\d{2}\b", "RX 500 series"),
        (r"RX\s*4\d{2}\b", "RX 400 series"),
        (r"Arc", "Intel Arc"),
    ]
    for pattern, label in checks:
        if re.search(pattern, n, re.I):
            return label
    return None


def cpu_socket(name: str | None) -> str | None:
    """Return socket label like 'AM5' or 'LGA1700' for a canonical CPU name."""
    if not name:
        return None
    n = str(name)
    if re.search(r"Core Ultra", n, re.I):
        return "LGA1851"
    m = re.search(r"Ryzen\s+\d+\s+(\d)\d{3}", n, re.I)
    if m:
        return "AM5" if int(m.group(1)) >= 7 else "AM4"
    m = re.search(r"i[3579][-\s](\d{4,5})", n, re.I)
    if m:
        num = int(re.sub(r"\D", "", m.group(1)))
        if num >= 12000: return "LGA1700"
        if num >= 10000: return "LGA1200"
        return "LGA1151"
    return None


def part_brand(name: str | None) -> str:
    """Return 'nvidia' / 'amd' / 'intel' / 'other' for a GPU or CPU string."""
    if not name:
        return "other"
    s = str(name).upper()
    if s.startswith(("RTX", "GTX")):
        return "nvidia"
    if s.startswith(("RX ", "RADEON", "RYZEN", "THREADRIPPER")):
        return "amd"
    if s.startswith(("ARC", "INTEL", "CORE ULTRA", "CORE ", "I3-", "I5-", "I7-", "I9-",
                     "I3 ", "I5 ", "I7 ", "I9 ")):
        return "intel"
    return "other"


def brand_color(name: str | None) -> str:
    return BRAND_COLORS[part_brand(name)]


FIG_LAYOUT = dict(
    template="plotly_dark",
    paper_bgcolor=COLORS["card"],
    plot_bgcolor=COLORS["card"],
    font=dict(color=COLORS["text"], family="Inter, -apple-system, Segoe UI, sans-serif", size=12),
    margin=dict(l=10, r=10, t=46, b=10),
    title_font=dict(size=15, color=COLORS["text"]),
    title_x=0.02,
    title_xanchor="left",
    xaxis=dict(gridcolor=COLORS["border"], zerolinecolor=COLORS["border"]),
    yaxis=dict(gridcolor=COLORS["border"], zerolinecolor=COLORS["border"]),
    hoverlabel=dict(bgcolor=COLORS["card_alt"], bordercolor=COLORS["accent"],
                    font=dict(color=COLORS["text"])),
)

PART_COSTS = {
    # GPUs
    "RTX 5090": 1800, "RTX 5080": 1100, "RTX 5070 Ti": 700, "RTX 5070": 550,
    "RTX 5060 Ti": 380, "RTX 5060": 300,
    "RTX 4090": 1200, "RTX 4080 Super": 800, "RTX 4080": 750,
    "RTX 4070 Ti Super": 580, "RTX 4070 Ti": 520, "RTX 4070 Super": 420,
    "RTX 4070": 340, "RTX 4060 Ti": 270, "RTX 4060": 220, "RTX 4050": 170,
    "RTX 3090 Ti": 580, "RTX 3090": 500, "RTX 3080 Ti": 400,
    "RTX 3080 12GB": 320, "RTX 3080": 280, "RTX 3070 Ti": 260,
    "RTX 3070": 220, "RTX 3060 Ti": 180, "RTX 3060": 140, "RTX 3050": 110,
    "RTX 2080 Ti": 280, "RTX 2080 Super": 200, "RTX 2080": 180,
    "RTX 2070 Super": 160, "RTX 2070": 140, "RTX 2060 Super": 130, "RTX 2060": 110,
    "GTX 1080 Ti": 140, "GTX 1080": 110, "GTX 1070 Ti": 90, "GTX 1070": 75,
    "GTX 1660 Ti": 80, "GTX 1660 Super": 75, "GTX 1660": 65,
    "RX 9070 XT": 480, "RX 9070": 420,
    "RX 7900 XTX": 600, "RX 7900 XT": 480, "RX 7900 GRE": 380,
    "RX 7800 XT": 280, "RX 7700 XT": 230, "RX 7600 XT": 190, "RX 7600": 160,
    "RX 6950 XT": 380, "RX 6900 XT": 330, "RX 6800 XT": 280, "RX 6800": 240,
    "RX 6750 XT": 200, "RX 6700 XT": 175, "RX 6700": 150,
    "RX 6650 XT": 140, "RX 6600 XT": 125, "RX 6600": 110,
    "Arc B580": 200, "Arc A770": 180, "Arc A750": 150,
    # CPUs
    "Ryzen 9 9950X3D": 700, "Ryzen 9 9900X": 400, "Ryzen 7 9800X3D": 380,
    "Ryzen 7 9700X": 280, "Ryzen 5 9600X": 220, "Ryzen 5 9600": 180,
    "Ryzen 9 7950X3D": 650, "Ryzen 9 7900X3D": 480, "Ryzen 9 7900X": 350,
    "Ryzen 7 7800X3D": 300, "Ryzen 7 7700X": 200, "Ryzen 7 7700": 170,
    "Ryzen 5 7600X": 170, "Ryzen 5 7600": 150,
    "Ryzen 9 5950X": 250, "Ryzen 9 5900X": 180, "Ryzen 7 5800X3D": 180,
    "Ryzen 7 5800X": 120, "Ryzen 7 5700X": 100, "Ryzen 5 5600X": 80,
    "Ryzen 5 5600": 70, "Ryzen 5 5500": 60,
    "Ryzen 7 3700X": 80, "Ryzen 5 3600": 60,
    "i9-14900KS": 420, "i9-14900K": 380, "i7-14700K": 320, "i7-14700KF": 300,
    "i5-14600K": 220, "i5-14600KF": 210,
    "i9-13900KS": 380, "i9-13900K": 340, "i7-13700K": 280, "i7-13700KF": 260,
    "i5-13600K": 200, "i5-13600KF": 190,
    "i9-12900K": 260, "i7-12700K": 200, "i7-12700KF": 190,
    "i5-12600K": 160, "i5-12400F": 100, "i5-12400": 110,
    "i7-11700K": 140, "i5-11600K": 110, "i7-10700K": 120,
    "i5-10600K": 90, "i5-10400F": 70,
    "Core Ultra 9 285K": 480, "Core Ultra 7 265K": 360, "Core Ultra 5 245K": 260,
}

BASE_BUILD_COST = 200  # case + PSU + motherboard + misc


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_data() -> pd.DataFrame:
    empty = pd.DataFrame(columns=[
        "title","price","gpu","cpu","ram_gb","storage",
        "status","url","date_sold","date_listed","date_scraped"
    ])
    if not CSV_PATH.exists():
        return empty
    try:
        df = pd.read_csv(CSV_PATH)
    except Exception:
        return empty

    df["price"]  = pd.to_numeric(df.get("price"), errors="coerce")
    df["ram_gb"] = pd.to_numeric(df.get("ram_gb"), errors="coerce")

    for col in ("date_sold", "date_listed", "date_scraped"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce", utc=True)

    for col in ("gpu", "cpu", "storage", "status", "title", "url"):
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip().replace("nan", None)

    # days to sell
    if "date_sold" in df.columns and "date_listed" in df.columns:
        mask = df["status"] == "sold"
        df["days_to_sell"] = None
        df.loc[mask, "days_to_sell"] = (
            (df.loc[mask, "date_sold"] - df.loc[mask, "date_listed"])
            .dt.days.clip(lower=0)
        )
    else:
        df["days_to_sell"] = None

    return df


def estimate_build_cost(gpu, cpu, ram_gb, storage) -> float | None:
    gpu_cost = PART_COSTS.get(str(gpu) if gpu else "")
    cpu_cost = PART_COSTS.get(str(cpu) if cpu else "")
    if gpu_cost is None or cpu_cost is None:
        return None
    try:
        ram_cost = float(ram_gb) * 2.5
    except (TypeError, ValueError):
        ram_cost = 16 * 2.5
    storage_cost = 40
    if storage:
        s = str(storage).upper()
        if "2TB" in s:
            storage_cost = 70
        elif "1TB" in s:
            storage_cost = 45
        elif any(x in s for x in ("512", "500")):
            storage_cost = 30
    return round(gpu_cost + cpu_cost + ram_cost + storage_cost + BASE_BUILD_COST, 2)


def no_data_fig(title="No data available"):
    fig = go.Figure()
    fig.update_layout(
        **FIG_LAYOUT,
        title=title,
        annotations=[dict(text="No data", x=0.5, y=0.5, showarrow=False,
                          font=dict(color=COLORS["muted"], size=16))]
    )
    return fig


# ---------------------------------------------------------------------------
# Section 1 — Market Trends
# ---------------------------------------------------------------------------

GRAPH_CONFIG = {
    "displayModeBar": "hover",
    "modeBarButtonsToRemove": [
        "autoScale2d", "lasso2d", "select2d",
        "hoverClosestCartesian", "hoverCompareCartesian",
        "toggleSpikelines", "toImage",
    ],
    "displaylogo": False,
    "doubleClick": "reset+autosize",
    "scrollZoom": False,
}


def chart_card(fig, height=320):
    return dbc.Card(
        dcc.Graph(figure=fig, config=GRAPH_CONFIG,
                  style={"height": f"{height}px"}),
        className="chart-card"
    )


def kpi_card(label: str, value: str, color: str):
    return dbc.Col(
        dbc.Card(
            dbc.CardBody([
                html.Div(label, className="kpi-label"),
                html.Div(value, className="kpi-value", style={"color": color}),
            ]),
            className="kpi-card",
        ),
        xs=6, md=4, lg=2,
    )


def brand_legend():
    def swatch(label, color):
        return html.Span([
            html.Span(className="brand-dot",
                      style={"backgroundColor": color}),
            html.Span(label, className="brand-label"),
        ], className="brand-chip")

    return html.Div([
        html.Span("Brand colors:", className="brand-legend-title"),
        swatch("NVIDIA", BRAND_COLORS["nvidia"]),
        swatch("AMD",    BRAND_COLORS["amd"]),
        swatch("Intel",  BRAND_COLORS["intel"]),
        html.Span("|", className="brand-sep"),
        html.Span("Status:", className="brand-legend-title"),
        swatch("Sold",   COLORS["sold"]),
        swatch("Active", COLORS["active"]),
    ], className="brand-legend mb-3")


def make_trends_section(df: pd.DataFrame):
    sold   = df[df["status"] == "sold"]
    active = df[df["status"] == "active"]

    # ── Row 0: KPI strip ───────────────────────────────────────────────────
    total = len(df)
    sold_n = len(sold)
    active_n = len(active)
    avg_sold = sold["price"].dropna().mean() if not sold.empty else None
    avg_active = active["price"].dropna().mean() if not active.empty else None
    sell_through = (sold_n / total * 100) if total else 0

    kpi_strip = dbc.Row([
        kpi_card("Total Listings", f"{total:,}", COLORS["accent"]),
        kpi_card("Sold", f"{sold_n:,}", COLORS["sold"]),
        kpi_card("Active", f"{active_n:,}", COLORS["active"]),
        kpi_card("Sell-Through", f"{sell_through:.0f}%", COLORS["gold"]),
        kpi_card("Avg Sold Price",
                 f"${avg_sold:,.0f}" if avg_sold else "—", COLORS["sold"]),
        kpi_card("Avg Active Price",
                 f"${avg_active:,.0f}" if avg_active else "—", COLORS["active"]),
    ], className="g-3 mb-4")

    # ── Row 1: Top 10 GPUs / CPUs (colored per brand) ──────────────────────
    def top10_bar(col, title):
        if df.empty or col not in df.columns:
            return no_data_fig(title)
        counts = (df[col].dropna()
                         .value_counts()
                         .head(10)
                         .sort_values())
        bar_colors = [brand_color(n) for n in counts.index]
        fig = go.Figure(go.Bar(
            x=counts.values, y=counts.index,
            orientation="h",
            marker=dict(color=bar_colors,
                        line=dict(color=COLORS["border"], width=0)),
            hovertemplate="<b>%{y}</b><br>%{x} listings<extra></extra>",
        ))
        fig.update_layout(**FIG_LAYOUT, title=title,
                          xaxis_title="Listings", yaxis_title="",
                          bargap=0.25)
        return fig

    gpu_fig = top10_bar("gpu", "Top 10 GPUs by Listings")
    cpu_fig = top10_bar("cpu", "Top 10 CPUs by Listings")

    # ── Row 2: Combo chart + Price distribution ─────────────────────────────
    def combo_fig():
        if df.empty:
            return no_data_fig("Top 15 CPU + GPU Combos")
        tmp = df.dropna(subset=["gpu","cpu"]).copy()
        tmp["combo"] = tmp["cpu"] + " + " + tmp["gpu"]
        grp = (tmp.groupby(["combo","status"])
                  .size().reset_index(name="count"))
        totals = grp.groupby("combo")["count"].sum().nlargest(15).index
        grp = grp[grp["combo"].isin(totals)]
        order = (grp.groupby("combo")["count"].sum()
                    .reindex(totals).sort_values().index.tolist())
        fig = go.Figure()
        for status, color in [("sold", COLORS["sold"]), ("active", COLORS["active"])]:
            sub = grp[grp["status"] == status].set_index("combo").reindex(order).fillna(0)
            fig.add_trace(go.Bar(
                name=status.capitalize(),
                x=sub["count"].values, y=order,
                orientation="h", marker_color=color,
                hovertemplate="%{y}<br>" + status + ": %{x}<extra></extra>",
            ))
        fig.update_layout(**FIG_LAYOUT, barmode="stack",
                          title="Top 15 CPU + GPU Combos",
                          xaxis_title="Listings", yaxis_title="",
                          legend=dict(orientation="h", y=1.02))
        return fig

    def price_dist_fig():
        if df.empty:
            return no_data_fig("Price Distribution")
        fig = go.Figure()
        for status, color, label in [
            ("sold",   COLORS["sold"],   "Sold"),
            ("active", COLORS["active"], "Active"),
        ]:
            prices = df[df["status"] == status]["price"].dropna()
            prices = prices[prices <= 5000]
            if not prices.empty:
                fig.add_trace(go.Histogram(
                    x=prices, name=label,
                    marker_color=color, opacity=0.7,
                    xbins=dict(start=0, end=5000, size=100),
                    hovertemplate="$%{x}–%{x}: %{y} listings<extra></extra>",
                ))
        fig.update_layout(**FIG_LAYOUT, barmode="overlay",
                          title="Price Distribution ($100 bins, $0–$5k)",
                          xaxis_range=[0, 5000], xaxis_title="Price ($)",
                          yaxis_title="Count",
                          legend=dict(orientation="h", y=1.02))
        return fig

    # ── Row 3: White vs Black builds | GPU brand sell-through | CPU brand sell-through ──
    def color_comparison_fig():
        if df.empty or "color" not in df.columns:
            return no_data_fig("White vs Black Builds")
        col_df = df[df["color"].isin(["White", "Black", "Mixed"])].copy()
        if col_df.empty:
            return no_data_fig("White vs Black Builds (no color data yet)")
        COLOR_SWATCHES = {"White": "#e6edf3", "Black": COLORS["muted"], "Mixed": COLORS["accent_2"]}
        fig = go.Figure()
        for status, sc in [("sold", COLORS["sold"]), ("active", COLORS["active"])]:
            sub = col_df[col_df["status"] == status]
            counts = sub["color"].value_counts().reindex(["White", "Black", "Mixed"], fill_value=0)
            fig.add_trace(go.Bar(
                name=status.capitalize(), x=counts.index, y=counts.values,
                marker_color=sc,
                hovertemplate="<b>%{x}</b><br>" + status.capitalize() + ": %{y}<extra></extra>",
            ))
        # Sell-through % annotation per color
        annotations = []
        for color in ["White", "Black", "Mixed"]:
            grp = col_df[col_df["color"] == color]
            if len(grp):
                st = grp["status"].value_counts()
                pct = int(st.get("sold", 0) / len(grp) * 100)
                annotations.append(dict(
                    x=color, y=len(grp) + 0.5,
                    text=f"{pct}% sold", showarrow=False,
                    font=dict(color=COLORS["muted"], size=11),
                ))
        fig.update_layout(**FIG_LAYOUT, barmode="stack",
                          title="White vs Black Build Volume",
                          xaxis_title="Build Color", yaxis_title="Listings",
                          legend=dict(orientation="h", y=1.02),
                          annotations=annotations)
        return fig

    def brand_sellthrough_fig(col, title):
        """Sell-through % per brand for gpu or cpu column."""
        if df.empty or col not in df.columns:
            return no_data_fig(title)
        tmp = df.dropna(subset=[col]).copy()
        tmp["brand"] = tmp[col].apply(part_brand)
        brands = tmp["brand"].value_counts()
        # Only keep brands with meaningful data
        valid = brands[brands >= 3].index.tolist()
        tmp = tmp[tmp["brand"].isin(valid)]
        if tmp.empty:
            return no_data_fig(title)
        grp = tmp.groupby("brand").apply(
            lambda g: pd.Series({
                "total": len(g),
                "sold": (g["status"] == "sold").sum(),
            })
        ).reset_index()
        grp["sell_through"] = grp["sold"] / grp["total"] * 100
        grp = grp.sort_values("sell_through", ascending=True)
        bar_colors = [BRAND_COLORS.get(b, COLORS["muted"]) for b in grp["brand"]]
        fig = go.Figure(go.Bar(
            x=grp["sell_through"], y=grp["brand"].str.capitalize(),
            orientation="h",
            marker=dict(color=bar_colors),
            text=[f"{v:.0f}%" for v in grp["sell_through"]],
            textposition="outside",
            hovertemplate="<b>%{y}</b><br>Sell-through: %{x:.1f}%<br>"
                          "Sold: %{customdata[0]} / %{customdata[1]}<extra></extra>",
            customdata=grp[["sold", "total"]].values,
        ))
        fig.update_layout(**FIG_LAYOUT, title=title,
                          xaxis_range=[0, 110], xaxis_title="Sell-Through %",
                          yaxis_title="", bargap=0.3)
        return fig

    # ── Row 4: Price range breakdown ───────────────────────────────────────
    def price_range_fig():  # noqa: E302
        if df.empty:
            return no_data_fig("Price Range Breakdown")
        labels  = ["<$500", "$500–$800", "$800–$1,200", "$1,200+"]
        bounds  = [0, 500, 800, 1200, float("inf")]
        tmp = df.dropna(subset=["price"]).copy()
        tmp["bucket"] = pd.cut(tmp["price"], bins=bounds, labels=labels, right=False)
        grp = tmp.groupby(["bucket","status"], observed=True).size().reset_index(name="n")
        fig = go.Figure()
        for status, color in [("sold", COLORS["sold"]), ("active", COLORS["active"])]:
            sub = grp[grp["status"] == status].set_index("bucket").reindex(labels).fillna(0)
            fig.add_trace(go.Bar(
                name=status.capitalize(),
                x=labels, y=sub["n"].values,
                marker_color=color,
                hovertemplate="%{x}: %{y} listings<extra></extra>",
            ))
        fig.update_layout(**FIG_LAYOUT, barmode="group",
                          title="Listings by Price Range",
                          xaxis_title="Price Range", yaxis_title="Count",
                          legend=dict(orientation="h", y=1.02))
        return fig

    return dbc.Container([
        kpi_strip,
        brand_legend(),
        dbc.Row([
            dbc.Col(chart_card(gpu_fig), md=6),
            dbc.Col(chart_card(cpu_fig), md=6),
        ], className="g-3"),
        dbc.Row([
            dbc.Col(chart_card(combo_fig(), height=400), md=7),
            dbc.Col(chart_card(price_dist_fig()), md=5),
        ], className="g-3"),
        dbc.Row([
            dbc.Col(chart_card(color_comparison_fig(), height=280), md=4),
            dbc.Col(chart_card(brand_sellthrough_fig("gpu", "GPU Brand Sell-Through %"), height=280), md=4),
            dbc.Col(chart_card(brand_sellthrough_fig("cpu", "CPU Brand Sell-Through %"), height=280), md=4),
        ], className="g-3"),
        dbc.Row([
            dbc.Col(chart_card(price_range_fig(), height=300), md=12),
        ], className="g-3"),
    ], fluid=True, className="px-0")


# ---------------------------------------------------------------------------
# Section 2 — Spec Lookup Tool
# ---------------------------------------------------------------------------

def _label(text):
    return html.Label(text, style={"color": COLORS["accent"], "fontWeight": "600",
                                   "fontSize": "11px", "textTransform": "uppercase",
                                   "letterSpacing": "0.06em", "marginBottom": "4px"})


def make_lookup_section(df: pd.DataFrame):
    gpus = sorted(df["gpu"].dropna().unique().tolist()) if "gpu" in df.columns else []
    cpus = sorted(df["cpu"].dropna().unique().tolist()) if "cpu" in df.columns else []
    dd = {"backgroundColor": COLORS["card"], "color": COLORS["text"]}

    controls = dbc.Card([
        dbc.CardBody([
            # ── Row 1: specific part filters ──────────────────────────────
            dbc.Row([
                dbc.Col([
                    _label("GPU"),
                    dcc.Dropdown(id="gpu-filter",
                                 options=[{"label": "Any", "value": "Any"}] +
                                         [{"label": g, "value": g} for g in gpus],
                                 value="Any", clearable=False, style=dd),
                ], md=3),
                dbc.Col([
                    _label("CPU"),
                    dcc.Dropdown(id="cpu-filter",
                                 options=[{"label": "Any", "value": "Any"}] +
                                         [{"label": c, "value": c} for c in cpus],
                                 value="Any", clearable=False, style=dd),
                ], md=3),
                dbc.Col([
                    _label("RAM"),
                    dcc.Dropdown(id="ram-filter",
                                 options=[{"label": "Any", "value": "Any"},
                                          {"label": "8 GB",  "value": "8"},
                                          {"label": "16 GB", "value": "16"},
                                          {"label": "32 GB", "value": "32"},
                                          {"label": "64 GB", "value": "64"}],
                                 value="Any", clearable=False, style=dd),
                ], md=2),
                dbc.Col([
                    _label("Storage"),
                    dcc.Dropdown(id="storage-filter",
                                 options=[
                                     {"label": "Any",        "value": "Any"},
                                     {"label": "500GB SSD",  "value": "500GB SSD"},
                                     {"label": "512GB SSD",  "value": "512GB SSD"},
                                     {"label": "1TB SSD",    "value": "1TB SSD"},
                                     {"label": "1TB NVMe",   "value": "1TB NVMe"},
                                     {"label": "2TB SSD",    "value": "2TB SSD"},
                                     {"label": "2TB NVMe",   "value": "2TB NVMe"},
                                     {"label": "2TB HDD",    "value": "2TB HDD"},
                                 ],
                                 value="Any", clearable=False, style=dd),
                ], md=2),
                dbc.Col([
                    _label("Build Color"),
                    dcc.Dropdown(id="color-filter",
                                 options=[
                                     {"label": "Any",    "value": "Any"},
                                     {"label": "White",  "value": "White"},
                                     {"label": "Black",  "value": "Black"},
                                     {"label": "Mixed",  "value": "Mixed"},
                                     {"label": "Pink",   "value": "Pink"},
                                     {"label": "Purple", "value": "Purple"},
                                     {"label": "Red",    "value": "Red"},
                                     {"label": "Blue",   "value": "Blue"},
                                     {"label": "Gray",   "value": "Gray"},
                                     {"label": "Silver", "value": "Silver"},
                                 ],
                                 value="Any", clearable=False, style=dd),
                ], md=2),
            ], className="g-3 mb-3"),
            # ── Row 2: generation / socket / time filters ─────────────────
            dbc.Row([
                dbc.Col([
                    _label("GPU Generation"),
                    dcc.Dropdown(id="gpu-gen-filter",
                                 options=[
                                     {"label": "Any",             "value": "Any"},
                                     {"label": "RTX 50 series",   "value": "RTX 50 series"},
                                     {"label": "RTX 40 series",   "value": "RTX 40 series"},
                                     {"label": "RTX 30 series",   "value": "RTX 30 series"},
                                     {"label": "RTX 20 series",   "value": "RTX 20 series"},
                                     {"label": "GTX 16 series",   "value": "GTX 16 series"},
                                     {"label": "GTX 10 series",   "value": "GTX 10 series"},
                                     {"label": "RX 9000 series",  "value": "RX 9000 series"},
                                     {"label": "RX 7000 series",  "value": "RX 7000 series"},
                                     {"label": "RX 6000 series",  "value": "RX 6000 series"},
                                     {"label": "RX 5000 series",  "value": "RX 5000 series"},
                                     {"label": "RX 500 series",   "value": "RX 500 series"},
                                     {"label": "Intel Arc",       "value": "Intel Arc"},
                                 ],
                                 value="Any", clearable=False, style=dd),
                ], md=3),
                dbc.Col([
                    _label("CPU Socket"),
                    dcc.Dropdown(id="socket-filter",
                                 options=[
                                     {"label": "Any",      "value": "Any"},
                                     {"label": "AM5",      "value": "AM5"},
                                     {"label": "AM4",      "value": "AM4"},
                                     {"label": "LGA1851",  "value": "LGA1851"},
                                     {"label": "LGA1700",  "value": "LGA1700"},
                                     {"label": "LGA1200",  "value": "LGA1200"},
                                     {"label": "LGA1151",  "value": "LGA1151"},
                                 ],
                                 value="Any", clearable=False, style=dd),
                ], md=3),
                dbc.Col([
                    _label("Time Range (sold)"),
                    dcc.Slider(id="time-slider", min=0, max=90, step=None, value=30,
                               marks={0: "All", 7: "7d", 14: "14d",
                                      30: "30d", 60: "60d", 90: "90d"}),
                ], md=4, className="pt-1"),
                dbc.Col(
                    dbc.Button("🔍 Search", id="search-btn",
                               style={"backgroundColor": COLORS["accent"],
                                      "border": "none", "color": "#0a0c10",
                                      "fontWeight": "700", "marginTop": "22px",
                                      "width": "100%"},
                               className="px-4"),
                    md=2,
                ),
            ], className="g-3"),
        ])
    ], className="chart-card mb-3")

    return dbc.Container([
        controls,
        html.Div(id="lookup-results"),
    ], fluid=True, className="px-0")


# ---------------------------------------------------------------------------
# Section 3 — Build Recommendations
# ---------------------------------------------------------------------------

def score_combos(df: pd.DataFrame) -> list[dict]:
    """Return scored list of (cpu, gpu) combos sorted descending by score."""
    if df.empty:
        return []

    tmp = df.dropna(subset=["gpu", "cpu"]).copy()
    if tmp.empty:
        return []

    results = []
    for (cpu, gpu), grp in tmp.groupby(["cpu", "gpu"]):
        total  = len(grp)
        if total < 3:
            continue

        sold_grp   = grp[grp["status"] == "sold"]
        active_grp = grp[grp["status"] == "active"]
        sold_count  = len(sold_grp)
        active_count = len(active_grp)

        sell_through  = sold_count / total
        volume_score  = min(total / 20, 1.0)

        # Most common RAM / storage in this combo
        common_ram     = grp["ram_gb"].mode()[0] if not grp["ram_gb"].dropna().empty else 16
        common_storage = (grp["storage"].dropna().mode()[0]
                          if not grp["storage"].dropna().empty else "1TB SSD")

        avg_sold_price = sold_grp["price"].dropna().mean() if sold_count else None
        build_cost     = estimate_build_cost(gpu, cpu, common_ram, common_storage)

        if avg_sold_price and build_cost and avg_sold_price > 0:
            margin_raw   = (avg_sold_price - build_cost) / avg_sold_price
            margin_score = max(0.0, min(margin_raw, 1.0))
        else:
            margin_raw   = None
            margin_score = 0.3  # neutral

        # Speed
        days_series = sold_grp["days_to_sell"].dropna()
        if not days_series.empty:
            avg_days    = float(days_series.mean())
            speed_score = 1 / (1 + avg_days / 14)
        else:
            avg_days    = None
            speed_score = 0.5

        competition_score = 1 / (1 + active_count)

        final_score = int(round(
            sell_through      * 35 +
            volume_score      * 15 +
            margin_score      * 25 +
            speed_score       * 15 +
            competition_score * 10
        ))

        # Tag
        if sell_through >= 0.8 and active_count <= 2:
            tag = "🔥 High Demand Low Competition"
        elif final_score >= 85:
            tag = "🔥 High Demand"
        elif active_count == 0:
            tag = "🎯 Zero Competition"
        elif margin_raw and margin_raw > 0.35:
            tag = "💰 Best Margin"
        elif avg_days and avg_days <= 7:
            tag = "⚡ Fastest Seller"
        else:
            tag = "📈 Solid Pick"

        # Avoid tag
        if sell_through < 0.3:
            avoid_tag = "🐌 Slow Mover"
        elif active_count >= 5:
            avoid_tag = "⚠️ Oversaturated"
        elif avg_days and avg_days > 30:
            avoid_tag = "📦 Long Shelf Life"
        else:
            avoid_tag = "❌ Poor ROI"

        results.append(dict(
            cpu=cpu, gpu=gpu,
            combo=f"{cpu} + {gpu}",
            score=final_score,
            total=total,
            sold_count=sold_count,
            active_count=active_count,
            sell_through=sell_through,
            avg_sold_price=avg_sold_price,
            build_cost=build_cost,
            margin_raw=margin_raw,
            avg_days=avg_days,
            common_ram=common_ram,
            common_storage=common_storage,
            tag=tag,
            avoid_tag=avoid_tag,
        ))

    results.sort(key=lambda x: x["score"], reverse=True)
    return results


def reco_card(r: dict, rank: int) -> dbc.Card:
    profit_usd = (
        round(r["avg_sold_price"] - r["build_cost"], 0)
        if r["avg_sold_price"] and r["build_cost"] else None
    )
    profit_pct = (
        round(r["margin_raw"] * 100, 1) if r["margin_raw"] is not None else None
    )

    def stat(label, value):
        return dbc.Col([
            html.Div(label, style={"color": COLORS["muted"], "fontSize": "11px",
                                   "textTransform": "uppercase", "letterSpacing": "1px"}),
            html.Div(value, style={"color": COLORS["text"], "fontWeight": "bold",
                                   "fontSize": "15px"}),
        ], xs=6, md=3, className="mb-2")

    return dbc.Card([
        dbc.CardHeader(
            dbc.Row([
                dbc.Col([
                    html.Span(f"#{rank}",
                              style={"color": COLORS["muted"],
                                     "fontWeight": "700", "fontSize": "13px",
                                     "marginRight": "10px"}),
                    html.Span(r["combo"],
                              style={"color": COLORS["text"],
                                     "fontWeight": "700", "fontSize": "15px"}),
                ], width=10),
                dbc.Col(html.Span(f"{r['score']}/100", style={
                    "display": "inline-block",
                    "padding": "4px 10px", "borderRadius": "999px",
                    "backgroundColor": f"{COLORS['accent']}22",
                    "color": COLORS["accent"],
                    "border": f"1px solid {COLORS['accent']}55",
                    "fontSize": "12px", "fontWeight": "700",
                }), width=2, className="text-end"),
            ], align="center"),
            style={"backgroundColor": COLORS["card_alt"],
                   "borderBottom": f"1px solid {COLORS['border']}",
                   "borderRadius": "12px 12px 0 0"}
        ),
        dbc.CardBody([
            dbc.Row([
                stat("Est. Build Cost",
                     f"${r['build_cost']:,.0f}" if r["build_cost"] else "N/A"),
                stat("Avg Sold Price",
                     f"${r['avg_sold_price']:,.0f}" if r["avg_sold_price"] else "N/A"),
                stat("Est. Profit",
                     f"${profit_usd:,.0f} ({profit_pct}%)"
                     if profit_usd is not None else "N/A"),
                stat("Sell-Through",
                     f"{r['sell_through']*100:.0f}%"),
                stat("Avg Days to Sell",
                     f"{r['avg_days']:.1f}d" if r["avg_days"] is not None else "N/A"),
                stat("Active Competitors", str(r["active_count"])),
                stat("Total Listings", str(r["total"])),
                stat("RAM / Storage",
                     f"{int(r['common_ram']) if r['common_ram'] else '?'}GB / "
                     f"{r['common_storage'] or '?'}"),
            ]),
            html.Span(r["tag"], style={
                "display": "inline-block",
                "padding": "5px 12px", "borderRadius": "999px",
                "backgroundColor": f"{COLORS['accent']}1a",
                "color": COLORS["accent"],
                "border": f"1px solid {COLORS['accent']}44",
                "fontSize": "12px", "fontWeight": "600",
                "marginTop": "10px",
            }),
        ]),
    ], className="reco-card")


def avoid_card(r: dict) -> dbc.Card:
    return dbc.Card([
        dbc.CardBody(
            dbc.Row([
                dbc.Col(html.Span(r["combo"],
                                  style={"color": COLORS["danger"], "fontWeight": "700"}), md=6),
                dbc.Col([
                    html.Span(f"Score {r['score']}/100  · ",
                              style={"color": COLORS["muted"], "fontSize": "12px"}),
                    html.Span(f"Sell-through {r['sell_through']*100:.0f}%  · ",
                              style={"color": COLORS["muted"], "fontSize": "12px"}),
                    html.Span(f"{r['active_count']} active",
                              style={"color": COLORS["muted"], "fontSize": "12px"}),
                ], md=4),
                dbc.Col(dbc.Badge(r["avoid_tag"], color="danger",
                                  style={"fontSize": "12px"}), md=2, className="text-end"),
            ], align="center")
        )
    ], className="avoid-card")


def make_recommendations_section(df: pd.DataFrame):
    scored = score_combos(df)
    total_sold = int((df["status"] == "sold").sum()) if not df.empty else 0

    summary = dbc.Alert(
        f"📊 Based on {total_sold} sold listings analyzed, here are the builds "
        f"most likely to sell quickly at a good margin."
        if total_sold else "No sold listings available yet — run the scraper first.",
        style={"backgroundColor": COLORS["card"],
               "border": f"1px solid {COLORS['border']}",
               "borderLeft": f"3px solid {COLORS['accent']}",
               "color": COLORS["text"], "borderRadius": "10px"},
        className="mb-4",
    )

    if not scored:
        return dbc.Container([
            summary,
            dbc.Alert("Not enough data to generate recommendations. "
                      "Need at least 3 listings per combo.",
                      color="warning"),
        ], fluid=True, className="px-0")

    top5   = scored[:5]
    bottom = scored[-3:] if len(scored) >= 3 else []
    # Make sure bottom doesn't overlap with top5
    top5_combos = {r["combo"] for r in top5}
    bottom = [r for r in reversed(scored) if r["combo"] not in top5_combos][:3]

    top_cards = [reco_card(r, i+1) for i, r in enumerate(top5)]

    avoid_section = []
    if bottom:
        avoid_section = [
            html.Hr(style={"borderColor": COLORS["border"], "marginTop": "30px"}),
            html.H4("🚫 Builds to Avoid",
                    style={"color": COLORS["danger"], "marginBottom": "16px",
                           "fontWeight": "700"}),
            html.P("These combos showed poor sell-through, heavy competition, or long days on market.",
                   style={"color": COLORS["muted"]}),
            *[avoid_card(r) for r in bottom],
        ]

    return dbc.Container(
        [summary] + top_cards + avoid_section,
        fluid=True, className="px-0"
    )


# ---------------------------------------------------------------------------
# App initialisation
# ---------------------------------------------------------------------------

app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.CYBORG],
    suppress_callback_exceptions=True,
)
app.title = "Jawa.gg Market Trends — AstroLabPCs"

# Expose Flask server for gunicorn (required for Render/production hosting)
server = app.server

app.index_string = """<!DOCTYPE html>
<html>
  <head>
    {%metas%}
    <title>{%title%}</title>
    {%favicon%}
    {%css%}
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
      :root {
        --bg: #0a0c10;
        --card: #14171c;
        --card-alt: #1c2128;
        --border: #2d333b;
        --accent: #14d991;
        --accent-2: #2dd4bf;
        --sold: #14d991;
        --active: #f59e0b;
        --text: #e6edf3;
        --muted: #7d8590;
      }
      html, body {
        background-color: var(--bg) !important;
        color: var(--text);
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        font-feature-settings: "cv02", "cv11";
        -webkit-font-smoothing: antialiased;
      }
      h1, h2, h3, h4, h5 { font-family: 'Inter', sans-serif; letter-spacing: -0.01em; }

      /* ── Cards ──────────────────────────────────────────────────────── */
      .chart-card {
        background-color: var(--card) !important;
        border: 1px solid var(--border) !important;
        border-radius: 12px !important;
        padding: 6px;
        transition: border-color 0.18s ease, transform 0.18s ease;
      }
      .chart-card:hover { border-color: #394149 !important; }

      .kpi-card {
        background: linear-gradient(145deg, var(--card) 0%, var(--card-alt) 100%) !important;
        border: 1px solid var(--border) !important;
        border-radius: 12px !important;
        text-align: center;
        height: 100%;
        transition: transform 0.15s ease, border-color 0.15s ease;
      }
      .kpi-card:hover { transform: translateY(-2px); border-color: var(--accent) !important; }
      .kpi-label {
        color: var(--muted);
        font-size: 11px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        margin-bottom: 6px;
      }
      .kpi-value { font-size: 22px; font-weight: 700; line-height: 1.1; }

      .reco-card {
        background-color: var(--card) !important;
        border: 1px solid var(--border) !important;
        border-left: 3px solid var(--accent) !important;
        border-radius: 12px;
        margin-bottom: 14px;
        transition: transform 0.18s ease, border-color 0.18s ease;
      }
      .reco-card:hover { transform: translateY(-2px); }
      .avoid-card {
        background-color: var(--card) !important;
        border: 1px solid var(--border) !important;
        border-left: 3px solid #f87171 !important;
        border-radius: 12px;
        margin-bottom: 10px;
      }

      /* ── Headers ─────────────────────────────────────────────────────── */
      .section-header {
        color: var(--text);
        font-size: 1.35rem;
        font-weight: 700;
        margin: 28px 0 18px;
        display: flex;
        align-items: center;
        gap: 10px;
      }
      .section-header::before {
        content: "";
        display: inline-block;
        width: 4px;
        height: 22px;
        border-radius: 2px;
        background: var(--accent);
      }

      /* ── Brand legend chips ──────────────────────────────────────────── */
      .brand-legend {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 14px;
        padding: 10px 14px;
        background: var(--card);
        border: 1px solid var(--border);
        border-radius: 10px;
      }
      .brand-legend-title {
        color: var(--muted);
        font-size: 11px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.08em;
      }
      .brand-chip { display: inline-flex; align-items: center; gap: 6px; }
      .brand-dot {
        display: inline-block;
        width: 10px;
        height: 10px;
        border-radius: 50%;
        box-shadow: 0 0 0 1px var(--border);
      }
      .brand-label { color: var(--text); font-size: 12px; font-weight: 500; }
      .brand-sep { color: var(--border); margin: 0 4px; }

      /* ── Form controls ───────────────────────────────────────────────── */
      .Select-control, .Select-menu-outer, .VirtualizedSelectOption {
        background-color: var(--card) !important;
        border-color: var(--border) !important;
      }
      .Select-value-label, .Select-placeholder { color: var(--text) !important; }
      .rc-slider-track { background-color: var(--accent) !important; }
      .rc-slider-handle {
        border-color: var(--accent) !important;
        background-color: var(--card) !important;
      }
      .rc-slider-dot-active { border-color: var(--accent) !important; }

      /* ── Data table ──────────────────────────────────────────────────── */
      .dash-table-container .dash-spreadsheet-container .dash-spreadsheet-inner td,
      .dash-table-container .dash-spreadsheet-container .dash-spreadsheet-inner th {
        background-color: var(--card) !important;
        color: var(--text) !important;
        border-color: var(--border) !important;
      }

      /* ── Plotly modebar ──────────────────────────────────────────────── */
      .modebar {
        background: var(--card) !important;
        border: 1px solid var(--border) !important;
        border-radius: 6px !important;
      }
      .modebar-btn path { fill: var(--muted) !important; }
      .modebar-btn:hover path, .modebar-btn.active path { fill: var(--accent) !important; }

      /* ── Scrollbar ───────────────────────────────────────────────────── */
      ::-webkit-scrollbar { width: 10px; height: 10px; }
      ::-webkit-scrollbar-track { background: var(--bg); }
      ::-webkit-scrollbar-thumb { background: var(--border); border-radius: 5px; }
      ::-webkit-scrollbar-thumb:hover { background: #3d444c; }
    </style>
  </head>
  <body>
    {%app_entry%}
    <footer>
      {%config%}
      {%scripts%}
      {%renderer%}
    </footer>
  </body>
</html>"""

# ---------------------------------------------------------------------------
# Load data once at startup for static sections
# ---------------------------------------------------------------------------

_df = load_data()

# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

def header():
    return html.Div([
        html.Div([
            html.Span("J", style={
                "display": "inline-flex",
                "alignItems": "center",
                "justifyContent": "center",
                "width": "40px", "height": "40px",
                "borderRadius": "10px",
                "background": f"linear-gradient(135deg, {COLORS['accent']} 0%, {COLORS['accent_2']} 100%)",
                "color": "#0a0c10",
                "fontWeight": "900", "fontSize": "22px",
                "marginRight": "14px",
            }),
            html.Div([
                html.H1("Jawa.gg PC Market Trends",
                        style={"color": COLORS["text"], "fontWeight": "800",
                               "fontSize": "1.8rem", "marginBottom": "2px",
                               "letterSpacing": "-0.02em"}),
                html.P("AstroLabPCs Research Dashboard",
                       style={"color": COLORS["muted"], "fontSize": "0.9rem",
                              "marginBottom": "0", "letterSpacing": "0.02em"}),
            ]),
        ], style={"display": "flex", "alignItems": "center"}),
        html.Div(style={"height": "1px", "background": COLORS["border"],
                        "marginTop": "18px"}),
    ])


def section_title(icon, text):
    return html.H2(f"{icon} {text}", className="section-header")


app.layout = dbc.Container(
    fluid=True,
    style={"backgroundColor": COLORS["bg"], "minHeight": "100vh", "padding": "20px 30px"},
    children=[
        header(),

        section_title("📊", "Section 1 — Market Trends"),
        make_trends_section(_df),

        html.Hr(style={"borderColor": COLORS["border"], "margin": "30px 0"}),

        section_title("🔍", "Section 2 — Spec Lookup Tool"),
        make_lookup_section(_df),

        html.Hr(style={"borderColor": COLORS["border"], "margin": "30px 0"}),

        section_title("🤖", "Section 3 — What Should I Build Next?"),
        make_recommendations_section(_df),

        html.Div(style={"height": "60px"}),
    ]
)


# ---------------------------------------------------------------------------
# Section 2 callback — Spec Lookup
# ---------------------------------------------------------------------------

@app.callback(
    Output("lookup-results", "children"),
    Input("search-btn", "n_clicks"),
    State("gpu-filter", "value"),
    State("cpu-filter", "value"),
    State("ram-filter", "value"),
    State("storage-filter", "value"),
    State("color-filter", "value"),
    State("gpu-gen-filter", "value"),
    State("socket-filter", "value"),
    State("time-slider", "value"),
    prevent_initial_call=True,
)
def run_lookup(n_clicks, gpu_sel, cpu_sel, ram_sel, storage_sel,
               color_sel, gpu_gen_sel, socket_sel, days):
    df = load_data()
    if df.empty:
        return dbc.Alert("No data found. Make sure jawa_listings.csv exists.",
                         color="warning")

    mask = pd.Series([True] * len(df), index=df.index)

    if gpu_sel and gpu_sel != "Any":
        mask &= df["gpu"].str.contains(gpu_sel, case=False, na=False)

    if cpu_sel and cpu_sel != "Any":
        mask &= df["cpu"].str.contains(cpu_sel, case=False, na=False)

    if ram_sel and ram_sel != "Any":
        try:
            mask &= df["ram_gb"] == int(ram_sel)
        except ValueError:
            pass

    if storage_sel and storage_sel != "Any":
        mask &= df["storage"].str.contains(
            re.escape(storage_sel), case=False, na=False
        )

    if color_sel and color_sel != "Any" and "color" in df.columns:
        mask &= df["color"].str.lower() == color_sel.lower()

    if gpu_gen_sel and gpu_gen_sel != "Any":
        mask &= df["gpu"].apply(gpu_generation) == gpu_gen_sel

    if socket_sel and socket_sel != "Any":
        mask &= df["cpu"].apply(cpu_socket) == socket_sel

    matched = df[mask].copy()

    # Apply time filter only to sold rows
    sold_mask = matched["status"] == "sold"
    if days and days > 0 and "date_sold" in matched.columns:
        cutoff = datetime.now(timezone.utc) - timedelta(days=int(days))
        time_ok = matched["date_sold"].isna() | (matched["date_sold"] >= cutoff)
        sold_mask = sold_mask & time_ok

    sold_rows   = matched[matched["status"] == "sold"][sold_mask[matched["status"] == "sold"]] \
        if days and days > 0 else matched[matched["status"] == "sold"]
    active_rows = matched[matched["status"] == "active"]

    avg_sold   = sold_rows["price"].dropna().mean()   if not sold_rows.empty else None
    avg_active = active_rows["price"].dropna().mean() if not active_rows.empty else None

    if avg_sold and avg_active:
        diff      = avg_active - avg_sold
        diff_color = COLORS["danger"] if diff > 0 else COLORS["accent"]
        diff_str  = f"+${diff:,.0f}" if diff > 0 else f"-${abs(diff):,.0f}"
        diff_note = "above" if diff > 0 else "below"
        diff_display = html.Span(
            f"{diff_str} ({diff_note} recent sold avg)",
            style={"color": diff_color, "fontWeight": "700"}
        )
    else:
        diff_display = html.Span("N/A", style={"color": COLORS["muted"]})

    def stat_card(label, value, color=COLORS["accent"]):
        return dbc.Col(dbc.Card(
            dbc.CardBody([
                html.Div(label, className="kpi-label"),
                html.Div(value, className="kpi-value", style={"color": color}),
            ]),
            className="kpi-card"
        ), xs=6, md=3, className="mb-3")

    stats_row = dbc.Row([
        stat_card("Avg Sold Price",
                  f"${avg_sold:,.0f}" if avg_sold else "N/A", COLORS["sold"]),
        stat_card("Avg Active Price",
                  f"${avg_active:,.0f}" if avg_active else "N/A", COLORS["active"]),
        stat_card("Price Difference", diff_display),
        stat_card("Matched Listings",
                  f"{len(sold_rows)} sold · {len(active_rows)} active",
                  COLORS["gold"]),
    ], className="g-3")

    # Table
    display_cols = ["title", "price", "status", "gpu", "cpu", "ram_gb", "storage", "color", "url"]
    table_df = matched[
        [c for c in display_cols if c in matched.columns]
    ].head(100).copy()
    table_df["price"] = table_df["price"].apply(
        lambda x: f"${x:,.0f}" if pd.notna(x) else ""
    )

    table = dash_table.DataTable(
        data=table_df.to_dict("records"),
        columns=[
            {"name": c.replace("_", " ").title(), "id": c,
             **({"presentation": "markdown"} if c == "url" else {})}
            for c in table_df.columns
        ],
        style_table={"overflowX": "auto"},
        style_header={
            "backgroundColor": COLORS["card_alt"], "color": COLORS["accent"],
            "fontWeight": "700", "border": f"1px solid {COLORS['border']}",
            "textTransform": "uppercase", "letterSpacing": "0.06em",
            "fontSize": "11px",
        },
        style_cell={
            "backgroundColor": COLORS["card"], "color": COLORS["text"],
            "border": f"1px solid {COLORS['border']}", "padding": "10px",
            "maxWidth": "300px", "overflow": "hidden",
            "textOverflow": "ellipsis", "fontFamily": "Inter, sans-serif",
        },
        style_data_conditional=[
            {"if": {"filter_query": '{status} = "sold"'},
             "color": COLORS["sold"]},
            {"if": {"filter_query": '{status} = "active"'},
             "color": COLORS["active"]},
            {"if": {"row_index": "odd"}, "backgroundColor": COLORS["card_alt"]},
        ],
        page_size=20,
        sort_action="native",
        filter_action="native",
        tooltip_data=[
            {c: {"value": str(row.get(c, "")), "type": "markdown"}
             for c in table_df.columns}
            for row in table_df.to_dict("records")
        ],
        tooltip_duration=None,
    )

    if matched.empty:
        return dbc.Alert(
            "No listings match the selected filters.",
            style={"backgroundColor": COLORS["card"],
                   "border": f"1px solid {COLORS['border']}",
                   "color": COLORS["muted"], "borderRadius": "10px"}
        )

    return html.Div([
        stats_row,
        dbc.Card(dbc.CardBody(table), className="chart-card mt-2"),
    ])


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8050))
    app.run(debug=False, host="0.0.0.0", port=port)

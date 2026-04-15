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

COLORS = {
    "bg":       "#0d0d0d",
    "card":     "#1a1a1a",
    "border":   "#2a2a2a",
    "accent":   "#00e5ff",
    "sold":     "#00e5ff",
    "active":   "#ff6b6b",
    "gold":     "#ffd700",
    "text":     "#e0e0e0",
    "muted":    "#888888",
}

FIG_LAYOUT = dict(
    template="plotly_dark",
    paper_bgcolor=COLORS["card"],
    plot_bgcolor="#111111",
    font_color=COLORS["text"],
    margin=dict(l=10, r=10, t=40, b=10),
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
    "scrollZoom": True,
}


def chart_card(fig, height=320):
    return dbc.Card(
        dcc.Graph(figure=fig, config=GRAPH_CONFIG,
                  style={"height": f"{height}px"}),
        className="chart-card mb-3"
    )


def make_trends_section(df: pd.DataFrame):
    sold   = df[df["status"] == "sold"]
    active = df[df["status"] == "active"]

    # ── Row 1: Top 10 GPUs / CPUs ──────────────────────────────────────────
    def top10_bar(col, color, title):
        if df.empty or col not in df.columns:
            return no_data_fig(title)
        counts = (df[col].dropna()
                         .value_counts()
                         .head(10)
                         .sort_values())
        fig = go.Figure(go.Bar(
            x=counts.values, y=counts.index,
            orientation="h",
            marker_color=color,
            hovertemplate="%{y}: %{x} listings<extra></extra>",
        ))
        fig.update_layout(**FIG_LAYOUT, title=title,
                          xaxis_title="Listings", yaxis_title="")
        return fig

    gpu_fig = top10_bar("gpu", COLORS["accent"], "Top 10 GPUs by Listings")
    cpu_fig = top10_bar("cpu", COLORS["active"],  "Top 10 CPUs by Listings")

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
            if not prices.empty:
                fig.add_trace(go.Histogram(
                    x=prices, name=label,
                    marker_color=color, opacity=0.7,
                    xbins=dict(size=100),
                    hovertemplate="$%{x}: %{y} listings<extra></extra>",
                ))
        fig.update_layout(**FIG_LAYOUT, barmode="overlay",
                          title="Price Distribution ($100 bins)",
                          xaxis_title="Price ($)", yaxis_title="Count",
                          legend=dict(orientation="h", y=1.02))
        return fig

    # ── Row 3: Avg price by GPU + Sold vs Active pie ───────────────────────
    def avg_price_fig():
        if sold.empty or "gpu" not in sold.columns:
            return no_data_fig("Avg Sold Price by GPU")
        avg = (sold.dropna(subset=["gpu","price"])
                   .groupby("gpu")["price"].mean()
                   .sort_values(ascending=False))
        fig = go.Figure(go.Bar(
            x=avg.values, y=avg.index,
            orientation="h",
            marker_color=COLORS["gold"],
            hovertemplate="%{y}: $%{x:,.0f}<extra></extra>",
        ))
        fig.update_layout(**FIG_LAYOUT, title="Avg Sold Price by GPU",
                          xaxis_title="Avg Price ($)", yaxis_title="")
        return fig

    def pie_fig():
        if df.empty:
            return no_data_fig("Sold vs Active")
        counts = df["status"].value_counts()
        fig = go.Figure(go.Pie(
            labels=counts.index.str.capitalize(),
            values=counts.values,
            hole=0.5,
            marker_colors=[COLORS["sold"], COLORS["active"]],
            hovertemplate="%{label}: %{value} (%{percent})<extra></extra>",
        ))
        fig.update_layout(**FIG_LAYOUT, title="Sold vs Active Ratio",
                          legend=dict(orientation="h", y=-0.1))
        return fig

    # ── Row 4: Price range breakdown ───────────────────────────────────────
    def price_range_fig():
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
        dbc.Row([
            dbc.Col(chart_card(gpu_fig), md=6),
            dbc.Col(chart_card(cpu_fig), md=6),
        ]),
        dbc.Row([
            dbc.Col(chart_card(combo_fig(), height=380), md=7),
            dbc.Col(chart_card(price_dist_fig()), md=5),
        ]),
        dbc.Row([
            dbc.Col(chart_card(avg_price_fig(), height=380), md=8),
            dbc.Col(chart_card(pie_fig()), md=4),
        ]),
        dbc.Row([
            dbc.Col(chart_card(price_range_fig(), height=300), md=12),
        ]),
    ], fluid=True, className="px-0")


# ---------------------------------------------------------------------------
# Section 2 — Spec Lookup Tool
# ---------------------------------------------------------------------------

def make_lookup_section(df: pd.DataFrame):
    gpus = sorted(df["gpu"].dropna().unique().tolist()) if "gpu" in df.columns else []
    cpus = sorted(df["cpu"].dropna().unique().tolist()) if "cpu" in df.columns else []

    dropdown_style = {"backgroundColor": "#1a1a1a", "color": COLORS["text"]}

    controls = dbc.Card([
        dbc.CardBody([
            dbc.Row([
                dbc.Col([
                    html.Label("GPU", style={"color": COLORS["accent"], "fontWeight": "bold"}),
                    dcc.Dropdown(
                        id="gpu-filter",
                        options=[{"label": "Any", "value": "Any"}] +
                                [{"label": g, "value": g} for g in gpus],
                        value="Any", clearable=False,
                        style=dropdown_style,
                    ),
                ], md=3),
                dbc.Col([
                    html.Label("CPU", style={"color": COLORS["accent"], "fontWeight": "bold"}),
                    dcc.Dropdown(
                        id="cpu-filter",
                        options=[{"label": "Any", "value": "Any"}] +
                                [{"label": c, "value": c} for c in cpus],
                        value="Any", clearable=False,
                        style=dropdown_style,
                    ),
                ], md=3),
                dbc.Col([
                    html.Label("RAM", style={"color": COLORS["accent"], "fontWeight": "bold"}),
                    dcc.Dropdown(
                        id="ram-filter",
                        options=[{"label": "Any", "value": "Any"},
                                 {"label": "8 GB",  "value": "8"},
                                 {"label": "16 GB", "value": "16"},
                                 {"label": "32 GB", "value": "32"},
                                 {"label": "64 GB", "value": "64"}],
                        value="Any", clearable=False,
                        style=dropdown_style,
                    ),
                ], md=2),
                dbc.Col([
                    html.Label("Storage", style={"color": COLORS["accent"], "fontWeight": "bold"}),
                    dcc.Dropdown(
                        id="storage-filter",
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
                        value="Any", clearable=False,
                        style=dropdown_style,
                    ),
                ], md=2),
                dbc.Col([
                    html.Label("Time Range (sold)",
                               style={"color": COLORS["accent"], "fontWeight": "bold"}),
                    dcc.Slider(
                        id="time-slider", min=0, max=90,
                        step=None, value=30,
                        marks={0: "All", 7: "7d", 14: "14d",
                               30: "30d", 60: "60d", 90: "90d"},
                    ),
                ], md=2, className="pt-1"),
            ]),
            dbc.Row([
                dbc.Col(
                    dbc.Button("🔍 Search", id="search-btn", color="info",
                               className="mt-3 px-4"),
                    width="auto"
                ),
            ]),
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
                dbc.Col(html.Span(f"#{rank}  {r['combo']}",
                                  style={"color": COLORS["accent"],
                                         "fontWeight": "bold", "fontSize": "15px"}), width=10),
                dbc.Col(dbc.Badge(f"{r['score']}/100", color="info",
                                  style={"fontSize": "13px"}), width=2,
                        className="text-end"),
            ], align="center"),
            style={"backgroundColor": "#1f1f1f", "borderBottom": f"1px solid {COLORS['border']}"}
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
            dbc.Badge(r["tag"], color="info",
                      style={"fontSize": "13px", "marginTop": "6px"}),
        ]),
    ], className="reco-card")


def avoid_card(r: dict) -> dbc.Card:
    return dbc.Card([
        dbc.CardBody(
            dbc.Row([
                dbc.Col(html.Span(r["combo"],
                                  style={"color": "#ff6b6b", "fontWeight": "bold"}), md=6),
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
        color="info",
        style={"backgroundColor": "#0a2a35", "border": f"1px solid {COLORS['accent']}",
               "color": COLORS["text"]},
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
            html.Hr(style={"borderColor": "#ff6b6b44", "marginTop": "30px"}),
            html.H4("🚫 Builds to Avoid",
                    style={"color": "#ff6b6b", "marginBottom": "16px"}),
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
    <style>
      body { background-color: #0d0d0d !important; color: #e0e0e0; }
      .chart-card {
        background-color: #1a1a1a !important;
        border: 1px solid #2a2a2a !important;
        border-radius: 8px;
        padding: 10px;
      }
      .stat-card {
        background-color: #1a1a1a;
        border: 1px solid #333;
        border-radius: 8px;
        padding: 16px;
        text-align: center;
        height: 100%;
      }
      .reco-card {
        background-color: #1a1a1a !important;
        border: 1px solid #00e5ff44 !important;
        border-radius: 10px;
        margin-bottom: 14px;
      }
      .avoid-card {
        background-color: #1a1a1a !important;
        border: 1px solid #ff6b6b44 !important;
        border-radius: 8px;
        margin-bottom: 10px;
      }
      .section-header {
        color: #00e5ff;
        font-size: 1.4rem;
        font-weight: 700;
        margin-bottom: 16px;
        margin-top: 8px;
        letter-spacing: 0.5px;
      }
      .Select-control { background-color: #1a1a1a !important; }
      .dash-table-container .dash-spreadsheet-container .dash-spreadsheet-inner td,
      .dash-table-container .dash-spreadsheet-container .dash-spreadsheet-inner th {
        background-color: #1a1a1a !important;
        color: #e0e0e0 !important;
        border-color: #333 !important;
      }
      .rc-slider-track { background-color: #00e5ff !important; }
      .rc-slider-handle { border-color: #00e5ff !important; }
      /* Modebar dark theme */
      .modebar { background: #1a1a1a !important; border: 1px solid #2a2a2a !important; border-radius: 6px !important; }
      .modebar-btn path { fill: #888 !important; }
      .modebar-btn:hover path { fill: #00e5ff !important; }
      .modebar-btn.active path { fill: #00e5ff !important; }
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
        html.H1("Jawa.gg PC Market Trends",
                style={"color": COLORS["accent"], "fontWeight": "900",
                       "fontSize": "2rem", "marginBottom": "4px"}),
        html.P("AstroLabPCs Research Dashboard",
               style={"color": COLORS["muted"], "fontSize": "1rem",
                      "marginBottom": "0"}),
        html.Hr(style={"borderColor": "#333", "marginTop": "12px"}),
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

        html.Hr(style={"borderColor": "#333", "margin": "30px 0"}),

        section_title("🔍", "Section 2 — Spec Lookup Tool"),
        make_lookup_section(_df),

        html.Hr(style={"borderColor": "#333", "margin": "30px 0"}),

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
    State("time-slider", "value"),
    prevent_initial_call=True,
)
def run_lookup(n_clicks, gpu_sel, cpu_sel, ram_sel, storage_sel, days):
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
        diff_color = "#ff6b6b" if diff > 0 else "#00e5ff"
        diff_str  = f"+${diff:,.0f}" if diff > 0 else f"-${abs(diff):,.0f}"
        diff_note = "above" if diff > 0 else "below"
        diff_display = html.Span(
            f"{diff_str} ({diff_note} recent sold avg)",
            style={"color": diff_color, "fontWeight": "bold"}
        )
    else:
        diff_display = html.Span("N/A", style={"color": COLORS["muted"]})

    def stat_card(label, value, color=COLORS["accent"]):
        return dbc.Col(dbc.Card(
            dbc.CardBody([
                html.Div(label, style={"color": COLORS["muted"], "fontSize": "12px",
                                       "textTransform": "uppercase"}),
                html.Div(value, style={"color": color, "fontWeight": "bold",
                                       "fontSize": "22px", "marginTop": "4px"}),
            ]),
            className="chart-card"
        ), xs=6, md=3, className="mb-3")

    stats_row = dbc.Row([
        stat_card("Avg Sold Price",
                  f"${avg_sold:,.0f}" if avg_sold else "N/A", COLORS["sold"]),
        stat_card("Avg Active Price",
                  f"${avg_active:,.0f}" if avg_active else "N/A", COLORS["active"]),
        stat_card("Price Difference", diff_display),
        stat_card(f"Matched Listings",
                  f"{len(sold_rows)} sold · {len(active_rows)} active",
                  COLORS["gold"]),
    ])

    # Table
    display_cols = ["title", "price", "status", "gpu", "cpu", "ram_gb", "storage", "url"]
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
            "backgroundColor": "#111", "color": COLORS["accent"],
            "fontWeight": "bold", "border": "1px solid #333",
        },
        style_cell={
            "backgroundColor": "#1a1a1a", "color": COLORS["text"],
            "border": "1px solid #2a2a2a", "padding": "8px",
            "maxWidth": "300px", "overflow": "hidden",
            "textOverflow": "ellipsis",
        },
        style_data_conditional=[
            {"if": {"filter_query": '{status} = "sold"'},
             "color": COLORS["sold"]},
            {"if": {"filter_query": '{status} = "active"'},
             "color": COLORS["active"]},
            {"if": {"row_index": "odd"}, "backgroundColor": "#161616"},
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
            "No listings match the selected filters.", color="secondary",
            style={"backgroundColor": "#1a1a1a", "border": "1px solid #333",
                   "color": COLORS["muted"]}
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

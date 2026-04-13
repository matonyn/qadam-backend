"""
analytics/dashboard.py
──────────────────────
Analytics Dashboard for Smart Campus

Runs as a standalone Dash application.
Tabs:
  1. Overview       – KPIs, active users, review volume
  2. Sentiment      – Sentiment trends by venue category
  3. Crowd          – Heatmap of predicted crowd levels
  4. Adoption       – Feature usage funnel and DAU/MAU

Start: uvicorn analytics.dashboard:server --port 8050
  OR:  python -m analytics.dashboard
"""

from __future__ import annotations

import json
import random
from datetime import datetime, timedelta
from collections import defaultdict

import numpy as np
import pandas as pd

try:
    import plotly.graph_objects as go
    import plotly.express as px
    from plotly.subplots import make_subplots
    import dash
    from dash import dcc, html, Input, Output, callback
    import dash_bootstrap_components as dbc
    DASH_AVAILABLE = True
except ImportError:
    DASH_AVAILABLE = False

from config import CAMPUS_LOCATIONS, SENTIMENT_CATEGORIES, VENUES

# ─── Colour palette ────────────────────────────────────────────────────────────
PALETTE = {
    "bg":        "#0D1117",
    "surface":   "#161B22",
    "border":    "#30363D",
    "accent":    "#58A6FF",
    "positive":  "#3FB950",
    "neutral":   "#D29922",
    "negative":  "#F85149",
    "text":      "#E6EDF3",
    "subtext":   "#8B949E",
}

PLOTLY_TEMPLATE = dict(
    layout=go.Layout(
        paper_bgcolor=PALETTE["surface"],
        plot_bgcolor=PALETTE["surface"],
        font=dict(color=PALETTE["text"], family="'JetBrains Mono', monospace"),
        xaxis=dict(gridcolor=PALETTE["border"], linecolor=PALETTE["border"]),
        yaxis=dict(gridcolor=PALETTE["border"], linecolor=PALETTE["border"]),
        colorway=[PALETTE["accent"], PALETTE["positive"], PALETTE["negative"],
                  PALETTE["neutral"], "#BC8CFF", "#FF7B72"],
        margin=dict(l=30, r=30, t=40, b=30),
    )
)


# ─── Synthetic data layer (replace with real DB queries in production) ─────────

def _date_range(days: int = 60) -> list[datetime]:
    base = datetime.utcnow() - timedelta(days=days)
    return [base + timedelta(days=i) for i in range(days)]


def _gen_sentiment_trends() -> pd.DataFrame:
    dates = _date_range(60)
    rows = []
    for cat in SENTIMENT_CATEGORIES:
        base_pos = random.uniform(0.45, 0.70)
        for dt in dates:
            # Slight upward trend over time
            drift = (dt - dates[0]).days / 200
            pos = min(0.95, base_pos + drift + random.gauss(0, 0.04))
            neg = max(0.02, 1 - pos - random.uniform(0.05, 0.25))
            neu = 1 - pos - neg
            rows.append({"date": dt, "category": cat,
                          "positive": pos, "neutral": neu, "negative": neg,
                          "review_count": random.randint(5, 40)})
    return pd.DataFrame(rows)


def _gen_adoption_metrics() -> pd.DataFrame:
    dates = _date_range(60)
    rows = []
    for i, dt in enumerate(dates):
        base = 80 + i * 2.5
        rows.append({
            "date":      dt,
            "dau":       int(base + random.gauss(0, 8)),
            "mau":       int(base * 8 + random.gauss(0, 30)),
            "nav_uses":  int(base * 1.4 + random.gauss(0, 10)),
            "recs_used": int(base * 0.6 + random.gauss(0, 5)),
            "reviews":   int(base * 0.3 + random.gauss(0, 4)),
        })
    return pd.DataFrame(rows)


def _gen_crowd_snapshot() -> pd.DataFrame:
    rows = []
    for loc_id, loc_data in CAMPUS_LOCATIONS.items():
        x, y, label, cat, building, floors, capacity = loc_data
        weight = random.uniform(0.1, 0.95)
        rows.append({
            "location_id": loc_id, "x": x, "y": y,
            "label": label, "category": cat,
            "building": building, "floors": floors,
            "capacity": capacity, "weight": weight,
        })
    return pd.DataFrame(rows)


def _gen_kpis() -> dict:
    return {
        "total_users":   1247,
        "dau":           312,
        "reviews_today": 48,
        "avg_sentiment": 3.8,
        "nav_requests":  823,
        "uptime_pct":    99.7,
    }


# ─── Figure builders ───────────────────────────────────────────────────────────

def fig_sentiment_trends(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    cats = df["category"].unique()
    # One line per category – show positive % over time
    for cat in cats:
        sub = df[df["category"] == cat].sort_values("date")
        fig.add_trace(go.Scatter(
            x=sub["date"], y=(sub["positive"] * 100).round(1),
            mode="lines", name=cat,
            line=dict(width=2),
            hovertemplate="%{y:.1f}% positive<extra>" + cat + "</extra>",
        ))
    fig.update_layout(
        **PLOTLY_TEMPLATE["layout"].to_plotly_json(),
        title="Positive Sentiment % by Venue Category",
        yaxis_title="% Positive Reviews",
        xaxis_title="Date",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        height=360,
    )
    return fig


def fig_sentiment_distribution(df: pd.DataFrame) -> go.Figure:
    latest = df.sort_values("date").groupby("category").last().reset_index()
    fig = go.Figure()
    for sentiment, color in [("positive", PALETTE["positive"]),
                              ("neutral",  PALETTE["neutral"]),
                              ("negative", PALETTE["negative"])]:
        fig.add_trace(go.Bar(
            x=latest["category"], y=(latest[sentiment] * 100).round(1),
            name=sentiment.capitalize(),
            marker_color=color,
        ))
    fig.update_layout(
        **PLOTLY_TEMPLATE["layout"].to_plotly_json(),
        barmode="stack",
        title="Current Sentiment Mix by Category",
        yaxis_title="% Reviews",
        height=320,
    )
    return fig


def fig_crowd_heatmap(df: pd.DataFrame) -> go.Figure:
    color_scale = [
        [0.0, PALETTE["positive"]],
        [0.4, PALETTE["neutral"]],
        [1.0, PALETTE["negative"]],
    ]
    fig = go.Figure(go.Scatter(
        x=df["x"], y=df["y"],
        mode="markers+text",
        marker=dict(
            size=28,
            color=df["weight"],
            colorscale=color_scale,
            cmin=0, cmax=1,
            colorbar=dict(title="Crowd", tickformat=".0%"),
            line=dict(color=PALETTE["border"], width=1),
        ),
        text=df["label"].str.split().str[0],  # first word of label
        textposition="top center",
        textfont=dict(size=9, color=PALETTE["text"]),
        customdata=np.stack([df["label"], (df["weight"]*100).round(1), df["category"]], axis=1),
        hovertemplate=(
            "<b>%{customdata[0]}</b><br>"
            "Occupancy: %{customdata[1]}%<br>"
            "Type: %{customdata[2]}<extra></extra>"
        ),
    ))
    fig.update_layout(
        **PLOTLY_TEMPLATE["layout"].to_plotly_json(),
        title="Campus Crowd Map – Live Prediction",
        xaxis=dict(showticklabels=False, title=""),
        yaxis=dict(showticklabels=False, title=""),
        height=420,
    )
    return fig


def fig_adoption(df: pd.DataFrame) -> go.Figure:
    fig = make_subplots(rows=1, cols=2,
                        subplot_titles=["Daily Active Users", "Feature Usage (30-day)"])
    sub = df.tail(30)
    fig.add_trace(go.Scatter(
        x=sub["date"], y=sub["dau"], fill="tozeroy",
        mode="lines", name="DAU",
        line=dict(color=PALETTE["accent"], width=2),
        fillcolor="rgba(88,166,255,0.15)",
    ), row=1, col=1)

    # Funnel
    feature_totals = {
        "Navigation":      df["nav_uses"].sum(),
        "Recommendations": df["recs_used"].sum(),
        "Reviews":         df["reviews"].sum(),
    }
    fig.add_trace(go.Bar(
        x=list(feature_totals.keys()),
        y=list(feature_totals.values()),
        marker_color=[PALETTE["accent"], PALETTE["positive"], PALETTE["neutral"]],
        name="Total Uses",
    ), row=1, col=2)

    fig.update_layout(
        **PLOTLY_TEMPLATE["layout"].to_plotly_json(),
        showlegend=False,
        height=340,
    )
    return fig


def fig_review_volume(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure(go.Bar(
        x=df["date"].dt.strftime("%b %d"),
        y=df["review_count"],
        marker_color=PALETTE["accent"],
        opacity=0.8,
        name="Reviews",
    ))
    # Moving average
    ma = df["review_count"].rolling(7).mean()
    fig.add_trace(go.Scatter(
        x=df["date"].dt.strftime("%b %d"),
        y=ma, mode="lines", name="7-day MA",
        line=dict(color=PALETTE["neutral"], width=2, dash="dot"),
    ))
    fig.update_layout(
        **PLOTLY_TEMPLATE["layout"].to_plotly_json(),
        title="Review Volume Over Time",
        yaxis_title="Reviews per Day",
        height=280,
    )
    return fig


# ─── KPI cards ─────────────────────────────────────────────────────────────────

def kpi_card(title: str, value: str, delta: str = "", color: str = PALETTE["accent"]) -> dbc.Card:
    return dbc.Card([
        dbc.CardBody([
            html.P(title, className="mb-0",
                   style={"color": PALETTE["subtext"], "fontSize": "0.75rem", "letterSpacing": "0.08em"}),
            html.H3(value, className="mb-0 mt-1",
                    style={"color": color, "fontFamily": "'JetBrains Mono', monospace"}),
            html.Small(delta, style={"color": PALETTE["positive"] if "+" in delta else PALETTE["subtext"]}),
        ])
    ], style={
        "background": PALETTE["surface"],
        "border":     f"1px solid {PALETTE['border']}",
        "borderRadius": "8px",
    })


# ─── App layout ────────────────────────────────────────────────────────────────

def build_app() -> dash.Dash:
    if not DASH_AVAILABLE:
        raise ImportError("Dash / Plotly not installed. Run: pip install dash plotly dash-bootstrap-components")

    app = dash.Dash(
        __name__,
        external_stylesheets=[
            dbc.themes.DARKLY,
            "https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&display=swap",
        ],
        title="Smart Campus Analytics",
    )

    # Pre-load data
    sentiment_df = _gen_sentiment_trends()
    adoption_df  = _gen_adoption_metrics()
    crowd_df     = _gen_crowd_snapshot()
    kpis         = _gen_kpis()

    app.layout = dbc.Container([
        # Header
        dbc.Row([
            dbc.Col([
                html.H2("🎓 Smart Campus Analytics",
                        style={"color": PALETTE["text"],
                               "fontFamily": "'JetBrains Mono', monospace",
                               "fontWeight": 600}),
                html.P(f"Nazarbayev University · {datetime.utcnow().strftime('%B %Y')}",
                       style={"color": PALETTE["subtext"], "marginBottom": 0}),
            ], width=8),
            dbc.Col([
                dbc.Badge("● LIVE", color="success", className="me-2"),
                html.Small("Updates every 60s", style={"color": PALETTE["subtext"]}),
            ], width=4, className="d-flex align-items-center justify-content-end"),
        ], className="mb-4 pt-4"),

        # KPI Row
        dbc.Row([
            dbc.Col(kpi_card("Total Users",      f"{kpis['total_users']:,}", "+12 this week"), width=2),
            dbc.Col(kpi_card("Daily Active",     f"{kpis['dau']:,}",        "+8%"),           width=2),
            dbc.Col(kpi_card("Reviews Today",    f"{kpis['reviews_today']}", "+5"),            width=2),
            dbc.Col(kpi_card("Avg Sentiment",    f"{kpis['avg_sentiment']}/5",
                             "", PALETTE["positive"]),                                          width=2),
            dbc.Col(kpi_card("Nav Requests",     f"{kpis['nav_requests']:,}", "+23%"),         width=2),
            dbc.Col(kpi_card("Uptime",           f"{kpis['uptime_pct']}%",
                             "30-day", PALETTE["positive"]),                                    width=2),
        ], className="mb-4 g-2"),

        # Tabs
        dbc.Tabs([
            # ── Overview ───────────────────────────────────────────────────
            dbc.Tab(label="Overview", tab_id="overview", children=[
                dbc.Row([
                    dbc.Col(dcc.Graph(
                        figure=fig_adoption(adoption_df),
                        config={"displayModeBar": False},
                    ), width=8),
                    dbc.Col(dcc.Graph(
                        figure=fig_review_volume(
                            sentiment_df.groupby("date")["review_count"].sum().reset_index()
                        ),
                        config={"displayModeBar": False},
                    ), width=4),
                ], className="mt-3"),
            ]),

            # ── Sentiment ──────────────────────────────────────────────────
            dbc.Tab(label="Sentiment", tab_id="sentiment", children=[
                dbc.Row([
                    dbc.Col(dcc.Graph(
                        figure=fig_sentiment_trends(sentiment_df),
                        config={"displayModeBar": False},
                    ), width=8),
                    dbc.Col(dcc.Graph(
                        figure=fig_sentiment_distribution(sentiment_df),
                        config={"displayModeBar": False},
                    ), width=4),
                ], className="mt-3"),
                dbc.Row([
                    dbc.Col([
                        html.H6("Category Filter", style={"color": PALETTE["subtext"]}),
                        dcc.Dropdown(
                            id="category-filter",
                            options=[{"label": c.replace("_", " ").title(), "value": c}
                                     for c in SENTIMENT_CATEGORIES],
                            value=SENTIMENT_CATEGORIES[0],
                            style={"background": PALETTE["surface"], "color": "#000"},
                        ),
                    ], width=3),
                ], className="mt-2"),
            ]),

            # ── Crowd ──────────────────────────────────────────────────────
            dbc.Tab(label="Crowd Prediction", tab_id="crowd", children=[
                dbc.Row([
                    dbc.Col([
                        dcc.Interval(id="crowd-interval", interval=60_000),
                        dcc.Graph(
                            id="crowd-map",
                            figure=fig_crowd_heatmap(crowd_df),
                            config={"displayModeBar": False},
                        ),
                    ], width=8),
                    dbc.Col([
                        html.H6("Crowd Levels", style={"color": PALETTE["subtext"],
                                                        "marginTop": "1rem"}),
                        html.Div(id="crowd-legend", children=_crowd_legend(crowd_df)),
                    ], width=4),
                ], className="mt-3"),
            ]),

            # ── Adoption ───────────────────────────────────────────────────
            dbc.Tab(label="Adoption Metrics", tab_id="adoption", children=[
                dbc.Row([
                    dbc.Col([
                        dcc.Graph(
                            figure=_fig_dau_mau(adoption_df),
                            config={"displayModeBar": False},
                        ),
                    ], width=12),
                ], className="mt-3"),
            ]),

        ], id="tabs", active_tab="overview",
           style={"borderBottom": f"1px solid {PALETTE['border']}"}),

        dcc.Interval(id="refresh-interval", interval=60_000, n_intervals=0),

    ], fluid=True, style={"background": PALETTE["bg"], "minHeight": "100vh"})

    # ── Callbacks ──────────────────────────────────────────────────────────────

    @app.callback(
        Output("crowd-map",    "figure"),
        Output("crowd-legend", "children"),
        Input("crowd-interval", "n_intervals"),
    )
    def refresh_crowd(_):
        df = _gen_crowd_snapshot()   # swap with real CrowdPredictionEngine call
        return fig_crowd_heatmap(df), _crowd_legend(df)

    return app


# ─── Crowd legend helper ───────────────────────────────────────────────────────

def _crowd_legend(df: pd.DataFrame) -> list:
    rows = []
    for _, row in df.sort_values("weight", ascending=False).iterrows():
        pct   = int(row["weight"] * 100)
        color = (PALETTE["negative"] if pct >= 70 else
                 PALETTE["neutral"]  if pct >= 40 else
                 PALETTE["positive"])
        rows.append(
            dbc.Row([
                dbc.Col(html.Div(style={
                    "width": "10px", "height": "10px", "borderRadius": "50%",
                    "background": color, "marginTop": "4px",
                }), width=1),
                dbc.Col(html.Small(row["label"], style={"color": PALETTE["text"]}), width=8),
                dbc.Col(html.Small(f"{pct}%", style={"color": color, "fontWeight": 600}), width=3),
            ], className="mb-1 g-0")
        )
    return rows


def _fig_dau_mau(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["mau"], name="MAU",
        line=dict(color=PALETTE["subtext"], width=1, dash="dot"),
        fill="tozeroy", fillcolor="rgba(139,148,158,0.05)",
    ))
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["dau"], name="DAU",
        line=dict(color=PALETTE["accent"], width=2),
        fill="tozeroy", fillcolor="rgba(88,166,255,0.12)",
    ))
    stickiness = (df["dau"] / df["mau"] * 100).round(1)
    fig.add_trace(go.Scatter(
        x=df["date"], y=stickiness, name="Stickiness %",
        yaxis="y2",
        line=dict(color=PALETTE["positive"], width=1.5, dash="dashdot"),
    ))
    fig.update_layout(
        **PLOTLY_TEMPLATE["layout"].to_plotly_json(),
        title="DAU / MAU & Stickiness (DAU/MAU %)",
        yaxis=dict(title="Users"),
        yaxis2=dict(title="Stickiness %", overlaying="y", side="right",
                    gridcolor="transparent"),
        legend=dict(orientation="h", y=1.05),
        height=400,
    )
    return fig


# ─── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = build_app()
    app.run(debug=True, port=8050)

# For uvicorn: expose Flask server
server = build_app().server if DASH_AVAILABLE else None

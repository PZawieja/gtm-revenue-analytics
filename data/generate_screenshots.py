"""
Generate static PNG screenshots of the four dashboard charts.

Reads directly from DuckDB — no Streamlit required.
Output: docs/screenshots/{mrr_waterfall,arr_bridge,nrr_cohorts,customer_mix}.png

Usage:
    python3 data/generate_screenshots.py

Requires kaleido (included in requirements.txt).
"""

import sys
from pathlib import Path

import duckdb
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

DB_PATH = Path(__file__).parent.parent / "gtm_revenue.duckdb"
OUT_DIR = Path(__file__).parent.parent / "docs" / "screenshots"

GOLD = "#c8a96e"
GOLD_LIGHT = "#e8d5b0"
GREEN = "#4caf82"
RED = "#e05c5c"
ORANGE = "#e8944a"
BLUE = "#5c9ee8"
MUTED = "#7a7870"
BG = "#0d0d0f"
SURFACE = "#141417"
BORDER = "#232328"

MOTION_COLORS = {
    "new_business": GREEN,
    "expansion": GOLD,
    "reactivation": BLUE,
    "contraction": ORANGE,
    "churn": RED,
}

MOTION_LABELS = {
    "new_business": "New Business",
    "expansion": "Expansion",
    "reactivation": "Reactivation",
    "contraction": "Contraction",
    "churn": "Churn",
}

LAYOUT_BASE = dict(
    paper_bgcolor=BG,
    plot_bgcolor=BG,
    font=dict(color=MUTED, size=13),
    margin=dict(t=50, b=80, l=70, r=30),
)


def connect():
    return duckdb.connect(str(DB_PATH), read_only=True)


def save(fig, name: str, width: int = 1200, height: int = 500):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"{name}.png"
    fig.write_image(str(path), width=width, height=height, scale=2)
    print(f"  saved → {path}")


def mrr_waterfall():
    con = connect()
    df = con.execute("""
        select effective_month, movement_type, mrr_delta, cumulative_mrr
        from main_marts.fct_mrr
        order by effective_month, movement_type
    """).df()
    df["effective_month"] = pd.to_datetime(df["effective_month"])

    cum = df.groupby("effective_month")["cumulative_mrr"].max().reset_index()
    pivot = df.pivot_table(
        index="effective_month", columns="movement_type",
        values="mrr_delta", aggfunc="sum", fill_value=0
    ).reset_index()

    fig = go.Figure()
    for motion in ["new_business", "expansion", "reactivation", "contraction", "churn"]:
        if motion not in pivot.columns:
            continue
        fig.add_trace(go.Bar(
            name=MOTION_LABELS[motion],
            x=pivot["effective_month"],
            y=pivot[motion],
            marker_color=MOTION_COLORS[motion],
            opacity=0.9,
        ))

    fig.add_trace(go.Scatter(
        name="Ending MRR",
        x=cum["effective_month"],
        y=cum["cumulative_mrr"],
        mode="lines+markers",
        line=dict(color=GOLD_LIGHT, width=2, dash="dot"),
        marker=dict(size=5),
        yaxis="y2",
    ))

    fig.update_layout(
        **LAYOUT_BASE,
        title=dict(text="Monthly MRR by Revenue Motion", font=dict(color=GOLD_LIGHT, size=16)),
        barmode="relative",
        height=500,
        legend=dict(bgcolor=SURFACE, bordercolor=BORDER, borderwidth=1,
                    orientation="h", y=-0.22),
        xaxis=dict(gridcolor=BORDER, tickfont=dict(color=MUTED)),
        yaxis=dict(title="MRR Delta ($)", gridcolor=BORDER, tickfont=dict(color=MUTED)),
        yaxis2=dict(title="Ending MRR ($)", overlaying="y", side="right",
                    gridcolor="rgba(0,0,0,0)", tickfont=dict(color=GOLD_LIGHT)),
    )
    save(fig, "mrr_waterfall")


def arr_bridge():
    con = connect()
    df = con.execute("""
        select * from main_marts.rpt_arr_bridge order by effective_month
    """).df()
    df["effective_month"] = pd.to_datetime(df["effective_month"])
    df = df.tail(18)

    fig = go.Figure()
    for col, label, color in [
        ("new_arr", "New Business", GREEN),
        ("expansion_arr", "Expansion", GOLD),
        ("reactivation_arr", "Reactivation", BLUE),
        ("contraction_arr", "Contraction", ORANGE),
        ("churn_arr", "Churn", RED),
    ]:
        if col in df.columns:
            fig.add_trace(go.Bar(
                name=label, x=df["effective_month"], y=df[col],
                marker_color=color, opacity=0.9,
            ))

    fig.add_trace(go.Scatter(
        name="Ending ARR",
        x=df["effective_month"], y=df["ending_arr"],
        mode="lines+markers",
        line=dict(color=GOLD_LIGHT, width=2),
        marker=dict(size=6),
        yaxis="y2",
    ))

    fig.update_layout(
        **LAYOUT_BASE,
        title=dict(text="ARR Bridge — Board Reporting View", font=dict(color=GOLD_LIGHT, size=16)),
        barmode="relative",
        height=500,
        legend=dict(bgcolor=SURFACE, bordercolor=BORDER, borderwidth=1,
                    orientation="h", y=-0.22),
        xaxis=dict(gridcolor=BORDER, tickfont=dict(color=MUTED)),
        yaxis=dict(title="ARR Delta ($)", gridcolor=BORDER, tickfont=dict(color=MUTED)),
        yaxis2=dict(title="Ending ARR ($)", overlaying="y", side="right",
                    gridcolor="rgba(0,0,0,0)", tickfont=dict(color=GOLD_LIGHT)),
    )
    save(fig, "arr_bridge")


def nrr_cohorts():
    con = connect()
    df = con.execute("""
        select cohort_month, cohort_size, starting_mrr, retained_mrr,
               nrr_pct, grr_pct
        from main_marts.fct_nrr
        order by cohort_month
    """).df()
    df["cohort_month"] = pd.to_datetime(df["cohort_month"])
    df["label"] = df["cohort_month"].dt.strftime("%b %Y")

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="GRR",
        x=df["label"], y=df["grr_pct"],
        marker_color=MUTED, opacity=0.5,
    ))
    fig.add_trace(go.Scatter(
        name="NRR",
        x=df["label"], y=df["nrr_pct"],
        mode="lines+markers",
        line=dict(color=GOLD, width=2),
        marker=dict(size=7, color=GOLD),
    ))
    fig.add_hline(y=100, line_dash="dash", line_color=MUTED, opacity=0.4,
                  annotation_text="100%", annotation_font_color=MUTED)

    fig.update_layout(
        **LAYOUT_BASE,
        title=dict(text="Net Revenue Retention by Cohort (T+12)", font=dict(color=GOLD_LIGHT, size=16)),
        height=460,
        margin=dict(t=50, b=100, l=70, r=30),
        legend=dict(bgcolor=SURFACE, bordercolor=BORDER, borderwidth=1),
        xaxis=dict(gridcolor=BORDER, tickfont=dict(color=MUTED), tickangle=-45),
        yaxis=dict(title="Retention (%)", gridcolor=BORDER, tickfont=dict(color=MUTED)),
    )
    save(fig, "nrr_cohorts")


def customer_mix():
    con = connect()
    df = con.execute("""
        select industry, country, plan_id, is_active
        from main_marts.dim_customer
        where subscription_id is not null and is_active = true
    """).df()

    colors = [GOLD, GOLD_LIGHT, MUTED, GREEN, BLUE, ORANGE, RED]

    fig = make_subplots(
        rows=1, cols=3,
        specs=[[{"type": "pie"}, {"type": "pie"}, {"type": "pie"}]],
        subplot_titles=["By Industry", "By Plan", "By Country"],
    )

    for col_idx, (field, title) in enumerate([
        ("industry", "Industry"),
        ("plan_id", "Plan"),
        ("country", "Country"),
    ], start=1):
        counts = df[field].value_counts().reset_index()
        counts.columns = [field, "count"]
        fig.add_trace(go.Pie(
            labels=counts[field],
            values=counts["count"],
            hole=0.5,
            marker=dict(colors=colors[:len(counts)]),
            textinfo="label+percent",
            textfont=dict(size=11),
            showlegend=False,
        ), row=1, col=col_idx)

    fig.update_layout(
        **LAYOUT_BASE,
        title=dict(text=f"Active Customer Mix ({len(df)} accounts)", font=dict(color=GOLD_LIGHT, size=16)),
        height=400,
        margin=dict(t=60, b=20, l=20, r=20),
    )
    for ann in fig.layout.annotations:
        ann.font.color = GOLD_LIGHT
        ann.font.size = 13

    save(fig, "customer_mix", height=400)


def churn_analysis():
    con = connect()
    df = con.execute("""
        select tenure_bucket, count(*) as churns, sum(mrr_lost) as mrr_lost,
               avg(months_to_churn) as avg_months
        from main_marts.fct_churn
        group by tenure_bucket
        order by min(months_to_churn)
    """).df()

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df["tenure_bucket"],
        y=df["mrr_lost"],
        marker_color=[GREEN, GOLD, ORANGE, RED][:len(df)],
        text=df["churns"].apply(lambda x: f"{x} subs"),
        textposition="outside",
        textfont=dict(color=MUTED, size=11),
    ))

    fig.update_layout(
        **LAYOUT_BASE,
        title=dict(text="Churn by Tenure Bucket — MRR Lost", font=dict(color=GOLD_LIGHT, size=16)),
        height=420,
        xaxis=dict(title="Tenure at Churn", gridcolor=BORDER, tickfont=dict(color=MUTED)),
        yaxis=dict(title="MRR Lost ($)", gridcolor=BORDER, tickfont=dict(color=MUTED)),
        showlegend=False,
    )
    save(fig, "churn_analysis")


def main():
    if not DB_PATH.exists():
        print(f"Error: database not found at {DB_PATH}")
        print("Run 'make dbt-build' first.")
        sys.exit(1)

    print("Generating dashboard screenshots...")
    mrr_waterfall()
    arr_bridge()
    nrr_cohorts()
    customer_mix()
    churn_analysis()
    print(f"\nAll screenshots saved to {OUT_DIR}/")


if __name__ == "__main__":
    main()

"""
GTM Revenue Analytics Dashboard

Demonstrates production-grade SaaS revenue modeling on top of the
dbt marts: MRR waterfall, ARR bridge, NRR cohort analysis.

All data is synthetic. Every metric is derived from the event log
in dbt — no ad-hoc SQL, no spreadsheets.

Run: streamlit run app/streamlit_app.py
"""

import duckdb
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "gtm_revenue.duckdb"

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

st.set_page_config(
    page_title="GTM Revenue Analytics",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(f"""
<style>
  .stApp {{ background: {BG}; }}
  section[data-testid="stSidebar"] {{ background: {SURFACE}; }}
  .metric-card {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 1.2rem 1.4rem;
  }}
  .metric-value {{ font-size: 1.8rem; font-weight: 700; color: {GOLD_LIGHT}; }}
  .metric-label {{ font-size: 0.75rem; text-transform: uppercase;
                   letter-spacing: 0.1em; color: {MUTED}; margin-top: 0.25rem; }}
  .metric-delta {{ font-size: 0.85rem; margin-top: 0.2rem; }}
  h1, h2, h3 {{ color: {GOLD_LIGHT} !important; }}
  .section-label {{
    font-family: monospace; font-size: 0.7rem; letter-spacing: 0.12em;
    text-transform: uppercase; color: {GOLD}; margin-bottom: 0.25rem;
  }}
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def get_connection():
    return duckdb.connect(str(DB_PATH), read_only=True)


@st.cache_data
def load_mrr_waterfall():
    con = get_connection()
    return con.execute("""
        select effective_month, movement_type, mrr_delta, cumulative_mrr
        from main_marts.fct_mrr
        order by effective_month, movement_type
    """).df()


@st.cache_data
def load_arr_bridge():
    con = get_connection()
    return con.execute("""
        select *
        from main_marts.rpt_arr_bridge
        order by effective_month
    """).df()


@st.cache_data
def load_nrr():
    con = get_connection()
    return con.execute("""
        select cohort_month, cohort_size, starting_mrr,
               expansion_mrr, contraction_mrr, churn_mrr,
               retained_mrr, nrr_pct, grr_pct
        from main_marts.fct_nrr
        order by cohort_month
    """).df()


@st.cache_data
def load_customers():
    con = get_connection()
    return con.execute("""
        select account_id, industry, country, company_size_band,
               plan_id, subscription_status, current_mrr, is_active,
               cohort_month
        from main_marts.dim_customer
        where subscription_id is not null
    """).df()


@st.cache_data
def load_churn():
    con = get_connection()
    return con.execute("""
        select subscription_id, account_id, cohort_month, churn_month,
               months_to_churn, mrr_lost, tenure_bucket
        from main_marts.fct_churn
        order by churn_month
    """).df()


@st.cache_data
def load_cohort_heatmap():
    con = get_connection()
    return con.execute("""
        with cohorts as (
            select subscription_id, cohort_month, starting_mrr
            from main_intermediate.int_customer_cohorts
        )
        , movements as (
            select subscription_id, effective_month, mrr_delta
            from main_intermediate.int_mrr_movements
        )
        , monthly_cohort_mrr as (
            select
                c.cohort_month
                , datediff('month', c.cohort_month, m.effective_month) as months_since_start
                , sum(c.starting_mrr) as cohort_starting_mrr
                , sum(c.starting_mrr)
                  + sum(sum(m.mrr_delta)) over (
                      partition by c.cohort_month
                      order by datediff('month', c.cohort_month, m.effective_month)
                      rows between unbounded preceding and current row
                  ) as cohort_retained_mrr
            from cohorts c
            join movements m on m.subscription_id = c.subscription_id
            where datediff('month', c.cohort_month, m.effective_month) between 0 and 12
            group by 1, 2
        )
        select
            cohort_month
            , months_since_start
            , round(cohort_retained_mrr / nullif(cohort_starting_mrr, 0) * 100, 1) as retention_pct
        from monthly_cohort_mrr
        order by cohort_month, months_since_start
    """).df()


def fmt_currency(v: float, unit: str = "MRR") -> str:
    if abs(v) >= 1_000_000:
        return f"${v/1_000_000:.1f}M"
    elif abs(v) >= 1_000:
        return f"${v/1_000:.0f}k"
    return f"${v:,.0f}"


def fmt_pct(v: float) -> str:
    return f"{v:.1f}%"


# ── Load data ──────────────────────────────────────────────────────────────────
mrr_df = load_mrr_waterfall()
arr_df = load_arr_bridge()
nrr_df = load_nrr()
customers_df = load_customers()
churn_df = load_churn()
heatmap_df = load_cohort_heatmap()

# ── Derived summary metrics ────────────────────────────────────────────────────
latest_month = mrr_df["effective_month"].max()
prev_month = mrr_df[mrr_df["effective_month"] < latest_month]["effective_month"].max()

latest_mrr = mrr_df[mrr_df["effective_month"] <= latest_month]["mrr_delta"].sum()
prev_mrr = mrr_df[mrr_df["effective_month"] <= prev_month]["mrr_delta"].sum()
mrr_change = latest_mrr - prev_mrr

active_accounts = customers_df["is_active"].sum()
arr = latest_mrr * 12

avg_nrr = nrr_df["nrr_pct"].mean()
avg_grr = nrr_df["grr_pct"].mean()

# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown('<p class="section-label">// gtm-revenue-analytics</p>', unsafe_allow_html=True)
st.title("Revenue Analytics Dashboard")
st.markdown(
    f"Synthetic SaaS dataset · 100 accounts · 24 months · "
    f"dbt + DuckDB · all metrics from the event log",
)
st.markdown("---")

# ── KPI row ────────────────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)

delta_color = GREEN if mrr_change >= 0 else RED
delta_sign = "+" if mrr_change >= 0 else ""

for col, label, value, delta in [
    (c1, "Ending MRR", fmt_currency(latest_mrr), f"{delta_sign}{fmt_currency(mrr_change)} MoM"),
    (c2, "ARR (MRR × 12)", fmt_currency(arr), "annualised"),
    (c3, "Active Accounts", str(int(active_accounts)), f"of 100"),
    (c4, "Avg NRR (T+12)", fmt_pct(avg_nrr), f"GRR {fmt_pct(avg_grr)}"),
]:
    col.markdown(f"""
    <div class="metric-card">
      <div class="metric-value">{value}</div>
      <div class="metric-label">{label}</div>
      <div class="metric-delta" style="color:{MUTED}">{delta}</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── MRR Waterfall ──────────────────────────────────────────────────────────────
st.markdown('<p class="section-label">// mrr waterfall</p>', unsafe_allow_html=True)
st.subheader("Monthly MRR by Revenue Motion")
st.caption(
    "Each bar segment is one revenue motion. "
    "The gray line is cumulative ending MRR. "
    "New business ends in month 12 once all 100 accounts are acquired."
)

waterfall_pivot = mrr_df.pivot_table(
    index="effective_month", columns="movement_type", values="mrr_delta", aggfunc="sum", fill_value=0
).reset_index()
waterfall_pivot["effective_month"] = pd.to_datetime(waterfall_pivot["effective_month"])

# Cumulative MRR by month (ending)
cum_mrr = mrr_df.groupby("effective_month")["mrr_delta"].sum().cumsum().reset_index()
cum_mrr.columns = ["effective_month", "cum_mrr"]
cum_mrr["effective_month"] = pd.to_datetime(cum_mrr["effective_month"])

fig_wf = go.Figure()

MOTION_ORDER = ["new_business", "expansion", "reactivation", "contraction", "churn"]
MOTION_LABELS = {
    "new_business": "New Business",
    "expansion": "Expansion",
    "reactivation": "Reactivation",
    "contraction": "Contraction",
    "churn": "Churn",
}

for motion in MOTION_ORDER:
    if motion not in waterfall_pivot.columns:
        continue
    fig_wf.add_trace(go.Bar(
        name=MOTION_LABELS[motion],
        x=waterfall_pivot["effective_month"],
        y=waterfall_pivot[motion],
        marker_color=MOTION_COLORS[motion],
        opacity=0.9,
    ))

fig_wf.add_trace(go.Scatter(
    name="Ending MRR",
    x=cum_mrr["effective_month"],
    y=cum_mrr["cum_mrr"],
    mode="lines+markers",
    line=dict(color=GOLD_LIGHT, width=2, dash="dot"),
    marker=dict(size=5),
    yaxis="y2",
))

fig_wf.update_layout(
    barmode="relative",
    paper_bgcolor=BG,
    plot_bgcolor=BG,
    font=dict(color=MUTED, size=12),
    legend=dict(bgcolor=SURFACE, bordercolor=BORDER, borderwidth=1, orientation="h", y=-0.18),
    margin=dict(t=20, b=60, l=60, r=20),
    height=380,
    xaxis=dict(gridcolor=BORDER, tickfont=dict(color=MUTED)),
    yaxis=dict(title="MRR Delta ($)", gridcolor=BORDER, tickfont=dict(color=MUTED)),
    yaxis2=dict(title="Ending MRR ($)", overlaying="y", side="right",
                gridcolor="rgba(0,0,0,0)", tickfont=dict(color=GOLD_LIGHT)),
)

st.plotly_chart(fig_wf, use_container_width=True)

# ── ARR Bridge ─────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown('<p class="section-label">// arr bridge</p>', unsafe_allow_html=True)
st.subheader("ARR Bridge — Board Reporting View")
st.caption(
    "The ARR bridge decomposes ARR change into the five revenue motions. "
    "This is the standard format for investor and board reporting in subscription SaaS."
)

arr_df["effective_month"] = pd.to_datetime(arr_df["effective_month"])
last_n = st.slider("Months to display", min_value=3, max_value=len(arr_df), value=12, step=1)
arr_display = arr_df.tail(last_n).copy()

fig_arr = go.Figure()

BRIDGE_COLS = [
    ("new_arr",         "New Business",  GREEN),
    ("expansion_arr",   "Expansion",     GOLD),
    ("reactivation_arr","Reactivation",  BLUE),
    ("contraction_arr", "Contraction",   ORANGE),
    ("churn_arr",       "Churn",         RED),
]

for col, label, color in BRIDGE_COLS:
    if col in arr_display.columns:
        fig_arr.add_trace(go.Bar(
            name=label,
            x=arr_display["effective_month"],
            y=arr_display[col],
            marker_color=color,
            opacity=0.9,
        ))

fig_arr.add_trace(go.Scatter(
    name="Ending ARR",
    x=arr_display["effective_month"],
    y=arr_display["ending_arr"],
    mode="lines+markers",
    line=dict(color=GOLD_LIGHT, width=2),
    marker=dict(size=6),
    yaxis="y2",
))

fig_arr.update_layout(
    barmode="relative",
    paper_bgcolor=BG,
    plot_bgcolor=BG,
    font=dict(color=MUTED, size=12),
    legend=dict(bgcolor=SURFACE, bordercolor=BORDER, borderwidth=1, orientation="h", y=-0.18),
    margin=dict(t=20, b=60, l=60, r=20),
    height=380,
    xaxis=dict(gridcolor=BORDER, tickfont=dict(color=MUTED)),
    yaxis=dict(title="ARR Delta ($)", gridcolor=BORDER, tickfont=dict(color=MUTED)),
    yaxis2=dict(title="Ending ARR ($)", overlaying="y", side="right",
                gridcolor="rgba(0,0,0,0)", tickfont=dict(color=GOLD_LIGHT)),
)

st.plotly_chart(fig_arr, use_container_width=True)

# ── NRR Cohort Analysis ────────────────────────────────────────────────────────
st.markdown("---")
st.markdown('<p class="section-label">// nrr cohort analysis</p>', unsafe_allow_html=True)
st.subheader("Net Revenue Retention by Cohort")
st.caption(
    "NRR > 100% means the cohort grew beyond its starting MRR through expansion. "
    "NRR < 100% means churn exceeded expansion. GRR excludes expansion and caps at 100%."
)

nrr_df["cohort_month"] = pd.to_datetime(nrr_df["cohort_month"])
nrr_display = nrr_df.copy()
nrr_display["cohort_label"] = nrr_display["cohort_month"].dt.strftime("%b %Y")

col_left, col_right = st.columns([2, 1])

with col_left:
    fig_nrr = go.Figure()

    fig_nrr.add_trace(go.Bar(
        name="GRR",
        x=nrr_display["cohort_label"],
        y=nrr_display["grr_pct"],
        marker_color=MUTED,
        opacity=0.6,
    ))
    fig_nrr.add_trace(go.Scatter(
        name="NRR",
        x=nrr_display["cohort_label"],
        y=nrr_display["nrr_pct"],
        mode="lines+markers",
        line=dict(color=GOLD, width=2),
        marker=dict(size=7, color=GOLD),
    ))
    fig_nrr.add_hline(y=100, line_dash="dash", line_color=MUTED, opacity=0.5,
                      annotation_text="100% baseline", annotation_font_color=MUTED)

    fig_nrr.update_layout(
        paper_bgcolor=BG,
        plot_bgcolor=BG,
        font=dict(color=MUTED, size=12),
        legend=dict(bgcolor=SURFACE, bordercolor=BORDER, borderwidth=1),
        margin=dict(t=20, b=80, l=60, r=20),
        height=360,
        xaxis=dict(gridcolor=BORDER, tickfont=dict(color=MUTED), tickangle=-45),
        yaxis=dict(title="Retention (%)", gridcolor=BORDER, tickfont=dict(color=MUTED)),
    )
    st.plotly_chart(fig_nrr, use_container_width=True)

with col_right:
    st.markdown('<p class="section-label">// cohort table</p>', unsafe_allow_html=True)
    summary_cols = ["cohort_label", "cohort_size", "starting_mrr", "retained_mrr", "nrr_pct"]
    summary = nrr_display[summary_cols].copy()
    summary.columns = ["Cohort", "Size", "Start MRR", "Retained MRR", "NRR %"]
    summary["Start MRR"] = summary["Start MRR"].apply(lambda x: f"${x:,.0f}")
    summary["Retained MRR"] = summary["Retained MRR"].apply(lambda x: f"${x:,.0f}")
    summary["NRR %"] = summary["NRR %"].apply(lambda x: f"{x:.1f}%")
    st.dataframe(summary, use_container_width=True, hide_index=True, height=340)

# ── Cohort Retention Heatmap ───────────────────────────────────────────────────
st.markdown("---")
st.markdown('<p class="section-label">// cohort retention heatmap</p>', unsafe_allow_html=True)
st.subheader("MRR Retention by Cohort × Month Age")
st.caption(
    "Each cell shows % of cohort starting MRR retained at month N. "
    "100% = flat retention. >100% = expansion. Red = churn eroded the cohort."
)

heatmap_df["cohort_month"] = pd.to_datetime(heatmap_df["cohort_month"])
heatmap_df["cohort_label"] = heatmap_df["cohort_month"].dt.strftime("%b %Y")

heatmap_pivot = heatmap_df.pivot_table(
    index="cohort_label", columns="months_since_start",
    values="retention_pct", aggfunc="first"
)
heatmap_pivot = heatmap_pivot.reindex(
    heatmap_df.sort_values("cohort_month")["cohort_label"].unique()
)

fig_heat = go.Figure(go.Heatmap(
    z=heatmap_pivot.values,
    x=[f"M+{int(c)}" for c in heatmap_pivot.columns],
    y=heatmap_pivot.index.tolist(),
    colorscale=[
        [0.0,  RED],
        [0.5,  SURFACE],
        [0.85, GOLD],
        [1.0,  GREEN],
    ],
    zmid=100,
    text=[[f"{v:.0f}%" if not pd.isna(v) else "" for v in row]
          for row in heatmap_pivot.values],
    texttemplate="%{text}",
    textfont=dict(size=10, color=GOLD_LIGHT),
    colorbar=dict(
        title=dict(text="Retention %", font=dict(color=MUTED)),
        tickfont=dict(color=MUTED),
        bgcolor=SURFACE,
        bordercolor=BORDER,
    ),
))
fig_heat.update_layout(
    paper_bgcolor=BG,
    plot_bgcolor=BG,
    font=dict(color=MUTED, size=11),
    margin=dict(t=20, b=60, l=80, r=20),
    height=420,
    xaxis=dict(tickfont=dict(color=MUTED), title="Months Since First Payment"),
    yaxis=dict(tickfont=dict(color=MUTED), title="Cohort"),
)
st.plotly_chart(fig_heat, use_container_width=True)

# ── Churn Analysis ─────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown('<p class="section-label">// churn analysis</p>', unsafe_allow_html=True)
st.subheader("Churn by Tenure Bucket")
st.caption(
    "When do customers churn? Customers who churn early (0–3 months) signal "
    "onboarding or product-fit problems. Late churn (12+ months) often means "
    "budget cuts or competitive displacement."
)

churn_df["churn_month"] = pd.to_datetime(churn_df["churn_month"])

col_churn_left, col_churn_right = st.columns([2, 1])

with col_churn_left:
    churn_bucket = (
        churn_df.groupby("tenure_bucket")
        .agg(churns=("subscription_id", "count"), mrr_lost=("mrr_lost", "sum"))
        .reset_index()
    )
    bucket_order = ["0–3 months", "4–6 months", "7–12 months", "12+ months"]
    churn_bucket["tenure_bucket"] = pd.Categorical(
        churn_bucket["tenure_bucket"], categories=bucket_order, ordered=True
    )
    churn_bucket = churn_bucket.sort_values("tenure_bucket")

    fig_churn = go.Figure()
    fig_churn.add_trace(go.Bar(
        x=churn_bucket["tenure_bucket"],
        y=churn_bucket["mrr_lost"],
        marker_color=[GREEN, GOLD, ORANGE, RED][:len(churn_bucket)],
        text=churn_bucket["churns"].apply(lambda x: f"{x} subs"),
        textposition="outside",
        textfont=dict(color=MUTED, size=12),
    ))
    fig_churn.update_layout(
        paper_bgcolor=BG, plot_bgcolor=BG,
        font=dict(color=MUTED, size=12),
        margin=dict(t=20, b=40, l=60, r=20),
        height=320,
        xaxis=dict(title="Tenure at Churn", gridcolor=BORDER, tickfont=dict(color=MUTED)),
        yaxis=dict(title="MRR Lost ($)", gridcolor=BORDER, tickfont=dict(color=MUTED)),
        showlegend=False,
    )
    st.plotly_chart(fig_churn, use_container_width=True)

with col_churn_right:
    total_churns = len(churn_df)
    total_mrr_lost = churn_df["mrr_lost"].sum()
    avg_months = churn_df["months_to_churn"].mean()
    median_mrr = churn_df["mrr_lost"].median()

    for label, value in [
        ("Total Churn Events", str(total_churns)),
        ("Total MRR Lost", f"${total_mrr_lost:,.0f}"),
        ("Avg Months to Churn", f"{avg_months:.1f}"),
        ("Median MRR per Churn", f"${median_mrr:,.0f}"),
    ]:
        st.markdown(f"""
        <div class="metric-card" style="margin-bottom:0.6rem">
          <div class="metric-value" style="font-size:1.4rem">{value}</div>
          <div class="metric-label">{label}</div>
        </div>
        """, unsafe_allow_html=True)

# ── Customer breakdown ─────────────────────────────────────────────────────────
st.markdown("---")
st.markdown('<p class="section-label">// customer breakdown</p>', unsafe_allow_html=True)
st.subheader("Active Customer Mix")

active_df = customers_df[customers_df["is_active"]].copy()

col_ind, col_plan, col_country = st.columns(3)

def pie_chart(df, col, label):
    counts = df[col].value_counts().reset_index()
    counts.columns = [col, "count"]
    fig = go.Figure(go.Pie(
        labels=counts[col],
        values=counts["count"],
        hole=0.55,
        marker=dict(colors=[GOLD, GOLD_LIGHT, MUTED, GREEN, BLUE, ORANGE, RED][:len(counts)]),
        textinfo="label+percent",
        textfont=dict(color=BG, size=11),
    ))
    fig.update_layout(
        paper_bgcolor=BG, plot_bgcolor=BG,
        font=dict(color=MUTED, size=11),
        showlegend=False,
        margin=dict(t=30, b=10, l=10, r=10),
        height=240,
        annotations=[dict(text=label, x=0.5, y=0.5, font_size=11,
                          font_color=GOLD_LIGHT, showarrow=False)],
    )
    return fig

col_ind.plotly_chart(pie_chart(active_df, "industry", "Industry"), use_container_width=True)
col_plan.plotly_chart(pie_chart(active_df, "plan_id", "Plan"), use_container_width=True)
col_country.plotly_chart(pie_chart(active_df, "country", "Country"), use_container_width=True)

# ── Footer ─────────────────────────────────────────────────────────────────────
st.markdown("---")
st.caption(
    "Synthetic data generated with `data/generate_data.py`. "
    "All metrics computed in dbt models — no ad-hoc SQL. "
    "Source: [github.com/PZawieja/gtm-revenue-analytics](https://github.com/PZawieja/gtm-revenue-analytics)"
)

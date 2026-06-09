# Changelog

## v1.1.0

- Added `fct_churn` mart model — one row per churn event with tenure bucket classification
- Added `assert_mrr_invariant` singular test — verifies ending MRR = cumulative sum of all deltas
- Fixed `fct_mrr.cumulative_mrr` — now computed at month level to avoid non-deterministic row ordering
- Added cohort retention heatmap to Streamlit dashboard
- Added churn analysis section (by tenure bucket) to Streamlit dashboard
- Added GitHub Actions CI — runs full dbt pipeline on every push
- Added `data/generate_screenshots.py` for static chart exports
- Added `kaleido` to requirements for PNG export
- Minor doc improvements: reactivation cooldown comment, partial NRR note, cohort scope assumption

## v1.0.0

- Initial release: synthetic data generator, dbt pipeline (staging → intermediate → marts)
- Models: `stg_accounts`, `stg_subscriptions`, `stg_subscription_events`
- Models: `int_mrr_movements`, `int_customer_cohorts`
- Models: `fct_mrr`, `fct_nrr`, `dim_customer`, `rpt_arr_bridge`
- Streamlit dashboard: MRR waterfall, ARR bridge, NRR cohort chart, customer mix
- ADR-001: MRR movement classification decisions
- 32 dbt tests

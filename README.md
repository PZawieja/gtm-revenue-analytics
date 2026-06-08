# GTM Revenue Analytics Platform

Production-grade SaaS revenue modeling on dbt + DuckDB + Streamlit.

MRR waterfall · NRR cohort analysis · ARR bridge · all from a single event log.

---

## The problem this solves

Most analytics teams have *some* version of a revenue dashboard. Almost none of them agree on the numbers.

Ask five people in your company what your NRR is and you'll get five answers. Ask where the number comes from and you'll find:
- a spreadsheet someone built two years ago
- a Tableau calculated field that's slightly different
- a dbt model that hasn't been updated since the pricing changed
- an analyst who runs a query from memory and formats it manually each month

The root cause is almost never bad data. It is **undefined business logic** — no single, documented, tested definition of what "churn" means, what counts as "expansion", whether reactivations go into NRR or not.

This project builds that definition layer in dbt and makes it explicit, testable, and auditable.

---

## What's here

```
gtm-revenue-analytics/
├── data/
│   └── generate_data.py          # synthetic data generator (100 accounts, 24 months)
├── dbt/
│   ├── seeds/                    # source data: accounts, subscriptions, events
│   └── models/
│       ├── staging/              # type-cast and rename raw source fields
│       │   ├── stg_accounts.sql
│       │   ├── stg_subscriptions.sql
│       │   └── stg_subscription_events.sql
│       ├── intermediate/         # business logic: one place, documented, tested
│       │   ├── int_mrr_movements.sql   ← the core model
│       │   └── int_customer_cohorts.sql
│       └── marts/                # reporting layer: one row = one answer to one question
│           ├── fct_mrr.sql             ← monthly waterfall
│           ├── fct_nrr.sql             ← NRR and GRR by cohort
│           ├── dim_customer.sql        ← current customer state
│           └── rpt_arr_bridge.sql      ← ARR bridge for board reporting
├── app/
│   └── streamlit_app.py          # interactive dashboard
├── docs/
│   └── adr-001-mrr-movement-classification.md
├── Makefile
└── requirements.txt
```

---

## Architecture

```
   Raw Sources (seeds)
   ┌──────────────────────────────────────────┐
   │  accounts.csv  subscriptions.csv         │
   │  subscription_events.csv                 │
   └──────────────────────────────────────────┘
                      │
                      ▼
   Staging (views)
   ┌──────────────────────────────────────────┐
   │  Type-cast · rename · no business logic  │
   └──────────────────────────────────────────┘
                      │
                      ▼
   Intermediate (tables)
   ┌──────────────────────────────────────────┐
   │  int_mrr_movements                       │
   │    classified event → movement_type      │
   │    new_business / expansion / contraction│
   │    churn / reactivation                  │
   │  int_customer_cohorts                    │
   │    subscription → cohort_month           │
   └──────────────────────────────────────────┘
                      │
                      ▼
   Marts (tables)
   ┌──────────────────────────────────────────┐
   │  fct_mrr        monthly waterfall        │
   │  fct_nrr        NRR + GRR by cohort      │
   │  dim_customer   current customer state   │
   │  rpt_arr_bridge ARR bridge (board view)  │
   └──────────────────────────────────────────┘
                      │
                      ▼
   Streamlit Dashboard
```

The key design choice: **`int_mrr_movements` is the single source of truth** for all revenue motion logic. Every mart model reads from it. No mart re-derives movement types. This means when a definition changes (and it will), you change it in one place.

---

## Revenue motion definitions

See [ADR-001](docs/adr-001-mrr-movement-classification.md) for the full reasoning. The short version:

| Motion | What it means |
|---|---|
| **new_business** | First MRR from this subscription |
| **expansion** | MRR increased on an existing subscription |
| **contraction** | MRR decreased on an existing subscription (still active) |
| **churn** | Subscription cancelled |
| **reactivation** | Previously churned subscription restarted |

NRR includes reactivation. GRR excludes expansion entirely. Both are computed in `fct_nrr`.

---

## Quick start

```bash
# Install dependencies
pip install -r requirements.txt

# Generate synthetic data and build the pipeline
make all

# Or step by step:
python3 data/generate_data.py    # generates seed CSVs
cd dbt && dbt deps && dbt seed && dbt run && dbt test
cd ..
streamlit run app/streamlit_app.py
```

The pipeline creates a local `gtm_revenue.duckdb` file. No external database required.

---

## Data

100 synthetic B2B accounts, 24 months of subscription events (Jan 2024 – Dec 2025).

Designed to mirror the schema of real billing systems:
- **Accounts** → Salesforce Account object
- **Subscriptions** → Chargebee/Stripe subscription resource
- **Subscription events** → Chargebee webhook events / Stripe event stream

No real company data. No PII. Fully reproducible with `data/generate_data.py`.

---

## Tests

```bash
cd dbt && dbt test
```

32 tests covering: uniqueness, not-null, accepted values, referential integrity, and movement type exhaustiveness.

Key invariant checked in documentation (verify manually):
```sql
-- Ending MRR for any month = sum of all mrr_delta up to that month
select sum(mrr_delta) from fct_mrr where effective_month <= '2025-12-01'
```

---

## Why this matters for GTM companies

Revenue data is the most politically sensitive data in most SaaS companies. Everyone has an opinion on the numbers. Finance wants ARR. Sales wants bookings. CS wants GRR. The CEO wants NRR.

The solution is not a better BI tool. It is a **documented, versioned, tested definition layer** that every stakeholder agrees to — built in dbt, reviewed in pull requests, and auditable by anyone.

This project demonstrates that layer. The Streamlit dashboard is the output. The dbt models are the product.

---

*Part of the [goldlayer.dev](https://goldlayer.dev) portfolio.*

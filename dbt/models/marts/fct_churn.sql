/*
  Churn event fact table.

  One row per subscription that churned. Designed for survival analysis —
  understanding how long customers stick around and how much MRR is at risk.

  Key use cases:
    - Time-to-churn distribution: how quickly do customers leave?
    - MRR at risk by cohort: which cohorts churn the most revenue?
    - Churn by plan: do enterprise customers churn more or less than starter?
    - Survival analysis input: % of cohort still active at month N

  Note: reactivations are not reflected here — this table records the
  churn events only. A subscription that churns and reactivates appears
  once for the churn. Use int_mrr_movements to see the full lifecycle.
*/
with churns as (
    select
        subscription_id
        , account_id
        , effective_month as churn_month
        , abs(mrr_delta)  as mrr_lost
    from {{ ref('int_mrr_movements') }}
    where movement_type = 'churn'
)

, cohorts as (
    select
        subscription_id
        , cohort_month
        , starting_mrr
    from {{ ref('int_customer_cohorts') }}
)

select
    c.subscription_id
    , c.account_id
    , co.cohort_month
    , c.churn_month
    , datediff('month', co.cohort_month, c.churn_month) as months_to_churn
    , c.mrr_lost
    , co.starting_mrr

    , case
        when datediff('month', co.cohort_month, c.churn_month) <= 3  then '0–3 months'
        when datediff('month', co.cohort_month, c.churn_month) <= 6  then '4–6 months'
        when datediff('month', co.cohort_month, c.churn_month) <= 12 then '7–12 months'
        else                                                               '12+ months'
      end                                                   as tenure_bucket

from churns c
left join cohorts co
    on co.subscription_id = c.subscription_id

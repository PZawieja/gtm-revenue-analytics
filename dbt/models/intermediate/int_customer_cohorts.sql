/*
  Customer cohort assignment.

  Each subscription is assigned to the cohort month it first paid.
  Cohort month is used in NRR analysis to compare starting MRR
  to retained + expanded MRR 12 months later.

  One row per subscription. Cohort never changes — it is the
  first effective_month of the subscription_created event.
*/
with first_payments as (
    select
        subscription_id
        , account_id
        , effective_month as cohort_month
        , new_mrr         as starting_mrr
    from {{ ref('int_mrr_movements') }}
    where movement_type = 'new_business'
)

select
    subscription_id
    , account_id
    , cohort_month
    , starting_mrr
from first_payments

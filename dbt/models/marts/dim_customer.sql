/*
  Current customer dimension — one row per account.

  Combines account attributes with current subscription state and
  derived fields (cohort month, lifetime value, months active).
  Intended for BI tools and dashboards where each row = one customer.
*/
with accounts as (
    select * from {{ ref('stg_accounts') }}
)

, subscriptions as (
    select * from {{ ref('stg_subscriptions') }}
)

, cohorts as (
    select * from {{ ref('int_customer_cohorts') }}
)

select
    a.account_id
    , a.account_name
    , a.industry
    , a.country
    , a.company_size_band
    , a.owner_id
    , a.created_at                           as account_created_at

    , s.subscription_id
    , s.plan_id
    , s.status                               as subscription_status
    , s.mrr                                  as current_mrr
    , s.started_at                           as subscription_started_at

    , c.cohort_month
    , c.starting_mrr

    , case
        when s.status = 'active'    then true
        else                             false
      end                                    as is_active

    , datediff(
        'month',
        c.cohort_month,
        date_trunc('month', current_date)
      )                                      as months_since_start

from accounts a
left join subscriptions s
    on s.account_id = a.account_id
left join cohorts c
    on c.subscription_id = s.subscription_id

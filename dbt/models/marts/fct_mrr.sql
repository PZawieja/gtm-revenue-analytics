/*
  Monthly MRR waterfall.

  One row per movement_type per month. The canonical representation
  of revenue motion — how much MRR came from each source each month.

  To reconstruct ending MRR for any month:
    sum(mrr_delta) for all rows where effective_month <= target_month

  To build the waterfall chart for a given month:
    filter to effective_month = target_month, group by movement_type
*/
with movements as (
    select * from {{ ref('int_mrr_movements') }}
)

, monthly as (
    select
        effective_month
        , movement_type
        , count(distinct subscription_id)    as subscription_count
        , count(distinct account_id)         as account_count
        , sum(mrr_delta)                     as mrr_delta
        , sum(new_mrr)                       as gross_new_mrr
    from movements
    group by 1, 2
)

, with_running_mrr as (
    select
        effective_month
        , movement_type
        , subscription_count
        , account_count
        , mrr_delta
        , gross_new_mrr
        , sum(mrr_delta) over (
            order by effective_month
            rows between unbounded preceding and current row
          )                                  as cumulative_mrr
    from monthly
)

select
    effective_month
    , movement_type
    , subscription_count
    , account_count
    , mrr_delta
    , gross_new_mrr
    , cumulative_mrr
from with_running_mrr
order by effective_month, movement_type

/*
  Monthly MRR waterfall.

  One row per movement_type per month. The canonical representation
  of revenue motion — how much MRR came from each source each month.

  cumulative_mrr is the ending MRR for the entire month (same value for
  all movement_type rows within a month). It is computed by summing monthly
  net MRR deltas first, then running the window function — this avoids
  non-deterministic ordering when multiple movement types share a month.

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

-- Compute ending MRR per month independently of movement type
, monthly_ending_mrr as (
    select
        effective_month
        , sum(net_mrr_delta) over (
            order by effective_month
            rows between unbounded preceding and current row
          )                                  as ending_mrr
    from (
        select effective_month, sum(mrr_delta) as net_mrr_delta
        from monthly
        group by effective_month
    )
)

select
    m.effective_month
    , m.movement_type
    , m.subscription_count
    , m.account_count
    , m.mrr_delta
    , m.gross_new_mrr
    , e.ending_mrr                           as cumulative_mrr
from monthly m
join monthly_ending_mrr e
    on e.effective_month = m.effective_month
order by m.effective_month, m.movement_type

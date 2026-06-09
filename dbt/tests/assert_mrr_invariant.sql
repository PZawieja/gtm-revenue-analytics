/*
  Singular test: MRR invariant validation.

  The invariant: for every month, the ending MRR stored in fct_mrr
  (max cumulative_mrr within that month) must equal the independently
  computed running sum of all mrr_delta values through that month.

  fct_mrr has multiple rows per month (one per movement_type), so we
  aggregate to month level before comparing. max(cumulative_mrr) gives
  the ending MRR for that month (the last row's value after all movements
  are applied).

  Returns rows when violated (zero rows = test passes).
*/
with monthly_totals as (
    select
        effective_month
        , sum(mrr_delta)      as monthly_mrr_delta
        , max(cumulative_mrr) as stored_ending_mrr
    from {{ ref('fct_mrr') }}
    group by effective_month
)

, expected as (
    select
        effective_month
        , sum(monthly_mrr_delta) over (
            order by effective_month
            rows between unbounded preceding and current row
          )                    as computed_ending_mrr
        , stored_ending_mrr
    from monthly_totals
)

select
    effective_month
    , computed_ending_mrr
    , stored_ending_mrr
    , abs(computed_ending_mrr - stored_ending_mrr) as delta
from expected
where abs(computed_ending_mrr - stored_ending_mrr) > 0.01

/*
  ARR bridge — board and investor reporting format.

  The ARR bridge answers: why did ARR change between two periods?
  It decomposes ARR delta into the five revenue motions and is the
  standard format for board reporting in subscription businesses.

  ARR = MRR * 12. We annualise MRR to align with ARR-denominated targets.

  This model produces the period-over-period comparison suitable for
  a waterfall chart: beginning ARR → new → expansion → contraction → churn
  → reactivation → ending ARR.
*/
with monthly_mrr as (
    select
        effective_month
        , movement_type
        , mrr_delta
    from {{ ref('fct_mrr') }}
)

, period_totals as (
    select
        effective_month
        , sum(case when movement_type = 'new_business'  then mrr_delta else 0 end) as new_mrr
        , sum(case when movement_type = 'expansion'     then mrr_delta else 0 end) as expansion_mrr
        , sum(case when movement_type = 'contraction'   then mrr_delta else 0 end) as contraction_mrr
        , sum(case when movement_type = 'churn'         then mrr_delta else 0 end) as churn_mrr
        , sum(case when movement_type = 'reactivation'  then mrr_delta else 0 end) as reactivation_mrr
        , sum(mrr_delta)                                                             as net_mrr_change
    from monthly_mrr
    group by 1
)

, with_arr as (
    select
        effective_month
        , new_mrr          * 12  as new_arr
        , expansion_mrr    * 12  as expansion_arr
        , contraction_mrr  * 12  as contraction_arr
        , churn_mrr        * 12  as churn_arr
        , reactivation_mrr * 12  as reactivation_arr
        , net_mrr_change   * 12  as net_arr_change
        , sum(net_mrr_change * 12) over (
            order by effective_month
            rows between unbounded preceding and 1 preceding
          )                      as beginning_arr
        , sum(net_mrr_change * 12) over (
            order by effective_month
            rows between unbounded preceding and current row
          )                      as ending_arr
    from period_totals
)

select
    effective_month
    , coalesce(beginning_arr, 0) as beginning_arr
    , new_arr
    , expansion_arr
    , contraction_arr
    , churn_arr
    , reactivation_arr
    , net_arr_change
    , ending_arr
from with_arr
order by effective_month

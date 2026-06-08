/*
  Net Revenue Retention by cohort month.

  NRR answers: of the MRR we had from a given cohort at their start month,
  how much do we still have 12 months later — including expansion and
  contraction, excluding new business from that cohort month?

  Formula:
    NRR = (starting_mrr + expansion - contraction - churn + reactivation)
          / starting_mrr

  Note: reactivation is included because those are returning customers
  from this cohort. New business is excluded by definition.

  See: docs/adr-001-mrr-movement-classification.md for the reasoning
  behind including reactivations in NRR vs GRR.
*/
with cohorts as (
    select * from {{ ref('int_customer_cohorts') }}
)

, movements as (
    select * from {{ ref('int_mrr_movements') }}
    where movement_type != 'new_business'
)

/*
  For each cohort, aggregate all subsequent movements up to 12 months later.
  We look at the trailing 12 months from the cohort start to measure
  NRR at the T+12 mark — the standard investor / board metric.
*/
, cohort_movements as (
    select
        c.cohort_month
        , c.subscription_id
        , c.starting_mrr
        , coalesce(sum(
            case when m.movement_type = 'expansion' then m.mrr_delta else 0 end
          ), 0)                                                     as expansion_mrr
        , coalesce(sum(
            case when m.movement_type = 'contraction' then abs(m.mrr_delta) else 0 end
          ), 0)                                                     as contraction_mrr
        , coalesce(sum(
            case when m.movement_type = 'churn' then abs(m.mrr_delta) else 0 end
          ), 0)                                                     as churn_mrr
        , coalesce(sum(
            case when m.movement_type = 'reactivation' then m.mrr_delta else 0 end
          ), 0)                                                     as reactivation_mrr
    from cohorts c
    left join movements m
        on  m.subscription_id = c.subscription_id
        and m.effective_month >  c.cohort_month
        and m.effective_month <= c.cohort_month + interval '12 months'
    group by 1, 2, 3
)

, cohort_summary as (
    select
        cohort_month
        , count(distinct subscription_id)    as cohort_size
        , sum(starting_mrr)                  as starting_mrr
        , sum(expansion_mrr)                 as expansion_mrr
        , sum(contraction_mrr)               as contraction_mrr
        , sum(churn_mrr)                     as churn_mrr
        , sum(reactivation_mrr)              as reactivation_mrr
        , sum(starting_mrr)
            + sum(expansion_mrr)
            - sum(contraction_mrr)
            - sum(churn_mrr)
            + sum(reactivation_mrr)          as retained_mrr
    from cohort_movements
    group by 1
)

select
    cohort_month
    , cohort_size
    , starting_mrr
    , expansion_mrr
    , contraction_mrr
    , churn_mrr
    , reactivation_mrr
    , retained_mrr
    , round(
        retained_mrr::float / nullif(starting_mrr, 0) * 100
      , 1)                                   as nrr_pct
    , round(
        (starting_mrr - churn_mrr)::float / nullif(starting_mrr, 0) * 100
      , 1)                                   as grr_pct
from cohort_summary
order by cohort_month

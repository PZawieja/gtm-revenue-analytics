/*
  MRR movement classification.

  Every subscription event is labelled with a movement_type and an mrr_delta.
  This is the model that makes revenue definitions explicit and auditable.

  Movement types (mutually exclusive, collectively exhaustive):
    new_business   — first MRR from this subscription
    expansion      — MRR increased on an existing subscription
    contraction    — MRR decreased on an existing subscription (but still active)
    churn          — subscription cancelled, MRR goes to zero
    reactivation   — previously churned subscription restarted

  Why not derive this from the subscription snapshot table?
  Because snapshot-based derivation silently loses same-month churn+reactivation
  events. The event log is the only reliable source.

  See: docs/adr-001-mrr-movement-classification.md
*/
with events as (
    select * from {{ ref('stg_subscription_events') }}
)

, classified as (
    select
        event_id
        , subscription_id
        , account_id
        , event_type
        , old_mrr
        , new_mrr
        , new_mrr - old_mrr                                       as mrr_delta
        , effective_month

        , case
            when event_type = 'subscription_created'     then 'new_business'
            when event_type = 'subscription_reactivated' then 'reactivation'
            when event_type = 'subscription_cancelled'   then 'churn'
            when event_type = 'subscription_changed'
                 and new_mrr > old_mrr                   then 'expansion'
            when event_type = 'subscription_changed'
                 and new_mrr < old_mrr                   then 'contraction'
            else 'unknown'
          end                                                      as movement_type

    from events
)

select
    event_id
    , subscription_id
    , account_id
    , event_type
    , movement_type
    , old_mrr
    , new_mrr
    , mrr_delta
    , effective_month
from classified

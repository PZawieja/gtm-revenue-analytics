with source as (
    select * from {{ ref('subscription_events') }}
)

select
    event_id
    , subscription_id
    , account_id
    , event_type
    , cast(old_mrr as integer) as old_mrr
    , cast(new_mrr as integer) as new_mrr
    , cast(effective_date as date) as effective_month
from source

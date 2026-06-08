with source as (
    select * from {{ ref('subscriptions') }}
)

select
    subscription_id
    , account_id
    , plan_id
    , status
    , mrr
    , cast(started_at as date) as started_at
    , cast(updated_at as date) as updated_at
from source

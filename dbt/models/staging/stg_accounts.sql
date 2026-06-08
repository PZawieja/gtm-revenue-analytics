with source as (
    select * from {{ ref('accounts') }}
)

select
    account_id
    , account_name
    , industry
    , country
    , company_size_band
    , owner_id
    , cast(created_at as date) as created_at
from source

-- Latest version of every customer (raw is append-only and can hold several versions).
with ranked as (
    select *,
        row_number() over (partition by customer_id order by updated_at desc, _ingested_at desc, _batch_id desc) as rn
    from {{ source('raw', 'customers') }}
)
select
    customer_id,
    lower(trim(email))      as email,
    initcap(trim(full_name)) as full_name,
    trim(city)              as city,
    upper(trim(country))    as country,
    lower(trim(segment))    as segment,
    signup_date,
    updated_at
from ranked
where rn = 1

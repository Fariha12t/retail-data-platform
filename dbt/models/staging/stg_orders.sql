with ranked as (
    select *,
        row_number() over (partition by order_id order by updated_at desc, _ingested_at desc, _batch_id desc) as rn
    from {{ source('raw', 'orders') }}
)
select
    order_id,
    customer_id,
    order_ts,
    lower(trim(status))  as status,
    lower(trim(channel)) as channel,
    updated_at
from ranked
where rn = 1

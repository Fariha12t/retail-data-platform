with ranked as (
    select *,
        row_number() over (partition by payment_id order by updated_at desc, _ingested_at desc, _batch_id desc) as rn
    from {{ source('raw', 'payments') }}
)
select
    payment_id,
    order_id,
    lower(trim(method)) as method,
    amount,
    lower(trim(status)) as status,
    paid_at,
    updated_at
from ranked
where rn = 1

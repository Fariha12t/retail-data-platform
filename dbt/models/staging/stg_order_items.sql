with ranked as (
    select *,
        row_number() over (partition by order_item_id order by updated_at desc, _ingested_at desc, _batch_id desc) as rn
    from {{ source('raw', 'order_items') }}
)
select
    order_item_id,
    order_id,
    product_id,
    quantity,
    unit_price,
    discount,
    round(quantity * unit_price, 2)                       as line_gross_amount,
    round(quantity * unit_price * discount, 2)            as line_discount_amount,
    round(quantity * unit_price * (1 - discount), 2)      as line_net_amount,
    updated_at
from ranked
where rn = 1

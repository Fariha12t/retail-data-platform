-- Grain: one row per order line. Dimension keys are resolved *as of the order time* (point-in-time join).
select
    i.order_item_id,
    i.order_id,
    cast(o.order_ts as date)                                  as order_date,
    o.order_ts,
    coalesce(c.customer_key, md5('unknown-customer'))         as customer_key,
    coalesce(p.product_key, md5('unknown-product'))           as product_key,
    o.channel,
    o.status                                                  as order_status,
    o.status in ('placed', 'shipped', 'delivered')            as is_revenue_order,
    i.quantity,
    i.unit_price,
    i.discount,
    i.line_gross_amount                                       as gross_amount,
    i.line_discount_amount                                    as discount_amount,
    i.line_net_amount                                         as net_amount,
    round(i.quantity * coalesce(p.unit_cost, 0), 2)           as cost_amount,
    i.line_net_amount - round(i.quantity * coalesce(p.unit_cost, 0), 2) as gross_margin
from {{ ref('stg_order_items') }} i
join {{ ref('stg_orders') }} o on o.order_id = i.order_id
left join {{ ref('dim_customer') }} c
    on c.customer_id = o.customer_id and o.order_ts >= c.valid_from and (c.valid_to is null or o.order_ts < c.valid_to)
left join {{ ref('dim_product') }} p
    on p.product_id = i.product_id and o.order_ts >= p.valid_from and (p.valid_to is null or o.order_ts < p.valid_to)

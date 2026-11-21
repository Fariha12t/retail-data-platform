-- Grain: one row per order.
with lines as (
    select
        order_id, order_date, order_ts, max(customer_key) as customer_key, channel, order_status, is_revenue_order,
        count(*)             as line_count,
        sum(quantity)        as units,
        sum(gross_amount)    as gross_amount,
        sum(discount_amount) as discount_amount,
        sum(net_amount)      as net_amount,
        sum(cost_amount)     as cost_amount,
        sum(gross_margin)    as gross_margin
    from {{ ref('fact_order_items') }}
    group by order_id, order_date, order_ts, channel, order_status, is_revenue_order
),
pay as (
    select
        order_id,
        max(status) as payment_status,
        sum(case when status = 'captured' then amount else 0 end) as captured_amount
    from {{ ref('stg_payments') }}
    group by order_id
)
select l.*, p.payment_status, coalesce(p.captured_amount, 0) as captured_amount
from lines l
left join pay p on p.order_id = l.order_id

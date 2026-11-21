-- Daily revenue report. Revenue counts placed/shipped/delivered orders; cancelled and returned are tracked separately.
with daily as (
    select
        order_date,
        count(*) filter (where is_revenue_order)                    as orders,
        count(*) filter (where order_status = 'cancelled')          as cancelled_orders,
        count(*) filter (where order_status = 'returned')           as returned_orders,
        coalesce(sum(units) filter (where is_revenue_order), 0)     as units_sold,
        coalesce(sum(gross_amount) filter (where is_revenue_order), 0)    as gross_revenue,
        coalesce(sum(discount_amount) filter (where is_revenue_order), 0) as discount_amount,
        coalesce(sum(net_amount) filter (where is_revenue_order), 0)      as net_revenue,
        coalesce(sum(gross_margin) filter (where is_revenue_order), 0)    as gross_margin,
        count(distinct customer_key) filter (where is_revenue_order)      as unique_customers
    from {{ ref('fact_orders') }}
    group by order_date
)
select
    order_date, orders, cancelled_orders, returned_orders, units_sold,
    gross_revenue, discount_amount, net_revenue, gross_margin, unique_customers,
    round(net_revenue / nullif(orders, 0), 2) as avg_order_value,
    round(avg(net_revenue) over (order by order_date rows between 6 preceding and current row), 2) as net_revenue_7d_avg,
    round((net_revenue / nullif(lag(net_revenue, 7) over (order by order_date), 0) - 1) * 100, 1) as net_revenue_wow_pct
from daily

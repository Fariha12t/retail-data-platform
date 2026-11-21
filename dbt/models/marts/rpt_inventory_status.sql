-- Latest stock position per product, with cover based on the last 14 days of sales.
with latest as (select max(snapshot_date) as d from {{ ref('fact_inventory_daily') }}),
stock as (
    select f.product_id, sum(f.stock_on_hand) as stock_on_hand, sum(f.reorder_level) as reorder_level
    from {{ ref('fact_inventory_daily') }} f
    cross join latest
    where f.snapshot_date = latest.d and f.product_id is not null
    group by f.product_id
),
sales as (
    select p.product_id, sum(f.quantity) filter (where f.is_revenue_order) / 14.0 as avg_daily_units_14d
    from {{ ref('fact_order_items') }} f
    join {{ ref('dim_product') }} p on p.product_key = f.product_key
    cross join latest
    where f.order_date > latest.d - 14 and f.order_date <= latest.d
    group by p.product_id
),
joined as (
    select
        s.product_id, p.product_name, p.category, latest.d as snapshot_date,
        s.stock_on_hand, s.reorder_level,
        round(coalesce(sa.avg_daily_units_14d, 0), 2) as avg_daily_units_14d,
        case when coalesce(sa.avg_daily_units_14d, 0) > 0 then round(s.stock_on_hand / sa.avg_daily_units_14d, 1) end as days_of_cover
    from stock s
    cross join latest
    join {{ ref('dim_product') }} p on p.product_id = s.product_id and p.is_current
    left join sales sa on sa.product_id = s.product_id
)
select *,
    case
        when stock_on_hand = 0 then 'out_of_stock'
        when stock_on_hand < reorder_level then 'below_reorder'
        when days_of_cover < 7 then 'low_cover'
        else 'healthy'
    end as stock_status
from joined

with sales as (
    select
        p.product_id,
        coalesce(sum(f.quantity) filter (where f.is_revenue_order), 0)    as units_sold,
        coalesce(sum(f.net_amount) filter (where f.is_revenue_order), 0)  as net_revenue,
        coalesce(sum(f.gross_margin) filter (where f.is_revenue_order), 0) as gross_margin,
        count(*) filter (where f.order_status = 'returned')               as returned_lines,
        count(*)                                                          as total_lines,
        coalesce(sum(f.net_amount) filter (
            where f.is_revenue_order and f.order_date > (select max(order_date) from {{ ref('fact_order_items') }}) - 30), 0) as net_revenue_30d
    from {{ ref('fact_order_items') }} f
    join {{ ref('dim_product') }} p on p.product_key = f.product_key
    group by p.product_id
)
select
    p.product_id, p.product_name, p.category, p.brand, p.list_price as current_list_price,
    s.units_sold, s.net_revenue, s.gross_margin,
    round(s.gross_margin / nullif(s.net_revenue, 0) * 100, 1)       as margin_pct,
    round(s.returned_lines::numeric / nullif(s.total_lines, 0) * 100, 1) as return_rate_pct,
    s.net_revenue_30d
from {{ ref('dim_product') }} p
join sales s on s.product_id = p.product_id
where p.is_current

-- The report layer must equal the fact layer to the cent (guards against join fan-out).
with fact as (
    select round(sum(net_amount), 2) as total from {{ ref('fact_order_items') }} where is_revenue_order
),
rpt as (
    select round(sum(net_revenue), 2) as total from {{ ref('rpt_daily_revenue') }}
)
select fact.total as fact_total, rpt.total as report_total
from fact, rpt
where fact.total is distinct from rpt.total

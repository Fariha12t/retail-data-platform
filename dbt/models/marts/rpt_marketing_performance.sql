-- Spend vs. attributed revenue per channel and day (channel on the order = last-touch attribution).
with spend as (
    select spend_date as report_date, channel, sum(impressions) as impressions, sum(clicks) as clicks, sum(spend) as spend
    from {{ ref('fact_marketing_spend_daily') }}
    group by 1, 2
),
rev as (
    select
        order_date as report_date, channel,
        count(*) filter (where is_revenue_order)                as orders,
        coalesce(sum(net_amount) filter (where is_revenue_order), 0) as net_revenue
    from {{ ref('fact_orders') }}
    group by 1, 2
),
joined as (
    select
        coalesce(s.report_date, r.report_date) as report_date,
        coalesce(s.channel, r.channel)         as channel,
        coalesce(s.impressions, 0) as impressions, coalesce(s.clicks, 0) as clicks, coalesce(s.spend, 0) as spend,
        coalesce(r.orders, 0) as orders, coalesce(r.net_revenue, 0) as net_revenue
    from spend s
    full outer join rev r on r.report_date = s.report_date and r.channel = s.channel
)
select
    *,
    round(clicks::numeric / nullif(impressions, 0) * 100, 2) as ctr_pct,
    round(spend / nullif(clicks, 0), 2)                      as cpc,
    round(net_revenue / nullif(spend, 0), 2)                 as roas,
    round(spend / nullif(orders, 0), 2)                      as cost_per_order
from joined
where report_date >= (select min(order_date) from {{ ref('fact_orders') }})

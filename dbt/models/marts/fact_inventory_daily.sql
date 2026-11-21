-- Grain: product x warehouse x day.
select
    s.snapshot_date,
    s.warehouse,
    s.product_id,
    coalesce(p.product_key, md5('unknown-product')) as product_key,
    s.stock_on_hand,
    s.reorder_level,
    s.stock_on_hand = 0                  as is_stockout,
    s.stock_on_hand < s.reorder_level    as is_below_reorder
from {{ ref('stg_inventory_snapshots') }} s
left join {{ ref('dim_product') }} p
    on p.product_id = s.product_id
   and cast(s.snapshot_date as timestamp) >= p.valid_from
   and (p.valid_to is null or cast(s.snapshot_date as timestamp) < p.valid_to)

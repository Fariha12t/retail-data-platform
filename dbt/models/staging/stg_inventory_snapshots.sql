with ranked as (
    select *,
        row_number() over (partition by snapshot_date, product_id, warehouse order by _ingested_at desc, _batch_id desc) as rn
    from {{ source('raw', 'inventory_snapshots') }}
)
select snapshot_date, product_id, upper(trim(warehouse)) as warehouse, stock_on_hand, reorder_level
from ranked
where rn = 1

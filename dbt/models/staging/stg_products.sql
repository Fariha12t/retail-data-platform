with ranked as (
    select *,
        row_number() over (partition by product_id order by updated_at desc, _ingested_at desc, _batch_id desc) as rn
    from {{ source('raw', 'products') }}
)
select
    product_id,
    upper(trim(sku))   as sku,
    trim(product_name) as product_name,
    trim(category)     as category,
    trim(brand)        as brand,
    unit_cost,
    list_price,
    updated_at
from ranked
where rn = 1

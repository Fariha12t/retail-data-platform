-- SCD Type 2 product dimension: price/cost history so margins use the cost valid at order time.
with snap as (
    select *,
        row_number() over (partition by product_id order by dbt_valid_from) as version_number
    from {{ ref('products_snapshot') }}
)
select
    {{ surrogate_key(['product_id', 'dbt_valid_from']) }} as product_key,
    product_id,
    sku,
    product_name,
    category,
    brand,
    unit_cost,
    list_price,
    round((list_price - unit_cost) / nullif(list_price, 0) * 100, 1) as margin_pct,
    case when version_number = 1 then cast('1900-01-01' as timestamp) else dbt_valid_from end as valid_from,
    dbt_valid_to         as valid_to,
    dbt_valid_to is null as is_current,
    version_number
from snap
union all
select
    md5('unknown-product'), -1, 'UNKNOWN', 'Unknown product', 'Unknown', cast(null as text),
    0, 0, cast(null as numeric), cast('1900-01-01' as timestamp), cast(null as timestamp), true, 1

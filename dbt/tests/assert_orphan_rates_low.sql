{{ config(severity='warn') }}
-- Share of order lines pointing at the "unknown" members should stay below 1%.
select unknown_lines, total_lines
from (
    select count(*) filter (where customer_key = md5('unknown-customer') or product_key = md5('unknown-product')) as unknown_lines,
           count(*) as total_lines
    from {{ ref('fact_order_items') }}
) t
where unknown_lines > 0.01 * total_lines

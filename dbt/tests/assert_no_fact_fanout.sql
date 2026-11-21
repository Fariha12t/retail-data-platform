-- Point-in-time dimension joins must not duplicate order lines:
-- fact rows can only be fewer than staging rows (lines whose order is missing), never more.
select fact_rows, stg_rows
from (
    select (select count(*) from {{ ref('fact_order_items') }}) as fact_rows,
           (select count(*) from {{ ref('stg_order_items') }}) as stg_rows
) t
where fact_rows > stg_rows

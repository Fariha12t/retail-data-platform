-- A customer must never have two versions valid at the same time.
select a.customer_id, a.version_number as v1, b.version_number as v2
from {{ ref('dim_customer') }} a
join {{ ref('dim_customer') }} b
  on a.customer_id = b.customer_id and a.version_number < b.version_number
 and a.valid_from < coalesce(b.valid_to, timestamp '9999-12-31')
 and b.valid_from < coalesce(a.valid_to, timestamp '9999-12-31')
 and a.valid_to is not null

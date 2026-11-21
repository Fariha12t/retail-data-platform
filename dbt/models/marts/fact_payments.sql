-- Grain: one row per payment transaction.
select
    p.payment_id,
    p.order_id,
    cast(p.paid_at as date) as paid_date,
    p.paid_at,
    p.method,
    p.status,
    p.amount
from {{ ref('stg_payments') }} p

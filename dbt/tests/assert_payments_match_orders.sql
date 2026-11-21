{{ config(severity='warn') }}
-- Captured payments should equal the order total. Mismatches usually mean a quarantined line or payment.
select order_id, net_amount, captured_amount
from {{ ref('fact_orders') }}
where payment_status = 'captured' and order_status in ('placed', 'shipped', 'delivered')
  and abs(net_amount - captured_amount) > 0.01

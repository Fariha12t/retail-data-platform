# Data model (star schema)

```mermaid
erDiagram
  dim_customer ||--o{ fact_order_items : customer_key
  dim_product  ||--o{ fact_order_items : product_key
  dim_date     ||--o{ fact_order_items : order_date
  dim_product  ||--o{ fact_inventory_daily : product_key
  fact_orders  ||--o{ fact_order_items : order_id
  fact_orders  ||--o{ fact_payments : order_id
  dim_customer { text customer_key PK
    int customer_id
    text email_hash
    text city
    text segment
    timestamp valid_from
    timestamp valid_to
    bool is_current }
  dim_product { text product_key PK
    int product_id
    text category
    numeric unit_cost
    numeric list_price
    timestamp valid_from
    timestamp valid_to
    bool is_current }
  fact_order_items { int order_item_id PK
    text customer_key FK
    text product_key FK
    date order_date FK
    int quantity
    numeric net_amount
    numeric gross_margin
    bool is_revenue_order }
  fact_orders { int order_id PK
    text customer_key
    numeric net_amount
    text payment_status }
  fact_payments { int payment_id PK
    int order_id
    text method
    numeric amount }
  fact_inventory_daily { date snapshot_date
    text warehouse
    text product_key FK
    int stock_on_hand
    bool is_below_reorder }
  fact_marketing_spend_daily { date spend_date
    text channel
    text campaign
    numeric spend }
```

## Grain
| Table | Grain |
|---|---|
| `fact_order_items` | one order line |
| `fact_orders` | one order |
| `fact_payments` | one payment transaction |
| `fact_inventory_daily` | product x warehouse x day |
| `fact_marketing_spend_daily` | campaign x day |

## Business rules
* **Revenue** counts orders in `placed`, `shipped`, `delivered`. `cancelled` and `returned` are reported separately, so past days can be restated when a return happens.
* **Net amount** = quantity x unit price x (1 - discount). **Gross margin** = net amount - quantity x unit cost valid at order time.
* **Attribution** is last-touch: the channel on the order.
* **Unknown members**: a fact row whose customer or product is missing (e.g. quarantined) points to a `-1` "Unknown" dimension row instead of being dropped. `assert_orphan_rates_low` warns if more than 1% do.
* **SCD2**: the first version of every member is valid from 1900-01-01, so history before the first snapshot still resolves.

## Reporting tables
`rpt_daily_revenue` (7-day average, week-over-week), `rpt_inventory_status` (days of cover, stock status), `rpt_marketing_performance` (CTR, CPC, ROAS, cost per order), `rpt_product_performance`.

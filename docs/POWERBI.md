# Power BI report

A `.pbix` file is binary and cannot be generated as code, so this is the exact recipe (about 20 minutes). A Streamlit version of the same pages is in `dashboard/app.py`.

## 1. Connect
Get data -> PostgreSQL database -> server `localhost:5432`, database `warehouse` -> Import mode.
Select schema `marts`: `dim_customer`, `dim_product`, `dim_date`, `fact_order_items`, `fact_orders`, `fact_inventory_daily`, `rpt_daily_revenue`, `rpt_inventory_status`, `rpt_marketing_performance`, `rpt_product_performance`.
For a cloud deployment point the same model at BigQuery/Redshift. Schedule refresh after the Airflow run (e.g. 03:30 UTC).

## 2. Relationships (Model view)
| From (many) | To (one) |
|---|---|
| `fact_order_items[customer_key]` | `dim_customer[customer_key]` |
| `fact_order_items[product_key]` | `dim_product[product_key]` |
| `fact_order_items[order_date]` | `dim_date[date_day]` |
| `fact_inventory_daily[product_key]` | `dim_product[product_key]` |

Mark `dim_date` as the date table. `dim_customer` and `dim_product` hold history, so use the fact-table keys for facts, and filter `is_current = TRUE` only on "current state" visuals.

## 3. Measures (DAX)
```DAX
Net Revenue = CALCULATE ( SUM ( fact_order_items[net_amount] ), fact_order_items[is_revenue_order] = TRUE () )
Gross Margin = CALCULATE ( SUM ( fact_order_items[gross_margin] ), fact_order_items[is_revenue_order] = TRUE () )
Margin % = DIVIDE ( [Gross Margin], [Net Revenue] )
Orders = CALCULATE ( DISTINCTCOUNT ( fact_order_items[order_id] ), fact_order_items[is_revenue_order] = TRUE () )
Avg Order Value = DIVIDE ( [Net Revenue], [Orders] )
Units Sold = CALCULATE ( SUM ( fact_order_items[quantity] ), fact_order_items[is_revenue_order] = TRUE () )
Net Revenue LY = CALCULATE ( [Net Revenue], SAMEPERIODLASTYEAR ( dim_date[date_day] ) )
Net Revenue WoW % = VAR prev = CALCULATE ( [Net Revenue], DATEADD ( dim_date[date_day], -7, DAY ) ) RETURN DIVIDE ( [Net Revenue] - prev, prev )
Net Revenue 7d Avg = AVERAGEX ( DATESINPERIOD ( dim_date[date_day], MAX ( dim_date[date_day] ), -7, DAY ), [Net Revenue] )
Return Rate % = DIVIDE ( CALCULATE ( COUNTROWS ( fact_order_items ), fact_order_items[order_status] = "returned" ), COUNTROWS ( fact_order_items ) )
ROAS = DIVIDE ( SUM ( rpt_marketing_performance[net_revenue] ), SUM ( rpt_marketing_performance[spend] ) )
Products Below Reorder = CALCULATE ( COUNTROWS ( rpt_inventory_status ), rpt_inventory_status[stock_status] IN { "below_reorder", "out_of_stock" } )
```

## 4. Pages
1. **Executive summary**: cards (Net Revenue, Orders, AOV, Margin %), daily revenue column chart with 7-day average line, WoW % card, date slicer.
2. **Sales**: revenue by category (bar), by channel (donut), top 10 products (table from `rpt_product_performance`), customer segment and city (from `dim_customer`).
3. **Marketing**: spend vs revenue by channel (clustered bar), ROAS by channel, CPC trend.
4. **Inventory**: stock status counts, table of `below_reorder` / `out_of_stock` / `low_cover` products sorted by `days_of_cover`.
5. **Data health** (optional): connect `audit.ingestion_batches` to show rows loaded, quarantined, last success.

Tip: put a screenshot of each page in this folder and link it from the README. Recruiters look at pictures first.

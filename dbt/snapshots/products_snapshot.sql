{% snapshot products_snapshot %}
{{ config(unique_key='product_id', strategy='timestamp', updated_at='updated_at') }}
-- SCD Type 2: price and cost history, so margin is calculated with the price valid at order time.
select * from {{ ref('stg_products') }}
{% endsnapshot %}

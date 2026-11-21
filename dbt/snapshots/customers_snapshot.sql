{% snapshot customers_snapshot %}
{{ config(unique_key='customer_id', strategy='timestamp', updated_at='updated_at') }}
-- SCD Type 2: every change to a customer (city, segment, ...) creates a new dated version.
select * from {{ ref('stg_customers') }}
{% endsnapshot %}

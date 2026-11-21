-- SCD Type 2 customer dimension built from the snapshot. One row per customer *version*.
-- Email is replaced by a hash + domain: analysts rarely need raw PII.
with snap as (
    select *,
        row_number() over (partition by customer_id order by dbt_valid_from) as version_number
    from {{ ref('customers_snapshot') }}
),
versions as (
    select
        {{ surrogate_key(['customer_id', 'dbt_valid_from']) }} as customer_key,
        customer_id,
        md5(email)                  as email_hash,
        split_part(email, '@', 2)   as email_domain,
        full_name,
        city,
        country,
        segment,
        signup_date,
        -- the first version is valid "since forever" so historical orders always find a customer
        case when version_number = 1 then cast('1900-01-01' as timestamp) else dbt_valid_from end as valid_from,
        dbt_valid_to                as valid_to,
        dbt_valid_to is null        as is_current,
        version_number
    from snap
)
select * from versions
union all
select
    md5('unknown-customer'), -1, cast(null as text), cast(null as text), 'Unknown customer',
    cast(null as text), cast(null as text), cast(null as text), cast(null as date),
    cast('1900-01-01' as timestamp), cast(null as timestamp), true, 1

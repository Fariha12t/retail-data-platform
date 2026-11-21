-- The API is re-pulled for the last few days (late corrections), so the newest pull wins.
with ranked as (
    select *,
        row_number() over (partition by spend_date, channel, campaign order by _ingested_at desc, _batch_id desc) as rn
    from {{ source('raw', 'marketing_spend') }}
)
select
    spend_date,
    lower(trim(channel)) as channel,
    trim(campaign)       as campaign,
    impressions,
    clicks,
    spend,
    upper(trim(currency)) as currency
from ranked
where rn = 1

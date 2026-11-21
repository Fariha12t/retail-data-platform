-- Grain: campaign x day.
select spend_date, channel, campaign, impressions, clicks, spend, currency
from {{ ref('stg_marketing_spend') }}

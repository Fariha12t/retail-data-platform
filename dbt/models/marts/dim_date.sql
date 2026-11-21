select
    d::date                              as date_day,
    extract(year from d)::int            as year,
    extract(quarter from d)::int         as quarter,
    extract(month from d)::int           as month,
    to_char(d, 'Mon')                    as month_name,
    extract(week from d)::int            as iso_week,
    extract(isodow from d)::int          as day_of_week,
    to_char(d, 'Dy')                     as day_name,
    extract(isodow from d) >= 6          as is_weekend,
    date_trunc('month', d)::date         as month_start,
    date_trunc('week', d)::date          as week_start
from generate_series('2024-01-01'::date, '2028-12-31'::date, interval '1 day') as d

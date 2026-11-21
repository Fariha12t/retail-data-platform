{# md5 hash of the given columns - a deterministic surrogate key (no external packages needed). #}
{% macro surrogate_key(fields) -%}
    md5(
    {%- for f in fields -%}
        coalesce(cast({{ f }} as {{ dbt.type_string() }}), '_null_')
        {%- if not loop.last %} || '-' || {% endif -%}
    {%- endfor -%}
    )
{%- endmacro %}

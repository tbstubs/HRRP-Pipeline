{#
    By default dbt prefixes a custom schema with the target schema, producing
    staging_marts and staging_staging. This project writes to the schemas
    created in sql/01_setup.sql, so a custom schema is used verbatim.

    The default behavior exists to stop developers overwriting each other in
    a shared warehouse. This is a single-developer project against its own
    account, so the prefix buys nothing and breaks the naming the setup SQL
    and the Power BI connection both expect.
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}

{#
    Title-case a CMS name, then restore acronyms that initcap() flattens.

    Snowflake's regexp_replace cannot upper-case a captured group, so each
    acronym needs its own explicit replacement. Generating them here keeps the
    model readable and the list editable in one place.

    DELIBERATELY EXCLUDED, measured 2026-10-29 against the real names:
      LA  "CALIFORNIA HOSPITAL MEDICAL CENTER LA" is Los Angeles and
          "CLINIC-CRYSTAL LA" is Crystal Lake -- not Louisiana
      IN  collides with the preposition
      CO  collides with "Co." for Company
      MT  collides with "Mount"
      NE  too few instances to justify the ambiguity
    Uppercasing those would introduce more errors than it fixes.
#}
{% macro display_name(column) %}
    {%- set acronyms = [
        'VA', 'LLC', 'HCA', 'UMass',
        'MD', 'NH', 'NY', 'TX', 'DC', 'IL', 'KS', 'MI',
        'SC', 'TN', 'NC', 'WI', 'MN', 'MO', 'MS', 'UT', 'AR', 'DE'
    ] -%}
    {%- set ns = namespace(expr = 'initcap(' ~ column ~ ')') -%}
    {%- for a in acronyms -%}
        {%- set titled = a[0] | upper ~ a[1:] | lower -%}
        {%- set ns.expr = "regexp_replace(" ~ ns.expr ~ ", '\\\\b" ~ titled ~ "\\\\b', '" ~ a ~ "')" -%}
    {%- endfor -%}
    {{ ns.expr }}
{% endmacro %}

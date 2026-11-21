{#- Name matching key. Must stay identical to pipeline.readers.normalize_name (Python);
    tests/test_dbt_db.py checks the two agree on every name in the data.
    ASCII + lower case, '&' -> 'and', 'St.'/'Ste.' -> 'saint'/'sainte',
    punctuation -> space, whitespace collapsed. -#}
{% macro normalize_name(column) -%}
    trim(regexp_replace(
        regexp_replace(
            regexp_replace(
                regexp_replace(
                    replace(lower(unaccent({{ column }})), '&', ' and '),
                    '\mste\.?\s', ' sainte ', 'g'),
                '\mst\.?\s', ' saint ', 'g'),
            '[^a-z0-9 ]', ' ', 'g'),
        '\s+', ' ', 'g'))
{%- endmacro %}

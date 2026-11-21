{#- Generic test: the combination of columns is unique (composite key).
    Written here instead of pulling in dbt_utils, so `dbt build` needs no packages. -#}
{% test unique_combination(model, columns) %}
select {{ columns | join(', ') }}, count(*) as n
from {{ model }}
group by {{ columns | join(', ') }}
having count(*) > 1
{% endtest %}

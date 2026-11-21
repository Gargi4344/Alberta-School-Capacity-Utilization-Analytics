-- One polygon per authority (public and separate codes never overlap).
select
    authority_code,
    authority_name as boundary_name,
    layer as boundary_layer,
    boundary_year,
    was_invalid as geometry_was_repaired,
    geom
from {{ source('raw', 'authority_boundary') }}

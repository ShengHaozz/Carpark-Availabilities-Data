-- Asserts that no carpark natural key (carpark_id, lot_type) has overlapping validity ranges in SCD Type 2 dimension.
-- Returns failing rows if two active or overlapping versions exist concurrently.

select
    a.carpark_id,
    a.lot_type,
    a.carpark_key as a_key,
    a.valid_from as a_valid_from,
    a.valid_to as a_valid_to,
    b.carpark_key as b_key,
    b.valid_from as b_valid_from,
    b.valid_to as b_valid_to
from {{ ref('dim_carpark') }} a
inner join {{ ref('dim_carpark') }} b
    on a.carpark_id = b.carpark_id
    and a.lot_type = b.lot_type
    and a.carpark_key <> b.carpark_key
    and a.valid_from < coalesce(b.valid_to, timestamp '9999-12-31 00:00:00')
    and coalesce(a.valid_to, timestamp '9999-12-31 00:00:00') > b.valid_from


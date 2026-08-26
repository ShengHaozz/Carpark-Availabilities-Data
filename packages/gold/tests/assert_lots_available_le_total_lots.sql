-- Asserts that lots_available never exceeds total_lots when total_lots is defined.
-- Returns failing rows where available lots exceed total capacity.

select
    availability_id,
    carpark_id,
    lot_type,
    snapshot_timestamp,
    lots_available,
    total_lots
from {{ ref('fct_lot_availability') }}
where total_lots is not null
  and total_lots > 0
  and lots_available > total_lots


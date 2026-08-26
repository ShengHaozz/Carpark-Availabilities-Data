-- Asserts that occupancy_rate is always between 0.0 (0%) and 1.0 (100%).
-- Returns failing rows where occupancy rate is out of realistic bounds.

select
    availability_id,
    carpark_id,
    lot_type,
    snapshot_timestamp,
    lots_available,
    total_lots,
    occupancy_rate
from {{ ref('fct_lot_availability') }}
where occupancy_rate is not null
  and (occupancy_rate < 0.0 or occupancy_rate > 1.0)


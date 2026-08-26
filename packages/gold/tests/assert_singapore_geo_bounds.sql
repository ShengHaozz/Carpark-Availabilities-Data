-- Asserts that carpark coordinates fall within Singapore's bounding box.
-- Latitude: ~1.15 to 1.48 | Longitude: ~103.55 to 104.10
-- Returns failing rows where coordinates are located outside of Singapore.

select
    carpark_key,
    carpark_id,
    lot_type,
    location_latitude,
    location_longitude
from {{ ref('dim_carpark') }}
where location_latitude is not null
  and location_longitude is not null
  and (
      location_latitude < 1.15
      or location_latitude > 1.48
      or location_longitude < 103.55
      or location_longitude > 104.10
  )


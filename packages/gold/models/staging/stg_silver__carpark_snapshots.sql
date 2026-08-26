with source_data as (
    select * from {{ source('silver', 'silver_cold') }}
),

typed_and_cleaned as (
    select
        to_hex(md5(to_utf8(concat(
            coalesce(carpark_id, ''), '|',
            coalesce(lot_type, ''), '|',
            cast(snapshot_timestamp as varchar)
        )))) as snapshot_id,
        cast(carpark_id as varchar) as carpark_id,
        cast(lot_type as varchar) as lot_type,
        cast(lots_available as integer) as lots_available,
        cast(total_lots as integer) as total_lots,
        cast(location_latitude as double) as location_latitude,
        cast(location_longitude as double) as location_longitude,
        cast(area as varchar) as area,
        cast(development as varchar) as development,
        cast(agency as varchar) as agency,
        cast(snapshot_timestamp as timestamp) as snapshot_timestamp,
        cast(ingestion_timestamp as timestamp) as ingestion_timestamp,
        cast(source_filepath as varchar) as source_filepath,
        row_number() over (
            partition by carpark_id, lot_type, snapshot_timestamp 
            order by ingestion_timestamp desc
        ) as row_num
    from source_data
    where carpark_id is not null
      and snapshot_timestamp is not null
)

select
    snapshot_id,
    carpark_id,
    lot_type,
    lots_available,
    total_lots,
    location_latitude,
    location_longitude,
    area,
    development,
    agency,
    snapshot_timestamp,
    ingestion_timestamp,
    source_filepath
from typed_and_cleaned
where row_num = 1


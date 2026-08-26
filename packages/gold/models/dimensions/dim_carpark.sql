{{ config(
    materialized='incremental',
    table_type='iceberg',
    incremental_strategy='merge',
    unique_key='carpark_key',
    schema='gold'
) }}

with snapshot_source as (
    select * from {{ ref('snp_carpark') }}
),

transformed as (
    select
        to_hex(md5(to_utf8(concat(
            carpark_id, '|',
            lot_type, '|',
            cast(dbt_valid_from as varchar)
        )))) as carpark_key,
        carpark_id,
        lot_type,
        total_lots,
        development,
        area,
        agency,
        location_latitude,
        location_longitude,
        dbt_valid_from as valid_from,
        dbt_valid_to as valid_to,
        case 
            when dbt_valid_to is null then true 
            else false 
        end as is_current
    from snapshot_source
)

select * from transformed


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

ranked as (
    select
        *,
        row_number() over (
            partition by carpark_id, lot_type 
            order by dbt_valid_from asc
        ) as version_rank
    from snapshot_source
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
        case 
            when version_rank = 1 then timestamp '1970-01-01 00:00:00'
            else dbt_valid_from
        end as valid_from,
        dbt_valid_to as valid_to,
        case 
            when dbt_valid_to is null then true 
            else false 
        end as is_current
    from ranked
)

select * from transformed


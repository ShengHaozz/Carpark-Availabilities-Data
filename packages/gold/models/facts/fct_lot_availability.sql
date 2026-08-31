{{ config(
    materialized='incremental',
    table_type='iceberg',
    incremental_strategy='merge',
    unique_key='availability_id',
    partitioned_by=['snapshot_date'],
    schema='gold'
) }}

with staging_snapshots as (
    select * from {{ ref('stg_silver__carpark_snapshots') }}
    {% if is_incremental() %}
    -- 7-day lookback window to support automatic backfills, late-arriving data, and reruns
    where snapshot_timestamp >= (
        select coalesce(date_add('day', -7, max(snapshot_timestamp)), timestamp '1970-01-01 00:00:00') 
        from {{ this }}
    )
    {% endif %}
),

dim_carparks as (
    select * from {{ ref('dim_carpark') }}
),

joined as (
    select
        s.snapshot_id as availability_id,
        d.carpark_key,
        s.carpark_id,
        s.lot_type,
        s.snapshot_timestamp,
        cast(s.snapshot_timestamp as date) as snapshot_date,
        s.lots_available,
        d.total_lots,
        case 
            when d.total_lots is not null and d.total_lots >= s.lots_available 
            then d.total_lots - s.lots_available
            else null 
        end as lots_occupied,
        case 
            when d.total_lots is not null and d.total_lots > 0 
            then round(cast(d.total_lots - s.lots_available as double) / cast(d.total_lots as double), 4)
            else null 
        end as occupancy_rate,
        case 
            when s.lots_available = 0 then true 
            else false 
        end as is_full,
        s.ingestion_timestamp
    from staging_snapshots s
    left join dim_carparks d
        on s.carpark_id = d.carpark_id
        and s.lot_type = d.lot_type
        and s.snapshot_timestamp >= d.valid_from
        and (s.snapshot_timestamp < d.valid_to or d.valid_to is null)
)

select * from joined


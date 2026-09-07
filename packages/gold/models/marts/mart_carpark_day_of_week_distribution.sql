{{ config(
    materialized='table',
    table_type='hive',
    format='textfile',
    field_delimiter=',',
    s3_data_dir='s3://' ~ env_var('S3_BUCKET') ~ '/level=mart/target=publisher/',
    schema='marts'
) }}

with base_observations as (
    select
        f.carpark_id,
        f.lot_type,
        f.snapshot_timestamp at time zone 'Asia/Singapore' as snapshot_ts_sgt,
        day_of_week(f.snapshot_timestamp at time zone 'Asia/Singapore') as day_of_week,
        case day_of_week(f.snapshot_timestamp at time zone 'Asia/Singapore')
            when 1 then 'Monday'
            when 2 then 'Tuesday'
            when 3 then 'Wednesday'
            when 4 then 'Thursday'
            when 5 then 'Friday'
            when 6 then 'Saturday'
            when 7 then 'Sunday'
        end as day_name,
        case 
            when day_of_week(f.snapshot_timestamp at time zone 'Asia/Singapore') in (6, 7) then true 
            else false 
        end as is_weekend,
        hour(f.snapshot_timestamp at time zone 'Asia/Singapore') as hour_of_day_sgt,
        f.lots_available,
        f.total_lots,
        f.lots_occupied,
        f.occupancy_rate,
        f.is_full
    from {{ ref('fct_lot_availability') }} f
    where f.snapshot_timestamp >= date_add('day', -60, current_timestamp)
),

carpark_meta as (
    select
        carpark_id,
        lot_type,
        total_lots,
        development,
        area,
        agency,
        location_latitude,
        location_longitude
    from {{ ref('dim_carpark') }}
    where is_current = true
),

hourly_aggregations as (
    select
        carpark_id,
        lot_type,
        day_of_week,
        day_name,
        is_weekend,
        hour_of_day_sgt,
        count(*) as observation_count,
        -- Available lots distribution
        min(lots_available) as lots_avail_min,
        approx_percentile(lots_available, array[0.10, 0.25, 0.50, 0.75, 0.90]) as lots_avail_pcts,
        max(lots_available) as lots_avail_max,
        round(avg(lots_available), 2) as lots_avail_mean,
        round(stddev(lots_available), 2) as lots_avail_stddev,
        -- Occupied lots distribution (null when total_lots is unknown)
        min(lots_occupied) as lots_occ_min,
        approx_percentile(lots_occupied, array[0.10, 0.25, 0.50, 0.75, 0.90]) as lots_occ_pcts,
        max(lots_occupied) as lots_occ_max,
        round(avg(lots_occupied), 2) as lots_occ_mean,
        round(stddev(lots_occupied), 2) as lots_occ_stddev,
        -- Occupancy rate distribution (null when total_lots is unknown)
        min(occupancy_rate) as occupancy_min,
        approx_percentile(occupancy_rate, array[0.10, 0.25, 0.50, 0.75, 0.90]) as occupancy_pcts,
        max(occupancy_rate) as occupancy_max,
        round(avg(occupancy_rate), 4) as occupancy_mean,
        round(stddev(occupancy_rate), 4) as occupancy_stddev,
        -- Capacity & Fullness probabilities
        round(cast(sum(case when is_full then 1 else 0 end) as double) / count(*), 4) as probability_full,
        case 
            when sum(case when occupancy_rate is not null then 1 else 0 end) > 0 
            then round(cast(sum(case when occupancy_rate >= 0.90 then 1 else 0 end) as double) / count(*), 4)
            else null 
        end as probability_high_occupancy
    from base_observations
    group by 
        carpark_id, 
        lot_type, 
        day_of_week, 
        day_name, 
        is_weekend, 
        hour_of_day_sgt
),

final_joined as (
    select
        to_hex(md5(to_utf8(concat(
            h.carpark_id, '|',
            h.lot_type, '|',
            cast(h.day_of_week as varchar), '|',
            cast(h.hour_of_day_sgt as varchar)
        )))) as distribution_id,
        h.carpark_id,
        h.lot_type,
        h.day_of_week,
        h.day_name,
        h.is_weekend,
        h.hour_of_day_sgt,
        h.observation_count,
        -- Lots Available stats
        h.lots_avail_min,
        h.lots_avail_pcts[1] as lots_avail_p10,
        h.lots_avail_pcts[2] as lots_avail_p25,
        h.lots_avail_pcts[3] as lots_avail_median,
        h.lots_avail_pcts[4] as lots_avail_p75,
        h.lots_avail_pcts[5] as lots_avail_p90,
        h.lots_avail_max,
        h.lots_avail_mean,
        h.lots_avail_stddev,
        -- Lots Occupied stats
        h.lots_occ_min,
        case when h.lots_occ_pcts is not null then h.lots_occ_pcts[1] else null end as lots_occ_p10,
        case when h.lots_occ_pcts is not null then h.lots_occ_pcts[2] else null end as lots_occ_p25,
        case when h.lots_occ_pcts is not null then h.lots_occ_pcts[3] else null end as lots_occ_median,
        case when h.lots_occ_pcts is not null then h.lots_occ_pcts[4] else null end as lots_occ_p75,
        case when h.lots_occ_pcts is not null then h.lots_occ_pcts[5] else null end as lots_occ_p90,
        h.lots_occ_max,
        h.lots_occ_mean,
        h.lots_occ_stddev,
        -- Occupancy Rate stats
        h.occupancy_min,
        case when h.occupancy_pcts is not null then h.occupancy_pcts[1] else null end as occupancy_p10,
        case when h.occupancy_pcts is not null then h.occupancy_pcts[2] else null end as occupancy_p25,
        case when h.occupancy_pcts is not null then h.occupancy_pcts[3] else null end as occupancy_median,
        case when h.occupancy_pcts is not null then h.occupancy_pcts[4] else null end as occupancy_p75,
        case when h.occupancy_pcts is not null then h.occupancy_pcts[5] else null end as occupancy_p90,
        h.occupancy_max,
        h.occupancy_mean,
        h.occupancy_stddev,
        -- Fullness and Congestion probabilities
        h.probability_full,
        h.probability_high_occupancy,
        -- Dimension attributes
        d.development,
        d.area,
        d.agency,
        d.total_lots,
        case 
            when d.total_lots is not null and d.total_lots > 0 then true 
            else false 
        end as has_capacity_data,
        d.location_latitude,
        d.location_longitude,
        current_timestamp as generated_at
    from hourly_aggregations h
    left join carpark_meta d
        on h.carpark_id = d.carpark_id
        and h.lot_type = d.lot_type
)

select * from final_joined

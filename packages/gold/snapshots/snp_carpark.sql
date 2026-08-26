{% snapshot snp_carpark %}

{{
    config(
      target_schema='prod_gold',
      unique_key="to_hex(md5(to_utf8(concat(carpark_id, '|', lot_type))))",
      strategy='check',
      check_cols=['total_lots', 'development', 'area', 'agency', 'location_latitude', 'location_longitude'],
      invalidate_hard_deletes=False
    )
}}

with staging as (
    select * from {{ ref('stg_silver__carpark_snapshots') }}
    -- Prunes Athena partition scan to the rolling last 7 days (1 week)
    where snapshot_timestamp >= date_add('day', -7, current_timestamp)
),

latest_carpark_state as (
    select
        carpark_id,
        lot_type,
        total_lots,
        development,
        area,
        agency,
        location_latitude,
        location_longitude,
        snapshot_timestamp
    from (
        select
            carpark_id,
            lot_type,
            total_lots,
            development,
            area,
            agency,
            location_latitude,
            location_longitude,
            snapshot_timestamp,
            row_number() over (
                partition by carpark_id, lot_type 
                order by snapshot_timestamp desc
            ) as rn
        from staging
    )
    where rn = 1
)

select * from latest_carpark_state

{% endsnapshot %}

-- Test: assert_mart_percentile_integrity.sql
-- Validates statistical monotonic integrity and bounding constraints for mart_carpark_day_of_week_distribution.

with validation_failures as (
    select
        distribution_id,
        carpark_id,
        lot_type,
        day_of_week,
        hour_of_day_sgt,
        lots_avail_min,
        lots_avail_p10,
        lots_avail_p25,
        lots_avail_median,
        lots_avail_p75,
        lots_avail_p90,
        lots_avail_max,
        occupancy_min,
        occupancy_p10,
        occupancy_p25,
        occupancy_median,
        occupancy_p75,
        occupancy_p90,
        occupancy_max,
        probability_full,
        probability_high_occupancy
    from {{ ref('mart_carpark_day_of_week_distribution') }}
    where
        -- 1. Available lots percentiles must be monotonically ordered (allowing minor approx_percentile margin)
        lots_avail_min > lots_avail_p10
        or lots_avail_p10 > lots_avail_p25
        or lots_avail_p25 > lots_avail_median
        or lots_avail_median > lots_avail_p75
        or lots_avail_p75 > lots_avail_p90
        or lots_avail_p90 > lots_avail_max
        or lots_avail_min < 0

        -- 2. Occupancy rate bounds (0.0 to 1.0) when capacity data is present
        or (
            occupancy_median is not null and (
                occupancy_min < 0.0
                or occupancy_max > 1.0
                or occupancy_min > occupancy_p10
                or occupancy_p10 > occupancy_p25
                or occupancy_p25 > occupancy_median
                or occupancy_median > occupancy_p75
                or occupancy_p75 > occupancy_p90
                or occupancy_p90 > occupancy_max
            )
        )

        -- 3. Probability metrics must fall strictly within [0.0, 1.0]
        or probability_full < 0.0
        or probability_full > 1.0
        or (probability_high_occupancy is not null and (probability_high_occupancy < 0.0 or probability_high_occupancy > 1.0))
)

select * from validation_failures

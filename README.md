# Carpark-Availabilities-Data
Data ingestion and ELT pipeline from LTA's DataMall API for Carpark Availabilities 


## Problem Statement
When planning a trip via car, drivers want an estimate of which carparks are usually available at specific times. However, most applications that utilise LTA's DataMall API only show availabilities at the current time, rather than historical availabilities throughout the day and week.

Gap: A system that captures historical availability patterns and surfaces them in a form that helps drivers make informed parking decisions.

## Core Business Questions
1. Given a target location and target arrival time, which carparks within 1km have the highest historical availability at that time-of-week?
2. For a specific carpark, what does occupancy look like across a typical week?
3. For a specific carpark currently filling up, when is it likely to hit 95% capacity based on historical fill rates?
4. Which carparks have the most volatile availability (high variance) vs the most predictable (low variance)?
5. Are there carparks that are systematically full at certain times that drivers should avoid entirely?
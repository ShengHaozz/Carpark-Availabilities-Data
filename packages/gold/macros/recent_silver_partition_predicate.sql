{% macro recent_silver_partition_predicate() %}
    {#
      Athena partition projection enumerates every possible S3 prefix unless
      year, month, and day are constrained with literal values. This includes
      today and the preceding configured calendar days.
    #}
    {% set lookback_days = var('silver_lookback_days') | int %}
    {% set first_partition_date = (run_started_at - modules.datetime.timedelta(days=lookback_days)).date() %}
    (
        {% for day_offset in range(lookback_days + 1) %}
            {% set partition_date = first_partition_date + modules.datetime.timedelta(days=day_offset) %}
            (
                year = {{ partition_date.strftime('%Y') }}
                and month = {{ partition_date.strftime('%m') | int }}
                and day = {{ partition_date.strftime('%d') | int }}
            )
            {% if not loop.last %}or{% endif %}
        {% endfor %}
    )
{% endmacro %}

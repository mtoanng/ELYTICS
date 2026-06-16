from backend.config.types import (
    MetadataConfig,
    TabularConfig,
    TimeseriesConfig,
)

_USER = ["IdM2BCD_holmes_pemely_sherlock", "IdM2BCD_holmes_pemely_development"]
# 12 hour TTL due to ETL schedules
_TABULAR_TTL = 43200
_META_TTL = 43200
_TS_TTL = 43200

# soh disabled, the table and page needs a lot of work.

TABULAR_CONFIG: list[TabularConfig] = [
    TabularConfig(table_name="runtime",                 route_name="runtime",                 auth_groups=_USER, ttl=_TABULAR_TTL),
    TabularConfig(table_name="order",               route_name="order",               auth_groups=_USER, ttl=_TABULAR_TTL),
    TabularConfig(table_name="polcurve",            route_name="polcurve",            auth_groups=_USER, ttl=_TABULAR_TTL, required_filters=["order_id", "sample_name"]),
    TabularConfig(table_name="vlite",            route_name="vlite",            auth_groups=_USER, ttl=_TABULAR_TTL, required_filters=["order_id"]),
    TabularConfig(table_name="sample",              route_name="sample",              auth_groups=_USER, ttl=_TABULAR_TTL),
    TabularConfig(table_name="soh_fleet",           route_name="soh_fleet",           auth_groups=_USER, ttl=_TABULAR_TTL),
    TabularConfig(table_name="soh_stack",           route_name="soh_stack",           auth_groups=_USER, ttl=_TABULAR_TTL, required_filters=["sample_name"]),
    TabularConfig(
        table_name="testrig_statistics",
        route_name="testrig_statistics",
        auth_groups=_USER,
        ttl=_TABULAR_TTL,
    ),
    TabularConfig(
        table_name="track_record",
        route_name="track_record",
        auth_groups=_USER,
        ttl=_TABULAR_TTL,
    ),
    TabularConfig(
        table_name="event",
        route_name="event",
        auth_groups=_USER,
        ttl=_TABULAR_TTL,
        required_filters=["order_id"]
    )
]

TIMESERIES_CONFIG: list[TimeseriesConfig] = [
    TimeseriesConfig(
        table_name="testrig_activity",
        route_name="testrig_activity",
        auth_groups=_USER,
        ttl=_TS_TTL,
        required_filters=["testrig_id"],
    ),
    TimeseriesConfig(
        table_name="timeseries_exp",
        route_name="timeseries_exp",
        auth_groups=_USER,
        ttl=_TS_TTL,
        required_filters=["order_id", "testrig_id", "sample_name"],
    ),
]

METADATA_CONFIG: list[MetadataConfig] = [
    MetadataConfig(
        table_name="polcurve", route_name="polcurve", auth_groups=_USER, ttl=_META_TTL
    ),
    MetadataConfig(
        table_name="vlite", route_name="vlite", auth_groups=_USER, ttl=_META_TTL
    ),
    MetadataConfig(
        table_name="timeseries_exp",
        route_name="timeseries_exp",
        auth_groups=_USER,
        ttl=_META_TTL,
    ),
    MetadataConfig(table_name="soh_fleet", route_name="soh", auth_groups=_USER, ttl=_META_TTL),
    MetadataConfig(
        table_name="testrig_activity",
        route_name="testrig_activity",
        auth_groups=_USER,
        ttl=_META_TTL,
    ),
    MetadataConfig(
        table_name="track_record",
        route_name="track_record",
        auth_groups=_USER,
        ttl=_META_TTL,
    ),
]

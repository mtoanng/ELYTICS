from backend.internal.config_types import (
    MetadataConfig,
    TabularConfig,
    TimeseriesConfig,
)

_USER = ["IdM2BCD_holmes_pemely_user"]
_TABULAR_TTL = 3600
_META_TTL = 7200
_TS_TTL = 1800

# soh disabled, the table and page needs a lot of work.

TABULAR_CONFIG: list[TabularConfig] = [
    TabularConfig(
        table_name="ccm", route_name="ccm", auth_groups=_USER, ttl=_TABULAR_TTL
    ),
    TabularConfig(
        table_name="order", route_name="order", auth_groups=_USER, ttl=_TABULAR_TTL
    ),
    TabularConfig(
        table_name="polcurve",
        route_name="polcurve",
        auth_groups=_USER,
        ttl=_TABULAR_TTL,
        required_filters=["order_id"],
    ),
    TabularConfig(
        table_name="polcurve_vlite",
        route_name="polcurve_vlite",
        auth_groups=_USER,
        ttl=_TABULAR_TTL,
        required_filters=["order_id"],
    ),
    TabularConfig(
        table_name="sample", route_name="sample", auth_groups=_USER, ttl=_TABULAR_TTL
    ),
    # TabularConfig(table_name="soh",                 route_name="soh",                 auth_groups=_USER, ttl=_TABULAR_TTL, required_filters=["sample_name"]),
    TabularConfig(
        table_name="testrig_activity",
        route_name="testrig_activity",
        auth_groups=_USER,
        ttl=_TABULAR_TTL,
        required_filters=["testrig_id"],
    ),
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
]

TIMESERIES_CONFIG: list[TimeseriesConfig] = [
    TimeseriesConfig(
        table_name="timeseries_exp",
        route_name="timeseries_exp",
        auth_groups=_USER,
        ttl=_TS_TTL,
        required_filters=["order_id"],
    ),
]

METADATA_CONFIG: list[MetadataConfig] = [
    MetadataConfig(
        table_name="polcurve", route_name="polcurve", auth_groups=_USER, ttl=_META_TTL
    ),
    MetadataConfig(
        table_name="polcurve_vlite",
        route_name="polcurve_vlite",
        auth_groups=_USER,
        ttl=_META_TTL,
    ),
    MetadataConfig(
        table_name="timeseries_exp",
        route_name="timeseries_exp",
        auth_groups=_USER,
        ttl=_META_TTL,
    ),
    # MetadataConfig(table_name="soh", route_name="soh", auth_groups=_USER, ttl=_META_TTL),
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

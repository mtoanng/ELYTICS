from backend.internal.config_types import MetadataConfig, TabularConfig, TimeseriesConfig

_USER = ["IdM2BCD_holmes_pemely_user"]
_TABULAR_TTL = 3600

TABULAR_CONFIG: list[TabularConfig] = [
    TabularConfig(table_name="component", route_name="component", auth_groups=_USER, ttl=_TABULAR_TTL),
    TabularConfig(table_name="eol", route_name="eol", auth_groups=_USER, ttl=_TABULAR_TTL),
    TabularConfig(table_name="polcurve", route_name="polcurve", auth_groups=_USER, ttl=_TABULAR_TTL),
    TabularConfig(table_name="production", route_name="production", auth_groups=_USER, ttl=_TABULAR_TTL),
    TabularConfig(table_name="soaking", route_name="soaking", auth_groups=_USER, ttl=_TABULAR_TTL),
    TabularConfig(table_name="stack", route_name="stack", auth_groups=_USER, ttl=_TABULAR_TTL),
]

TIMESERIES_CONFIG: list[TimeseriesConfig] = []

METADATA_CONFIG: list[MetadataConfig] = []

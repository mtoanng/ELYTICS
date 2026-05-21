from backend.config.types import MetadataConfig, TabularConfig, TimeseriesConfig

_USER = ["IdM2BCD_holmes_pemely_enola", "IdM2BCD_holmes_pemely_development"]
# 12 hour TTL due to ETL schedules
_TABULAR_TTL = 43200

# Enola routes require management group: IdM2BCD_holmes_pemely_management
TABULAR_CONFIG: list[TabularConfig] = [
    TabularConfig(table_name="customer", route_name="customer", auth_groups=_USER, ttl=_TABULAR_TTL),
]

TIMESERIES_CONFIG: list[TimeseriesConfig] = []
METADATA_CONFIG: list[MetadataConfig] = []

from dataclasses import dataclass, field
import re

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass
class TabularConfig:
    table_name: str
    route_name: str
    auth_groups: list[str]
    ttl: int
    required_filters: list[str] = field(default_factory=list)
    max_limit: int = 5000


@dataclass
class TimeseriesConfig:
    table_name: str
    route_name: str
    auth_groups: list[str]
    ttl: int
    required_filters: list[str] = field(default_factory=list)


@dataclass
class MetadataConfig:
    table_name: str
    route_name: str
    auth_groups: list[str]
    ttl: int


def validate_space_configs(
    space: str,
    tabular: list[TabularConfig],
    timeseries: list[TimeseriesConfig],
    metadata: list[MetadataConfig],
) -> None:
    def _validate_group_route_names(
        group_name: str,
        configs: list[TabularConfig | TimeseriesConfig | MetadataConfig],
    ) -> None:
        seen: set[str] = set()
        for cfg in configs:
            if cfg.route_name in seen:
                raise ValueError(
                    f"[{space}] duplicate route_name in {group_name}: {cfg.route_name!r}"
                )
            seen.add(cfg.route_name)

    for cfg in [*tabular, *timeseries, *metadata]:
        if not _IDENTIFIER_RE.fullmatch(cfg.table_name):
            raise ValueError(f"[{space}] invalid table_name: {cfg.table_name!r}")
        if not _IDENTIFIER_RE.fullmatch(cfg.route_name):
            raise ValueError(f"[{space}] invalid route_name: {cfg.route_name!r}")
        if not cfg.auth_groups:
            raise ValueError(f"[{space}] route {cfg.route_name!r} has no auth_groups")
        if cfg.ttl <= 0:
            raise ValueError(f"[{space}] route {cfg.route_name!r} ttl must be > 0")

    _validate_group_route_names("tabular", tabular)
    _validate_group_route_names("timeseries", timeseries)
    _validate_group_route_names("metadata", metadata)

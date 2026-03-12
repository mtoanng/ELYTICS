from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from internal.auth import require_groups
from internal.util import fully_qualified_view, get_query_result

router = APIRouter()

DEFAULT_SPACE_GROUPS = {
    "sherlock": ["IdM2BCD_holmes_pemely_user"],
    "watson": ["IdM2BCD_holmes_pemely_user"],
    "mycroft": ["IdM2BCD_holmes_pemely_user"],
    "enola": ["IdM2BCD_holmes_pemely_management"],
}

# Map table names directly. Final view name:
# holmes_<space>_<data|metadata>_<table_name>_view
SPACE_TABLE_MAP: dict[str, dict[str, list[str]]] = {
    "sherlock": {
        "data": [
            "ccm",
            "order",
            "polcurve",
            "polcurve_vlite",
            "sample",
            "soh",
            "testrig_activity",
            "testrig_statistics",
            "timeseries_exp",
            "track_record",
        ],
        "metadata": [
            "polcurve",
            "polcurve_vlite",
            "timeseries_exp",
        ],
    },
    "watson": {
        "data": [],
        "metadata": [],
    },
    "mycroft": {
        "data": [],
        "metadata": [],
    },
    "enola": {
        "data": [],
        "metadata": [],
    },
}

# Tables that require specific filters to protect query cost.
REQUIRED_FILTERS: dict[str, dict[str, dict[str, list[str]]]] = {
    "sherlock": {
        "data": {
            "timeseries_exp": ["experiment_id"],
            "track_record": ["experiment_id"],
        },
        "metadata": {},
    }
}


def _parse_filters(request: Request) -> dict[str, list[str]]:
    excluded = {"limit", "offset", "sort_by", "sort_dir"}
    parsed: dict[str, list[str]] = defaultdict(list)

    for key, value in request.query_params.multi_items():
        if key in excluded:
            continue
        parsed[key].append(value)

    return dict(parsed)


def _register_table_route(space: str, data_kind: str, table_name: str) -> None:
    required_groups = DEFAULT_SPACE_GROUPS.get(space, ["IdM2BCD_holmes_pemely_user"])
    required_filters = REQUIRED_FILTERS.get(space, {}).get(data_kind, {}).get(table_name, [])
    route_tag = f"{space.title()} - {data_kind.title()}"
    # Reflect the actual view segment (metadata -> meta) in the OpenAPI description.
    view_segment = "meta" if data_kind == "metadata" else data_kind
    resolved_view = f"holmes_{space}_{view_segment}_{table_name}_view"

    async def route_handler(
        request: Request,
        limit: int = Query(100, ge=1, le=5000),
        offset: int = Query(0, ge=0),
        sort_by: str | None = Query(None),
        sort_dir: str = Query("asc"),
        token: dict = Depends(require_groups(required_groups)),
    ):
        _ = token
        normalized_sort_dir = sort_dir.lower()
        if normalized_sort_dir not in {"asc", "desc"}:
            raise HTTPException(status_code=400, detail="sort_dir must be either 'asc' or 'desc'")

        filters = _parse_filters(request)

        for filter_name in required_filters:
            if filter_name not in filters:
                raise HTTPException(
                    status_code=400,
                    detail=f"Missing required filter '{filter_name}' for table '{table_name}'",
                )

        view_name = fully_qualified_view(space=space, data_kind=data_kind, table_name=table_name)
        data = get_query_result(
            view_name=view_name,
            filters=filters,
            sort_by=sort_by,
            sort_dir=normalized_sort_dir,
            limit=limit,
            offset=offset,
        )
        return {"data": data}

    router.add_api_route(
        path=f"/api/{space}/tables/{data_kind}/{table_name}",
        endpoint=route_handler,
        methods=["GET"],
        name=f"{space}_{data_kind}_{table_name}",
        tags=[route_tag],
        summary=f"{space} {data_kind} {table_name}",
        description=(
            f"Query mapped Databricks view `{resolved_view}` with optional filters, sorting, and pagination."
        ),
    )


for _space, _kind_map in SPACE_TABLE_MAP.items():
    for _data_kind, _tables in _kind_map.items():
        for _table_name in _tables:
            _register_table_route(
                space=_space,
                data_kind=_data_kind,
                table_name=_table_name,
            )

from datetime import datetime, timezone

import dash_mantine_components as dmc
from dash import Input, Output, callback, dcc, html, register_page
from dash_iconify import DashIconify

from services.backend_service import get_table_stats

register_page(__name__, path="/system", title="HOLMES - System")


def layout():
    return dmc.Container(
        size="xl",
        py="xl",
        children=[
            dcc.Interval(id="system-stats-interval", interval=300, max_intervals=1),
            dcc.Store(id="system-stats-store"),
            dmc.Stack(
                gap="lg",
                children=[
                    dmc.Group(
                        justify="space-between",
                        children=[
                            dmc.Stack(
                                gap=2,
                                children=[
                                    dmc.Title("System Table Statistics", order=1),
                                    dmc.Text(
                                        "Benchmark statistics for all configured Databricks views. Results are cached for 1 hour.",
                                        c="dimmed",
                                        size="sm",
                                    ),
                                ],
                            ),
                            dmc.Button(
                                "Refresh",
                                id="system-stats-refresh-btn",
                                variant="light",
                                leftSection=DashIconify(icon="tabler:refresh", width=16),
                                size="sm",
                            ),
                        ],
                    ),
                    html.Div(
                        id="system-stats-content",
                        children=dmc.Center(
                            dmc.Loader(size="lg"),
                            style={"minHeight": "200px"},
                        ),
                    ),
                ],
            ),
        ],
    )


@callback(
    Output("system-stats-store", "data"),
    Input("system-stats-interval", "n_intervals"),
    Input("system-stats-refresh-btn", "n_clicks"),
    prevent_initial_call=False,
)
def fetch_stats(_interval, _clicks):
    try:
        return get_table_stats()
    except Exception as exc:
        return {"error": str(exc)}


@callback(
    Output("system-stats-content", "children"),
    Input("system-stats-store", "data"),
    prevent_initial_call=True,
)
def render_stats(data):
    if not data:
        return dmc.Text("No data available.", c="dimmed")

    if "error" in data:
        return dmc.Alert(
            data["error"],
            title="Failed to load statistics",
            color="red",
            icon=DashIconify(icon="tabler:alert-triangle"),
        )

    results = data.get("results", [])
    error_count = data.get("error_count", 0)

    # Meta info
    generated_ts = data.get("generated_at_utc")
    try:
        generated_str = datetime.fromtimestamp(generated_ts, tz=timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S UTC"
        )
    except Exception:
        generated_str = str(generated_ts)

    meta_row = dmc.Group(
        gap="sm",
        children=[
            dmc.Badge(
                f"Cache: {data.get('cache', '?').upper()}",
                color="green" if data.get("cache") == "hit" else "orange",
                variant="light",
            ),
            dmc.Text(
                f"Query duration: {data.get('duration_seconds', '?')}s",
                size="sm",
                c="dimmed",
            ),
            dmc.Text(f"Generated: {generated_str}", size="sm", c="dimmed"),
        ],
    )

    # Summary stat cards
    summary_grid = dmc.SimpleGrid(
        cols={"base": 2, "sm": 4},
        spacing="md",
        children=[
            _stat_card(
                "Total Tables",
                str(data.get("table_count", 0)),
                "tabler:table",
                "blue",
            ),
            _stat_card(
                "OK",
                str(data.get("ok_count", 0)),
                "tabler:circle-check",
                "green",
            ),
            _stat_card(
                "Errors",
                str(error_count),
                "tabler:alert-triangle",
                "red" if error_count > 0 else "gray",
            ),
            _stat_card(
                "Est. Total Size",
                data.get("estimated_total_size_all_tables", "—"),
                "tabler:database",
                "violet",
            ),
        ],
    )

    # Results table rows
    table_rows = []
    for r in results:
        status = r.get("status", "?")
        is_ok = status == "ok"
        table_rows.append(
            [
                r.get("space", "—"),
                r.get("data_kind", "—"),
                r.get("table", "—"),
                f"{r['row_count']:,}" if is_ok else "—",
                str(r.get("column_count", "—")) if is_ok else "—",
                f"{r.get('avg_row_bytes', 0):.0f} B" if is_ok else "—",
                r.get("estimated_total_size", "—") if is_ok else "—",
                status.upper(),
            ]
        )

    results_table = dmc.Table(
        data={
            "head": ["Space", "Kind", "Table", "Rows", "Columns", "Avg Row", "Est. Size", "Status"],
            "body": table_rows,
        },
        striped=True,
        highlightOnHover=True,
        withTableBorder=True,
        withColumnBorders=True,
    )

    return dmc.Stack(
        gap="lg",
        children=[meta_row, summary_grid, results_table],
    )


def _stat_card(label: str, value: str, icon: str, color: str = "blue"):
    return dmc.Paper(
        p="md",
        radius="md",
        withBorder=True,
        children=dmc.Group(
            gap="sm",
            children=[
                dmc.ThemeIcon(
                    DashIconify(icon=icon, width=20),
                    size="lg",
                    radius="md",
                    color=color,
                    variant="light",
                ),
                dmc.Stack(
                    gap=0,
                    children=[
                        dmc.Text(value, fw=700, size="xl", lh=1),
                        dmc.Text(label, size="xs", c="dimmed"),
                    ],
                ),
            ],
        ),
    )

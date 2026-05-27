"""Deploy SQL views from views/spaces into Databricks."""

from __future__ import annotations

import argparse
import inspect
import os
from pathlib import Path

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementState

SPACES_DIR = Path(inspect.getfile(inspect.currentframe())).parent / "spaces"


def build_view_name(sql_path: Path, spaces_dir: Path = SPACES_DIR) -> str:
    """Derive the Databricks view name from a SQL file path under spaces/."""
    segments = list(sql_path.relative_to(spaces_dir).with_suffix("").parts)
    return "holmes_" + "_".join(segments) + "_view"


def collect_sql_files(spaces_dir: Path = SPACES_DIR) -> list[tuple[Path, str]]:
    return [
        (p, build_view_name(p, spaces_dir)) for p in sorted(spaces_dir.rglob("*.sql"))
    ]


def deploy_view_with_sql_warehouse(
    client: WorkspaceClient,
    warehouse_id: str,
    catalog: str,
    schema: str,
    view_name: str,
    sql_body: str,
) -> None:
    statement = (
        f"CREATE OR REPLACE VIEW `{catalog}`.`{schema}`.`{view_name}` AS\n{sql_body}"
    )
    response = client.statement_execution.execute_statement(
        warehouse_id=warehouse_id,
        statement=statement,
        wait_timeout="30s",
    )
    if response.status.state != StatementState.SUCCEEDED:
        raise RuntimeError(
            f"Failed to deploy '{view_name}': "
            f"[{response.status.error.error_code}] {response.status.error.message}"
        )


def deploy_view_with_spark(
    spark,
    catalog: str,
    schema: str,
    view_name: str,
    sql_body: str,
) -> None:
    statement = (
        f"CREATE OR REPLACE VIEW `{catalog}`.`{schema}`.`{view_name}` AS\n{sql_body}"
    )
    spark.sql(statement)


def _running_in_databricks_runtime() -> bool:
    return "DATABRICKS_RUNTIME_VERSION" in os.environ


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Deploy SQL views from spaces/ to Databricks"
    )
    parser.add_argument(
        "--catalog", default=os.environ.get("DATABRICKS_CATALOG", "ps_xplatform_dev")
    )
    parser.add_argument(
        "--schema", default=os.environ.get("DATABRICKS_SCHEMA", "pemely_dev")
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    catalog = args.catalog
    schema = args.schema
    failures: list[tuple[str, str]] = []

    sql_files = collect_sql_files()
    print(f"Found {len(sql_files)} view(s) to deploy -> {catalog}.{schema}")

    if _running_in_databricks_runtime():
        from pyspark.sql import SparkSession

        spark = SparkSession.getActiveSession() or SparkSession.builder.getOrCreate()
        print("Execution mode: Databricks job cluster (Spark SQL)")

        for sql_path, view_name in sql_files:
            print(f"  deploying {view_name} ...", end=" ", flush=True)
            try:
                deploy_view_with_spark(
                    spark=spark,
                    catalog=catalog,
                    schema=schema,
                    view_name=view_name,
                    sql_body=sql_path.read_text(encoding="utf-8"),
                )
                print("OK")
            except Exception as exc:
                failures.append((view_name, str(exc)))
                print("FAILED")
    else:
        client = WorkspaceClient(
            host=os.environ["DATABRICKS_HOST"],
            azure_client_id=os.environ["ARM_CLIENT_ID"],
            azure_client_secret=os.environ["ARM_CLIENT_SECRET"],
            azure_tenant_id=os.environ["ARM_TENANT_ID"],
        )
        warehouse_id = os.environ["DATABRICKS_WAREHOUSE_ID"]
        print("Execution mode: External client (SQL Warehouse API)")

        for sql_path, view_name in sql_files:
            print(f"  deploying {view_name} ...", end=" ", flush=True)
            try:
                deploy_view_with_sql_warehouse(
                    client=client,
                    warehouse_id=warehouse_id,
                    catalog=catalog,
                    schema=schema,
                    view_name=view_name,
                    sql_body=sql_path.read_text(encoding="utf-8"),
                )
                print("OK")
            except Exception as exc:
                failures.append((view_name, str(exc)))
                print("FAILED")

    if failures:
        print("\nDeployment finished with failures:")
        for view_name, error in failures:
            print(f"  - {view_name}: {error}")
        raise RuntimeError(
            f"Failed deployments: {len(failures)} of {len(sql_files)} view(s)."
        )

    print(f"\nAll {len(sql_files)} view(s) deployed successfully.")


if __name__ == "__main__":
    main()

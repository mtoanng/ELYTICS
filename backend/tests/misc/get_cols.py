import csv
import os
from databricks import sql as databricks_sql

import backend.config.sherlock as sherlock
import backend.config.watson as watson
import backend.config.enola as enola
import backend.config.mycroft as mycroft

from dotenv import load_dotenv

load_dotenv()

def fq_name(catalog, schema, space, data_kind, table_name):
    segment = "meta" if data_kind == "metadata" else "data"
    return f"holmes_{space}_{segment}_{table_name}_view"


def gather_view_names(catalog, schema):
    modules = [
        ("sherlock", sherlock),
        ("watson", watson),
        ("enola", enola),
        ("mycroft", mycroft),
    ]
    names = set()
    for space, mod in modules:
        for cfg in mod.TABULAR_CONFIG:
            names.add(fq_name(catalog, schema, space, "data", cfg.table_name))
        for cfg in mod.TIMESERIES_CONFIG:
            names.add(fq_name(catalog, schema, space, "data", cfg.table_name))
        for cfg in mod.METADATA_CONFIG:
            names.add(fq_name(catalog, schema, space, "metadata", cfg.table_name))
    return sorted(names)


def main():
    catalog = os.getenv("DATABRICKS_CATALOG", "ps_xplatform_prod")
    schema = os.getenv("DATABRICKS_SCHEMA", "pemely_ops")
    host = os.environ["DATABRICKS_SERVER_HOSTNAME"]
    http_path = os.environ["DATABRICKS_HTTP_PATH"]
    token = os.environ["DATABRICKS_TOKEN"]

    views = gather_view_names(catalog, schema)
    if not views:
        print("No configured views found.")
        return

    in_clause = ", ".join("'" + v.replace("'", "''") + "'" for v in views)
    query = f"""
    SELECT
      table_catalog,
      table_schema,
      table_name,
      ordinal_position,
      column_name,
      data_type
    FROM {catalog}.information_schema.columns
    WHERE table_schema = '{schema}'
      AND table_name IN ({in_clause})
    ORDER BY table_name, ordinal_position
    """

    with databricks_sql.connect(
        server_hostname=host,
        http_path=http_path,
        access_token=token,
    ) as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            rows = cur.fetchall()
            cols = [d[0] for d in cur.description]

    print(f"Found {len(rows)} columns across {len(views)} views.")
    current = None
    for row in rows:
        rec = dict(zip(cols, row))
        t = rec["table_name"]
        if t != current:
            current = t
            print(f"\n[{t}]")
        print(f"  {rec['ordinal_position']:>3}  {rec['column_name']}  ({rec['data_type']})")

    out_file = "table_columns_inventory.csv"
    with open(out_file, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cols)
        w.writerows(rows)
    print(f"\nWrote CSV: {out_file}")


if __name__ == "__main__":
    main()
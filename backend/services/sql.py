import os
import re

DATABRICKS_CATALOG = os.getenv("DATABRICKS_CATALOG", "ps_xplatform_dev")
LOCAL_SQL = os.getenv("LOCAL_SQL", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}


def to_sql_literal(value: str) -> str:
    text = str(value)
    lowered = text.lower()
    if lowered == "null":
        return "NULL"
    if lowered in {"true", "false"}:
        return lowered.upper()
    if re.fullmatch(r"-?\d+", text):
        return text
    if re.fullmatch(r"-?\d+\.\d+", text):
        return text
    return f"'{text.replace(chr(39), chr(39) * 2)}'"

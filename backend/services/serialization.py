import math
from datetime import date, datetime, time as dtime
from decimal import Decimal
from typing import Any


def normalize_json_value(value: Any) -> Any:
    if value is None or isinstance(value, str):
        return value
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, Decimal):
        as_float = float(value)
        return as_float if math.isfinite(as_float) else None
    if isinstance(value, (datetime, date, dtime)):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")

    item_method = getattr(value, "item", None)
    if callable(item_method):
        try:
            return normalize_json_value(item_method())
        except Exception:
            pass

    if isinstance(value, dict):
        return {str(k): normalize_json_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [normalize_json_value(v) for v in value]

    as_dict = getattr(value, "asDict", None)
    if callable(as_dict):
        try:
            mapped = as_dict(recursive=False)
        except TypeError:
            mapped = as_dict()
        return {str(k): normalize_json_value(v) for k, v in mapped.items()}

    as_dict = getattr(value, "_asdict", None)
    if callable(as_dict):
        mapped = as_dict()
        return {str(k): normalize_json_value(v) for k, v in mapped.items()}

    if hasattr(value, "__dict__"):
        return {
            str(k): normalize_json_value(v)
            for k, v in vars(value).items()
            if not k.startswith("_")
        }

    try:
        return [normalize_json_value(v) for v in value]
    except TypeError:
        return str(value)

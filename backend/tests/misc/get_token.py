"""
Extract the Azure access_token from a Flask-Session Redis entry.

Usage:
    python get_token.py <session_cookie_value>

The printed token can then be set as:
    $env:HOLMES_BEARER_TOKEN = "<token>"
"""
import os
import sys

import redis


def _decode(raw: bytes) -> dict:
    # Flask-Session >= 0.7 uses msgspec.msgpack
    try:
        import msgspec.msgpack
        return msgspec.msgpack.decode(raw)
    except Exception:
        pass
    # Older Flask-Session uses msgpack-python
    try:
        import msgpack
        return msgpack.unpackb(raw, raw=False)
    except Exception:
        pass
    # Last resort: pickle
    import pickle
    return pickle.loads(raw)


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python get_token.py <session_cookie_value>")

    sid = sys.argv[1].strip()
    r = redis.StrictRedis(
        host=os.getenv("REDIS_HOST", "redis"),
        port=int(os.getenv("REDIS_PORT", "6379")),
        db=int(os.getenv("REDIS_DB", "0")),
    )

    raw = r.get(f"session:{sid}") or r.get(sid)
    if not raw:
        raise SystemExit("Session not found in Redis. Check the cookie value and REDIS_HOST/PORT/DB.")

    try:
        data = _decode(raw)
    except Exception as exc:
        raise SystemExit(f"Could not decode session payload: {exc}")

    if not isinstance(data, dict):
        raise SystemExit(f"Unexpected payload type: {type(data)}")

    token = data.get("access_token")
    if not token:
        raise SystemExit(f"No access_token found. Keys present: {list(data.keys())}")

    print(token)


if __name__ == "__main__":
    main()
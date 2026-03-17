import os, json, pickle
import redis

sid = os.environ["HOLMES_SESSION_ID"] # paste cookie value into env first
r = redis.StrictRedis(
host=os.getenv("REDIS_HOST", "localhost"),
port=int(os.getenv("REDIS_PORT", "6379")),
db=int(os.getenv("REDIS_DB", "0")),
)

raw = r.get(f"session:{sid}") or r.get(sid)
if not raw:
    raise SystemExit("Session not found in Redis. Check cookie value and Redis DB/host.")
data = None
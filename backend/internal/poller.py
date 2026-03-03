import os
import glob
import redis
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from internal.databricks_service import DatabricksService

load_dotenv()

redis_client = redis.StrictRedis(host="localhost", port=6379, db=0, decode_responses=True)

QUERIES_DIR = os.path.join(os.path.dirname(__file__), "../queries")

def poll_and_update():
    db_service = DatabricksService()
    for sql_file in glob.glob(os.path.join(QUERIES_DIR, "**", "*.sql"), recursive=True):
        rel_path = os.path.relpath(sql_file, QUERIES_DIR)
        query_name = os.path.splitext(rel_path)[0].replace(os.sep, "/")
        try:
            query = db_service.load_query(sql_file)
            df = db_service.execute_query(query)
            # Store as JSON in Redis
            redis_client.set(f"query_result:{query_name}", df.to_json(orient="records"))
            print(f"Updated Redis for {query_name}")
        except Exception as e:
            print(f"Failed to update {query_name}: {e}")

def start_scheduler():
    poll_and_update()  # Initial run on startup
    scheduler = BackgroundScheduler()
    scheduler.add_job(poll_and_update, "interval", seconds=int(os.getenv("POLL_INTERVAL_SECONDS", 600)), next_run_time=None)
    scheduler.start()
    print("Databricks poller started.")
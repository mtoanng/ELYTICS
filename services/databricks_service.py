import pandas as pd
import os
from dotenv import load_dotenv
import time
import glob
import numpy as np
import databricks.sql

load_dotenv()
# Load environment variables from tokens.env (or .env)
# load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '../tookens.env'))

class DatabricksService:
    @staticmethod
    def load_query(filename):
        with open(filename, 'r') as file:
            return file.read()

    def __init__(self):
        self.server_hostname = os.environ.get('DATABRICKS_SERVER_HOSTNAME')
        self.http_path = os.environ.get('DATABRICKS_HTTP_PATH')
        self.access_token = os.environ.get('DATABRICKS_TOKEN')
        if not (self.server_hostname and self.http_path and self.access_token):
            raise ValueError("Missing Databricks connection info in environment variables.")

    def execute_query(self, query):
        with databricks.sql.connect(
            server_hostname=self.server_hostname,
            http_path=self.http_path,
            access_token=self.access_token
        ) as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            return pd.DataFrame(rows, columns=columns)

def get_databricks_service():
    return DatabricksService()

if __name__ == "__main__":

    queries_dir = os.path.join(os.path.dirname(__file__), "../queries")
    query_files = glob.glob(os.path.join(queries_dir, "*.sql"))
    service = get_databricks_service()

    results = []

    for query_file in query_files:
        query_name = os.path.basename(query_file)
        timings = []
        sizes = []
        query = DatabricksService.load_query(query_file)
        print(f"Profiling query: {query_name}")
        for i in range(5):
            start = time.time()
            df = service.execute_query(query)
            elapsed = time.time() - start
            mem_mb = df.memory_usage(deep=True).sum() / (1024 * 1024)
            timings.append(elapsed)
            sizes.append(mem_mb)
            print(f"  Run {i+1}: {elapsed:.2f}s, {mem_mb:.2f} MB")
        avg_time = np.mean(timings)
        avg_size = np.mean(sizes)
        results.append((query_name, avg_time, avg_size))

    print("\nSummary:")
    for query_name, avg_time, avg_size in results:
        print(f"{query_name}: avg time = {avg_time:.2f}s, avg size = {avg_size:.2f} MB")
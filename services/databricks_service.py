import pandas as pd
import os
from dotenv import load_dotenv
import databricks.sql

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
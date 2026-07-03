import os
import logging
from pathlib import Path

import dash
import dash_bootstrap_components as dbc
import plotly.io as pio

from components.appshell import create_appshell
from services.auth import OIDCAuthWithToken
from spaces.sherlock.co_energystacck_migration.reporting_dashboard import register_callbacks as register_co_reporting_callbacks

import redis
from flask_session import Session

from dotenv import load_dotenv
from waitress import serve

load_dotenv()

PAGES_FOLDER = str(Path(__file__).resolve().parent / "spaces" / "sherlock")


def configure_logging():
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    numeric_level = getattr(logging, log_level, logging.INFO)

    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        force=True,
    )

    for logger_name in ("dash", "flask", "waitress", "werkzeug"):
        logging.getLogger(logger_name).setLevel(numeric_level)

    logging.getLogger(__name__).info("Frontend logging configured at level %s", log_level)


configure_logging()

pio.templates["plotly_dark"].layout.paper_bgcolor = "rgba(0,0,0,0)"
pio.templates["plotly_dark"].layout.plot_bgcolor = "#1f1f1f"
pio.templates["plotly"].layout.paper_bgcolor = "rgba(0,0,0,0)"

app = dash.Dash(
    __name__,
    use_pages=True,
    external_stylesheets=[dbc.themes.FLATLY],
    suppress_callback_exceptions=True,
    pages_folder=PAGES_FOLDER,
    prevent_initial_callbacks=True,
    update_title=None
)

redis_host = os.getenv("REDIS_HOST", "localhost")
redis_port = int(os.getenv("REDIS_PORT", "6379"))
redis_db = int(os.getenv("REDIS_DB", "0"))

app.server.config["SESSION_TYPE"] = "redis"
app.server.config["SESSION_REDIS"] = redis.StrictRedis(host=redis_host, port=redis_port, db=redis_db)
app.server.config["SESSION_PERMANENT"] = True
app.server.config["PERMANENT_SESSION_LIFETIME"] = int(os.getenv("SESSION_LIFETIME_SECONDS", str(7 * 24 * 60 * 60)))  # 7 days
app.server.config["PREFERRED_URL_SCHEME"] = "https"
Session(app.server)

if os.getenv("DISABLE_AUTH", "false").strip().lower() in {"1", "true", "yes", "on"}:
    logging.getLogger(__name__).warning("Frontend auth disabled for local demo mode")
else:
    auth = OIDCAuthWithToken(app, secret_key=os.getenv("FRONTEND_OIDC_SECRET_KEY", "dev"))
    auth.register_provider(
        "azure",
        token_endpoint_auth_method="client_secret_post",
        client_id=os.getenv("FRONTEND_AZURE_CLIENT_ID"),
        client_secret=os.getenv("FRONTEND_AZURE_CLIENT_SECRET"),
        server_metadata_url=f'https://login.microsoftonline.com/{os.getenv("FRONTEND_AZURE_TENANT_ID")}/v2.0/.well-known/openid-configuration',
        scope=f"openid profile email offline_access api://{os.getenv('BACKEND_AZURE_CLIENT_ID')}/user_impersonation"
    )

app.layout = create_appshell()
# Dash Pages only wires up the layout for spaces/sherlock/explore/co_reporting.py;
# the CO Reporting tabs' interactive callbacks must be registered explicitly.
register_co_reporting_callbacks(app)

if __name__ == "__main__":
    use_dash_debug_server = os.getenv("USE_DASH_DEBUG_SERVER", "false").lower() == "true"
    logging.getLogger(__name__).info(
        "Starting frontend server (debug=%s, threads=%s, connection_limit=%s)",
        use_dash_debug_server,
        os.getenv("WAITRESS_THREADS", "4"),
        os.getenv("WAITRESS_CONNECTION_LIMIT", "200"),
    )
    if use_dash_debug_server:
        app.run(debug=True, host="0.0.0.0", port=8501, use_reloader=True)
    else:
        waitress_threads = int(os.getenv("WAITRESS_THREADS", "4"))
        waitress_connection_limit = int(os.getenv("WAITRESS_CONNECTION_LIMIT", "200"))

        serve(
            app.server,
            host="0.0.0.0",
            port=8501,
            trusted_proxy="*",
            trusted_proxy_count=1,
            threads=waitress_threads,
            connection_limit=waitress_connection_limit,
        )
# Elytics CO Reporting Demo

Elytics CO Reporting is a local/demo analytics application for CO2 electrolyzer experiment data. It provides an interactive Dash reporting UI backed by a small FastAPI service that queries Databricks SQL gold serving tables. The app is designed for fast experiment review, standard report visualization, custom channel exploration, and demo validation after rebuilding the Elytics data pipeline.

The local demo intentionally has no frontend OIDC gate. Access to data is controlled by the Databricks SQL Warehouse credentials configured in `backend/.env`.

## Purpose

This repository is the application layer for visualizing rebuilt Elytics CO reporting data. It does not contain the upstream XLSX-to-bronze/silver/gold conversion pipeline. Instead, it expects the pipeline to have already produced Databricks gold tables with canonical channel names, derived metrics, aggregate tiers, and experiment metadata.

The main goals are:

- list rebuilt experiments and sheet-level measurement groups
- expose each experiment's channel catalog dynamically
- query raw and aggregate time-series data from Databricks SQL
- render standard report charts such as Voltage, Gas Pressure, Anolyte Pressure, Faradaic Efficiency, Energy Efficiency, and SPCE
- support custom report exploration over the selected experiment's actual channels
- cache expensive Databricks responses through Redis for smoother demos

## Architecture

```text
Browser
  -> Dash frontend on :8501
  -> FastAPI backend on :8000
  -> Databricks SQL Warehouse
  -> Gold serving tables

Redis
  -> backend response cache
  -> frontend Flask session store
```

Key runtime pieces:

- Frontend route: `/elytics/co-reporting`
- Backend API prefix: `/api/elytics/co-reporting`
- Container stack: Redis, backend, frontend
- Serving data source: Databricks SQL Warehouse
- Local demo ports: frontend `8501`, backend `8000`, Redis `6379`

## Tech Stack

Backend:

- Python 3.12
- FastAPI
- Gunicorn with Uvicorn workers
- SQLAlchemy Databricks dialect via `databricks-sqlalchemy`
- Databricks SDK / SQL connector dependencies
- Redis response caching
- Pandas/PyArrow for result handling and serialization support

Frontend:

- Python 3.12
- Dash with Dash Pages
- Dash Bootstrap Components, Dash Mantine Components, Dash AG Grid
- Plotly for interactive time-series charts
- Waitress production-style local serving
- Flask-Session backed by Redis

Runtime/deployment:

- Podman / Podman Desktop on Windows
- `compose.demo.yml` for the intended three-service stack
- Manual `podman run` commands also work when `podman compose` has no compose provider installed

## Repository Layout

```text
backend/
  main.py                     FastAPI app, lifespan hooks, request timing logs
  routers/co_reporting.py     CO reporting API routes
  services/co_reporting.py    SQL query construction, identity filtering, cache integration
  services/databricks.py      Databricks SQLAlchemy engine and retry handling
  services/cache.py           Redis cache helpers
  tests/                      Backend service/API tests

frontend/
  app.py                      Dash app entrypoint and Waitress server
  components/                 Shared app shell/header/sidebar pieces
  services/backend_service.py Frontend HTTP client for backend API
  spaces/elytics/             Dash Pages app space
  spaces/elytics/reporting/   Elytics CO reporting UI, data provider, tabs, plotting
  assets/                     CSS and static visual assets
  tests/                      Frontend/data-provider tests

compose.demo.yml              Redis/backend/frontend Podman stack
README.md                     Project overview and runbook
```

## Data Model And Serving Contract

The app reads these Databricks gold serving tables:

- `gold_experiment_index`
- `gold_channel_catalog_experiment`
- `gold_timeseries`
- `gold_timeseries_agg_1min`
- `gold_timeseries_agg_15min`
- `gold_timeseries_agg_60min`

Experiment identity is handled as follows:

- `experiment_id` is the preferred query identity for serving tables.
- `uuid` identifies the source file.
- `group` identifies the source sheet / measurement group.
- `uuid + group` is the source-side sheet-grained identity.

Channel availability varies by experiment. The UI must be driven by the selected series/experiment channel catalog, not by a global hardcoded channel list. Standard report definitions provide desired report channels, but rendering and querying must gracefully handle channels that are absent from the selected experiment.

Derived and semantic channels expected by the demo include:

- `Delta p Anolyte` displayed as `Δp Anolyte`
- `Energy Efficiency`
- `Current density`
- `Single Pass Conversion Efficiency`
- `Faradaic Efficiency of CO and H2`

Some experiments start at nonzero elapsed time, including ranges around `1,000,000s`. The frontend uses experiment metadata from `gold_experiment_index` to choose an initial visible window that lands inside the selected experiment's actual elapsed range.

## Backend API

The backend exposes:

- `GET /api/elytics/co-reporting/series`
- `GET /api/elytics/co-reporting/channels`
- `GET /api/elytics/co-reporting/timeseries`
- `POST /api/elytics/co-reporting/query`

The windowed query endpoint supports raw and aggregate resolutions:

- `auto`
- `raw`
- `agg_1m` / `agg1`
- `agg_15m` / `agg15`
- `agg_60m` / `agg60`

Resolution selection is controlled by span and environment settings, with Redis caching applied unless `LOCAL_SQL` disables the cache path.

## Configuration

Create runtime env files from the examples:

```powershell
Copy-Item backend\.env.demo.example backend\.env
Copy-Item frontend\.env.demo.example frontend\.env
```

Required backend settings:

```text
DATABRICKS_SERVER_HOSTNAME=
DATABRICKS_HTTP_PATH=
DATABRICKS_AUTH_TYPE=azure-sp-m2m or access-token
```

For Azure service principal auth:

```text
DATABRICKS_AZURE_CLIENT_ID=
DATABRICKS_AZURE_CLIENT_SECRET=
DATABRICKS_AZURE_TENANT_ID=
DATABRICKS_AZURE_WORKSPACE_RESOURCE_ID=
```

For local PAT fallback:

```text
DATABRICKS_AUTH_TYPE=access-token
DATABRICKS_TOKEN=
```

Serving table settings:

```text
CO_GOLD_CATALOG=ps_xplatform_dev
CO_GOLD_SCHEMA=co2elyd_dev
CO_GOLD_RAW_TABLE=gold_timeseries
CO_GOLD_AGG_1M_TABLE=gold_timeseries_agg_1min
CO_GOLD_AGG_15M_TABLE=gold_timeseries_agg_15min
CO_GOLD_AGG_60M_TABLE=gold_timeseries_agg_60min
CO_GOLD_EXPERIMENT_INDEX_TABLE=gold_experiment_index
CO_GOLD_CHANNEL_CATALOG_EXPERIMENT_TABLE=gold_channel_catalog_experiment
```

Frontend settings:

```text
BACKEND_API_URL=http://backend:8000
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0
USE_DASH_DEBUG_SERVER=false
```

Do not commit populated `.env` files. They may contain live Databricks credentials.

## Local Validation

Use the checked-in virtual environment when available:

```powershell
.\.testvenv\Scripts\python.exe -m pytest backend/tests frontend/tests
```

Focused checks used during the demo work:

```powershell
.\.testvenv\Scripts\python.exe -m pytest backend/tests/test_co_reporting.py frontend/tests/test_elytics_data_provider.py
```

## Podman Demo

The intended stack is defined in `compose.demo.yml`:

```powershell
podman compose -f compose.demo.yml up --build
```

Open:

```text
http://localhost:8501/elytics/co-reporting
```

The frontend calls the backend at `http://backend:8000` inside the Podman network. The backend queries Databricks SQL and uses Redis for response caching.

If `podman` is installed but not visible in the current PowerShell, call it directly:

```powershell
& "C:\Users\got4hc\AppData\Local\Programs\Podman\podman.exe" --version
```

If no Podman machine exists:

```powershell
& "C:\Users\got4hc\AppData\Local\Programs\Podman\podman.exe" machine init
& "C:\Users\got4hc\AppData\Local\Programs\Podman\podman.exe" machine start
```

If `podman compose` reports that no compose provider is installed, start the stack manually:

```powershell
$podman = "C:\Users\got4hc\AppData\Local\Programs\Podman\podman.exe"

& $podman network create elytics
& $podman build -t tbp-holmes-backend -f backend/Dockerfile backend
& $podman build -t tbp-holmes-frontend -f frontend/Dockerfile frontend

& $podman run -d --name tbp-holmes-redis --network elytics --network-alias redis -p 6379:6379 redis:7-alpine redis-server --save "" --appendonly no --maxmemory 700mb --maxmemory-policy allkeys-lru

& $podman run -d --name tbp-holmes-backend --network elytics --network-alias backend --env-file backend/.env -e REDIS_HOST=redis -e REDIS_PORT=6379 -e REDIS_DB=0 -e PYTHONPATH=/app -p 8000:8000 tbp-holmes-backend

& $podman run -d --name tbp-holmes-frontend --network elytics --network-alias frontend --env-file frontend/.env -e BACKEND_API_URL=http://backend:8000 -e REDIS_HOST=redis -e REDIS_PORT=6379 -e REDIS_DB=0 -e PYTHONPATH=/app -p 8501:8501 tbp-holmes-frontend
```

Stop the manual stack:

```powershell
& "C:\Users\got4hc\AppData\Local\Programs\Podman\podman.exe" rm -f tbp-holmes-frontend tbp-holmes-backend tbp-holmes-redis
```

## Podman Proxy Notes

In some corporate Windows environments, Podman Desktop is installed but the Podman service inside the WSL machine does not inherit proxy variables. If image pulls fail with DNS or registry errors, configure the Podman user service inside the machine with the corporate proxy and restart the socket.

Example:

```powershell
$podman = "C:\Users\got4hc\AppData\Local\Programs\Podman\podman.exe"

& $podman machine ssh "sudo chown -R user:user /home/user/.config/systemd; mkdir -p /home/user/.config/systemd/user/podman.service.d; cat > /home/user/.config/systemd/user/podman.service.d/proxy.conf <<'EOF'
[Service]
Environment=HTTP_PROXY=http://rb-proxy-apac.bosch.com:8080
Environment=HTTPS_PROXY=http://rb-proxy-apac.bosch.com:8080
Environment=http_proxy=http://rb-proxy-apac.bosch.com:8080
Environment=https_proxy=http://rb-proxy-apac.bosch.com:8080
Environment=NO_PROXY=backend,frontend,redis,localhost,127.0.0.1,host.docker.internal,.bosch.com
Environment=no_proxy=backend,frontend,redis,localhost,127.0.0.1,host.docker.internal,.bosch.com
EOF
systemctl --user daemon-reload
systemctl --user restart podman.socket"
```

Adjust proxy host/port for the target environment.

## Smoke Checks

Backend series check:

```powershell
Invoke-RestMethod http://localhost:8000/api/elytics/co-reporting/series
```

Frontend route check:

```powershell
(Invoke-WebRequest http://localhost:8501/elytics/co-reporting -UseBasicParsing).StatusCode
```

Inspect containers:

```powershell
& "C:\Users\got4hc\AppData\Local\Programs\Podman\podman.exe" ps --filter name=tbp-holmes --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

Clear Redis cache after data rebuilds:

```powershell
& "C:\Users\got4hc\AppData\Local\Programs\Podman\podman.exe" exec tbp-holmes-redis redis-cli FLUSHALL
```

## Post-E2E Data Readiness Checks

Before demoing, the rebuilt Databricks environment should pass these gates:

- no duplicate `bronze_filemeta` rows per `uuid + group`
- no `bronze_filemeta` grain mismatch between rows and distinct groups
- no duplicate `gold_experiment_index` rows per `experiment_id + uuid + group`
- no duplicate aggregate rows per `experiment_id + std_channel + elapsed_bin_s`
- no duplicate channel catalog rows per `experiment_id + std_channel`
- expected derived channels exist in `gold_channel_catalog_experiment`
- `Δp Anolyte` exists in `gold_timeseries`
- `Δp Anolyte = Anolyte inlet pressure - Anolyte outlet pressure` has no mismatches at `1e-9`
- serving tables are populated

The most recent checked environment passed those SQL/data-model gates against `ps_xplatform_dev.co2elyd_dev`.

## Demo Notes

- Hard refresh the browser after rebuilding the frontend image so new CSS and callbacks are loaded.
- Some experiments do not have every standard report channel. That is expected; channel options and report queries should be driven by the selected experiment catalog.
- Some experiments start at nonzero elapsed time. A `0h-24h` window can be empty for those experiments, so the frontend defaults to the selected experiment's actual elapsed start time.
- If a manual Y-axis range is entered, it overrides autorange. Clear the Y range boxes or use Plotly autoscale to return to full-range viewing.


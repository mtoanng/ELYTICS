# Elytics CO Reporting Demo

This repository contains the Elytics CO reporting demo app: a Dash frontend backed by a thin FastAPI service that queries Databricks SQL gold serving tables.

## Architecture

- Frontend route: `/elytics/co-reporting`
- Backend API prefix: `/api/elytics/co-reporting`
- Serving model: `gold_experiment_index`, `gold_channel_catalog_experiment`, `gold_timeseries`, and 1/15/60 minute aggregate gold tables
- Cache: Redis-backed response cache with TTL controls
- Databricks access: SQLAlchemy connection pool using either `azure-sp-m2m` service principal auth or local PAT fallback

The local demo intentionally has no frontend OIDC gate. Access to data is controlled by the Databricks SQL Warehouse credentials configured in `backend/.env`.

## Local Validation

```powershell
.\.testvenv\Scripts\python.exe -m pytest backend/tests frontend/tests
```

## Podman Demo

Copy `backend/.env.demo.example` to `backend/.env` and `frontend/.env.demo.example` to `frontend/.env`, then fill in the Databricks SQL Warehouse settings and credentials.

```powershell
podman compose -f compose.demo.yml up --build
```

Open `http://localhost:8501/elytics/co-reporting`. The frontend calls the backend at `http://backend:8000`, and the backend queries Databricks SQL directly while using Redis for response caching.

For live smoke testing outside containers, populate `backend/.env` from `backend/.env.demo.example`, then run focused CO reporting checks against the configured Databricks SQL Warehouse.
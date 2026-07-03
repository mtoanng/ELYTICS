# Local Demo Podman Checklist

## Goal

Run the Elytics CO reporting demo locally with:

- frontend container
- backend container
- Redis container
- Databricks SQL Warehouse as the data source
- Gold serving tables in dev (`ps_xplatform_dev.co2elyd_dev.*`)

## Runtime Decision

The current Elytics local demo intentionally runs without frontend OIDC/app auth. The backend uses one machine credential to query Databricks SQL serving tables.

Recommended credential mode:

- `DATABRICKS_AUTH_TYPE=azure-sp-m2m`
- Azure service principal client id/secret/tenant stored in a local `.env` for demo or in Key Vault/container secrets for deployment

Local fallback only:

- Databricks PAT/access token via `DATABRICKS_TOKEN`

## Files To Prepare

Create and fill:

- `backend/.env`
- `frontend/.env`

Templates:

- `backend/.env.demo.example`
- `frontend/.env.demo.example`

## Required Backend Values

Always required:

- `ENVIRONMENT=development`
- `REDIS_HOST`
- `REDIS_PORT`
- `REDIS_DB`
- `DATABRICKS_SERVER_HOSTNAME`
- `DATABRICKS_HTTP_PATH`
- `DATABRICKS_AUTH_TYPE=azure-sp-m2m`
- `DATABRICKS_AZURE_CLIENT_ID`
- `DATABRICKS_AZURE_CLIENT_SECRET`
- `DATABRICKS_AZURE_TENANT_ID`

Recommended for Azure Databricks:

- `DATABRICKS_AZURE_WORKSPACE_RESOURCE_ID`

Local fallback only:

- `DATABRICKS_TOKEN` with `DATABRICKS_AUTH_TYPE=access-token`

## Required Frontend Values

Always required:

- `BACKEND_API_URL`
- `REDIS_HOST`
- `REDIS_PORT`
- `REDIS_DB`

## Databricks Access Checklist

The backend credential must have SQL Warehouse access and read access to:

- `ps_xplatform_dev.co2elyd_dev.gold_experiment_index`
- `ps_xplatform_dev.co2elyd_dev.gold_channel_catalog_experiment`
- `ps_xplatform_dev.co2elyd_dev.gold_timeseries`
- `ps_xplatform_dev.co2elyd_dev.gold_timeseries_agg_1min`
- `ps_xplatform_dev.co2elyd_dev.gold_timeseries_agg_15min`
- `ps_xplatform_dev.co2elyd_dev.gold_timeseries_agg_60min`

## Podman Runtime Layout

Recommended containers:

1. `redis`
2. `holmes-backend`
3. `holmes-frontend`

Recommended port mapping:

- backend: `8000:8000`
- frontend: `8501:8501`
- redis: `6379:6379`

## Expected Demo Behavior

The local demo should expose only the Holmes-integrated Sherlock CO reporting path, with:

- Standard Reports
- Custom Reports
- Databricks Gold-backed queries
- Redis caching
- Holmes visual shell

Not required for the demo:

- old mapping management flows
- ADLS browsing flows
- local silver/materialization workflows

## Current Code Status

Already implemented:

- dedicated CO reporting backend router/service
- Gold-table-aware serving contract
- windowed query endpoint
- Holmes-styled reporting page
- Standard Reports partial migration to buffered window queries

Still a likely runtime hotspot:

- Custom Reports remains more legacy/server-heavy than Standard Reports

## Pre-Run Checks

Before starting containers, verify:

1. `podman --version` works in the current shell
2. your Podman machine is running if needed on Windows
3. backend `.env` exists
4. frontend `.env` exists
5. Redis hostnames in env files match runtime network names
6. Databricks SQL Warehouse credentials are valid

## First Validation Steps After Startup

1. backend health/import starts cleanly
2. frontend starts cleanly
3. Sherlock CO reporting page opens
4. series list loads from `gold_experiment_index`
5. channel list loads from `gold_channel_catalog`
6. Standard Reports first chart renders from aggregate tables
7. zoom/drilldown issues new backend queries as expected

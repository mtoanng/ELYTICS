# CO Reporting Demo Cleanup Notes

## Purpose

This note records which old CO Energystack migration files are still intentionally retained in the TBP-HOLMES repo during demo hardening, and which paths are no longer part of the live CO reporting demo path.

## Live Demo Path

The current CO reporting demo path is:

- `frontend/spaces/sherlock/explore/co_reporting.py`
- `frontend/spaces/sherlock/co_energystacck_migration/reporting_dashboard.py`
- `frontend/spaces/sherlock/co_energystacck_migration/holmes_data_provider.py`
- `frontend/spaces/sherlock/co_energystacck_migration/tabs/standard_reports.py`
- `frontend/spaces/sherlock/co_energystacck_migration/tabs/custom_reports.py`
- `frontend/spaces/sherlock/co_energystacck_migration/backend/tag_manager.py`
- `frontend/spaces/sherlock/co_energystacck_migration/backend/data_visualization.py`
- `frontend/spaces/sherlock/co_energystacck_migration/tabs/export_helpers.py`
- `frontend/services/backend_service.py`
- `backend/routers/co_reporting.py`
- `backend/services/co_reporting.py`

## Intentionally Retained Legacy Files

The following legacy-origin files are still retained because the live demo path still imports helpers or types from them directly or indirectly:

- `frontend/spaces/sherlock/co_energystacck_migration/backend/series_data_manager.py`
- `frontend/spaces/sherlock/co_energystacck_migration/backend/paths.py`
- `frontend/spaces/sherlock/co_energystacck_migration/backend/project_root.py`
- `frontend/spaces/sherlock/co_energystacck_migration/backend/data_loading.py`
- `frontend/spaces/sherlock/co_energystacck_migration/backend/data_enrichment.py`
- `frontend/spaces/sherlock/co_energystacck_migration/backend/storage_backend.py`
- `frontend/spaces/sherlock/co_energystacck_migration/backend/adls_filesystem.py`
- `frontend/spaces/sherlock/co_energystacck_migration/tabs/tab_helpers.py`

These should not be mass-deleted without first removing the remaining import and behavior dependencies from Standard Reports and Custom Reports.

## Not In Live Demo Navigation

The following legacy UI surfaces are not part of the active Holmes demo navigation path for CO reporting:

- `frontend/spaces/sherlock/co_energystacck_migration/tabs/adls_files.py`
- `frontend/spaces/sherlock/co_energystacck_migration/tabs/series_management.py`

They remain on disk as migration leftovers and reference implementations. They are candidates for later deletion only after a full import/reference audit confirms no dynamic imports or shared helper dependencies remain.

## Generic Sherlock SQL Backend

The SQL files under `views/spaces/sherlock/*.sql` are not part of the new dedicated CO reporting backend.

They still serve the older generic Sherlock tabular/metadata/timeseries routes and should not be removed as part of CO reporting cleanup unless the remaining Sherlock pages are migrated off the generic SQL-view system.

## Cleanup Strategy

Safe cleanup order:

1. Remove dead imports from live CO reporting modules.
2. Finish refactoring Standard and Custom Reports so they no longer rely on old `SeriesDataManager`-driven load assumptions.
3. Re-run import and demo smoke validation.
4. Only then delete unreferenced legacy modules.

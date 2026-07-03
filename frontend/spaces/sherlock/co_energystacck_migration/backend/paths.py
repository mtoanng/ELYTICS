"""paths -- Env-var-driven path resolver for read-only and writable artefacts.

Why this module exists
======================

On Azure App Service Linux Python runtimes, the Oryx build system extracts
the deployment ZIP into ``/tmp/<hash>/``; that directory becomes the runtime
CWD and is wiped on every container restart, scale-out, slot swap, and
deploy. The only location guaranteed to persist across container restarts
is ``/home`` (an SMB-mounted Azure Storage share that the platform attaches
to every built-in Linux image).

Microsoft Learn references
--------------------------
* `Configure a Linux Python app for Azure App Service
  <https://learn.microsoft.com/en-us/azure/app-service/configure-language-python>`_
  â€” explicit statement: "write any additional files created at runtime to a
  location under ``/home`` or by using Bring Your Own Storage for
  persistence" and "Any changes that you make outside the ``/home``
  directory are stored in the container itself and don't persist beyond an
  app restart". Also: ``APP_PATH`` env var points at the Oryx CWD.
* `Operating System Functionality in Azure App Service
  <https://learn.microsoft.com/en-us/azure/app-service/operating-system-functionality>`_
* `Azure App Service on Linux FAQ
  <https://learn.microsoft.com/en-us/azure/app-service/faq-app-service-linux>`_
  â€” note: ``WEBSITES_ENABLE_APP_SERVICE_STORAGE`` "has no impact" on
  built-in images (our case), so ``/home`` is always mounted.

Public surface
==============

Read-only paths (always under PROJECT_ROOT, i.e. the deploy package)::

    READONLY_CONFIG_DIR       e.g. /tmp/<hash>/config
    READONLY_DATA_DIR         e.g. /tmp/<hash>/data
    SCHEMA_PATH               READONLY_DATA_DIR/schema.csv
    SERIES_STRUCTURE_PATH     READONLY_CONFIG_DIR/series_structure.json
    STACK_DEFINITIONS_PATH    READONLY_CONFIG_DIR/stack_definitions.json
    STANDARD_REPORTS_PATH     READONLY_CONFIG_DIR/standard_reports.json

Writable paths (env-overridable, default under PROJECT_ROOT for local dev)::

    BRONZE_DIR                ENERGYSTACK_BRONZE_DIR   (default {root}/data/bronze)
    SILVER_DIR                ENERGYSTACK_SILVER_DIR   (default {root}/data/silver)
    CACHE_DIR                 ENERGYSTACK_CACHE_DIR    (default {root}/cache)
    WRITABLE_CONFIG_DIR       ENERGYSTACK_CONFIG_DIR   (default {root}/config)
    SERIES_DEF_PATH           WRITABLE_CONFIG_DIR/series.json
    TAGS_PATH                 WRITABLE_CONFIG_DIR/tags.json

Helpers::

    normalize_separators(p)         backslash -> forward-slash, no-op for None
    resolve_under_project_root(p)   join relative paths with PROJECT_ROOT
    to_storage_path(absolute)       portable form to put back into series.json
    ensure_dirs()                   makedirs() every writable dir
    bootstrap_writable_config()     seed WRITABLE_CONFIG_DIR from READONLY_CONFIG_DIR

App Service production setup
============================

Set these App Service Application Settings (Configuration â†’ Application
Settings â†’ "+ New application setting"), then **restart** the App Service::

    ENERGYSTACK_BRONZE_DIR  = /home/data/bronze
    ENERGYSTACK_SILVER_DIR  = /home/data/silver
    ENERGYSTACK_CACHE_DIR   = /home/data/cache
    ENERGYSTACK_CONFIG_DIR  = /home/config

App Service Application Settings are exposed to the Python process as
environment variables verbatim (alphanumerics + ``_`` only in the name; the
*value* can contain slashes, colons, etc.). On the first request after a
restart the bootstrap copies series.json / tags.json / series_structure.json
/ stack_definitions.json / standard_reports.json from the read-only deploy
package into ``/home/config``, so the persistent state starts as a clone of
whatever shipped with the latest deploy. Subsequent runtime edits stay
in ``/home/config`` and survive future deploys.
"""

from __future__ import annotations

import logging
import os
import shutil
from typing import Optional

from .project_root import PROJECT_ROOT

log = logging.getLogger(__name__)


def normalize_separators(p: Optional[str]) -> Optional[str]:
    """Return *p* with every backslash converted to a forward slash.

    Forward slashes are valid path separators on both Windows and Linux,
    so normalising on read makes the same ``config/series.json`` file work
    regardless of the platform that authored it. ``None`` / non-strings
    pass through unchanged.
    """
    if not p or not isinstance(p, str):
        return p
    return p.replace("\\", "/")


# Backwards-compatible alias kept for callers that already imported the
# private name from ``data_loading`` (and for symmetry with how this module
# is used internally).
_normalize_path = normalize_separators


def _resolve_writable_dir(env_var: str, default_subdir: str) -> str:
    """Pick a writable directory: env-var override or PROJECT_ROOT/default."""
    override = os.environ.get(env_var, "").strip()
    if override:
        return os.path.abspath(normalize_separators(override))
    return os.path.abspath(os.path.join(PROJECT_ROOT, default_subdir))


# ---------------------------------------------------------------------------
# Read-only paths â€” always under the deploy package
# ---------------------------------------------------------------------------
READONLY_CONFIG_DIR: str = os.path.abspath(os.path.join(PROJECT_ROOT, "config"))
READONLY_DATA_DIR: str = os.path.abspath(os.path.join(PROJECT_ROOT, "data"))
SCHEMA_PATH: str = os.path.join(READONLY_DATA_DIR, "schema.csv")
SERIES_STRUCTURE_PATH: str = os.path.join(
    READONLY_CONFIG_DIR, "series_structure.json"
)
STACK_DEFINITIONS_PATH: str = os.path.join(
    READONLY_CONFIG_DIR, "stack_definitions.json"
)
STANDARD_REPORTS_PATH: str = os.path.join(
    READONLY_CONFIG_DIR, "standard_reports.json"
)

# ---------------------------------------------------------------------------
# Writable paths â€” env-var configurable
# ---------------------------------------------------------------------------
BRONZE_DIR: str = _resolve_writable_dir(
    "ENERGYSTACK_BRONZE_DIR", os.path.join("data", "bronze")
)
SILVER_DIR: str = _resolve_writable_dir(
    "ENERGYSTACK_SILVER_DIR", os.path.join("data", "silver")
)
CACHE_DIR: str = _resolve_writable_dir("ENERGYSTACK_CACHE_DIR", "cache")
WRITABLE_CONFIG_DIR: str = _resolve_writable_dir(
    "ENERGYSTACK_CONFIG_DIR", "config"
)

SERIES_DEF_PATH: str = os.path.join(WRITABLE_CONFIG_DIR, "series.json")
TAGS_PATH: str = os.path.join(WRITABLE_CONFIG_DIR, "tags.json")
# Same writable-dir variants for the seed JSONs the bootstrap copies over.
# Callers should prefer the writable copy when it exists (lets users edit
# stack definitions at runtime in the future) and fall back to the read-only
# deploy-package version.
WRITABLE_SERIES_STRUCTURE_PATH: str = os.path.join(
    WRITABLE_CONFIG_DIR, "series_structure.json"
)
WRITABLE_STACK_DEFINITIONS_PATH: str = os.path.join(
    WRITABLE_CONFIG_DIR, "stack_definitions.json"
)
WRITABLE_STANDARD_REPORTS_PATH: str = os.path.join(
    WRITABLE_CONFIG_DIR, "standard_reports.json"
)


def ensure_dirs() -> None:
    """Create every writable directory (idempotent).

    Called once at module import. Safe to call again from anywhere.
    A failure (e.g. read-only filesystem in a sandboxed test) is logged
    rather than raised; the affected directory will simply be missing and
    the first write attempt will surface the underlying OSError.
    """
    for d in (BRONZE_DIR, SILVER_DIR, CACHE_DIR, WRITABLE_CONFIG_DIR):
        try:
            os.makedirs(d, exist_ok=True)
        except OSError as exc:
            log.warning("ensure_dirs: could not create %s: %s", d, exc)


_BOOTSTRAP_FILES = (
    "series.json",
    "tags.json",
    "series_structure.json",
    "stack_definitions.json",
    "standard_reports.json",
)


def bootstrap_writable_config() -> None:
    """Seed ``WRITABLE_CONFIG_DIR`` from ``READONLY_CONFIG_DIR`` if missing.

    Idempotent: each known seed file is copied only when it does NOT yet
    exist in the writable directory. Existing user-edited writable files
    are NEVER overwritten. Each copy is performed atomically through a
    sibling ``.bootstrap.tmp`` file plus ``os.replace`` so a crash mid-copy
    can never leave half-written JSON in place.

    Logs a single INFO line per file copied.
    """
    if not os.path.isdir(READONLY_CONFIG_DIR):
        return
    try:
        os.makedirs(WRITABLE_CONFIG_DIR, exist_ok=True)
    except OSError as exc:
        log.warning(
            "bootstrap_writable_config: could not create %s: %s",
            WRITABLE_CONFIG_DIR,
            exc,
        )
        return
    for name in _BOOTSTRAP_FILES:
        src = os.path.join(READONLY_CONFIG_DIR, name)
        dst = os.path.join(WRITABLE_CONFIG_DIR, name)
        if not os.path.isfile(src) or os.path.isfile(dst):
            continue
        tmp = dst + ".bootstrap.tmp"
        try:
            shutil.copy2(src, tmp)
            os.replace(tmp, dst)
            log.info(
                "bootstrap_writable_config: seeded %s from %s", dst, src
            )
        except OSError as exc:
            log.warning(
                "bootstrap_writable_config: could not copy %s -> %s: %s",
                src,
                dst,
                exc,
            )
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except OSError:
                pass


def resolve_under_project_root(p: Optional[str]) -> Optional[str]:
    """Return an absolute, forward-slash-friendly path for a stored *path*.

    Stored paths can be:

    * Forward-slash relative to PROJECT_ROOT â€” e.g. ``data/bronze/foo.xlsx``
      (the canonical form ``import_file_to_bronze`` writes back).
    * Backslash relative to PROJECT_ROOT â€” legacy Windows-authored entries
      such as ``data\\bronze\\foo.xlsx``. Folded to forward slashes.
    * Absolute â€” produced when ``BRONZE_DIR`` is configured outside
      PROJECT_ROOT (e.g. ``/home/data/bronze/foo.xlsx``).

    The returned path is always absolute and uses native separators, so it
    is safe to feed straight into ``open()`` / ``os.path.exists()``.
    """
    if not p:
        return p
    p = normalize_separators(p)
    if os.path.isabs(p):
        return p
    return os.path.normpath(os.path.join(PROJECT_ROOT, p))


def to_storage_path(absolute_path: str) -> str:
    """Convert an absolute on-disk path to the canonical stored form.

    Portability rule:

    * If *absolute_path* sits under ``PROJECT_ROOT``, return a forward-slash
      path relative to ``PROJECT_ROOT`` (e.g. ``data/bronze/foo.xlsx``).
      This keeps ``config/series.json`` valid across local checkout and
      remote deploys regardless of where the workspace lives.
    * Otherwise (e.g. when ``BRONZE_DIR`` resolves to ``/home/data/bronze``
      on App Service), return the absolute path with forward slashes.

    The returned form is round-trippable through
    :func:`resolve_under_project_root`.
    """
    if not absolute_path:
        return absolute_path
    abs_path = os.path.abspath(normalize_separators(absolute_path))
    project_root_abs = os.path.abspath(PROJECT_ROOT)
    try:
        common = os.path.commonpath([abs_path, project_root_abs])
    except ValueError:
        # Different drives on Windows: commonpath raises. Fall back to
        # absolute form so we never produce an unresolvable ``../..`` path.
        return normalize_separators(abs_path)
    if common == project_root_abs:
        rel = os.path.relpath(abs_path, project_root_abs)
        return normalize_separators(rel)
    return normalize_separators(abs_path)


# Run bootstrap + ensure once at import time. Both are idempotent and log
# rather than raise on failure, so importing this module is safe in every
# environment we care about (local dev, App Service, unit tests).
ensure_dirs()
bootstrap_writable_config()


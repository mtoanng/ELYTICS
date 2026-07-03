"""project_root -- Single source of truth for the workspace root path.

This mirrors the legacy project-root discovery logic but is packaged under
``src`` so the reorganized branch can run the app via ``python -m src.reporting_dashboard``.
"""

import os
import sys

_SENTINEL = os.path.join("data", "schema.csv")


def _find_project_root() -> str:
    """Walk upward from this file's directory until we find the repo root."""
    start = os.path.dirname(os.path.realpath(os.path.abspath(__file__)))
    current = start

    for _ in range(10):
        if os.path.isfile(os.path.join(current, _SENTINEL)):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent

    fallback = os.path.dirname(os.path.dirname(start))
    print(
        f"WARNING  project_root  Sentinel '{_SENTINEL}' not found above "
        f"{start}; falling back to {fallback}",
        file=sys.stderr,
    )
    return fallback


PROJECT_ROOT: str = _find_project_root()
"""Absolute path to the workspace / repository root directory."""


"""storage_backend -- Filesystem-protocol abstraction over local FS / ADLS Gen2.

Phase 1 of the storage migration: lands a backend-agnostic protocol plus
a local FS adapter and an ADLS Gen2 adapter (wrapping the existing
:class:`~src.backend.adls_filesystem.ADLSFileSystem`), without modifying
any existing call site.  Setting ``ENERGYSTACK_STORAGE_BACKEND=adls``
today has **no production effect** -- Series Management still uses the
local filesystem directly.  Phase 2 (separate PR) will wire
:mod:`src.backend.series_data_manager` through this protocol behind a
feature flag so a single env-var flip moves every writable artefact off
``/home`` and into the configured ADLS container.

See :mod:`src.backend.paths` for the broader read-only / writable
directory layout.  Both adapters share that module's
:func:`~src.backend.paths.normalize_separators` policy: backslashes fold
to forward slashes and relative paths join to the adapter's root.
"""

from __future__ import annotations

import io
import logging
import os
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import BinaryIO, Callable, Optional, Protocol, TypeVar, runtime_checkable

from . import paths as _paths
from .adls_filesystem import (
    ADLSEntry,
    ADLSError,
    ADLSFileSystem,
    ADLSNotConfiguredError,
    ADLSNotFoundError,
)

log = logging.getLogger(__name__)
_T = TypeVar("_T")


# â”€â”€ Public types â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


class StorageError(Exception):
    """Base class for backend-agnostic storage errors."""


class StorageNotFoundError(StorageError):
    """The requested file or directory does not exist."""


class StorageNotConfiguredError(StorageError):
    """The chosen backend is missing its required configuration."""


@dataclass(frozen=True)
class StorageEntry:
    """One filesystem entry.  Mirrors :class:`ADLSEntry` for trivial conversion."""

    name: str
    path: str
    is_dir: bool
    size: int = 0
    last_modified: Optional[datetime] = None

    @property
    def kind(self) -> str:
        return "dir" if self.is_dir else "file"


@runtime_checkable
class StorageBackend(Protocol):
    """Minimum filesystem surface that backs Series Management storage.

    Adapters accept POSIX-style paths (forward slashes, no leading
    separator).  Callers should depend only on this protocol and on the
    ``Storage*`` exception hierarchy, never on adapter-specific types.
    """

    backend_name: str

    def exists(self, path: str) -> bool: ...
    def stat(self, path: str) -> StorageEntry: ...
    def ls(self, path: str = "") -> list[StorageEntry]: ...
    def read_bytes(self, path: str) -> bytes: ...
    def write_bytes(
        self, path: str, data: bytes, *, overwrite: bool = True
    ) -> None: ...
    def open_read(self, path: str) -> BinaryIO: ...
    def open_write(self, path: str, *, overwrite: bool = True) -> BinaryIO: ...
    def mkdir(
        self, path: str, *, parents: bool = True, exist_ok: bool = True
    ) -> None: ...
    def rm(self, path: str) -> None: ...
    def rmdir(self, path: str, *, recursive: bool = True) -> None: ...
    def rename(self, src: str, dst: str) -> None: ...


def _norm(path: Optional[str]) -> str:
    """Return *path* in canonical relative form (forward slashes, no leading /)."""
    if not path:
        return ""
    p = (_paths.normalize_separators(str(path)) or "").strip()
    return p.strip("/")


# â”€â”€ Local FS adapter â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


class _AtomicLocalWriter(io.BytesIO):
    """``BytesIO`` that flushes to *target* via ``.tmp`` + :func:`os.replace`.

    Same atomicity pattern as :func:`paths.bootstrap_writable_config`: a
    crash mid-write can never leave a half-written file at *target*.
    """

    def __init__(self, target: str, *, overwrite: bool):
        super().__init__()
        self._target = target
        self._overwrite = overwrite
        self._flushed = False

    def close(self) -> None:
        if self._flushed or self.closed:
            super().close()
            return
        try:
            if not self._overwrite and os.path.exists(self._target):
                raise StorageError(
                    f"open_write: target already exists: {self._target}"
                )
            os.makedirs(os.path.dirname(self._target) or ".", exist_ok=True)
            tmp = self._target + ".tmp"
            with open(tmp, "wb") as fh:
                fh.write(self.getvalue())
            os.replace(tmp, self._target)
            self._flushed = True
        finally:
            super().close()


class LocalStorageBackend:
    """POSIX-filesystem :class:`StorageBackend` rooted at *root*.

    Relative paths are joined to *root* via :func:`os.path.join` after
    normalisation through :func:`paths.normalize_separators`, so the
    behaviour is identical on Windows and Linux.  Writes go through
    ``.tmp`` + :func:`os.replace` for atomicity.
    """

    backend_name = "local"

    def __init__(self, root: str):
        self._root = os.path.abspath(_paths.normalize_separators(root) or root)

    def _abs(self, path: str) -> str:
        rel = _norm(path)
        return os.path.normpath(os.path.join(self._root, rel)) if rel else self._root

    def _entry(self, abs_path: str, rel_path: str) -> StorageEntry:
        st = os.stat(abs_path)
        is_dir = os.path.isdir(abs_path)
        return StorageEntry(
            name=os.path.basename(rel_path) or os.path.basename(self._root),
            path=rel_path,
            is_dir=is_dir,
            size=0 if is_dir else int(st.st_size),
            last_modified=datetime.fromtimestamp(st.st_mtime, tz=timezone.utc),
        )

    def exists(self, path: str) -> bool:
        return os.path.exists(self._abs(path))

    def stat(self, path: str) -> StorageEntry:
        target = self._abs(path)
        if not os.path.exists(target):
            raise StorageNotFoundError(f"stat: '{path}' not found")
        return self._entry(target, _norm(path))

    def ls(self, path: str = "") -> list[StorageEntry]:
        target = self._abs(path)
        if not os.path.isdir(target):
            raise StorageNotFoundError(f"ls: '{path}' is not a directory")
        rel_root = _norm(path)
        entries: list[StorageEntry] = []
        for name in os.listdir(target):
            child_rel = f"{rel_root}/{name}" if rel_root else name
            try:
                entries.append(self._entry(os.path.join(target, name), child_rel))
            except OSError as exc:
                # Skip broken symlinks / permission errors / races.
                log.debug("ls: skipping %s: %s", child_rel, exc)
        entries.sort(key=lambda e: (not e.is_dir, e.name.lower()))
        return entries

    def read_bytes(self, path: str) -> bytes:
        try:
            with open(self._abs(path), "rb") as fh:
                return fh.read()
        except FileNotFoundError as exc:
            raise StorageNotFoundError(f"read_bytes: '{path}' not found") from exc

    def write_bytes(
        self, path: str, data: bytes, *, overwrite: bool = True
    ) -> None:
        if not _norm(path):
            raise StorageError("write_bytes: empty path is not allowed")
        target = self._abs(path)
        if not overwrite and os.path.exists(target):
            raise StorageError(f"write_bytes: target already exists: {path}")
        os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
        tmp = target + ".tmp"
        with open(tmp, "wb") as fh:
            fh.write(data)
        os.replace(tmp, target)

    def open_read(self, path: str) -> BinaryIO:
        try:
            return open(self._abs(path), "rb")
        except FileNotFoundError as exc:
            raise StorageNotFoundError(f"open_read: '{path}' not found") from exc

    def open_write(self, path: str, *, overwrite: bool = True) -> BinaryIO:
        if not _norm(path):
            raise StorageError("open_write: empty path is not allowed")
        return _AtomicLocalWriter(self._abs(path), overwrite=overwrite)

    def mkdir(
        self, path: str, *, parents: bool = True, exist_ok: bool = True
    ) -> None:
        if not _norm(path):
            raise StorageError("mkdir: empty path is not allowed")
        target = self._abs(path)
        if os.path.isdir(target):
            if exist_ok:
                return
            raise StorageError(f"mkdir: target already exists: {path}")
        if parents:
            os.makedirs(target, exist_ok=exist_ok)
        else:
            os.mkdir(target)

    def rm(self, path: str) -> None:
        try:
            os.remove(self._abs(path))
        except FileNotFoundError as exc:
            raise StorageNotFoundError(f"rm: '{path}' not found") from exc

    def rmdir(self, path: str, *, recursive: bool = True) -> None:
        if not _norm(path):
            raise StorageError("rmdir: cannot remove storage root")
        target = self._abs(path)
        if not os.path.isdir(target):
            raise StorageNotFoundError(f"rmdir: '{path}' is not a directory")
        (shutil.rmtree if recursive else os.rmdir)(target)

    def rename(self, src: str, dst: str) -> None:
        if not _norm(src) or not _norm(dst):
            raise StorageError("rename: source and destination must be non-empty")
        s_abs, d_abs = self._abs(src), self._abs(dst)
        if not os.path.exists(s_abs):
            raise StorageNotFoundError(f"rename: '{src}' not found")
        os.makedirs(os.path.dirname(d_abs) or ".", exist_ok=True)
        os.replace(s_abs, d_abs)


# â”€â”€ ADLS adapter â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


def _entry_from_adls(entry: ADLSEntry) -> StorageEntry:
    return StorageEntry(
        name=entry.name,
        path=entry.path,
        is_dir=entry.is_dir,
        size=entry.size,
        last_modified=entry.last_modified,
    )


def _translate_adls(exc: ADLSError) -> StorageError:
    """Map ``ADLS*`` exceptions onto the ``Storage*`` hierarchy.

    ``ADLSAlreadyExistsError`` and any other ``ADLSError`` subclass falls
    through to the generic :class:`StorageError`.
    """
    if isinstance(exc, ADLSNotFoundError):
        return StorageNotFoundError(str(exc))
    if isinstance(exc, ADLSNotConfiguredError):
        return StorageNotConfiguredError(str(exc))
    return StorageError(str(exc))


def _adls_call(fn: Callable[[], _T]) -> _T:
    """Run *fn* and translate any ``ADLSError`` into the storage hierarchy."""
    try:
        return fn()
    except ADLSError as exc:
        raise _translate_adls(exc) from exc


class _ADLSWriteBuffer(io.BytesIO):
    """Buffer that uploads to ADLS on ``close``.

    TODO(phase-2): swap for a real chunked / streaming uploader.  Holding
    the entire payload in RAM is fine for ``series.json`` / ``tags.json``
    but will not scale to bronze Excel uploads (multi-hundred-MB).
    """

    def __init__(self, fs: "ADLSStorageBackend", path: str, *, overwrite: bool):
        super().__init__()
        self._fs = fs
        self._path = path
        self._overwrite = overwrite
        self._flushed = False

    def close(self) -> None:
        if self._flushed or self.closed:
            super().close()
            return
        try:
            self._fs.write_bytes(self._path, self.getvalue(), overwrite=self._overwrite)
            self._flushed = True
        finally:
            super().close()


class ADLSStorageBackend:
    """:class:`StorageBackend` backed by an injected :class:`ADLSFileSystem`.

    The wrapped client is **not** re-instantiated per call: pass an
    :class:`ADLSFileSystem` you already have (typically the one the Dash
    app builds at startup) so credentials, sessions, and the cached
    ``FileSystemClient`` are shared.  Every ``ADLS*`` exception is
    translated to the corresponding ``Storage*`` exception so callers
    don't need to import azure-specific types.
    """

    backend_name = "adls"

    def __init__(self, fs: ADLSFileSystem):
        self._fs = fs

    def exists(self, path: str) -> bool:
        return _adls_call(lambda: self._fs.exists(path))

    def stat(self, path: str) -> StorageEntry:
        return _adls_call(lambda: _entry_from_adls(self._fs.stat(path)))

    def ls(self, path: str = "") -> list[StorageEntry]:
        return _adls_call(lambda: [_entry_from_adls(e) for e in self._fs.ls(path)])

    def read_bytes(self, path: str) -> bytes:
        return _adls_call(lambda: self._fs.read_bytes(path))

    def write_bytes(
        self, path: str, data: bytes, *, overwrite: bool = True
    ) -> None:
        _adls_call(lambda: self._fs.write_bytes(path, data, overwrite=overwrite))

    def open_read(self, path: str) -> BinaryIO:
        # TODO(phase-2): swap for a real streaming downloader.
        return io.BytesIO(self.read_bytes(path))

    def open_write(self, path: str, *, overwrite: bool = True) -> BinaryIO:
        # TODO(phase-2): swap for a real streaming/chunked uploader.
        return _ADLSWriteBuffer(self, path, overwrite=overwrite)

    def mkdir(
        self, path: str, *, parents: bool = True, exist_ok: bool = True
    ) -> None:
        # ADLSFileSystem.mkdir always creates parents; the parents flag
        # is accepted for protocol parity but is a no-op switch.
        _ = parents
        _adls_call(lambda: self._fs.mkdir(path, exist_ok=exist_ok))

    def rm(self, path: str) -> None:
        _adls_call(lambda: self._fs.rm(path))

    def rmdir(self, path: str, *, recursive: bool = True) -> None:
        _adls_call(lambda: self._fs.rmdir(path, recursive=recursive))

    def rename(self, src: str, dst: str) -> None:
        _adls_call(lambda: self._fs.rename(src, dst))


# â”€â”€ Factory â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


def get_storage_backend() -> StorageBackend:
    """Pick a backend based on env var ``ENERGYSTACK_STORAGE_BACKEND``.

    Values:

    * ``"local"`` (default) -- :class:`LocalStorageBackend` rooted at
      :data:`src.backend.paths.PROJECT_ROOT`.
    * ``"adls"`` -- :class:`ADLSStorageBackend` wrapping a fresh
      :class:`~src.backend.adls_filesystem.ADLSFileSystem` (which reads
      the ``ADLS_*`` service-principal env vars on construction).

    The selection is recomputed on every call so tests can monkey-patch
    the env var without restarting the process.  Production should call
    this once at startup and cache the result.

    Phase 1 only: setting ``ENERGYSTACK_STORAGE_BACKEND=adls`` today has
    no effect because Series Management still talks to the local
    filesystem directly.  Phase 2 (separate PR) will wire it in.
    """
    choice = (os.environ.get("ENERGYSTACK_STORAGE_BACKEND") or "local").strip().lower()
    if choice == "adls":
        return ADLSStorageBackend(ADLSFileSystem())
    if choice not in ("", "local"):
        log.warning(
            "ENERGYSTACK_STORAGE_BACKEND=%r is not a known backend; "
            "falling back to 'local'",
            choice,
        )
    return LocalStorageBackend(_paths.PROJECT_ROOT)


__all__ = [
    "StorageEntry",
    "StorageBackend",
    "StorageError",
    "StorageNotFoundError",
    "StorageNotConfiguredError",
    "LocalStorageBackend",
    "ADLSStorageBackend",
    "get_storage_backend",
]


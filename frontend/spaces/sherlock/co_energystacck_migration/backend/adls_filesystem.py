"""adls_filesystem -- Thin CRUD wrapper around Azure Data Lake Storage Gen2.

The Dash app treats ADLS as a virtual mounted filesystem: callers pass
POSIX-style paths (``/folder/file.txt`` or ``folder/file.txt``) and
receive familiar entries like ``ls()`` / ``stat()`` / ``read_bytes()``.

The backing store is an ADLS Gen2 account with hierarchical namespace
enabled.  Authentication is service-principal via three environment
variables (kept distinct from the OIDC variables used for app login):

    ADLS_ACCOUNT_NAME      storage account, e.g. ``co2elydatalake``
    ADLS_CONTAINER         filesystem / container name, e.g. ``reports``
    ADLS_TENANT_ID         Azure AD tenant id
    ADLS_CLIENT_ID         service principal application (client) id
    ADLS_CLIENT_SECRET     service principal secret

When ``ADLS_ACCOUNT_NAME`` is unset the class is left in an
**unconfigured** state: ``is_configured()`` returns ``False`` and every
operation raises :class:`ADLSNotConfiguredError`.  The Dash tab uses
this to render a friendly setup hint instead of crashing.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


__all__ = [
    "ADLSAlreadyExistsError",
    "ADLSAuthError",
    "ADLSConnectionTestResult",
    "ADLSEntry",
    "ADLSError",
    "ADLSFileSystem",
    "ADLSNetworkError",
    "ADLSNotConfiguredError",
    "ADLSNotFoundError",
    "ADLSPermissionDeniedError",
]


# ===================================================================== #
#  Public types                                                         #
# ===================================================================== #


class ADLSError(Exception):
    """Base class for ADLS-related errors raised by this wrapper."""


class ADLSNotConfiguredError(ADLSError):
    """Raised when ADLS env vars are missing and the caller tries to act."""


class ADLSNotFoundError(ADLSError):
    """The requested file or directory does not exist."""


class ADLSAlreadyExistsError(ADLSError):
    """The target path already exists (e.g., mkdir on an existing dir)."""


class ADLSAuthError(ADLSError):
    """Service-principal authentication failed (bad/expired secret, wrong tenant, ...)."""


class ADLSPermissionDeniedError(ADLSError):
    """The service principal authenticated but lacks the RBAC role for the operation."""


class ADLSNetworkError(ADLSError):
    """ADLS is unreachable from the current host (proxy / DNS / TLS / network)."""


@dataclass(frozen=True)
class ADLSConnectionTestResult:
    """Outcome of :meth:`ADLSFileSystem.test_connection`.

    Attributes
    ----------
    ok : bool
        ``True`` only when the probe call succeeded.
    kind : str
        One of ``"ok"``, ``"not_configured"``, ``"auth_failed"``,
        ``"rbac_denied"``, ``"account_or_container_missing"``,
        ``"network_error"``, ``"unknown"``.  Used by the UI to pick a
        colour and a remediation hint.
    summary : dict
        Redacted output of :meth:`ADLSFileSystem.config_summary` so the
        UI can show what configuration was used (the secret is always
        rendered as ``"***"`` or ``"(unset)"``).
    detail : str
        Short human-readable diagnostic.  Never contains the SP secret.
    sdk_error : str
        ``repr()`` of the underlying SDK exception, or ``""`` on success
        / not-configured.  Surfaced inside a collapsible block in the UI.
    """

    ok: bool
    kind: str
    summary: dict = field(default_factory=dict)
    detail: str = ""
    sdk_error: str = ""


@dataclass(frozen=True)
class ADLSEntry:
    """A single entry returned by :meth:`ADLSFileSystem.ls`.

    Attributes
    ----------
    name : str
        Basename only (e.g. ``"report.csv"``).
    path : str
        Full path inside the filesystem (e.g. ``"reports/2026/report.csv"``).
    is_dir : bool
        ``True`` for directories, ``False`` for files.
    size : int
        File size in bytes.  Always ``0`` for directories.
    last_modified : Optional[datetime]
        Server-side modification timestamp, or ``None`` if unavailable.
    """

    name: str
    path: str
    is_dir: bool
    size: int = 0
    last_modified: Optional[datetime] = None

    @property
    def kind(self) -> str:
        """Return ``"dir"`` or ``"file"`` for UI display."""
        return "dir" if self.is_dir else "file"


# ===================================================================== #
#  Path helpers                                                         #
# ===================================================================== #


def _normalize(path: Optional[str]) -> str:
    """Return *path* in canonical form (forward slashes, no leading slash).

    ``None``/``""`` / ``"/"`` all collapse to ``""`` which represents the
    root of the filesystem.  Backslashes are converted to forward
    slashes (matches the rest of the app's path-normalisation policy).
    """
    if not path or path in ("/", "."):
        return ""
    p = str(path).replace("\\", "/").strip()
    while p.startswith("/"):
        p = p[1:]
    while p.endswith("/"):
        p = p[:-1]
    return p


def _join(parent: str, child: str) -> str:
    """Join *parent* and *child* with a single ``/`` separator."""
    parent_n = _normalize(parent)
    child_n = _normalize(child)
    if not parent_n:
        return child_n
    if not child_n:
        return parent_n
    return f"{parent_n}/{child_n}"


def _basename(path: str) -> str:
    """Return the trailing component of *path* (no separator)."""
    p = _normalize(path)
    if "/" not in p:
        return p
    return p.rsplit("/", 1)[1]


def _dirname(path: str) -> str:
    """Return the parent path of *path* (``""`` for root entries).
    """
    p = _normalize(path)
    if "/" not in p:
        return ""
    return p.rsplit("/", 1)[0]


def _is_network_error(exc: BaseException) -> bool:
    """Best-effort: classify *exc* as a DNS / connection-layer failure."""
    import socket

    if isinstance(exc, socket.gaierror):
        return True
    try:
        import requests  # type: ignore

        return isinstance(exc, requests.ConnectionError)
    except Exception:  # pragma: no cover - requests not installed
        return False


# ===================================================================== #
#  Main class                                                           #
# ===================================================================== #


class ADLSFileSystem:
    """CRUD wrapper around a single ADLS Gen2 filesystem (container).

    Instances are cheap to construct and lazily initialise the SDK
    client on first use.  Thread-safe for concurrent reads/writes (the
    underlying ``DataLakeServiceClient`` is thread-safe by design).

    Example
    -------
    >>> fs = ADLSFileSystem()
    >>> if fs.is_configured():
    ...     for entry in fs.ls("reports"):
    ...         print(entry.kind, entry.size, entry.path)
    """

    def __init__(
        self,
        account_name: Optional[str] = None,
        container: Optional[str] = None,
        tenant_id: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
    ):
        self.account_name = account_name or os.getenv("ADLS_ACCOUNT_NAME", "")
        self.container = container or os.getenv("ADLS_CONTAINER", "")
        self._tenant_id = tenant_id or os.getenv("ADLS_TENANT_ID", "")
        self._client_id = client_id or os.getenv("ADLS_CLIENT_ID", "")
        self._client_secret = client_secret or os.getenv("ADLS_CLIENT_SECRET", "")

        self._service_client = None
        self._fs_client = None

    # ----- configuration ------------------------------------------------

    def is_configured(self) -> bool:
        """Return ``True`` iff all required env vars / kwargs are present."""
        return bool(
            self.account_name
            and self.container
            and self._tenant_id
            and self._client_id
            and self._client_secret
        )

    def config_summary(self) -> dict:
        """Return a redacted view of the current configuration (for the UI)."""
        return {
            "account_name": self.account_name or "(unset)",
            "container": self.container or "(unset)",
            "tenant_id": self._tenant_id or "(unset)",
            "client_id": self._client_id or "(unset)",
            "client_secret": "***" if self._client_secret else "(unset)",
            "is_configured": self.is_configured(),
        }

    # ----- connection probe --------------------------------------------

    def test_connection(self) -> ADLSConnectionTestResult:
        """Probe ADLS with one benign list call and classify the result.

        Backs the **Test connection** button in the ADLS Files tab.  Does
        not mutate state on the server, never raises, and does not cache
        the verdict â€” a second call re-runs the probe.  The underlying
        ``FileSystemClient`` is still cached by :meth:`_get_fs_client`
        exactly as it is during regular CRUD calls.
        """
        summary = self.config_summary()

        def _result(kind: str, detail: str, sdk_error: str = "") -> ADLSConnectionTestResult:
            return ADLSConnectionTestResult(
                ok=(kind == "ok"),
                kind=kind,
                summary=summary,
                detail=detail,
                sdk_error=sdk_error,
            )

        if not self.is_configured():
            missing = [
                env
                for env, val in (
                    ("ADLS_ACCOUNT_NAME", self.account_name),
                    ("ADLS_CONTAINER", self.container),
                    ("ADLS_TENANT_ID", self._tenant_id),
                    ("ADLS_CLIENT_ID", self._client_id),
                    ("ADLS_CLIENT_SECRET", self._client_secret),
                )
                if not val
            ]
            return _result(
                "not_configured",
                "ADLS env vars are unset: " + ", ".join(missing)
                if missing
                else "ADLS is not configured.",
            )

        # Lazy SDK imports keep adls_filesystem importable even when
        # azure-core is missing in a stripped-down env.
        try:
            from azure.core.exceptions import (
                ClientAuthenticationError,
                HttpResponseError,
                ServiceRequestError,
            )
        except Exception as e:  # pragma: no cover - SDK install issue
            return _result(
                "unknown",
                f"Could not import azure.core.exceptions: {e}",
                repr(e),
            )

        try:
            fs = self._get_fs_client()
        except Exception as e:  # pragma: no cover - very unusual
            return _result(
                "unknown",
                f"Could not initialise the ADLS SDK client: {e}",
                repr(e),
            )

        try:
            try:
                next(
                    iter(fs.get_paths(path=None, recursive=False, max_results=1)),
                    None,
                )
            except TypeError:
                # Older SDK versions reject ``max_results``; fall back to
                # a bare list-and-slice (still benign for connectivity).
                list(fs.get_paths(path=None, recursive=False))[:1]
        except ClientAuthenticationError as e:
            return _result(
                "auth_failed",
                "Service principal authentication failed.  Verify "
                "ADLS_CLIENT_SECRET (it may be expired) and that "
                "ADLS_TENANT_ID matches the SP's home tenant.",
                repr(e),
            )
        except HttpResponseError as e:
            status = getattr(e, "status_code", None) or getattr(
                getattr(e, "response", None), "status_code", None
            )
            msg = str(e)
            if status == 403:
                return _result(
                    "rbac_denied",
                    "RBAC denied.  The service principal needs the "
                    "'Storage Blob Data Contributor' role on the "
                    "storage account or container.",
                    repr(e),
                )
            missing_tokens = ("ContainerNotFound", "FilesystemNotFound", "AccountNotFound")
            if status in (404, 409) or any(tok in msg for tok in missing_tokens):
                return _result(
                    "account_or_container_missing",
                    f"Container '{self.container}' or account "
                    f"'{self.account_name}' was not found.  Verify the "
                    "names and create the filesystem if missing.",
                    repr(e),
                )
            return _result(
                "unknown",
                f"HTTP error {status or '?'} from ADLS: {e}",
                repr(e),
            )
        except ServiceRequestError as e:
            return _result(
                "network_error",
                "Network error reaching ADLS.  Check App Service "
                "outbound rules, DNS resolution, and any required "
                "proxy settings.",
                repr(e),
            )
        except Exception as e:  # noqa: BLE001 - last-resort net classification
            if _is_network_error(e):
                return _result(
                    "network_error",
                    "Network error reaching ADLS (DNS / TLS / "
                    "connection).  Check App Service outbound rules "
                    "or proxy.",
                    repr(e),
                )
            return _result(
                "unknown",
                f"Unexpected error during connection probe: {e}",
                repr(e),
            )

        return _result(
            "ok",
            f"Connected to '{self.account_name}/{self.container}' "
            "via service-principal auth.",
        )

    # ----- internals ----------------------------------------------------

    def _require_configured(self):
        if not self.is_configured():
            raise ADLSNotConfiguredError(
                "ADLS is not configured. Set ADLS_ACCOUNT_NAME, ADLS_CONTAINER, "
                "ADLS_TENANT_ID, ADLS_CLIENT_ID, ADLS_CLIENT_SECRET."
            )

    def _get_fs_client(self):
        """Build (once) and cache the underlying FileSystemClient."""
        if self._fs_client is not None:
            return self._fs_client

        self._require_configured()
        # Import lazily so the rest of the app can run without the SDK.
        from azure.identity import ClientSecretCredential
        from azure.storage.filedatalake import DataLakeServiceClient

        credential = ClientSecretCredential(
            tenant_id=self._tenant_id,
            client_id=self._client_id,
            client_secret=self._client_secret,
        )
        self._service_client = DataLakeServiceClient(
            account_url=f"https://{self.account_name}.dfs.core.windows.net",
            credential=credential,
        )
        self._fs_client = self._service_client.get_file_system_client(self.container)
        return self._fs_client

    @staticmethod
    def _wrap_sdk_error(exc, *, action: str, path: str):
        """Translate Azure SDK exceptions to our ADLS* hierarchy.

        The ``ADLS*`` subclasses are picked so the Dash tab can render a
        short actionable toast per failure family without having to peek
        inside the underlying ``azure.core`` exception hierarchy.
        """
        from azure.core.exceptions import (
            ClientAuthenticationError,
            HttpResponseError,
            ResourceExistsError,
            ResourceNotFoundError,
            ServiceRequestError,
        )

        # Order matters: ResourceNotFoundError / ResourceExistsError are
        # both subclasses of HttpResponseError, so they have to be matched
        # first or they'd be swallowed by the 403/generic branches below.
        if isinstance(exc, ResourceNotFoundError):
            return ADLSNotFoundError(f"{action} failed: '{path}' not found")
        if isinstance(exc, ResourceExistsError):
            return ADLSAlreadyExistsError(f"{action} failed: '{path}' already exists")
        if isinstance(exc, ClientAuthenticationError):
            return ADLSAuthError(
                f"{action} failed for '{path}': service-principal authentication "
                "failed (check ADLS_CLIENT_SECRET / ADLS_TENANT_ID)"
            )
        if isinstance(exc, HttpResponseError):
            status = getattr(exc, "status_code", None) or getattr(
                getattr(exc, "response", None), "status_code", None
            )
            if status == 403:
                return ADLSPermissionDeniedError(
                    f"{action} failed for '{path}': RBAC denied (the service "
                    "principal needs Storage Blob Data Contributor on the "
                    "container)"
                )
        if isinstance(exc, ServiceRequestError):
            return ADLSNetworkError(
                f"{action} failed for '{path}': network error reaching ADLS "
                f"({exc})"
            )
        return ADLSError(f"{action} failed for '{path}': {exc}")

    # ----- listing / metadata ------------------------------------------

    def ls(self, path: str = "") -> list[ADLSEntry]:
        """List the immediate children of directory *path*.

        Parameters
        ----------
        path : str
            ``""`` / ``"/"`` for the filesystem root.

        Returns
        -------
        list[ADLSEntry]
            Directories first, then files, each sorted by name.
        """
        fs = self._get_fs_client()
        p = _normalize(path)
        try:
            raw = list(fs.get_paths(path=p or None, recursive=False))
        except Exception as e:
            raise self._wrap_sdk_error(e, action="ls", path=p) from e

        entries = [
            ADLSEntry(
                name=_basename(getattr(r, "name", "")),
                path=_normalize(getattr(r, "name", "")),
                is_dir=bool(getattr(r, "is_directory", False)),
                size=int(getattr(r, "content_length", 0) or 0),
                last_modified=getattr(r, "last_modified", None),
            )
            for r in raw
            if getattr(r, "name", None)
        ]

        # Dirs first, then files; alphabetical within each group.
        entries.sort(key=lambda e: (not e.is_dir, e.name.lower()))
        return entries

    def stat(self, path: str) -> ADLSEntry:
        """Return metadata for a single file or directory."""
        fs = self._get_fs_client()
        p = _normalize(path)
        if not p:
            return ADLSEntry(name="", path="", is_dir=True)
        try:
            client = fs.get_file_client(p)
            props = client.get_file_properties()
        except Exception as e:
            raise self._wrap_sdk_error(e, action="stat", path=p) from e

        is_dir = False
        meta = getattr(props, "metadata", {}) or {}
        if str(meta.get("hdi_isfolder", "")).lower() == "true":
            is_dir = True
        return ADLSEntry(
            name=_basename(p),
            path=p,
            is_dir=is_dir,
            size=int(getattr(props, "size", 0) or 0),
            last_modified=getattr(props, "last_modified", None),
        )

    def exists(self, path: str) -> bool:
        """Return ``True`` if *path* exists as a file or directory."""
        try:
            self.stat(path)
            return True
        except ADLSNotFoundError:
            return False

    # ----- read / write -------------------------------------------------

    def read_bytes(self, path: str) -> bytes:
        """Download *path* and return its full contents as bytes."""
        fs = self._get_fs_client()
        p = _normalize(path)
        try:
            file_client = fs.get_file_client(p)
            downloader = file_client.download_file()
            return downloader.readall()
        except Exception as e:
            raise self._wrap_sdk_error(e, action="read", path=p) from e

    def read_text(self, path: str, encoding: str = "utf-8") -> str:
        """Convenience: :meth:`read_bytes` decoded with *encoding*."""
        return self.read_bytes(path).decode(encoding)

    def write_bytes(self, path: str, data: bytes, overwrite: bool = True) -> None:
        """Upload *data* to *path*, creating or overwriting the file."""
        fs = self._get_fs_client()
        p = _normalize(path)
        if not p:
            raise ADLSError("write_bytes: empty path is not allowed")
        try:
            file_client = fs.get_file_client(p)
            file_client.upload_data(
                data, overwrite=overwrite, length=len(data) if data else 0
            )
        except Exception as e:
            raise self._wrap_sdk_error(e, action="write", path=p) from e

    def write_text(
        self, path: str, text: str, encoding: str = "utf-8", overwrite: bool = True
    ) -> None:
        """Convenience: :meth:`write_bytes` with *text* encoded as *encoding*."""
        self.write_bytes(path, text.encode(encoding), overwrite=overwrite)

    def upload_file(
        self, local_path: str, remote_path: str, overwrite: bool = True
    ) -> None:
        """Stream a local file to ADLS at *remote_path*."""
        if not os.path.isfile(local_path):
            raise FileNotFoundError(local_path)
        with open(local_path, "rb") as fh:
            self.write_bytes(remote_path, fh.read(), overwrite=overwrite)

    def download_file(self, remote_path: str, local_path: str) -> str:
        """Download *remote_path* to *local_path* and return *local_path*."""
        data = self.read_bytes(remote_path)
        os.makedirs(os.path.dirname(local_path) or ".", exist_ok=True)
        with open(local_path, "wb") as fh:
            fh.write(data)
        return local_path

    # ----- directories --------------------------------------------------

    def mkdir(self, path: str, exist_ok: bool = False) -> None:
        """Create directory *path*.  Parents are created automatically.

        With ``exist_ok=False`` a pre-existing directory raises
        :class:`ADLSAlreadyExistsError`.
        """
        fs = self._get_fs_client()
        p = _normalize(path)
        if not p:
            raise ADLSError("mkdir: empty path is not allowed")
        if exist_ok and self.exists(p):
            return
        try:
            fs.create_directory(p)
        except Exception as e:
            raise self._wrap_sdk_error(e, action="mkdir", path=p) from e

    def rmdir(self, path: str, recursive: bool = True) -> None:
        """Delete directory *path* and (by default) all of its contents."""
        fs = self._get_fs_client()
        p = _normalize(path)
        if not p:
            raise ADLSError("rmdir: cannot remove filesystem root")
        try:
            dir_client = fs.get_directory_client(p)
            dir_client.delete_directory()
            # The SDK's delete_directory is always recursive in HNS-enabled
            # accounts; the `recursive` flag is retained for API symmetry.
            _ = recursive
        except Exception as e:
            raise self._wrap_sdk_error(e, action="rmdir", path=p) from e

    # ----- delete / rename / copy --------------------------------------

    def rm(self, path: str) -> None:
        """Delete a single file at *path*."""
        fs = self._get_fs_client()
        p = _normalize(path)
        if not p:
            raise ADLSError("rm: empty path is not allowed")
        try:
            fs.get_file_client(p).delete_file()
        except Exception as e:
            raise self._wrap_sdk_error(e, action="rm", path=p) from e

    def rename(self, src: str, dst: str) -> None:
        """Atomically rename / move *src* to *dst* inside the same filesystem."""
        fs = self._get_fs_client()
        s = _normalize(src)
        d = _normalize(dst)
        if not s or not d:
            raise ADLSError("rename: source and destination must be non-empty")
        try:
            entry = self.stat(s)
            if entry.is_dir:
                client = fs.get_directory_client(s)
                client.rename_directory(new_name=f"{self.container}/{d}")
            else:
                client = fs.get_file_client(s)
                client.rename_file(new_name=f"{self.container}/{d}")
        except Exception as e:
            raise self._wrap_sdk_error(e, action="rename", path=f"{s} -> {d}") from e

    def copy(self, src: str, dst: str) -> None:
        """Copy *src* to *dst* (download-then-upload; not atomic).

        ADLS Gen2 does not expose a server-side copy in the public Python
        SDK, so this performs a read-then-write round-trip.  Suitable
        for small/medium files; for very large objects prefer a job that
        uses ``azcopy`` outside the app.
        """
        s = _normalize(src)
        d = _normalize(dst)
        if not s or not d:
            raise ADLSError("copy: source and destination must be non-empty")
        entry = self.stat(s)
        if entry.is_dir:
            raise ADLSError("copy: copying directories is not supported")
        data = self.read_bytes(s)
        self.write_bytes(d, data, overwrite=True)


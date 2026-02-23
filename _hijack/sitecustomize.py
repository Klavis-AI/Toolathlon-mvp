"""
Auto-loaded hijack — redirects network and file access via env-var-driven monkeypatches.

HOW IT WORKS:
    Python automatically imports sitecustomize.py at startup from any directory
    on PYTHONPATH. By prepending the _hijack/ directory to PYTHONPATH in
    subprocess env, this module runs before the child script starts.

    SOCKET PATCH:
    It monkey-patches socket.getaddrinfo() so that:
      - localhost:1143 → HIJACK_IMAP_HOST:HIJACK_IMAP_PORT  (IMAP)
      - localhost:1587 → HIJACK_SMTP_HOST:HIJACK_SMTP_PORT  (SMTP)
      - All other connections (e.g. localhost:17362) pass through unchanged.

    Both imaplib and smtplib use socket.getaddrinfo() under the hood, so this
    catches all email connections before they're even attempted.

    FILE OPEN PATCH:
    It monkey-patches builtins.open(), io.open(), os.stat(), and
    pathlib.Path.stat() so that:
      - Any open()/stat() of a path ending with
        'configs/google_credentials.json' is silently redirected to the
        temp file path given by HIJACK_GOOGLE_CREDENTIALS_PATH.
      - Any open()/stat() of a path ending with
        'configs/gcp-service_account.keys.json' is silently redirected to
        the temp file path given by HIJACK_GCP_SERVICE_ACCOUNT_PATH.
    This lets the Klavis sandbox inject credentials from its auth_data
    without writing to the shared configs/ directory.

ACTIVATION:
    Socket patch activates if HIJACK_IMAP_HOST or HIJACK_SMTP_HOST is set.
    File-open patch activates if HIJACK_GOOGLE_CREDENTIALS_PATH or
    HIJACK_GCP_SERVICE_ACCOUNT_PATH is set.
    If none of the HIJACK_* env vars are present, this module does nothing.

PARALLEL SAFETY:
    Each subprocess gets its own env vars → each can redirect to a different
    remote server / temp file without conflict.
"""

import builtins
import io
import os
import socket
import sys

_orig_getaddrinfo = socket.getaddrinfo

# Hosts we consider "local" — these are what the child scripts hardcode
_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})

# Map of hardcoded port → (env var for replacement host, env var for replacement port)
_REDIRECT_MAP = {
    1143: ("HIJACK_IMAP_HOST", "HIJACK_IMAP_PORT"),
    1587: ("HIJACK_SMTP_HOST", "HIJACK_SMTP_PORT"),
}

# Only patch if at least one redirect env var is actually set
_any_redirect = any(os.environ.get(h) for _, (h, _) in _REDIRECT_MAP.items())


def _hijacked_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    """Intercept DNS resolution: swap localhost:<hijacked-port> to remote target."""
    try:
        numeric_port = int(port)
    except (ValueError, TypeError):
        numeric_port = None

    if host in _LOCAL_HOSTS and numeric_port in _REDIRECT_MAP:
        host_env, port_env = _REDIRECT_MAP[numeric_port]
        new_host = os.environ.get(host_env)
        new_port = os.environ.get(port_env)
        if new_host and new_port:
            print(
                f"[socket_hijack] Redirecting {host}:{port} -> {new_host}:{new_port}",
                file=sys.stderr,
            )
            host = new_host
            port = int(new_port)

    return _orig_getaddrinfo(host, port, family, type, proto, flags)


if _any_redirect:
    socket.getaddrinfo = _hijacked_getaddrinfo


# ---------------------------------------------------------------------------
# File-open patch: redirect credential files → temp files
# ---------------------------------------------------------------------------

_google_creds_override = os.environ.get("HIJACK_GOOGLE_CREDENTIALS_PATH")
_gcp_sa_override = os.environ.get("HIJACK_GCP_SERVICE_ACCOUNT_PATH")

# Map of file-path suffixes to their hijack env vars.
# Each entry: suffix → env-var name whose value is the temp-file path.
_FILE_REDIRECT_SUFFIXES = {}
if _google_creds_override:
    _FILE_REDIRECT_SUFFIXES["configs/google_credentials.json"] = "HIJACK_GOOGLE_CREDENTIALS_PATH"
if _gcp_sa_override:
    _FILE_REDIRECT_SUFFIXES["configs/gcp-service_account.keys.json"] = "HIJACK_GCP_SERVICE_ACCOUNT_PATH"

if _FILE_REDIRECT_SUFFIXES:
    _orig_open = builtins.open

    def _resolve_redirect(file_str):
        """Return the override path if *file_str* matches a redirect suffix, else None."""
        normalised = file_str.replace("\\", "/")
        for suffix, env_var in _FILE_REDIRECT_SUFFIXES.items():
            if normalised.endswith(suffix):
                return os.environ.get(env_var)
        return None

    def _hijacked_open(file, *args, **kwargs):
        """Intercept open(): swap credential files to their temp-file overrides."""
        override = _resolve_redirect(str(file))
        if override:
            print(
                f"[file_hijack] Redirecting {file} -> {override}",
                file=sys.stderr,
            )
            file = override
        return _orig_open(file, *args, **kwargs)

    builtins.open = _hijacked_open
    io.open = _hijacked_open

    # ------------------------------------------------------------------
    # Patch os.stat / os.path.exists / pathlib.Path.exists so that
    # existence checks on the hijacked paths succeed even though the
    # original file does not exist on disk.
    # ------------------------------------------------------------------
    import pathlib as _pathlib

    _orig_os_stat = os.stat

    def _hijacked_os_stat(path, *args, **kwargs):
        override = _resolve_redirect(str(path))
        if override:
            print(
                f"[file_hijack] stat redirect {path} -> {override}",
                file=sys.stderr,
            )
            path = override
        return _orig_os_stat(path, *args, **kwargs)

    os.stat = _hijacked_os_stat

    _orig_path_stat = _pathlib.Path.stat

    def _hijacked_path_stat(self, *args, **kwargs):
        override = _resolve_redirect(str(self))
        if override:
            print(
                f"[file_hijack] Path.stat redirect {self} -> {override}",
                file=sys.stderr,
            )
            return _orig_path_stat(_pathlib.Path(override), *args, **kwargs)
        return _orig_path_stat(self, *args, **kwargs)

    _pathlib.Path.stat = _hijacked_path_stat

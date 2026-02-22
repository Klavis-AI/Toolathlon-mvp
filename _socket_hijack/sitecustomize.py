"""
Auto-loaded hijack — redirects network and file access via env-var-driven monkeypatches.

HOW IT WORKS:
    Python automatically imports sitecustomize.py at startup from any directory
    on PYTHONPATH. By prepending the _socket_hijack/ directory to PYTHONPATH in
    subprocess env, this module runs before the child script starts.

    SOCKET PATCH:
    It monkey-patches socket.getaddrinfo() so that:
      - localhost:1143 → HIJACK_IMAP_HOST:HIJACK_IMAP_PORT  (IMAP)
      - localhost:1587 → HIJACK_SMTP_HOST:HIJACK_SMTP_PORT  (SMTP)
      - All other connections (e.g. localhost:17362) pass through unchanged.

    Both imaplib and smtplib use socket.getaddrinfo() under the hood, so this
    catches all email connections before they're even attempted.

    FILE OPEN PATCH:
    It monkey-patches builtins.open() and io.open() so that:
      - Any open() of a path ending with 'configs/google_credentials.json'
        is silently redirected to the temp file path given by
        HIJACK_GOOGLE_CREDENTIALS_PATH.
    This lets the Klavis sandbox inject Google OAuth credentials from its
    auth_data without writing to the shared configs/ directory.

ACTIVATION:
    Socket patch activates if HIJACK_IMAP_HOST or HIJACK_SMTP_HOST is set.
    File-open patch activates if HIJACK_GOOGLE_CREDENTIALS_PATH is set.
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
# File-open patch: redirect configs/google_credentials.json → temp file
# ---------------------------------------------------------------------------

_google_creds_override = os.environ.get("HIJACK_GOOGLE_CREDENTIALS_PATH")

if _google_creds_override:
    _orig_open = builtins.open

    def _hijacked_open(file, *args, **kwargs):
        """Intercept open(): swap configs/google_credentials.json to temp file."""
        # Normalise to forward-slashes so the check works cross-platform
        file_str = str(file).replace("\\", "/")
        if file_str.endswith("configs/google_credentials.json"):
            override = os.environ.get("HIJACK_GOOGLE_CREDENTIALS_PATH")
            if override:
                print(
                    f"[file_hijack] Redirecting {file} -> {override}",
                    file=sys.stderr,
                )
                file = override
        return _orig_open(file, *args, **kwargs)

    builtins.open = _hijacked_open
    io.open = _hijacked_open

"""
Auto-loaded socket hijack — redirects hardcoded localhost IMAP/SMTP to remote servers.

HOW IT WORKS:
    Python automatically imports sitecustomize.py at startup from any directory
    on PYTHONPATH. By prepending the _socket_hijack/ directory to PYTHONPATH in
    subprocess env, this module runs before the child script starts.

    It monkey-patches socket.getaddrinfo() so that:
      - localhost:1143 → HIJACK_IMAP_HOST:HIJACK_IMAP_PORT  (IMAP)
      - localhost:1587 → HIJACK_SMTP_HOST:HIJACK_SMTP_PORT  (SMTP)
      - All other connections (e.g. localhost:17362) pass through unchanged.

    Both imaplib and smtplib use socket.getaddrinfo() under the hood, so this
    catches all email connections before they're even attempted.

ACTIVATION:
    Only activates if HIJACK_IMAP_HOST (or HIJACK_SMTP_HOST) is set in env.
    If none of the HIJACK_* env vars are present, this module does nothing.

PARALLEL SAFETY:
    Each subprocess gets its own env vars → each can redirect to a different
    remote server without conflict.
"""

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

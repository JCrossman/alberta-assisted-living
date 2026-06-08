"""Shared TLS trust configuration for outbound HTTPS.

By default httpx verifies certificates against certifi's bundle, which ignores a
corporate or proxy CA installed in the **system** trust store. Many operators
(and this project's own test environment) run behind a TLS-intercepting egress
proxy, so a certifi-only client fails with CERTIFICATE_VERIFY_FAILED even though
the host is reachable.

`verify_setting()` returns an httpx ``verify`` value that honors the system trust
store and the standard CA environment variables, while still falling back to
certifi everywhere else. It is portable: on a normal machine with no proxy it
behaves exactly like the httpx default. We never *disable* verification - that
would expose the citizen to interception (Constitution Art. 1 spirit); we only
broaden the set of CAs we trust to include ones the operator has installed.
"""

from __future__ import annotations

import os
import ssl
from typing import Union

VerifySetting = Union[str, ssl.SSLContext]


def verify_setting() -> VerifySetting:
    """Build a certificate-verification setting for httpx clients.

    Precedence, matching the requests/httpx conventions an operator expects:

    1. An explicit CA bundle file in ``REQUESTS_CA_BUNDLE`` or ``SSL_CERT_FILE``
       (e.g. a proxy-aware ``ca-certificates.crt``) is used as-is.
    2. Otherwise the system default trust store (which also honors
       ``SSL_CERT_FILE`` / ``SSL_CERT_DIR``), augmented with certifi's roots so
       verification never silently weakens on a minimal image.
    """
    bundle = os.getenv("REQUESTS_CA_BUNDLE") or os.getenv("SSL_CERT_FILE")
    if bundle and os.path.isfile(bundle):
        return bundle

    ctx = ssl.create_default_context()
    try:
        import certifi

        ctx.load_verify_locations(cafile=certifi.where())
    except Exception:  # noqa: BLE001 - certifi is best-effort backup, not required
        pass
    return ctx

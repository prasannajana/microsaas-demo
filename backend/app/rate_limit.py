"""Shared slowapi limiter instance and per-route limit strings.

Client identification uses ``get_remote_address`` (``request.client.host``). Behind a
reverse proxy / load balancer every request would otherwise appear to come from the
proxy, so all users would share one bucket. Run uvicorn with
``--proxy-headers --forwarded-allow-ips=<proxy ip(s)>`` so that ``X-Forwarded-For``
is honoured *only* when it comes from the trusted proxy; never use ``*`` when the
app port is reachable directly, or clients can spoof their address and evade limits.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

# Credential endpoints (register/login): tight, brute-force protection.
AUTH_RATE_LIMIT = "5/minute"
# Token rotation: called automatically by every open tab when the access token
# expires, so it needs more headroom; a refresh token is already a strong secret.
REFRESH_RATE_LIMIT = "30/minute"

limiter = Limiter(key_func=get_remote_address)

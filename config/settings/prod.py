from .base import *  # noqa: F401,F403

DEBUG = False

# Caddy terminates SSL and forwards the original scheme.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_CONTENT_TYPE_NOSNIFF = True

# Caddy is the only reverse proxy in front of Gunicorn, so DRF should trust
# exactly one hop when reading the client IP from X-Forwarded-For (used by throttling).
REST_FRAMEWORK = {**REST_FRAMEWORK, "NUM_PROXIES": 1}  # noqa: F405

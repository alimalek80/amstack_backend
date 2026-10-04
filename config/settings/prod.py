from .base import *  # noqa: F401,F403

DEBUG = False

# Caddy terminates SSL and forwards the original scheme.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_CONTENT_TYPE_NOSNIFF = True

# Number of reverse proxies in front of Gunicorn, so DRF reads the real client IP from
# X-Forwarded-For (used by throttling). Own server: Caddy = 1. Behind another nginx: 2.
REST_FRAMEWORK = {**REST_FRAMEWORK, "NUM_PROXIES": env.int("NUM_PROXIES", default=1)}  # noqa: F405

"""
Gunicorn runtime settings for Render.

Memory: set WEB_CONCURRENCY=1 on 512MB, 2 on 2GB+ (env on Render).
gthread handles concurrent requests without extra processes when workers=1.
"""

import os

bind = f"0.0.0.0:{os.getenv('PORT', '5000')}"

# 512MB instance: keep a single process.
workers = int(os.getenv("WEB_CONCURRENCY", "1"))

# Threads require gthread.
worker_class = "gthread"
threads = int(os.getenv("GUNICORN_THREADS", "8"))

timeout = int(os.getenv("GUNICORN_TIMEOUT", "120"))

# Log to stdout/stderr so Render shows it.
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")

# Proactively recycle the worker to avoid gradual bloat.
max_requests = int(os.getenv("GUNICORN_MAX_REQUESTS", "8000"))
max_requests_jitter = int(os.getenv("GUNICORN_MAX_REQUESTS_JITTER", "50"))


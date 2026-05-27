"""
Gunicorn runtime settings for Render (512 MB RAM).

Keep memory stable:
- 1 worker (avoid duplicating app memory)
- gthread with a few threads (handle concurrent requests without extra processes)
- recycle worker periodically to mitigate slow leaks/fragmentation
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


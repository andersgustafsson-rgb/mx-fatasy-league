"""
Gunicorn runtime settings for Render.

Memory: WEB_CONCURRENCY=1 on 512MB–2GB; gthread handles concurrency without extra processes.
"""

import os

bind = f"0.0.0.0:{os.getenv('PORT', '5000')}"

_on_render = bool(os.getenv("RENDER"))
workers = int(os.getenv("WEB_CONCURRENCY", "1"))

worker_class = "gthread"
# Fewer threads = less concurrent portrait decoding in RAM on small instances.
threads = int(os.getenv("GUNICORN_THREADS", "4" if _on_render else "8"))

timeout = int(os.getenv("GUNICORN_TIMEOUT", "180" if _on_render else "120"))

accesslog = "-"
errorlog = "-"
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")

# Recycle worker before gradual heap growth becomes permanent.
max_requests = int(os.getenv("GUNICORN_MAX_REQUESTS", "800" if _on_render else "8000"))
max_requests_jitter = int(os.getenv("GUNICORN_MAX_REQUESTS_JITTER", "80" if _on_render else "50"))


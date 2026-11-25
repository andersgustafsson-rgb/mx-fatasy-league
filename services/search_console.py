"""Google Search Console metrics — free API (no paid Google product).

Needs a one-time OAuth connect (admin) that stores a refresh token in
app_runtime_flags. Uses the same GOOGLE_CLIENT_ID/SECRET as login.
"""
from __future__ import annotations

import os
import time
from datetime import date, timedelta
from typing import Any

import requests

from services.schema_patches import _ensure_app_runtime_flags_table

GSC_TOKEN_KEY = "gsc_refresh_token"
GSC_SITE_KEY = "gsc_site_url"
DEFAULT_SITE = (os.environ.get("GSC_SITE_URL") or "sc-domain:mx-fantasy.se").strip()

GSC_SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"
TOKEN_URL = "https://oauth2.googleapis.com/token"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
SEARCH_ANALYTICS_URL = (
    "https://www.googleapis.com/webmasters/v3/sites/{site}/searchAnalytics/query"
)

_cache: dict[str, Any] = {"at": 0.0, "payload": None}
_CACHE_TTL = 6 * 3600  # 6h — free quota friendly


def _client_id() -> str:
    return (os.environ.get("GOOGLE_CLIENT_ID") or "").strip()


def _client_secret() -> str:
    return (os.environ.get("GOOGLE_CLIENT_SECRET") or "").strip()


def gsc_oauth_configured() -> bool:
    return bool(_client_id() and _client_secret())


def _flag_get(key: str) -> str | None:
    from models import db

    _ensure_app_runtime_flags_table()
    try:
        row = db.session.execute(
            db.text(
                "SELECT flag_value FROM app_runtime_flags WHERE flag_key = :k LIMIT 1"
            ),
            {"k": key},
        ).first()
        if not row:
            return None
        val = (row[0] or "").strip()
        return val or None
    except Exception:
        db.session.rollback()
        return None


def _flag_set(key: str, value: str) -> None:
    from models import db

    _ensure_app_runtime_flags_table()
    db.session.execute(
        db.text("DELETE FROM app_runtime_flags WHERE flag_key = :k"),
        {"k": key},
    )
    db.session.execute(
        db.text(
            "INSERT INTO app_runtime_flags (flag_key, flag_value, set_at) "
            "VALUES (:k, :v, CURRENT_TIMESTAMP)"
        ),
        {"k": key, "v": value},
    )
    db.session.commit()


def get_stored_refresh_token() -> str | None:
    env = (os.environ.get("GSC_REFRESH_TOKEN") or "").strip()
    if env:
        return env
    return _flag_get(GSC_TOKEN_KEY)


def get_site_url() -> str:
    return _flag_get(GSC_SITE_KEY) or DEFAULT_SITE


def store_refresh_token(token: str, *, site_url: str | None = None) -> None:
    _flag_set(GSC_TOKEN_KEY, token.strip())
    if site_url:
        _flag_set(GSC_SITE_KEY, site_url.strip())


def build_gsc_authorize_url(*, redirect_uri: str, state: str) -> str:
    from urllib.parse import urlencode

    params = {
        "client_id": _client_id(),
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": GSC_SCOPE,
        "state": state,
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
    }
    return f"{AUTH_URL}?{urlencode(params)}"


def exchange_gsc_code(*, code: str, redirect_uri: str) -> dict[str, Any]:
    resp = requests.post(
        TOKEN_URL,
        data={
            "code": code,
            "client_id": _client_id(),
            "client_secret": _client_secret(),
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        },
        timeout=25,
    )
    resp.raise_for_status()
    return resp.json()


def _access_token_from_refresh(refresh_token: str) -> str:
    resp = requests.post(
        TOKEN_URL,
        data={
            "client_id": _client_id(),
            "client_secret": _client_secret(),
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
        timeout=25,
    )
    resp.raise_for_status()
    data = resp.json()
    token = data.get("access_token")
    if not token:
        raise RuntimeError("No access_token from Google")
    return str(token)


def _query_search_analytics(
    *,
    access_token: str,
    site_url: str,
    start: date,
    end: date,
    dimensions: list[str] | None = None,
    row_limit: int = 10,
) -> dict[str, Any]:
    from urllib.parse import quote

    url = SEARCH_ANALYTICS_URL.format(site=quote(site_url, safe=""))
    body: dict[str, Any] = {
        "startDate": start.isoformat(),
        "endDate": end.isoformat(),
        "rowLimit": row_limit,
    }
    if dimensions:
        body["dimensions"] = dimensions
    resp = requests.post(
        url,
        headers={"Authorization": f"Bearer {access_token}"},
        json=body,
        timeout=30,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"GSC API {resp.status_code}: {resp.text[:400]}")
    return resp.json()


def fetch_gsc_summary(*, days: int = 28, force: bool = False) -> dict[str, Any]:
    """Clicks / impressions / CTR / top pages — free Search Console API."""
    now = time.time()
    if (
        not force
        and _cache["payload"] is not None
        and (now - float(_cache["at"])) < _CACHE_TTL
    ):
        return dict(_cache["payload"])

    if not gsc_oauth_configured():
        return {
            "ok": False,
            "configured": False,
            "connected": False,
            "error": "GOOGLE_CLIENT_ID/SECRET saknas",
            "cost": "gratis",
        }

    refresh = get_stored_refresh_token()
    if not refresh:
        return {
            "ok": False,
            "configured": True,
            "connected": False,
            "error": "Inte kopplad ännu — klicka Anslut Search Console i admin",
            "cost": "gratis",
            "connect_path": "/admin/gsc/connect",
        }

    site = get_site_url()
    # GSC data is delayed ~2–3 days
    end = date.today() - timedelta(days=2)
    start = end - timedelta(days=max(7, min(days, 90)) - 1)

    try:
        access = _access_token_from_refresh(refresh)
        totals = _query_search_analytics(
            access_token=access,
            site_url=site,
            start=start,
            end=end,
            dimensions=None,
            row_limit=1,
        )
        by_page = _query_search_analytics(
            access_token=access,
            site_url=site,
            start=start,
            end=end,
            dimensions=["page"],
            row_limit=8,
        )
        by_query = _query_search_analytics(
            access_token=access,
            site_url=site,
            start=start,
            end=end,
            dimensions=["query"],
            row_limit=8,
        )
    except Exception as e:
        return {
            "ok": False,
            "configured": True,
            "connected": True,
            "error": str(e),
            "site": site,
            "cost": "gratis",
        }

    def _agg_rows(payload: dict[str, Any]) -> dict[str, float]:
        rows = payload.get("rows") or []
        if not rows:
            return {"clicks": 0, "impressions": 0, "ctr": 0, "position": 0}
        # Without dimensions, one summary row; with dimensions, sum clicks/impr
        clicks = sum(float(r.get("clicks") or 0) for r in rows)
        impr = sum(float(r.get("impressions") or 0) for r in rows)
        ctr = (clicks / impr) if impr else 0.0
        # avg position weighted by impressions
        pos_num = sum(
            float(r.get("position") or 0) * float(r.get("impressions") or 0)
            for r in rows
        )
        position = (pos_num / impr) if impr else 0.0
        return {
            "clicks": round(clicks, 1),
            "impressions": round(impr, 1),
            "ctr": round(ctr * 100, 2),
            "position": round(position, 1),
        }

    # Totals: API returns one row without dimensions
    trows = totals.get("rows") or []
    if trows:
        tr = trows[0]
        summary = {
            "clicks": round(float(tr.get("clicks") or 0), 1),
            "impressions": round(float(tr.get("impressions") or 0), 1),
            "ctr": round(float(tr.get("ctr") or 0) * 100, 2),
            "position": round(float(tr.get("position") or 0), 1),
        }
    else:
        summary = _agg_rows(totals)

    def _dim_rows(payload: dict[str, Any], key: str) -> list[dict[str, Any]]:
        out = []
        for r in payload.get("rows") or []:
            keys = r.get("keys") or []
            out.append(
                {
                    key: keys[0] if keys else "",
                    "clicks": round(float(r.get("clicks") or 0), 1),
                    "impressions": round(float(r.get("impressions") or 0), 1),
                    "ctr": round(float(r.get("ctr") or 0) * 100, 2),
                    "position": round(float(r.get("position") or 0), 1),
                }
            )
        return out

    payload = {
        "ok": True,
        "configured": True,
        "connected": True,
        "cost": "gratis",
        "site": site,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "days": (end - start).days + 1,
        "summary": summary,
        "top_pages": _dim_rows(by_page, "page"),
        "top_queries": _dim_rows(by_query, "query"),
        "note": "Search Console-data är gratis och ~2–3 dagar fördröjd.",
    }
    _cache["at"] = now
    _cache["payload"] = payload
    return dict(payload)

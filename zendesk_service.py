"""Zendesk Support API helpers for Kundmail (create tickets)."""
from __future__ import annotations

import os
from typing import Any

import requests


def zendesk_configured() -> bool:
    return bool(
        (os.getenv("ZENDESK_SUBDOMAIN") or "").strip()
        and (os.getenv("ZENDESK_EMAIL") or "").strip()
        and (os.getenv("ZENDESK_API_TOKEN") or "").strip()
    )


def _zendesk_base_url() -> str:
    sub = (os.getenv("ZENDESK_SUBDOMAIN") or "").strip().rstrip("/")
    if sub.endswith(".zendesk.com"):
        sub = sub.replace(".zendesk.com", "")
    return f"https://{sub}.zendesk.com"


def _zendesk_auth() -> tuple[str, str]:
    email = (os.getenv("ZENDESK_EMAIL") or "").strip()
    token = (os.getenv("ZENDESK_API_TOKEN") or "").strip()
    # Zendesk token auth: {email}/token : {api_token}
    return (f"{email}/token", token)


def create_support_ticket(
    *,
    subject: str,
    body: str,
    requester_email: str,
    requester_name: str | None = None,
    order_number: str | None = None,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """
    Create a Zendesk ticket. Returns {ok, ticket_id, ticket_url, error?}.
    """
    if not zendesk_configured():
        return {
            "ok": False,
            "error": "Zendesk är inte konfigurerat. Sätt ZENDESK_SUBDOMAIN, ZENDESK_EMAIL och ZENDESK_API_TOKEN.",
        }

    subject = (subject or "").strip()
    body = (body or "").strip()
    requester_email = (requester_email or "").strip()
    if not subject:
        return {"ok": False, "error": "Ämne saknas"}
    if not body:
        return {"ok": False, "error": "Meddelandetext saknas"}
    if not requester_email or "@" not in requester_email:
        return {"ok": False, "error": "Ange kundens e-post"}

    ticket: dict[str, Any] = {
        "subject": subject,
        "comment": {"body": body},
        "requester": {
            "email": requester_email,
            "name": (requester_name or "").strip() or requester_email.split("@")[0],
        },
    }

    tag_list = [t for t in (tags or []) if t]
    order = (order_number or "").strip()
    if order:
        tag_list.append(f"order_{order}")
        # Also surface order in the first comment if no custom field is mapped.
        field_id = (os.getenv("ZENDESK_ORDER_FIELD_ID") or "").strip()
        if field_id.isdigit():
            ticket["custom_fields"] = [{"id": int(field_id), "value": order}]
        else:
            ticket["comment"]["body"] = f"Ordernummer: {order}\n\n{body}"

    if tag_list:
        ticket["tags"] = tag_list

    url = f"{_zendesk_base_url()}/api/v2/tickets.json"
    try:
        resp = requests.post(
            url,
            json={"ticket": ticket},
            auth=_zendesk_auth(),
            headers={"Content-Type": "application/json"},
            timeout=30,
        )
    except requests.RequestException as e:
        return {"ok": False, "error": f"Kunde inte nå Zendesk: {e}"}

    if resp.status_code not in (200, 201):
        detail = ""
        try:
            detail = resp.json()
        except Exception:
            detail = (resp.text or "")[:400]
        return {
            "ok": False,
            "error": f"Zendesk svarade {resp.status_code}",
            "detail": detail,
        }

    data = resp.json() if resp.content else {}
    ticket_obj = data.get("ticket") or {}
    ticket_id = ticket_obj.get("id")
    if not ticket_id:
        return {"ok": False, "error": "Zendesk skapade ingen ticket-id", "detail": data}

    sub = (os.getenv("ZENDESK_SUBDOMAIN") or "").strip().replace(".zendesk.com", "")
    ticket_url = f"https://{sub}.zendesk.com/agent/tickets/{ticket_id}"
    return {
        "ok": True,
        "ticket_id": int(ticket_id),
        "ticket_url": ticket_url,
    }

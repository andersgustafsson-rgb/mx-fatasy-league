"""Zendesk Support API helpers for Kundmail (create tickets)."""
from __future__ import annotations

import os
import re
from typing import Any

import requests

# Motoaction Zendesk defaults (override via env if needed)
FIELD_RETURARENDE = int(os.getenv("ZENDESK_FIELD_RETURARENDE", "114098652774"))
FIELD_RETURVAL = int(os.getenv("ZENDESK_FIELD_RETURVAL", "360019968360"))
FIELD_TYP_AV_ARENDE = int(os.getenv("ZENDESK_FIELD_TYP_AV_ARENDE", "360020096679"))
FIELD_ORDERNUMMER = int(os.getenv("ZENDESK_ORDER_FIELD_ID", "360020096759"))
FIELD_ENGAGEMENT_MAIL = int(os.getenv("ZENDESK_FIELD_ENGAGEMENT_MAIL", "37225890150674"))

DEFAULT_ASSIGNEE_ID = int(os.getenv("ZENDESK_ASSIGNEE_ID", "280814751"))  # Anders Gustafsson
DEFAULT_GROUP_ID = int(os.getenv("ZENDESK_GROUP_ID", "20391188"))  # Support

# template_id -> Typ av ärende tagger value
TEMPLATE_CASE_TYPE = {
    "slut": "leverans",
    "inkommer": "leverans",
    "utgatt": "leverans",
    "forsening": "leverans",
    "usa_forsening": "leverans",
    "outlost": "leverans",
    "avbokad": "avboka",
    "angerkop": "ångerköp",
    "retur": "reklamation",
    "alternativ": "produktfråga",
    "produktlank": "produktfråga",
    "prisandring": "produktfråga",
}

RETURN_TEMPLATES = {"retur", "angerkop"}


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
    return (f"{email}/token", token)


def _order_as_int(order_number: str | None) -> int | None:
    raw = (order_number or "").strip()
    if not raw:
        return None
    digits = re.sub(r"\D+", "", raw)
    if not digits:
        return None
    try:
        return int(digits)
    except ValueError:
        return None


def resolve_case_type(template_id: str | None, override: str | None = None) -> str:
    if override and override.strip():
        return override.strip()
    tid = (template_id or "").strip()
    return TEMPLATE_CASE_TYPE.get(tid, "övrigt")


def resolve_is_return(template_id: str | None, override: bool | None = None) -> bool:
    if override is not None:
        return bool(override)
    return (template_id or "").strip() in RETURN_TEMPLATES


def create_support_ticket(
    *,
    subject: str,
    body: str,
    requester_email: str,
    requester_name: str | None = None,
    order_number: str | None = None,
    template_id: str | None = None,
    case_type: str | None = None,
    is_return: bool | None = None,
    notify_requester: bool = True,
    solve: bool = True,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """
    Create a Zendesk ticket for Motoaction kundmail.

    notify_requester=False => internal note (no customer email).
    solve=True => status solved + assignee/group + required custom fields filled.
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

    is_ret = resolve_is_return(template_id, is_return)
    typ = resolve_case_type(template_id, case_type)
    order_int = _order_as_int(order_number)

    custom_fields: list[dict[str, Any]] = [
        {"id": FIELD_RETURARENDE, "value": "claims_yes" if is_ret else "claims_no"},
        {"id": FIELD_TYP_AV_ARENDE, "value": typ},
        {"id": FIELD_ENGAGEMENT_MAIL, "value": False},
    ]
    if order_int is not None:
        custom_fields.append({"id": FIELD_ORDERNUMMER, "value": order_int})
    if is_ret:
        # Default return shipping choice; agent can change in Zendesk if needed.
        custom_fields.append({"id": FIELD_RETURVAL, "value": "motoaction_dhl"})

    tag_list = [t for t in (tags or []) if t]
    tag_list.append("kundmail")
    if order_int is not None:
        tag_list.append(f"order_{order_int}")

    ticket: dict[str, Any] = {
        "subject": subject,
        "comment": {
            "body": body,
            "public": bool(notify_requester),
        },
        "requester": {
            "email": requester_email,
            "name": (requester_name or "").strip() or requester_email.split("@")[0],
        },
        "assignee_id": DEFAULT_ASSIGNEE_ID,
        "group_id": DEFAULT_GROUP_ID,
        "custom_fields": custom_fields,
        "tags": tag_list,
    }
    if solve:
        ticket["status"] = "solved"

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
        detail: Any = ""
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
        "status": ticket_obj.get("status"),
        "notified_requester": bool(notify_requester),
    }

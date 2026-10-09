"""Kundmail + Zendesk Support API routes."""
from __future__ import annotations

import os

from flask import Blueprint, jsonify, render_template, request, session

from auth_helpers import require_ops_tools_api, require_ops_tools_page
from models import User

bp = Blueprint("kundmail", __name__)


@bp.get("/kundmail")
def kundmail_page():
    denied = require_ops_tools_page()
    if denied:
        return denied
    return render_template(
        "kundmail.html",
        username=session.get("username") or "",
        is_logged_in=True,
    )


@bp.post("/api/kundmail/translate")
def kundmail_translate():
    denied = require_ops_tools_api()
    if denied:
        return denied

    data = request.get_json(silent=True) or {}
    subject = (data.get("subject") or "").strip()
    body = (data.get("body") or "").strip()
    source = (data.get("from") or "sv").strip().lower()
    target = (data.get("to") or "da").strip().lower()

    if not subject and not body:
        return jsonify({"error": "Ingen text att översätta"}), 400

    try:
        from rider_bio_translate import translate_text

        return jsonify({
            "success": True,
            "subject": translate_text(subject, source=source, target=target) if subject else "",
            "body": translate_text(body, source=source, target=target) if body else "",
        })
    except Exception as e:
        print(f"kundmail translate error: {e}")
        return jsonify({"error": "Översättning misslyckades"}), 500


@bp.get("/api/kundmail/checklist")
def kundmail_checklist_list():
    denied = require_ops_tools_api()
    if denied:
        return denied
    import checklist_service as cs

    return jsonify({"success": True, "items": cs.list_items(int(session["user_id"]))})


@bp.post("/api/kundmail/checklist")
def kundmail_checklist_create():
    denied = require_ops_tools_api()
    if denied:
        return denied
    import checklist_service as cs

    data = request.get_json(silent=True) or {}
    row, err = cs.create_item(int(session["user_id"]), data.get("text") or "")
    if err:
        return jsonify({"error": err}), 400
    return jsonify({"success": True, "item": cs.item_to_dict(row)}), 201


@bp.patch("/api/kundmail/checklist/<int:item_id>")
def kundmail_checklist_update(item_id: int):
    denied = require_ops_tools_api()
    if denied:
        return denied
    import checklist_service as cs

    data = request.get_json(silent=True) or {}
    if "done" not in data:
        return jsonify({"error": "Saknar done"}), 400
    row, err = cs.set_done(int(session["user_id"]), item_id, bool(data.get("done")))
    if err == "not_found":
        return jsonify({"error": "not_found"}), 404
    if err:
        return jsonify({"error": err}), 400
    return jsonify({"success": True, "item": cs.item_to_dict(row)})


@bp.delete("/api/kundmail/checklist/<int:item_id>")
def kundmail_checklist_delete(item_id: int):
    denied = require_ops_tools_api()
    if denied:
        return denied
    import checklist_service as cs

    if not cs.delete_item(int(session["user_id"]), item_id):
        return jsonify({"error": "not_found"}), 404
    return jsonify({"success": True})


@bp.post("/api/kundmail/checklist/clear-done")
def kundmail_checklist_clear_done():
    denied = require_ops_tools_api()
    if denied:
        return denied
    import checklist_service as cs

    removed = cs.clear_done(int(session["user_id"]))
    return jsonify({"success": True, "removed": removed})


@bp.get("/api/kundmail/zendesk_status")
def kundmail_zendesk_status():
    denied = require_ops_tools_api()
    if denied:
        return denied
    from zendesk_service import resolve_assignee, zendesk_configured

    username = (session.get("username") or "").strip()
    display_name = ""
    try:
        user = User.query.get(int(session["user_id"]))
        if user:
            username = user.username or username
            display_name = (user.display_name or "").strip()
    except Exception:
        pass

    assignee = resolve_assignee(username=username, display_name=display_name or None)
    return jsonify({
        "configured": zendesk_configured(),
        "subdomain": (os.getenv("ZENDESK_SUBDOMAIN") or "").strip() or None,
        "fantasy_username": username or None,
        "assignee_name": assignee.get("name"),
        "assignee_id": assignee.get("id"),
    })


@bp.post("/api/kundmail/zendesk_ticket")
def kundmail_zendesk_ticket():
    """Create a new Zendesk ticket from kundmail (subject/body/requester)."""
    denied = require_ops_tools_api()
    if denied:
        return denied

    data = request.get_json(silent=True) or {}
    subject = (data.get("subject") or "").strip()
    body = (data.get("body") or "").strip()
    requester_email = (data.get("requester_email") or data.get("email") or "").strip()
    requester_name = (data.get("requester_name") or data.get("customer_name") or "").strip()
    order_number = (data.get("order_number") or "").strip()
    template_id = (data.get("template_id") or "").strip() or None
    case_type = (data.get("case_type") or "").strip() or None
    notify_requester = bool(data.get("notify_requester", True))
    solve = bool(data.get("solve", True))

    is_return = data.get("is_return", None)
    if isinstance(is_return, str):
        is_return = is_return.strip().lower() in ("1", "true", "yes", "ja")

    fantasy_username = (session.get("username") or "").strip()
    fantasy_display_name = ""
    try:
        user = User.query.get(int(session["user_id"]))
        if user:
            fantasy_username = user.username or fantasy_username
            fantasy_display_name = (user.display_name or "").strip()
    except Exception:
        pass

    from zendesk_service import create_support_ticket

    result = create_support_ticket(
        subject=subject,
        body=body,
        requester_email=requester_email,
        requester_name=requester_name or None,
        order_number=order_number or None,
        template_id=template_id,
        case_type=case_type,
        is_return=is_return if isinstance(is_return, bool) else None,
        notify_requester=notify_requester,
        solve=solve,
        tags=["kundmail"],
        fantasy_username=fantasy_username or None,
        fantasy_display_name=fantasy_display_name or None,
    )
    status = 200 if result.get("ok") else 400
    return jsonify(result), status

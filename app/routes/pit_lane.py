from __future__ import annotations

from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for

from models import db, User, AdminAnnouncement, MessageThread, Message
import pit_lane_service as pls

bp = Blueprint("pit_lane", __name__)


def _require_login():
    if "user_id" not in session:
        return None
    return int(session["user_id"])


@bp.route("/pit-lane")
def pit_lane_page():
    uid = _require_login()
    if uid is None:
        return redirect(url_for("index"))
    pls.ensure_pit_lane_tables()
    thread_id = request.args.get("thread", type=int)
    tab = request.args.get("tab") or ("messages" if thread_id else "all")
    compose_to = request.args.get("to", type=int)
    compose_label = None
    if compose_to:
        u = User.query.get(compose_to)
        if u:
            compose_label = (u.display_name or u.username or "").strip()
    return render_template(
        "pit_lane.html",
        thread_id=thread_id,
        initial_tab=tab,
        compose_to_user_id=compose_to,
        compose_to_label=compose_label,
    )


@bp.get("/api/pit-lane/summary")
def api_summary():
    uid = _require_login()
    if uid is None:
        return jsonify({"error": "not_logged_in"}), 401
    return jsonify(
        {
            "unread_count": pls.total_unread_count(uid),
            "recent": pls.recent_items_for_dropdown(uid),
        }
    )


@bp.get("/api/pit-lane/announcements")
def api_announcements():
    uid = _require_login()
    if uid is None:
        return jsonify({"error": "not_logged_in"}), 401
    from models import UserAnnouncementDismissal

    rows = (
        AdminAnnouncement.query.order_by(AdminAnnouncement.created_at.desc())
        .limit(50)
        .all()
    )
    dismissed_ids = {
        d.announcement_id
        for d in UserAnnouncementDismissal.query.filter_by(user_id=uid).all()
    }
    return jsonify(
        {
            "announcements": [
                {
                    **pls.announcement_to_dict(a),
                    "dismissed": a.id in dismissed_ids,
                }
                for a in rows
            ]
        }
    )


@bp.post("/api/pit-lane/announcements/<int:announcement_id>/dismiss")
def api_dismiss_announcement(announcement_id: int):
    uid = _require_login()
    if uid is None:
        return jsonify({"error": "not_logged_in"}), 401
    ann = AdminAnnouncement.query.get_or_404(announcement_id)
    pls.dismiss_announcement(uid, ann.id)
    return jsonify({"success": True})


@bp.get("/api/pit-lane/threads")
def api_threads():
    uid = _require_login()
    if uid is None:
        return jsonify({"error": "not_logged_in"}), 401
    unread_only = request.args.get("unread_only", "1") not in ("0", "false", "False")
    threads = pls.list_threads_for_user(uid, unread_only=unread_only)
    all_threads = pls.list_threads_for_user(uid, unread_only=False)
    read_count = sum(1 for t in all_threads if t["unread_count"] == 0)
    return jsonify(
        {
            "threads": threads,
            "read_count": read_count,
            "unread_only": unread_only,
        }
    )


@bp.post("/api/pit-lane/threads/mark-all-read")
def api_mark_all_threads_read():
    uid = _require_login()
    if uid is None:
        return jsonify({"error": "not_logged_in"}), 401
    n = pls.mark_all_dm_threads_read(uid)
    return jsonify({"success": True, "marked": n})


@bp.get("/api/pit-lane/threads/<int:thread_id>")
def api_thread_messages(thread_id: int):
    uid = _require_login()
    if uid is None:
        return jsonify({"error": "not_logged_in"}), 401
    thread = MessageThread.query.get_or_404(thread_id)
    if uid not in (thread.user_a_id, thread.user_b_id):
        return jsonify({"error": "forbidden"}), 403
    pls.mark_thread_read(thread_id, uid)
    other_id = pls.other_user_in_thread(thread, uid)
    other = User.query.get(other_id)
    msgs = (
        Message.query.filter_by(thread_id=thread_id)
        .order_by(Message.created_at.asc())
        .all()
    )
    return jsonify(
        {
            "thread": pls.thread_to_dict(thread, uid),
            "messages": [
                {
                    "id": m.id,
                    "from_user_id": m.from_user_id,
                    "body": m.body,
                    "created_at": m.created_at.isoformat() if m.created_at else "",
                    "is_mine": m.from_user_id == uid,
                }
                for m in msgs
            ],
            "other_display_name": pls._display_name(other),
        }
    )


@bp.post("/api/pit-lane/send")
def api_send_message():
    uid = _require_login()
    if uid is None:
        return jsonify({"error": "not_logged_in"}), 401
    data = request.get_json(silent=True) or {}
    to_user_id = data.get("to_user_id")
    body = data.get("body", "")
    thread_id = data.get("thread_id")
    try:
        if thread_id:
            thread = MessageThread.query.get_or_404(int(thread_id))
            if uid not in (thread.user_a_id, thread.user_b_id):
                return jsonify({"error": "forbidden"}), 403
            other_id = pls.other_user_in_thread(thread, uid)
            msg = pls.send_direct_message(uid, other_id, body)
            return jsonify({"success": True, "thread_id": thread.id, "message_id": msg.id})
        if not to_user_id:
            return jsonify({"error": "missing_recipient"}), 400
        to_user_id = int(to_user_id)
        if to_user_id == uid:
            return jsonify({"error": "cannot_message_self"}), 400
        msg = pls.send_direct_message(uid, to_user_id, body)
        thread = MessageThread.query.get(msg.thread_id)
        return jsonify({"success": True, "thread_id": thread.id if thread else None, "message_id": msg.id})
    except ValueError as e:
        code = str(e)
        status = 400
        if code == "user_not_found":
            status = 404
        return jsonify({"error": code}), status


@bp.get("/api/pit-lane/user/<int:user_id>/can-message")
def api_can_message(user_id: int):
    uid = _require_login()
    if uid is None:
        return jsonify({"error": "not_logged_in"}), 401
    if user_id == uid:
        return jsonify({"can_message": False})
    user = User.query.get(user_id)
    return jsonify({"can_message": user is not None})

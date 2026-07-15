from __future__ import annotations

import os

from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for

bp = Blueprint('public', __name__)


@bp.get('/health')
def health():
	return jsonify(status='ok')


@bp.get("/tidrapport")
def tidrapport_page():
	# Endast för inloggad användare (du sa att det bara är du som använder den).
	if "user_id" not in session:
		# app-factory-varianten har inte alla routes här, så vi tar en robust redirect.
		return redirect("/login")

	# Vi har ingen gemensam base-template, så sidan är fristående.
	return render_template("tidrapport.html", username=session.get("username") or "")


@bp.get("/kundmail")
def kundmail_page():
	if "user_id" not in session:
		return redirect("/login")

	return render_template("kundmail.html", username=session.get("username") or "")


@bp.post("/api/kundmail/translate")
def kundmail_translate():
	if "user_id" not in session:
		return jsonify({"error": "Unauthorized"}), 401

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


def _require_login():
	if "user_id" not in session:
		return None
	return int(session["user_id"])


def _cron_authorized() -> bool:
	secret = (os.getenv("CRON_SECRET") or os.getenv("REMINDER_CRON_SECRET") or "").strip()
	if not secret:
		return False
	token = (
		request.headers.get("Authorization", "").replace("Bearer ", "").strip()
		or request.headers.get("X-Cron-Secret", "").strip()
		or (request.get_json(silent=True) or {}).get("secret", "")
	)
	return token == secret


@bp.get("/api/reminders")
def api_reminders_list():
	uid = _require_login()
	if uid is None:
		return jsonify({"error": "Unauthorized"}), 401
	import reminder_service as rs

	return jsonify({"success": True, "reminders": rs.list_reminders(uid)})


@bp.post("/api/reminders")
def api_reminders_create():
	uid = _require_login()
	if uid is None:
		return jsonify({"error": "Unauthorized"}), 401
	import reminder_service as rs

	data = request.get_json(silent=True) or {}
	row, err = rs.create_reminder(uid, data)
	if err:
		return jsonify({"error": err}), 400
	return jsonify({"success": True, "reminder": rs.reminder_to_dict(row)}), 201


@bp.patch("/api/reminders/<int:reminder_id>")
def api_reminders_update(reminder_id: int):
	uid = _require_login()
	if uid is None:
		return jsonify({"error": "Unauthorized"}), 401
	import reminder_service as rs

	data = request.get_json(silent=True) or {}
	row, err = rs.update_reminder(uid, reminder_id, data)
	if err == "not_found":
		return jsonify({"error": err}), 404
	if err:
		return jsonify({"error": err}), 400
	return jsonify({"success": True, "reminder": rs.reminder_to_dict(row)})


@bp.delete("/api/reminders/<int:reminder_id>")
def api_reminders_delete(reminder_id: int):
	uid = _require_login()
	if uid is None:
		return jsonify({"error": "Unauthorized"}), 401
	import reminder_service as rs

	if not rs.delete_reminder(uid, reminder_id):
		return jsonify({"error": "not_found"}), 404
	return jsonify({"success": True})


@bp.post("/api/reminders/<int:reminder_id>/test")
def api_reminders_test(reminder_id: int):
	uid = _require_login()
	if uid is None:
		return jsonify({"error": "Unauthorized"}), 401
	import reminder_service as rs

	result = rs.send_reminder_test(uid, reminder_id)
	if result.get("error") == "not_found":
		return jsonify({"error": "not_found"}), 404
	if not result.get("ok"):
		return jsonify({"success": False, **result}), 400
	return jsonify({"success": True, "message": "Test-push skickad"})


@bp.post("/api/cron/reminders")
def api_cron_reminders():
	if not _cron_authorized():
		return jsonify({"error": "unauthorized"}), 401
	import reminder_service as rs

	return jsonify(rs.process_due_reminders())

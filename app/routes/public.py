from __future__ import annotations

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

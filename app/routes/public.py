from __future__ import annotations

from flask import Blueprint, jsonify, redirect, render_template, session, url_for

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

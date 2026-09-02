from __future__ import annotations

import base64
import os

from flask import Blueprint, Response, jsonify, redirect, render_template, request, session, url_for

bp = Blueprint('public', __name__)


@bp.get('/health')
@bp.get('/healthz')
def health():
	"""Liveness — keep-alive / Render probes (never fail the wake-up ping)."""
	return jsonify(status='ok')


@bp.get("/tidrapport")
def tidrapport_page():
	# Endast för inloggad användare (du sa att det bara är du som använder den).
	if "user_id" not in session:
		# app-factory-varianten har inte alla routes här, så vi tar en robust redirect.
		return redirect("/login")

	# Vi har ingen gemensam base-template, så sidan är fristående.
	return render_template("tidrapport.html", username=session.get("username") or "")


@bp.get("/tröjtryck")
@bp.get("/trojtryck")
def trojtryck_page():
	"""Prototype: jersey name/number designer with Svemo validation + print export."""
	from trojtryck_service import mock_jerseys, print_tiers

	jerseys = []
	for j in mock_jerseys():
		images = j.get("images") or {}
		jerseys.append({
			**j,
			"thumb_url": url_for("static", filename=f"images/trojtryck/{images.get('thumb', '')}"),
			"back_url": url_for("static", filename=f"images/trojtryck/{images.get('back', '')}"),
		})
	return render_template(
		"trojtryck.html",
		jerseys=jerseys,
		print_tiers=print_tiers(),
	)


@bp.get("/api/trojtryck/logo/<variant>.png")
def trojtryck_logo(variant: str):
	"""Skala EPS-loggan on-demand för preview (vektor master, raster vid visning)."""
	from trojtryck_service import MOTOACTION_LOGO_ASPECT, render_motoaction_logo_png

	if variant not in MOTOACTION_LOGO_ASPECT:
		return jsonify({"error": "Ogiltig logotypvariant"}), 400
	w = min(1600, max(64, int(request.args.get("w", 480))))
	h_arg = int(request.args.get("h", 0))
	if h_arg > 0:
		h = min(1200, max(32, h_arg))
	else:
		h = max(32, int(w / MOTOACTION_LOGO_ASPECT[variant]))
	try:
		png = render_motoaction_logo_png(variant=variant, max_w=w, max_h=h)
	except Exception as e:
		print(f"trojtryck logo error: {e}")
		return jsonify({"error": "Kunde inte rendera logotyp"}), 500
	return Response(png, mimetype="image/png", headers={"Cache-Control": "public, max-age=86400"})


@bp.post("/api/trojtryck/export")
def trojtryck_export():
	data = request.get_json(silent=True) or {}
	production = bool(data.get("production"))
	tier_id = (data.get("tier_id") or "standard").strip()
	include_brand = tier_id == "motoaction_brand"
	custom_b64 = (data.get("custom_logo_base64") or "").strip()
	custom_bytes = None
	if custom_b64:
		try:
			if "," in custom_b64:
				custom_b64 = custom_b64.split(",", 1)[1]
			custom_bytes = base64.b64decode(custom_b64)
		except Exception:
			return jsonify({"error": "Ogiltig logotypfil"}), 400

	name = (data.get("name") or "").strip()
	number = (data.get("number") or "").strip()
	fill = (data.get("fill") or "#FFFFFF").strip()
	outline = (data.get("outline") or "#111111").strip()
	jersey_fabric = (data.get("jersey_fabric") or "#f8fafc").strip()
	logo_variant = (data.get("logo_variant") or "").strip().lower()
	if logo_variant not in ("black", "white"):
		logo_variant = None
	font = (data.get("font") or "Black Ops One").strip()[:40] or "Black Ops One"
	allowed_fonts = {"Black Ops One", "Racing Sans One", "Orbitron"}
	if font not in allowed_fonts:
		font = "Black Ops One"
	order_label = (data.get("order_label") or "").strip()

	try:
		from trojtryck_service import render_print_png, render_production_png

		kwargs = {
			"name": name,
			"number": number,
			"fill": fill,
			"outline": outline,
			"include_brand_logo": include_brand,
			"custom_logo_bytes": custom_bytes if tier_id == "custom_back_logo" else None,
			"jersey_fabric": jersey_fabric,
			"logo_variant": logo_variant,
			"font": font,
		}
		if production:
			png = render_production_png(**kwargs, order_label=order_label)
		else:
			png = render_print_png(**kwargs)
	except ValueError as e:
		return jsonify({"error": str(e)}), 400
	except Exception as e:
		print(f"trojtryck export error: {e}")
		return jsonify({"error": "Kunde inte generera printfil"}), 500

	name_slug = (name or "nummer").strip().upper()[:18] or "nummer"
	number_slug = "".join(ch for ch in (number or "") if ch.isdigit())[:3]
	suffix = "produktion" if production else "tryck"
	filename = f"trojtryck-{name_slug}-{number_slug}-{suffix}.png"
	return Response(
		png,
		mimetype="image/png",
		headers={"Content-Disposition": f'attachment; filename="{filename}"'},
	)


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


@bp.get("/api/kundmail/zendesk_status")
def kundmail_zendesk_status():
	if "user_id" not in session:
		return jsonify({"error": "Unauthorized"}), 401
	from zendesk_service import resolve_assignee, zendesk_configured

	username = (session.get("username") or "").strip()
	display_name = ""
	try:
		from models import User

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
	if "user_id" not in session:
		return jsonify({"error": "Unauthorized"}), 401

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
		from models import User

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

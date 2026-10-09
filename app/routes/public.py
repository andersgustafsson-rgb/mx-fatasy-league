from __future__ import annotations

import base64
import json
import os
from pathlib import Path

from flask import (
	Blueprint,
	Response,
	current_app,
	jsonify,
	make_response,
	redirect,
	render_template,
	request,
	send_from_directory,
	session,
	url_for,
)

from auth_helpers import require_ops_tools_api, require_ops_tools_page

bp = Blueprint('public', __name__)


def _schema_dist_dir() -> Path:
	return Path(current_app.static_folder) / "schema"


@bp.get('/health')
@bp.get('/healthz')
def health():
	"""Liveness — keep-alive / Render probes (never fail the wake-up ping)."""
	return jsonify(status='ok')


@bp.get("/barniva")
@bp.get("/verktyg")
def barniva_hub():
	"""Hub for BarnIVA tools: tidrapport + schemaanalys."""
	denied = require_ops_tools_page()
	if denied:
		return denied
	return render_template("barniva_hub.html", username=session.get("username") or "")


@bp.get("/tidrapport")
def tidrapport_page():
	# Ops-verktyg (ops_tools), inte spelet — egen flagga från is_admin.
	denied = require_ops_tools_page()
	if denied:
		return denied

	# Vi har ingen gemensam base-template, så sidan är fristående.
	return render_template("tidrapport.html", username=session.get("username") or "")


@bp.get("/schema")
@bp.get("/schema/")
def schema_app_index():
	"""Serve BarnIVA schema SPA (built into static/schema)."""
	denied = require_ops_tools_page()
	if denied:
		return denied
	dist = _schema_dist_dir()
	index = dist / "index.html"
	if not index.is_file():
		return (
			"Schemaanalys är inte byggd ännu. Kör `npm run build:mx` i barniva-schema.",
			503,
		)
	html = index.read_text(encoding="utf-8")
	boot = {
		"username": (session.get("username") or "").strip(),
		"displayName": "",
		"userId": session.get("user_id"),
	}
	try:
		from models import User

		uid = session.get("user_id")
		if uid:
			user = User.query.get(int(uid))
			if user and getattr(user, "display_name", None):
				boot["displayName"] = (user.display_name or "").strip()
	except Exception:
		pass
	boot_json = json.dumps(boot, ensure_ascii=False)
	inject = (
		f"<script>window.__BARNIVA__={boot_json};</script>\n"
	)
	if "</head>" in html:
		html = html.replace("</head>", inject + "</head>", 1)
	else:
		html = inject + html
	return Response(html, mimetype="text/html; charset=utf-8")


@bp.get("/schema/<path:asset_path>")
def schema_app_asset(asset_path: str):
	"""Assets for the schema SPA under /schema/…"""
	denied = require_ops_tools_page()
	if denied:
		return denied
	dist = _schema_dist_dir()
	candidate = dist / asset_path
	if candidate.is_file():
		return send_from_directory(dist, asset_path)
	# SPA fallback
	index = dist / "index.html"
	if index.is_file():
		return send_from_directory(dist, "index.html")
	return ("Schemaanalys saknas.", 404)


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
	font = (data.get("font") or "Anton").strip()[:40] or "Anton"
	allowed_fonts = {
		"Anton",
		"Bebas Neue",
		"Russo One",
		"Bungee",
		"Graduate",
		"Archivo Black",
		"Oswald",
		"Racing Sans One",
		"Orbitron",
		"Black Ops One",
	}
	if font not in allowed_fonts:
		font = "Anton"
	order_label = (data.get("order_label") or "").strip()
	dpi = int(data.get("dpi") or 300)
	dpi = min(300, max(72, dpi))

	try:
		from trojtryck_service import render_print_png, render_production_png

		kwargs = {
			"name": name,
			"number": number,
			"fill": fill,
			"outline": outline,
			"dpi": dpi,
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
	denied = require_ops_tools_api()
	if denied:
		return denied
	uid = int(session["user_id"])
	import reminder_service as rs

	return jsonify({"success": True, "reminders": rs.list_reminders(uid)})


@bp.post("/api/reminders")
def api_reminders_create():
	denied = require_ops_tools_api()
	if denied:
		return denied
	uid = int(session["user_id"])
	import reminder_service as rs

	data = request.get_json(silent=True) or {}
	row, err = rs.create_reminder(uid, data)
	if err:
		return jsonify({"error": err}), 400
	return jsonify({"success": True, "reminder": rs.reminder_to_dict(row)}), 201


@bp.patch("/api/reminders/<int:reminder_id>")
def api_reminders_update(reminder_id: int):
	denied = require_ops_tools_api()
	if denied:
		return denied
	uid = int(session["user_id"])
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
	denied = require_ops_tools_api()
	if denied:
		return denied
	uid = int(session["user_id"])
	import reminder_service as rs

	if not rs.delete_reminder(uid, reminder_id):
		return jsonify({"error": "not_found"}), 404
	return jsonify({"success": True})


@bp.post("/api/reminders/<int:reminder_id>/test")
def api_reminders_test(reminder_id: int):
	denied = require_ops_tools_api()
	if denied:
		return denied
	uid = int(session["user_id"])
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


# --- BarnIVA shared schema workspace (server) ---------------------------------

_BARNIVA_VERSION_KEEP = 40
# Don't create a restore-point on every 2s autosave — only when meaningful.
_BARNIVA_SNAPSHOT_COOLDOWN_SEC = 10 * 60
_BARNIVA_SNAPSHOT_LOG_JUMP = 8


def _ensure_barniva_workspace_table() -> None:
	try:
		from models import BarnivaSchemaWorkspace, BarnivaSchemaWorkspaceVersion, db

		BarnivaSchemaWorkspace.__table__.create(db.engine, checkfirst=True)
		BarnivaSchemaWorkspaceVersion.__table__.create(db.engine, checkfirst=True)
	except Exception as e:
		print(f"WARNING barniva workspace table: {e}")


def _barniva_actor() -> tuple[int | None, str]:
	uid = session.get("user_id")
	username = (session.get("username") or "").strip()
	display = ""
	try:
		from models import User

		if uid:
			user = User.query.get(int(uid))
			if user:
				display = (getattr(user, "display_name", None) or "").strip()
				username = username or (user.username or "").strip()
	except Exception:
		pass
	label = display or username or "Okänd"
	try:
		return (int(uid) if uid is not None else None, label)
	except Exception:
		return (None, label)


def _payload_stats(payload: dict) -> tuple[int, int]:
	result = payload.get("result") if isinstance(payload, dict) else None
	weeks = (result or {}).get("weeks") if isinstance(result, dict) else None
	if not isinstance(weeks, list):
		return 0, 0
	edit_logs = 0
	for w in weeks:
		if not isinstance(w, dict):
			continue
		log = w.get("editLog") or []
		if isinstance(log, list):
			edit_logs += len(log)
	return len(weeks), edit_logs


def _workspace_payload_dict(row) -> dict:
	import json as _json

	try:
		data = _json.loads(row.payload_json or "{}")
	except Exception:
		data = {}
	if not isinstance(data, dict):
		data = {}
	week_count, edit_log_count = _payload_stats(data)
	return {
		"kind": row.kind,
		"version": int(row.version or 1),
		"updatedAt": row.updated_at.isoformat() + "Z" if row.updated_at else None,
		"updatedBy": row.updated_by_username or None,
		"fileName": data.get("fileName"),
		"result": data.get("result"),
		"selectedWeek": data.get("selectedWeek"),
		"draftsByWeek": data.get("draftsByWeek") or {},
		"weekCount": week_count,
		"editLogCount": edit_log_count,
	}


def _snapshot_workspace_row(
	row,
	*,
	note: str | None = None,
	force_snapshot: bool = False,
) -> bool:
	"""Store current workspace as a restore point before overwrite.

	Routine autosaves are throttled so the history list stays usable.
	Always snapshots when force_snapshot=True (force-write, restore, etc.).
	"""
	import json as _json
	from datetime import datetime

	from models import BarnivaSchemaWorkspaceVersion, db

	try:
		payload = _json.loads(row.payload_json or "{}")
	except Exception:
		payload = {}
	if not isinstance(payload, dict):
		payload = {}
	week_count, edit_log_count = _payload_stats(payload)
	# Skip empty shells
	if week_count <= 0 and edit_log_count <= 0:
		return False

	if not force_snapshot:
		latest = (
			BarnivaSchemaWorkspaceVersion.query.filter_by(kind=row.kind)
			.order_by(
				BarnivaSchemaWorkspaceVersion.saved_at.desc(),
				BarnivaSchemaWorkspaceVersion.id.desc(),
			)
			.first()
		)
		if latest is not None and latest.saved_at is not None:
			age = (datetime.utcnow() - latest.saved_at).total_seconds()
			log_jump = edit_log_count - int(latest.edit_log_count or 0)
			routine = not note or note.startswith("Autospar")
			if (
				routine
				and age < _BARNIVA_SNAPSHOT_COOLDOWN_SEC
				and log_jump < _BARNIVA_SNAPSHOT_LOG_JUMP
			):
				return False

	snap = BarnivaSchemaWorkspaceVersion(
		kind=row.kind,
		version=int(row.version or 1),
		payload_json=row.payload_json or "{}",
		saved_at=datetime.utcnow(),
		saved_by_user_id=row.updated_by_user_id,
		saved_by_username=row.updated_by_username,
		note=note,
		edit_log_count=edit_log_count,
		week_count=week_count,
	)
	db.session.add(snap)
	db.session.flush()
	# Keep last N snapshots per kind
	old = (
		BarnivaSchemaWorkspaceVersion.query.filter_by(kind=row.kind)
		.order_by(
			BarnivaSchemaWorkspaceVersion.saved_at.desc(),
			BarnivaSchemaWorkspaceVersion.id.desc(),
		)
		.offset(_BARNIVA_VERSION_KEEP)
		.all()
	)
	for o in old:
		db.session.delete(o)
	return True


@bp.get("/api/barniva/session")
def api_barniva_session():
	denied = require_ops_tools_api()
	if denied:
		return denied
	uid = int(session["user_id"])
	_uid, label = _barniva_actor()
	return jsonify({
		"success": True,
		"userId": _uid,
		"username": (session.get("username") or "").strip(),
		"displayName": label,
	})


@bp.get("/api/barniva/workspace/<kind>")
def api_barniva_workspace_get(kind: str):
	denied = require_ops_tools_api()
	if denied:
		return denied
	uid = int(session["user_id"])
	kind_u = (kind or "").strip().upper()
	if kind_u not in ("SSK", "USK"):
		return jsonify({"error": "Invalid kind"}), 400
	_ensure_barniva_workspace_table()
	from models import BarnivaSchemaWorkspace

	row = BarnivaSchemaWorkspace.query.get(kind_u)
	if not row or not (row.payload_json or "").strip():
		return jsonify({"success": True, "workspace": None})
	return jsonify({"success": True, "workspace": _workspace_payload_dict(row)})


@bp.get("/api/barniva/workspace/<kind>/summary")
def api_barniva_workspace_summary(kind: str):
	"""Lightweight health check: weeks + edit-log counts without full payload."""
	denied = require_ops_tools_api()
	if denied:
		return denied
	uid = int(session["user_id"])
	kind_u = (kind or "").strip().upper()
	if kind_u not in ("SSK", "USK"):
		return jsonify({"error": "Invalid kind"}), 400
	_ensure_barniva_workspace_table()
	from models import BarnivaSchemaWorkspace

	row = BarnivaSchemaWorkspace.query.get(kind_u)
	if not row:
		return jsonify({
			"success": True,
			"kind": kind_u,
			"exists": False,
			"weekCount": 0,
			"editLogCount": 0,
			"version": None,
			"updatedBy": None,
			"updatedAt": None,
		})
	ws = _workspace_payload_dict(row)
	return jsonify({
		"success": True,
		"kind": kind_u,
		"exists": True,
		"weekCount": ws["weekCount"],
		"editLogCount": ws["editLogCount"],
		"version": ws["version"],
		"updatedBy": ws["updatedBy"],
		"updatedAt": ws["updatedAt"],
		"fileName": ws.get("fileName"),
	})


@bp.get("/api/barniva/workspace/<kind>/versions")
def api_barniva_workspace_versions(kind: str):
	denied = require_ops_tools_api()
	if denied:
		return denied
	uid = int(session["user_id"])
	kind_u = (kind or "").strip().upper()
	if kind_u not in ("SSK", "USK"):
		return jsonify({"error": "Invalid kind"}), 400
	_ensure_barniva_workspace_table()
	from models import BarnivaSchemaWorkspaceVersion

	rows = (
		BarnivaSchemaWorkspaceVersion.query.filter_by(kind=kind_u)
		.order_by(
			BarnivaSchemaWorkspaceVersion.saved_at.desc(),
			BarnivaSchemaWorkspaceVersion.id.desc(),
		)
		.limit(_BARNIVA_VERSION_KEEP)
		.all()
	)
	# Collapse rapid autosave spam so the UI stays readable.
	filtered: list = []
	last_at = None
	last_logs = None
	for r in rows:
		note = (r.note or "").strip()
		important = note.startswith("Före") or "force" in note.lower()
		if important or last_at is None or r.saved_at is None:
			filtered.append(r)
			last_at = r.saved_at
			last_logs = int(r.edit_log_count or 0)
			continue
		age = (last_at - r.saved_at).total_seconds() if last_at else 0
		log_diff = abs(int(r.edit_log_count or 0) - int(last_logs or 0))
		if age >= _BARNIVA_SNAPSHOT_COOLDOWN_SEC or log_diff >= _BARNIVA_SNAPSHOT_LOG_JUMP:
			filtered.append(r)
			last_at = r.saved_at
			last_logs = int(r.edit_log_count or 0)
	return jsonify({
		"success": True,
		"versions": [
			{
				"id": r.id,
				"kind": r.kind,
				"version": r.version,
				"savedAt": r.saved_at.isoformat() + "Z" if r.saved_at else None,
				"savedBy": r.saved_by_username,
				"note": r.note,
				"weekCount": r.week_count,
				"editLogCount": r.edit_log_count,
			}
			for r in filtered
		],
	})


@bp.post("/api/barniva/workspace/<kind>/restore/<int:version_id>")
def api_barniva_workspace_restore(kind: str, version_id: int):
	denied = require_ops_tools_api()
	if denied:
		return denied
	uid = int(session["user_id"])
	kind_u = (kind or "").strip().upper()
	if kind_u not in ("SSK", "USK"):
		return jsonify({"error": "Invalid kind"}), 400
	_ensure_barniva_workspace_table()
	from models import BarnivaSchemaWorkspace, BarnivaSchemaWorkspaceVersion, db
	from datetime import datetime

	snap = BarnivaSchemaWorkspaceVersion.query.get(version_id)
	if not snap or snap.kind != kind_u:
		return jsonify({"error": "Version hittades inte"}), 404

	actor_id, actor_label = _barniva_actor()
	row = BarnivaSchemaWorkspace.query.get(kind_u)
	if row is not None:
		_snapshot_workspace_row(
			row,
			note=f"Före återställning till snapshot #{snap.id}",
			force_snapshot=True,
		)
		row.payload_json = snap.payload_json
		row.version = int(row.version or 1) + 1
		row.updated_at = datetime.utcnow()
		row.updated_by_user_id = actor_id
		row.updated_by_username = actor_label
	else:
		row = BarnivaSchemaWorkspace(
			kind=kind_u,
			payload_json=snap.payload_json,
			version=1,
			updated_at=datetime.utcnow(),
			updated_by_user_id=actor_id,
			updated_by_username=actor_label,
		)
		db.session.add(row)
	db.session.commit()
	return jsonify({
		"success": True,
		"workspace": _workspace_payload_dict(row),
		"restoredFrom": snap.id,
	})


@bp.put("/api/barniva/workspace/<kind>")
def api_barniva_workspace_put(kind: str):
	denied = require_ops_tools_api()
	if denied:
		return denied
	uid = int(session["user_id"])
	kind_u = (kind or "").strip().upper()
	if kind_u not in ("SSK", "USK"):
		return jsonify({"error": "Invalid kind"}), 400
	_ensure_barniva_workspace_table()
	from models import BarnivaSchemaWorkspace, db

	data = request.get_json(silent=True) or {}
	result = data.get("result")
	if not isinstance(result, dict) or not isinstance(result.get("weeks"), list):
		return jsonify({"error": "Missing result.weeks"}), 400

	client_version = data.get("version")
	try:
		client_version = int(client_version) if client_version is not None else None
	except Exception:
		client_version = None

	force = bool(data.get("force"))
	actor_id, actor_label = _barniva_actor()

	import json as _json
	from datetime import datetime

	payload = {
		"fileName": data.get("fileName"),
		"result": result,
		"selectedWeek": data.get("selectedWeek"),
		"draftsByWeek": data.get("draftsByWeek") or {},
	}

	row = BarnivaSchemaWorkspace.query.get(kind_u)
	if row is None:
		row = BarnivaSchemaWorkspace(
			kind=kind_u,
			payload_json=_json.dumps(payload, ensure_ascii=False),
			version=1,
			updated_at=datetime.utcnow(),
			updated_by_user_id=actor_id,
			updated_by_username=actor_label,
		)
		db.session.add(row)
		db.session.commit()
		return jsonify({"success": True, "workspace": _workspace_payload_dict(row)})

	if (
		client_version is not None
		and int(row.version or 1) != client_version
		and not force
	):
		return jsonify({
			"success": False,
			"conflict": True,
			"error": "Version conflict — någon annan har sparat.",
			"workspace": _workspace_payload_dict(row),
		}), 409

	# Snapshot before overwrite — always on force; throttled for routine autosave
	try:
		_snapshot_workspace_row(
			row,
			note=("Före force-skrivning" if force else "Autospar / uppdatering"),
			force_snapshot=bool(force),
		)

		row.payload_json = _json.dumps(payload, ensure_ascii=False)
		row.version = int(row.version or 1) + 1
		row.updated_at = datetime.utcnow()
		row.updated_by_user_id = actor_id
		row.updated_by_username = actor_label
		db.session.commit()
		return jsonify({"success": True, "workspace": _workspace_payload_dict(row)})
	except Exception as e:
		db.session.rollback()
		print(f"ERROR barniva workspace put {kind_u}: {e}")
		return jsonify({"error": "Kunde inte spara workspace"}), 500


# -------------------------------------------------
# SEO: robots / sitemap / tippa-landing / om / manual
# -------------------------------------------------

@bp.get("/robots.txt")
def robots_txt():
	"""Tell search engines which pages to crawl."""
	from public_url import get_public_base_url

	base = get_public_base_url()
	body = (
		"User-agent: *\n"
		"Allow: /\n"
		"Disallow: /admin\n"
		"Disallow: /api/\n"
		f"Sitemap: {base}/sitemap.xml\n"
		f"# AI agents: {base}/llms.txt\n"
	)
	resp = make_response(body)
	resp.headers["Content-Type"] = "text/plain; charset=utf-8"
	return resp


@bp.get("/llms.txt")
def llms_txt():
	"""Curated reading list for AI agents (optional; complements sitemap)."""
	from public_url import get_public_base_url
	from services.seo_tippa import _llms_txt_body

	resp = make_response(_llms_txt_body(get_public_base_url()))
	resp.headers["Content-Type"] = "text/plain; charset=utf-8"
	return resp


@bp.get("/sitemap.xml")
def sitemap_xml():
	"""Sitemap with public pages for Google."""
	from datetime import date as _date

	from public_url import get_public_base_url

	base = get_public_base_url()
	today = _date.today().isoformat()
	urls = [
		("/", "weekly", "1.0"),
		("/om", "weekly", "0.95"),
		("/tippa-supercross", "weekly", "0.9"),
		("/tippa-motocross", "weekly", "0.9"),
		("/tippa-smx", "weekly", "0.9"),
		("/tippa-wsx", "weekly", "0.9"),
		("/tippa-mxgp", "weekly", "0.9"),
		("/tippa-mxon", "weekly", "0.9"),
		("/start", "weekly", "0.9"),
		("/manual", "monthly", "0.85"),
		("/llms.txt", "monthly", "0.4"),
		("/register", "monthly", "0.7"),
		("/login", "monthly", "0.5"),
		("/privacy", "yearly", "0.3"),
		("/terms", "yearly", "0.3"),
		("/contact", "yearly", "0.4"),
	]
	parts = [
		'<?xml version="1.0" encoding="UTF-8"?>',
		'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
	]
	for path, freq, prio in urls:
		parts.append("  <url>")
		parts.append(f"    <loc>{base}{path}</loc>")
		parts.append(f"    <lastmod>{today}</lastmod>")
		parts.append(f"    <changefreq>{freq}</changefreq>")
		parts.append(f"    <priority>{prio}</priority>")
		parts.append("  </url>")
	parts.append("</urlset>")
	resp = make_response("\n".join(parts) + "\n")
	resp.headers["Content-Type"] = "application/xml; charset=utf-8"
	return resp


@bp.get("/om")
def about_game_page():
	"""SEO landing: vad spelet är, hur det funkar, FAQ (svenska)."""
	return render_template("om_spelet.html")


@bp.route("/manual")
def manual_page():
	"""Manual page for the game."""
	is_logged_in = "user_id" in session
	username = session.get("username", "Gäst") if is_logged_in else "Gäst"
	return render_template("manual.html", is_logged_in=is_logged_in, username=username)


@bp.get("/tippa-supercross")
def tippa_supercross_page():
	"""SEO: hur man tippar Supercross / fantasy SX."""
	from services.seo_tippa import _tippa_supercross_page_data

	return render_template("tippa_serie.html", page=_tippa_supercross_page_data())


@bp.get("/tippa-motocross")
def tippa_motocross_page():
	"""SEO: hur man tippar motocross / fantasy MX."""
	from services.seo_tippa import _tippa_motocross_page_data

	return render_template("tippa_serie.html", page=_tippa_motocross_page_data())


@bp.get("/tippa-smx")
def tippa_smx_page():
	"""SEO: hur man tippar SMX / SuperMotocross."""
	from services.seo_tippa import _tippa_smx_page_data

	return render_template("tippa_serie.html", page=_tippa_smx_page_data())


@bp.get("/tippa-wsx")
def tippa_wsx_page():
	"""SEO: hur man tippar WSX / World Supercross."""
	from services.seo_tippa import _tippa_wsx_page_data

	return render_template("tippa_serie.html", page=_tippa_wsx_page_data())


@bp.get("/tippa-mxgp")
def tippa_mxgp_page():
	"""SEO: hur man tippar MXGP / FIM Motocross World Championship."""
	from services.seo_tippa import _tippa_mxgp_page_data

	return render_template("tippa_serie.html", page=_tippa_mxgp_page_data())


@bp.get("/tippa-mxon")
def tippa_mxon_page():
	"""SEO: hur man tippar MXoN / Motocross of Nations."""
	from services.seo_tippa import _tippa_mxon_page_data

	return render_template("tippa_serie.html", page=_tippa_mxon_page_data())

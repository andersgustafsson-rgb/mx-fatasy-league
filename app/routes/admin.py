from __future__ import annotations

import os
import traceback
from datetime import date, datetime, timedelta
from functools import wraps

from flask import (
	Blueprint,
	current_app,
	jsonify,
	redirect,
	render_template,
	request,
	Response,
	session,
	url_for,
)

from models import (
	db,
	Competition,
	CompetitionResult,
	HoleshotPick,
	PicksSnapshot,
	RacePick,
	Rider,
	SeasonTeamClassPromotion,
	SeasonTeamRider,
	User,
	WildcardPick,
)

bp = Blueprint('admin', __name__, url_prefix='')  # keep same absolute paths


# Minimal copies of helpers to avoid circular imports with main.py

def get_today() -> date:
	return date.today()


def is_admin_user() -> bool:
	username = session.get("username")
	if not username:
		return False
	try:
		user = User.query.filter_by(username=username).first()
		if user and hasattr(user, 'is_admin') and user.is_admin:
			return True
	except Exception:
		pass
	return username == "test"


def login_required(f):
	@wraps(f)
	def decorated_function(*args, **kwargs):
		if "user_id" not in session:
			return redirect(url_for("login"))
		# session timeout handling (match main.py)
		if "login_time" in session:
			try:
				login_time = datetime.fromisoformat(session["login_time"])
				if datetime.utcnow() - login_time > timedelta(hours=24):
					session.clear()
					return redirect(url_for("login"))
			except Exception:
				pass
		return f(*args, **kwargs)
	return decorated_function


@bp.route("/admin/social-recap")
@login_required
def social_recap_page():
	if not is_admin_user():
		return redirect(url_for("index"))
	return render_template("admin_social_recap.html")


@bp.get("/admin/api/social-recap")
@login_required
def social_recap_api():
	if not is_admin_user():
		return jsonify({"error": "Unauthorized"}), 401
	comp_id = request.args.get("competition_id", type=int)
	if not comp_id:
		return jsonify({"error": "competition_id_required"}), 400
	race_top = request.args.get("race_top", default=3, type=int)
	season_top = request.args.get("season_top", default=5, type=int)
	include_race = request.args.get("include_race", "1") not in ("0", "false", "no")
	include_weekly = request.args.get("include_weekly", "1") not in ("0", "false", "no")
	include_season_snippet = request.args.get("include_season_snippet", "1") not in (
		"0",
		"false",
		"no",
	)
	include_facts = request.args.get("include_facts", "1") not in ("0", "false", "no")
	include_rider_podium = request.args.get("include_rider_podium", "1") not in ("0", "false", "no")
	# Bakåtkompatibilitet
	if request.args.get("include_season", "1") in ("0", "false", "no"):
		include_season_snippet = False
	if request.args.get("include_weekly") is None and request.args.get("include_season") == "1":
		include_weekly = True
	try:
		from social_recap_service import build_social_recap_data

		data = build_social_recap_data(
			comp_id,
			race_top=race_top,
			season_top=season_top,
			include_race=include_race,
			include_weekly=include_weekly,
			include_season_snippet=include_season_snippet,
			include_facts=include_facts,
			include_rider_podium=include_rider_podium,
		)
		layout = request.args.get("layout", "facebook")
		if layout == "feed":
			layout = "facebook"
		data["export_dual"] = layout == "facebook"
		return jsonify(data)
	except ValueError as e:
		return jsonify({"error": str(e)}), 404
	except Exception as e:
		current_app.logger.exception("social_recap_api failed: %s", e)
		payload = {"error": str(e) or type(e).__name__, "error_type": type(e).__name__}
		if (os.getenv("ADMIN_API_TRACEBACK", "") or "").strip().lower() in ("1", "true", "yes"):
			payload["traceback"] = traceback.format_exc()
		return jsonify(payload), 500


@bp.get("/admin/api/social-recap.png")
@login_required
def social_recap_png():
	if not is_admin_user():
		return jsonify({"error": "Unauthorized"}), 401
	comp_id = request.args.get("competition_id", type=int)
	if not comp_id:
		return jsonify({"error": "competition_id_required"}), 400
	race_top = request.args.get("race_top", default=3, type=int)
	season_top = request.args.get("season_top", default=5, type=int)
	include_race = request.args.get("include_race", "1") not in ("0", "false", "no")
	include_weekly = request.args.get("include_weekly", "1") not in ("0", "false", "no")
	include_season_snippet = request.args.get("include_season_snippet", "1") not in (
		"0",
		"false",
		"no",
	)
	include_facts = request.args.get("include_facts", "1") not in ("0", "false", "no")
	include_rider_podium = request.args.get("include_rider_podium", "1") not in ("0", "false", "no")
	if request.args.get("include_season", "1") in ("0", "false", "no"):
		include_season_snippet = False
	layout = request.args.get("layout", "facebook")
	if layout == "feed":
		layout = "facebook"
	if layout not in ("facebook", "portrait", "story"):
		layout = "facebook"
	try:
		from social_recap_service import build_social_recap_data, render_social_recap_png

		data = build_social_recap_data(
			comp_id,
			race_top=race_top,
			season_top=season_top,
			include_race=include_race,
			include_weekly=include_weekly,
			include_season_snippet=include_season_snippet,
			include_facts=include_facts,
			include_rider_podium=include_rider_podium,
		)
		data["layout"] = layout
		part = request.args.get("part", "graphic")
		if layout != "facebook":
			part = "graphic"
		png_bytes = render_social_recap_png(data, layout=layout, part=part)
		resp = Response(png_bytes, mimetype="image/png")
		resp.headers["Cache-Control"] = "no-store, max-age=0, must-revalidate"
		return resp
	except ValueError as e:
		return jsonify({"error": str(e)}), 404
	except Exception as e:
		current_app.logger.exception("social_recap_png failed: %s", e)
		payload = {"error": str(e) or type(e).__name__, "error_type": type(e).__name__}
		if (os.getenv("ADMIN_API_TRACEBACK", "") or "").strip().lower() in ("1", "true", "yes"):
			payload["traceback"] = traceback.format_exc()
		return jsonify(payload), 500


@bp.route("/admin")
@login_required
def admin_page():
	if not is_admin_user():
		return redirect(url_for("index"))
	try:
		# fetch minimal data if needed by template; current template loads via APIs
		_ = Competition.query.order_by(Competition.event_date).first()
		return render_template("admin_organized.html")
	except Exception as e:
		return f"<h1>Database Error</h1><p>{e}</p>"


@bp.route('/competition_management')
@login_required
def competition_management():
	if not is_admin_user():
		return redirect(url_for("index"))
	return render_template("competition_management.html")


@bp.route('/rider_management')
@login_required
def rider_management():
	if not is_admin_user():
		return redirect(url_for("index"))
	try:
		# SMX förare: alla 450cc och 250cc (oavsett coast_250)
		riders_smx = Rider.query.filter(
			Rider.class_name.in_(['450cc', '250cc'])
		).order_by(Rider.class_name, Rider.rider_number).all()
		
		# WSX förare: alla wsx_sx1 och wsx_sx2
		riders_wsx = Rider.query.filter(
			Rider.class_name.in_(['wsx_sx1', 'wsx_sx2'])
		).order_by(Rider.class_name, Rider.rider_number).all()
		
		return render_template('rider_management.html',
							riders_smx=riders_smx,
							riders_wsx=riders_wsx)
	except Exception as e:
		return f"<h1>Database Error</h1><p>{e}</p>"


@bp.route('/rider_management/bulk_update_numbers', methods=['POST'])
@login_required
def bulk_update_rider_numbers():
	"""Bulk update rider numbers for SMX riders"""
	if not is_admin_user():
		return jsonify({'error': 'Unauthorized'}), 401
	
	try:
		# New rider numbers mapping (from user's list - only those without *)
		NEW_NUMBERS = {
			"Seth Hammaker": 10,
			"Julien Beaumer": 13,
			"Maximus Vohland": 19,
			"Jordon Smith": 20,
			"Coty Schock": 22,
			"Michael Mosiman": 23,
			"Nate Thrasher": 25,
			"Jorge Prado": 26,
			"Chance Hymas": 29,
			"Mikkel Haarup": 31,
			"Austin Forkner": 33,
			"Ryder DiFrancesco": 34,
			"Drew Adams": 35,
			"Garrett Marchbanks": 36,
			"Cole Davies": 37,
			"Valentin Guillod": 39,
			"Parker Ross": 40,
			"Mitchell Harrison": 41,
			"Dilan Schwartz": 42,
			"Lux Turner": 43,
			"Ty Masterpool": 44,
			"Harri Kullas": 48,
			"Cullin Park": 49,
			"Lorenzo Locurcio": 50,
			"Mitchell Oldenburg": 52,
			"Henry Miller": 53,
			"Benny Bloss": 54,
			"Benoit Paturel": 55,
			"Jalek Swoll": 56,
			"Avery Long": 57,
			"Daxton Bennick": 58,
			"Casey Cochran": 59,
			"Hunter Yoder": 60,
			"Max Anstie": 61,
			"Grant Harlan": 62,
			"Fredrik Noren": 63,
			"Romain Pape": 64,
			"Marshal Weltin": 65,
			"Cole Thompson": 66,
			"Hardy Munoz": 67,
			"Enzo Lopes": 68,
			"Jack Chambers": 69,
			"Anthony Bourdon": 70,
			"Carson Mumford": 71,
			"Trevor Colip": 72,
			"Gavin Towers": 73,
			"Gage Linville": 74,
			"Lance Kobusch": 75,
			"Kyle Webster": 76,
			"Derek Kelley": 77,
			"Kevin Moranz": 78,
			"Dylan Walsh": 79,
			"Bryce Shelly": 80,
			"Jerry Robin": 81,
			"Caden Dudney": 82,
			"Justin Rodbell": 83,
			"TJ Albright": 84,
			"Alexander Fedortsov": 85,
			"Jett Reynolds": 86,
			"Jeremy Hand": 87,
			"Mark Fineis": 88,
			"Devin Simonson": 89,
			"John Short": 90,
			"Izaih Clark": 91,
			"Enzo Temmerman": 92,
			"Antonio Cairoli": 93,
			"Luke Neese": 95,
			"Brad West": 97,
			"Derek Drake": 98,
			"Kayden Minear": 99,
		}
		
		# Get all SMX riders
		smx_riders = Rider.query.filter(
			Rider.class_name.in_(['450cc', '250cc'])
		).all()
		
		# Create mapping
		riders_by_name = {}
		for rider in smx_riders:
			if rider.name in NEW_NUMBERS:
				riders_by_name[rider.name] = rider
			else:
				# Case-insensitive match
				for name in NEW_NUMBERS.keys():
					if rider.name.lower() == name.lower():
						riders_by_name[name] = rider
						break
		
		# Find updates needed
		updates = []
		for name, new_number in NEW_NUMBERS.items():
			if name not in riders_by_name:
				continue
			rider = riders_by_name[name]
			if rider.rider_number != new_number:
				updates.append({
					'rider': rider,
					'current': rider.rider_number,
					'new': new_number
				})
		
		if not updates:
			return jsonify({'message': 'No riders need updates', 'updated': 0})
		
		# Check conflicts
		conflicts = []
		for update in updates:
			existing = Rider.query.filter_by(
				class_name=update['rider'].class_name,
				rider_number=update['new']
			).filter(Rider.id != update['rider'].id).first()
			
			if existing and not any(u['rider'].id == existing.id for u in updates):
				conflicts.append(update)
		
		# Use temporary numbers for conflicts
		temp_num = 9000
		for conflict in conflicts:
			conflict['rider'].rider_number = temp_num
			temp_num += 1
		
		if conflicts:
			db.session.commit()
		
		# Update all riders
		updated_count = 0
		for update in updates:
			update['rider'].rider_number = update['new']
			updated_count += 1
		
		db.session.commit()
		
		return jsonify({
			'success': True,
			'message': f'Updated {updated_count} rider numbers',
			'updated': updated_count,
			'conflicts_resolved': len(conflicts)
		})
		
	except Exception as e:
		db.session.rollback()
		import traceback
		traceback.print_exc()
		return jsonify({'error': str(e)}), 500


@bp.get("/admin/diagnostics/rider_recent_results")
@login_required
def admin_rider_recent_results():
	"""
	Admin: senaste resultat för en förare i en scope (t.ex. SX 250 West).
	Samma path som i main.py — behövs på Render där wsgi använder create_app().
	Exempel:
	  /admin/diagnostics/rider_recent_results?name=romano&series=SX&class=250cc&coast=west&limit=10
	"""
	if not is_admin_user():
		return jsonify({"error": "unauthorized"}), 401
	try:
		name_q = (request.args.get("name") or "").strip().lower()
		series = (request.args.get("series") or "SX").strip()
		class_name = (request.args.get("class") or "250cc").strip().lower()
		coast = (request.args.get("coast") or "west").strip().lower()
		limit = int(request.args.get("limit") or 8)
		limit = max(1, min(limit, 30))

		if not name_q:
			return jsonify({"error": "missing_name"}), 400

		rider = (
			Rider.query.filter(db.func.lower(Rider.name).like(f"%{name_q}%"))
			.filter(Rider.class_name == class_name)
			.first()
		)
		if not rider:
			return jsonify({"error": "rider_not_found"}), 404

		comp_q = Competition.query.filter(Competition.series == series).filter(Competition.event_date.isnot(None))
		if class_name == "250cc" and coast in ("east", "west"):
			# DB kan ha "West"/"west" — jämför case-insensitive
			comp_q = comp_q.filter(
				db.func.lower(db.func.trim(Competition.coast_250)) == coast
			)
		comps = comp_q.order_by(Competition.event_date.desc(), Competition.id.desc()).limit(limit).all()

		out = []
		for c in comps:
			res = CompetitionResult.query.filter_by(competition_id=c.id, rider_id=rider.id).first()
			out.append(
				{
					"competition_id": c.id,
					"competition_name": c.name,
					"event_date": c.event_date.isoformat() if c.event_date else None,
					"series": c.series,
					"coast_250": getattr(c, "coast_250", None),
					"position": int(res.position) if res and res.position is not None else None,
					"has_result_in_db": res is not None,
				}
			)

		with_pos = sum(1 for r in out if r.get("has_result_in_db"))

		return jsonify(
			{
				"rider": {
					"id": rider.id,
					"name": rider.name,
					"class": rider.class_name,
					"coast_250": rider.coast_250,
				},
				"filters": {"series": series, "class": class_name, "coast": coast, "limit": limit},
				"competition_count": len(comps),
				"with_result_count": with_pos,
				"result_count": with_pos,
				"results": out,
				"hint": (
					"Inga tävlingar matchade filter (kolla series/coast i DB)."
					if len(comps) == 0
					else (
						"Ingen CompetitionResult-rad för denna förare i dessa race — resultat saknas i DB eller fel rider_id."
						if with_pos == 0
						else None
					)
				),
			}
		)
	except Exception as e:
		return jsonify({"error": str(e)}), 500


@bp.get("/admin/diagnostics/db_fingerprint")
@login_required
def admin_db_fingerprint():
	"""
	Admin: visa vilken DB instansen faktiskt är kopplad mot (utan hemligheter).
	Använd för att verifiera att tjänsten kör på Frankfurt-DB efter migration.
	"""
	if not is_admin_user():
		return jsonify({"error": "unauthorized"}), 401
	try:
		# Generic SQLAlchemy engine URL (redacted)
		try:
			engine_url = str(db.engine.url)
			# SQLAlchemy already hides password in most str() representations, but be safe:
			engine_url = engine_url.replace(str(db.engine.url.password or ""), "***") if getattr(db.engine.url, "password", None) else engine_url
		except Exception:
			engine_url = None

		info = {"engine_url": engine_url}

		# Postgres-specific fingerprint
		try:
			row = db.session.execute(
				db.text(
					"select current_database() as db, inet_server_addr()::text as addr, inet_server_port() as port, version() as version"
				)
			).mappings().first()
			if row:
				info["postgres"] = dict(row)
		except Exception as e:
			info["postgres_error"] = str(e)

		return jsonify({"ok": True, "fingerprint": info})
	except Exception as e:
		return jsonify({"ok": False, "error": str(e)}), 500


@bp.get("/admin/diagnostics/picks_snapshots")
@login_required
def admin_picks_snapshots_diagnostics():
	"""
	Admin: verifiera att snapshots finns när picks är låsta.

	- GET /admin/diagnostics/picks_snapshots?competition_id=123
	- Lägg till &create_missing=1 för att skapa saknade snapshots (best-effort).
	"""
	if not is_admin_user():
		return jsonify({"error": "unauthorized"}), 401
	try:
		comp_id = int(request.args.get("competition_id") or 0)
		if comp_id <= 0:
			return jsonify({"error": "missing_competition_id"}), 400
		create_missing = str(request.args.get("create_missing") or "").strip() in ("1", "true", "yes")

		comp = Competition.query.get(comp_id)
		if not comp:
			return jsonify({"error": "competition_not_found"}), 404

		# Users with any picks (live tables)
		user_ids = set()
		user_ids.update(
			uid
			for (uid,) in db.session.query(RacePick.user_id)
			.filter(RacePick.competition_id == comp_id)
			.distinct()
			.all()
			if uid is not None
		)
		user_ids.update(
			uid
			for (uid,) in db.session.query(HoleshotPick.user_id)
			.filter(HoleshotPick.competition_id == comp_id)
			.distinct()
			.all()
			if uid is not None
		)
		user_ids.update(
			uid
			for (uid,) in db.session.query(WildcardPick.user_id)
			.filter(WildcardPick.competition_id == comp_id)
			.distinct()
			.all()
			if uid is not None
		)

		existing = {
			int(uid)
			for (uid,) in db.session.query(PicksSnapshot.user_id)
			.filter(PicksSnapshot.competition_id == comp_id)
			.all()
		}
		missing = sorted(int(uid) for uid in user_ids if int(uid) not in existing)

		created = 0
		create_errors: list[str] = []

		if create_missing and missing:
			import json

			for uid in missing:
				try:
					# Minimal snapshot payload (same shape as in main.py)
					rp = (
						RacePick.query.filter_by(user_id=uid, competition_id=comp_id)
						.order_by(RacePick.predicted_position.asc())
						.all()
					)
					race_picks = [
						{"rider_id": int(p.rider_id), "predicted_position": int(p.predicted_position)}
						for p in rp
						if p.rider_id is not None and p.predicted_position is not None
					]

					hp = HoleshotPick.query.filter_by(user_id=uid, competition_id=comp_id).all()
					holeshot_picks = {
						(str(p.class_name).strip() if p.class_name else ""): int(p.rider_id)
						for p in hp
						if p.rider_id is not None
					}
					holeshot_picks = {k: v for k, v in holeshot_picks.items() if k}

					wc = WildcardPick.query.filter_by(user_id=uid, competition_id=comp_id).first()
					payload = {
						"user_id": int(uid),
						"competition_id": int(comp_id),
						"race_picks": race_picks,
						"holeshot_picks": holeshot_picks,
						"wildcard_pick": int(wc.rider_id) if wc and wc.rider_id is not None else None,
						"wildcard_pos": int(wc.position) if wc and wc.position is not None else None,
					}

					db.session.add(
						PicksSnapshot(
							user_id=int(uid),
							competition_id=int(comp_id),
							payload_json=json.dumps(payload, ensure_ascii=False),
							source="admin_diagnostics",
						)
					)
					created += 1
				except Exception as e:
					create_errors.append(f"user_id={uid}: {e}")

			try:
				db.session.commit()
			except Exception as e:
				db.session.rollback()
				create_errors.append(f"commit_failed: {e}")
				created = 0

			# recompute missing after create
			existing2 = {
				int(uid)
				for (uid,) in db.session.query(PicksSnapshot.user_id)
				.filter(PicksSnapshot.competition_id == comp_id)
				.all()
			}
			missing = sorted(int(uid) for uid in user_ids if int(uid) not in existing2)

		return jsonify(
			{
				"ok": True,
				"competition": {"id": comp.id, "name": comp.name, "series": comp.series, "event_date": str(comp.event_date)},
				"users_with_any_live_picks": len(user_ids),
				"snapshots_existing": len(existing),
				"snapshots_missing": len(missing),
				"missing_user_ids": missing[:50],
				"created": created,
				"create_errors": create_errors[:20],
			}
		)
	except Exception as e:
		return jsonify({"ok": False, "error": str(e)}), 500


@bp.get("/admin/diagnostics/picks_snapshots_preview")
@login_required
def admin_picks_snapshots_preview():
	"""
	Admin: visa snapshot-innehåll (summerat) för att verifiera att inga picks "försvunnit".

	- GET /admin/diagnostics/picks_snapshots_preview?competition_id=123
	- Valfritt: &limit=20
	"""
	if not is_admin_user():
		return jsonify({"error": "unauthorized"}), 401
	try:
		import json

		comp_id = int(request.args.get("competition_id") or 0)
		if comp_id <= 0:
			return jsonify({"error": "missing_competition_id"}), 400

		limit = int(request.args.get("limit") or 20)
		limit = max(1, min(limit, 200))

		comp = Competition.query.get(comp_id)
		if not comp:
			return jsonify({"error": "competition_not_found"}), 404

		rows = (
			PicksSnapshot.query.filter_by(competition_id=comp_id)
			.order_by(PicksSnapshot.created_at.desc())
			.limit(limit)
			.all()
		)

		previews = []
		for s in rows:
			try:
				payload = json.loads(s.payload_json or "{}")
			except Exception:
				payload = {}

			user = User.query.get(int(s.user_id)) if s.user_id is not None else None
			username = user.username if user else None

			race_picks = payload.get("race_picks") or []
			holeshot_picks = payload.get("holeshot_picks") or {}
			wildcard_pick = payload.get("wildcard_pick", None)
			wildcard_pos = payload.get("wildcard_pos", None)

			previews.append(
				{
					"user_id": int(s.user_id),
					"username": username,
					"snapshot_id": int(s.id),
					"created_at": (s.created_at.isoformat() if getattr(s, "created_at", None) else None),
					"source": getattr(s, "source", None),
					"counts": {
						"race_picks": (len(race_picks) if isinstance(race_picks, list) else None),
						"holeshot_picks": (len(holeshot_picks) if isinstance(holeshot_picks, dict) else None),
						"has_wildcard": (wildcard_pick is not None),
					},
					"wildcard": {"rider_id": wildcard_pick, "position": wildcard_pos},
				}
			)

		return jsonify(
			{
				"ok": True,
				"competition": {"id": comp.id, "name": comp.name, "series": comp.series, "event_date": str(comp.event_date)},
				"limit": limit,
				"snapshots_returned": len(previews),
				"previews": previews,
			}
		)
	except Exception as e:
		return jsonify({"ok": False, "error": str(e)}), 500


def _rider_option(r: Rider) -> dict:
	return {
		"id": r.id,
		"name": r.name,
		"class_name": r.class_name,
		"rider_number": r.rider_number,
		"bike_brand": r.bike_brand,
	}


@bp.route("/rider_management/class_promotions", methods=["GET"])
@login_required
def list_class_promotions():
	"""Lista MX-klassbyten (gratis säsongsteam-byte) + förare för dropdown."""
	if not is_admin_user():
		return jsonify({"error": "Unauthorized"}), 401
	from season_team_promotions import ensure_promotions_table

	ensure_promotions_table()
	promotions = []
	for row in (
		SeasonTeamClassPromotion.query.order_by(
			SeasonTeamClassPromotion.created_at.desc()
		).all()
	):
		fr = Rider.query.get(row.from_rider_id)
		tr = Rider.query.get(row.to_rider_id)
		teams = SeasonTeamRider.query.filter_by(rider_id=row.from_rider_id).count()
		promotions.append(
			{
				"id": row.id,
				"from_rider_id": row.from_rider_id,
				"to_rider_id": row.to_rider_id,
				"from_name": fr.name if fr else f"ID {row.from_rider_id}",
				"from_number": fr.rider_number if fr else None,
				"from_class": fr.class_name if fr else "250cc",
				"to_name": tr.name if tr else f"ID {row.to_rider_id}",
				"to_number": tr.rider_number if tr else None,
				"to_class": tr.class_name if tr else "450cc",
				"is_active": row.is_active,
				"note": row.note,
				"teams_with_from": teams,
				"teams_with_250": teams,
				"created_at": row.created_at.isoformat() if row.created_at else None,
			}
		)

	riders_250 = Rider.query.filter_by(class_name="250cc").order_by(Rider.name).all()
	riders_450 = Rider.query.filter_by(class_name="450cc").order_by(Rider.name).all()
	return jsonify(
		{
			"promotions": promotions,
			"riders_250": [_rider_option(r) for r in riders_250],
			"riders_450": [_rider_option(r) for r in riders_450],
		}
	)


@bp.route("/rider_management/class_promotions/setup", methods=["POST"])
@login_required
def setup_class_promotion():
	"""
	Aktivera MX-klassbyte: koppla gammal klass → ny klass och uppdatera startnummer i målklassen.
	JSON: from_rider_id, new_number (eller new_450_number), to_rider_id (valfritt), note (valfritt)
	"""
	if not is_admin_user():
		return jsonify({"error": "Unauthorized"}), 401

	from season_team_promotions import ensure_promotions_table

	ensure_promotions_table()
	data = request.get_json(silent=True) or {}
	try:
		from_rider_id = int(data.get("from_rider_id"))
		raw_num = data.get("new_number", data.get("new_450_number"))
		new_number = int(raw_num)
	except (TypeError, ValueError):
		return jsonify({"error": "from_rider_id och new_number krävs"}), 400

	to_rider_id = data.get("to_rider_id")
	note = (data.get("note") or "").strip() or None

	from_rider = Rider.query.get(from_rider_id)
	if not from_rider:
		return jsonify({"error": "Föraren (gammal klass) hittades inte"}), 404
	if from_rider.class_name not in ("250cc", "450cc"):
		return jsonify({"error": "from_rider_id måste vara 250cc eller 450cc"}), 400

	target_class = "450cc" if from_rider.class_name == "250cc" else "250cc"
	from_short = "250" if from_rider.class_name == "250cc" else "450"
	to_short = "450" if target_class == "450cc" else "250"

	if to_rider_id:
		try:
			to_rider_id = int(to_rider_id)
		except (TypeError, ValueError):
			return jsonify({"error": "Ogiltigt to_rider_id"}), 400
		to_rider = Rider.query.get(to_rider_id)
	else:
		to_rider = (
			Rider.query.filter(
				Rider.name.ilike(from_rider.name.strip()),
				Rider.class_name == target_class,
			)
			.order_by(Rider.id.desc())
			.first()
		)

	if not to_rider:
		return jsonify(
			{
				"error": (
					f"Ingen {to_short}-förare hittades med samma namn. "
					f"Skapa {to_short}-raden först under förarlistan."
				)
			}
		), 400
	if to_rider.class_name != target_class:
		return jsonify({"error": f"to_rider_id måste vara {target_class}"}), 400
	if to_rider.class_name == from_rider.class_name:
		return jsonify({"error": "Från- och till-förare måste vara olika klasser"}), 400

	conflict = (
		Rider.query.filter_by(class_name=target_class, rider_number=new_number)
		.filter(Rider.id != to_rider.id)
		.first()
	)
	if conflict:
		return jsonify(
			{
				"error": "nummer_upptaget",
				"message": (
					f"#{new_number} i {to_short} är redan {conflict.name}. "
					"Byt nummer på den föraren först."
				),
				"existing_rider_id": conflict.id,
				"existing_rider_name": conflict.name,
			}
		), 409

	old_to_number = to_rider.rider_number
	to_rider.rider_number = new_number

	row = SeasonTeamClassPromotion.query.filter_by(from_rider_id=from_rider_id).first()
	if not row:
		row = SeasonTeamClassPromotion(
			from_rider_id=from_rider_id,
			to_rider_id=to_rider.id,
			is_active=True,
			note=note,
		)
		db.session.add(row)
	else:
		row.to_rider_id = to_rider.id
		row.is_active = True
		row.note = note

	db.session.commit()
	teams = SeasonTeamRider.query.filter_by(rider_id=from_rider_id).count()
	return jsonify(
		{
			"success": True,
			"message": (
				f"Klassbyte aktivt: {from_rider.name} "
				f"(#{from_rider.rider_number} {from_short}) → "
				f"{to_rider.name} (#{old_to_number} → #{new_number} {to_short}). "
				f"{teams} säsongsteam har fortfarande {from_short}-versionen (gratis byte)."
			),
			"promotion_id": row.id,
			"teams_with_from": teams,
			"teams_with_250": teams,
		}
	)


@bp.route("/rider_management/class_promotions/<int:promo_id>", methods=["PATCH", "DELETE"])
@login_required
def manage_class_promotion(promo_id: int):
	if not is_admin_user():
		return jsonify({"error": "Unauthorized"}), 401
	from season_team_promotions import ensure_promotions_table

	ensure_promotions_table()
	row = SeasonTeamClassPromotion.query.get_or_404(promo_id)

	if request.method == "DELETE":
		db.session.delete(row)
		db.session.commit()
		return jsonify({"success": True, "message": "Klassbyte borttaget"})

	data = request.get_json(silent=True) or {}
	if "is_active" in data:
		row.is_active = bool(data["is_active"])
	if "note" in data:
		row.note = (data.get("note") or "").strip() or None
	db.session.commit()
	return jsonify({"success": True, "is_active": row.is_active})


def _entry_list_payload() -> tuple[str, str, str | None, bool, int, bool, bool, bool, bool]:
	data = request.get_json(silent=True) or {}
	text = (data.get("text") or "").strip()
	class_name = (data.get("class_name") or "250cc").strip()
	coast_raw = data.get("coast_250")
	coast_250 = (coast_raw or "").strip() or None
	if coast_250 not in ("west", "east"):
		coast_250 = None
	only_marked_new = bool(data.get("only_marked_new"))
	default_price = int(data.get("default_price") or 100_000)
	add_new = bool(data.get("add_new", False))
	update_numbers = bool(data.get("update_numbers", False))
	confirm_season_active = bool(data.get("confirm_season_active", False))
	allow_cross_class_create = bool(data.get("allow_cross_class_create", False))
	return (
		text,
		class_name,
		coast_250,
		only_marked_new,
		default_price,
		add_new,
		update_numbers,
		confirm_season_active,
		allow_cross_class_create,
	)


def _entry_list_season_active() -> bool:
	try:
		from main import is_season_active
		return bool(is_season_active())
	except Exception:
		return False


def _parse_and_diff_entry_list(
	text: str,
	class_name: str,
	coast_250: str | None,
	only_marked_new: bool,
):
	from entry_list_import import diff_against_db, normalize_class_name, parse_provisional_entry_text

	klass = normalize_class_name(class_name)
	parsed = parse_provisional_entry_text(text, klass)
	if only_marked_new:
		parsed = [p for p in parsed if p.get("is_new_in_list")]
	diff = diff_against_db(parsed, klass, coast_250, Rider.query)
	return klass, diff


def _serialize_diff(diff: dict) -> dict:
	def row(p: dict, extra: dict | None = None) -> dict:
		out = {
			"number": p["number"],
			"name": p["name"],
			"bike_brand": p.get("bike_brand"),
			"hometown": p.get("hometown"),
			"is_new_in_list": p.get("is_new_in_list", False),
		}
		if extra:
			out.update(extra)
		return out

	number_updates = diff.get("number_updates") or []

	other_class = diff.get("other_class") or []

	return {
		"parsed_total": diff["parsed_total"],
		"new_count": len(diff["new"]),
		"existing_count": len(diff["existing"]),
		"other_class_count": len(other_class),
		"number_updates_count": len(number_updates),
		"name_variants_count": len(diff.get("name_variants") or []),
		"number_conflicts_count": len(diff["number_conflicts"]),
		"new": [row(p) for p in diff["new"]],
		"other_class": [
			row(
				p,
				{
					"existing_id": p.get("existing_id"),
					"existing_number": p.get("existing_number"),
					"existing_class": p.get("existing_class"),
					"note": p.get("note"),
				},
			)
			for p in other_class
		],
		"number_updates": [
			row(
				p,
				{
					"existing_id": p.get("existing_id"),
					"existing_number": p.get("existing_number"),
					"number_changed": True,
				},
			)
			for p in number_updates
		],
		"existing": [
			row(
				p,
				{
					"existing_id": p.get("existing_id"),
					"existing_number": p.get("existing_number"),
					"number_changed": p.get("number_changed"),
				},
			)
			for p in diff["existing"]
		],
		"number_conflicts": [
			row(p, {"existing_id": p.get("existing_id"), "existing_name": p.get("existing_name")})
			for p in diff["number_conflicts"]
		],
	}


def _serialize_review(klass: str, diff: dict) -> list[dict]:
	from entry_list_import import build_review_items

	items = build_review_items(diff, klass)
	out = []
	for it in items:
		row = {
			"key": it["key"],
			"action": it["action"],
			"action_label": it["action_label"],
			"selectable": it["selectable"],
			"name": it["name"],
			"list": it.get("list"),
			"db": it.get("db"),
			"note": it.get("note"),
			"coast_mismatch": it.get("coast_mismatch", False),
			"is_new_in_list": it.get("is_new_in_list", False),
			"can_ignore": it.get("can_ignore", True),
		}
		out.append(row)
	return out


@bp.route("/rider_management/entry_list/preview", methods=["POST"])
@login_required
def entry_list_preview():
	"""Preview pasted provisional entry list; show only riders not already in DB."""
	if not is_admin_user():
		return jsonify({"error": "Unauthorized"}), 401

	text, class_name, coast_250, only_marked_new, _, _, _, _, _ = _entry_list_payload()
	if not text:
		return jsonify({"error": "Klistra in entry list först"}), 400

	try:
		klass, diff = _parse_and_diff_entry_list(text, class_name, coast_250, only_marked_new)
		body = _serialize_diff(diff)
		body["review_items"] = _serialize_review(klass, diff)
		body["selectable_count"] = sum(1 for i in body["review_items"] if i["selectable"])
		body["success"] = True
		body["class_name"] = klass
		body["coast_250"] = coast_250
		body["filtered_marked_new_only"] = only_marked_new
		body["season_active"] = _entry_list_season_active()
		body["safety_note"] = (
			"Poäng, picks och säsongsteam följer förarens id. "
			"Importen ändrar aldrig klass och tar inte bort förare. "
			"Samma namn i annan klass (t.ex. 250→450) skapas inte automatiskt — använd MX-klassbyte."
		)
		return jsonify(body)
	except Exception as e:
		print(f"entry_list_preview error: {e}")
		traceback.print_exc()
		return jsonify({"error": str(e)}), 500


@bp.route("/rider_management/entry_list/fetch_url", methods=["POST"])
@login_required
def entry_list_fetch_url():
	"""Fetch RacerX entry list by URL and return TSV-like text for preview/import."""
	if not is_admin_user():
		return jsonify({"error": "Unauthorized"}), 401
	data = request.get_json(silent=True) or {}
	url = (data.get("url") or "").strip()
	class_name = (data.get("class_name") or "250cc").strip()
	if not url:
		return jsonify({"error": "URL saknas"}), 400
	if "racerxonline.com" not in url.lower():
		return jsonify({"error": "Endast racerxonline.com stöds"}), 400
	try:
		from racerx_entry_list import fetch_entry_list
		from entry_list_import import normalize_class_name

		klass = normalize_class_name(class_name)
		title, rows = fetch_entry_list(url)
		# Make a pasteable text that our parser understands (tabs)
		lines = []
		for r in rows:
			new_cell = "New" if r.is_new else ""
			lines.append(f"{r.number}\t{r.name}\t{new_cell}\t{r.hometown}\t{r.bike}")
		return jsonify({
			"success": True,
			"title": title,
			"class_name": klass,
			"count": len(rows),
			"text": "\n".join(lines),
		})
	except Exception as e:
		print(f"entry_list_fetch_url error: {e}")
		traceback.print_exc()
		return jsonify({"error": str(e)}), 500


@bp.route("/rider_management/entry_list/fetch_images", methods=["POST"])
@login_required
def entry_list_fetch_images():
	"""Fetch and store rider images (data URLs) for selected riders in the current list."""
	if not is_admin_user():
		return jsonify({"error": "Unauthorized"}), 401
	data = request.get_json(silent=True) or {}
	selected_keys = set(data.get("selected") or [])
	force = bool(data.get("force"))
	text = (data.get("text") or "").strip()
	class_name = (data.get("class_name") or "250cc").strip()
	coast_raw = data.get("coast_250")
	coast_250 = (coast_raw or "").strip() or None
	if coast_250 not in ("west", "east"):
		coast_250 = None
	only_marked_new = bool(data.get("only_marked_new"))
	if not text:
		return jsonify({"error": "Klistra in entry list först"}), 400
	if not selected_keys:
		return jsonify({"error": "Välj minst en rad"}), 400
	try:
		from racerx_entry_list import fetch_rider_image_data_url
		from entry_list_import import normalize_class_name

		klass = normalize_class_name(class_name)
		_, diff = _parse_and_diff_entry_list(text, klass, coast_250, only_marked_new)
		# Map selectable items to rider ids
		rider_ids: set[int] = set()
		for p in diff.get("number_updates", []):
			if f"update:{int(p['existing_id'])}" in selected_keys:
				rider_ids.add(int(p["existing_id"]))
		for p in diff.get("name_variants", []):
			if f"variant:{int(p['existing_id'])}" in selected_keys:
				rider_ids.add(int(p["existing_id"]))
		updated = 0
		skipped = 0
		errors: list[str] = []
		for rid in sorted(rider_ids):
			r = Rider.query.get(rid)
			if not r:
				continue
			if not force and getattr(r, "rider_image_data", None):
				skipped += 1
				continue
			# Try to build a rider URL from name (best effort) if we don't have it.
			slug = (r.name or "").strip().lower().replace(" ", "-")
			rider_url = f"https://racerxonline.com/rider/{slug}/races"
			try:
				img_data = fetch_rider_image_data_url(rider_url)
				if not img_data:
					skipped += 1
					continue
				r.rider_image_data = img_data
				updated += 1
			except Exception as e:
				errors.append(f"{r.name}: {e}")
		db.session.commit()
		return jsonify({
			"success": True,
			"updated": updated,
			"skipped": skipped,
			"errors": errors,
			"message": f"Hämtade {updated} bilder (skippade {skipped})",
		})
	except Exception as e:
		db.session.rollback()
		print(f"entry_list_fetch_images error: {e}")
		traceback.print_exc()
		return jsonify({"error": str(e)}), 500


def _norm_racerx_name(name: str) -> str:
	import re

	s = (name or "").strip()
	s = re.sub(r"\s+", " ", s)
	s = re.sub(r"\s+(Jr\.|Sr\.|III|II|IV)$", "", s, flags=re.IGNORECASE)
	return s.lower()


def _load_racerx_images_csv() -> list[dict]:
	import csv
	from pathlib import Path

	path = Path("data/racerx_riders_2026.csv")
	if not path.exists():
		return []
	with path.open(encoding="utf-8") as f:
		return list(csv.DictReader(f))


@bp.route("/rider_management/racerx_images/preview", methods=["POST"])
@login_required
def rider_images_racerx_preview():
	"""Preview which riders can get images from data/racerx_riders_2026.csv."""
	if not is_admin_user():
		return jsonify({"error": "Unauthorized"}), 401
	try:
		rows = _load_racerx_images_csv()
		if not rows:
			return jsonify({"error": "Hittar inte data/racerx_riders_2026.csv"}), 400

		# Build quick lookup by normalized name
		by_name: dict[str, dict] = {}
		for r in rows:
			name = (r.get("name_guess") or "").strip()
			img = (r.get("img_url") or "").strip()
			profile = (r.get("profile_url") or "").strip()
			if not name or not img:
				continue
			if img.lower().endswith("post_thumb.png"):
				continue
			by_name[_norm_racerx_name(name)] = {"img_url": img, "profile_url": profile, "name_guess": name}

		candidates = []
		for rider in Rider.query.all():
			if getattr(rider, "rider_image_data", None):
				continue
			key = _norm_racerx_name(rider.name)
			src = by_name.get(key)
			if not src:
				continue
			candidates.append({
				"key": f"img:{rider.id}",
				"rider_id": rider.id,
				"name": rider.name,
				"class_name": rider.class_name,
				"number": rider.rider_number,
				"img_url": src["img_url"],
				"profile_url": src["profile_url"],
			})

		return jsonify({
			"success": True,
			"candidates": candidates,
			"count": len(candidates),
			"message": f"Hittade {len(candidates)} förare utan bild som kan matchas mot RacerX.",
		})
	except Exception as e:
		print(f"rider_images_racerx_preview error: {e}")
		traceback.print_exc()
		return jsonify({"error": str(e)}), 500


@bp.route("/rider_management/racerx_images/apply", methods=["POST"])
@login_required
def rider_images_racerx_apply():
	"""Apply selected image updates from RacerX CSV (stores as rider_image_data data URL)."""
	if not is_admin_user():
		return jsonify({"error": "Unauthorized"}), 401
	data = request.get_json(silent=True) or {}
	selected = data.get("selected") or []
	force = bool(data.get("force"))
	try:
		selected_ids = []
		for k in selected:
			if isinstance(k, str) and k.startswith("img:") and k[4:].isdigit():
				selected_ids.append(int(k[4:]))
		if not selected_ids:
			return jsonify({"error": "Välj minst en rad"}), 400

		rows = _load_racerx_images_csv()
		if not rows:
			return jsonify({"error": "Hittar inte data/racerx_riders_2026.csv"}), 400

		by_name: dict[str, dict] = {}
		for r in rows:
			name = (r.get("name_guess") or "").strip()
			img = (r.get("img_url") or "").strip()
			if not name or not img:
				continue
			if img.lower().endswith("post_thumb.png"):
				continue
			by_name[_norm_racerx_name(name)] = {"img_url": img}

		import base64
		import requests

		headers = {
			"User-Agent": (
				"Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
				"AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
			)
		}

		updated = 0
		skipped = 0
		errors: list[str] = []
		for rid in selected_ids:
			r = Rider.query.get(rid)
			if not r:
				continue
			if not force and getattr(r, "rider_image_data", None):
				skipped += 1
				continue
			src = by_name.get(_norm_racerx_name(r.name))
			if not src:
				skipped += 1
				continue
			try:
				resp = requests.get(src["img_url"], headers=headers, timeout=30)
				resp.raise_for_status()
				mime = (resp.headers.get("Content-Type") or "image/jpeg").split(";", 1)[0].strip()
				if not mime.startswith("image/"):
					mime = "image/jpeg"
				r.rider_image_data = f"data:{mime};base64,{base64.b64encode(resp.content).decode('ascii')}"
				updated += 1
			except Exception as e:
				errors.append(f"{r.name}: {e}")
		db.session.commit()
		return jsonify({
			"success": True,
			"updated": updated,
			"skipped": skipped,
			"errors": errors,
			"message": f"Uppdaterade {updated} bilder (skippade {skipped})",
		})
	except Exception as e:
		db.session.rollback()
		print(f"rider_images_racerx_apply error: {e}")
		traceback.print_exc()
		return jsonify({"error": str(e)}), 500


@bp.route("/rider_management/racerx_images/refresh_csv", methods=["POST"])
@login_required
def rider_images_racerx_refresh_csv():
	"""Run the RacerX rider scraper to refresh data/racerx_riders_2026.csv."""
	if not is_admin_user():
		return jsonify({"error": "Unauthorized"}), 401
	try:
		# Run scraper in-process so we don't depend on shell.
		from tools import scrape_racerx_riders

		start = datetime.utcnow()
		scrape_racerx_riders.main()
		elapsed_ms = int((datetime.utcnow() - start).total_seconds() * 1000)
		return jsonify({
			"success": True,
			"message": f"Uppdaterade racerx_riders_2026.csv (tog {elapsed_ms} ms).",
		})
	except Exception as e:
		print(f"rider_images_racerx_refresh_csv error: {e}")
		traceback.print_exc()
		return jsonify({"error": str(e)}), 500


def _execute_entry_list_apply() -> tuple[dict, int]:
	from entry_list_import import (
		DEFAULT_PRICE,
		apply_name_variants,
		apply_number_updates,
		import_new_riders,
		review_item_key_create,
		review_item_key_cross_create,
		review_item_key_name_variant,
		review_item_key_update,
	)

	data = request.get_json(silent=True) or {}
	selected_keys = set(data.get("selected") or [])
	(
		text,
		class_name,
		coast_250,
		only_marked_new,
		default_price,
		_,
		_,
		confirm_season_active,
		allow_cross_class_create,
	) = _entry_list_payload()
	if not text:
		return {"error": "Klistra in entry list först"}, 400
	if not selected_keys:
		return {"error": "Välj minst en rad att spara"}, 400
	if _entry_list_season_active() and not confirm_season_active:
		return {
			"error": (
				"Säsong pågår — kryssa i bekräftelsen under listan innan du sparar "
				"(endast valda rader, samma id behåller poäng)"
			),
			"season_active": True,
		}, 400

	try:
		klass, diff = _parse_and_diff_entry_list(text, class_name, coast_250, only_marked_new)
		new_selected = [
			p for p in diff["new"]
			if review_item_key_create(p["name"]) in selected_keys
		]
		cross_selected = [
			p for p in diff.get("other_class", [])
			if review_item_key_cross_create(p["name"]) in selected_keys
		]
		updates_selected = [
			p for p in diff["number_updates"]
			if review_item_key_update(int(p["existing_id"])) in selected_keys
		]
		variants_selected = [
			p for p in diff.get("name_variants", [])
			if review_item_key_name_variant(int(p["existing_id"])) in selected_keys
		]
		errors: list[str] = []
		created: list[str] = []
		updated: list[str] = []
		conflicts_resolved = 0

		any_writes = bool(new_selected or cross_selected or updates_selected or variants_selected)
		combined = sum(1 for x in (new_selected, cross_selected, updates_selected, variants_selected) if x) > 1
		if new_selected:
			created, err_new = import_new_riders(
				new_selected,
				Rider,
				db.session,
				Rider.query,
				coast_250=coast_250,
				default_price=default_price or DEFAULT_PRICE,
				auto_commit=not combined,
				allow_cross_class_create=False,
			)
			errors.extend(err_new)
		if cross_selected and not errors:
			cross_created, err_cross = import_new_riders(
				cross_selected,
				Rider,
				db.session,
				Rider.query,
				coast_250=coast_250,
				default_price=default_price or DEFAULT_PRICE,
				auto_commit=not combined,
				allow_cross_class_create=True,
			)
			created.extend(cross_created)
			errors.extend(err_cross)
		if updates_selected and not errors:
			updated, err_num, conflicts_resolved = apply_number_updates(
				updates_selected,
				Rider,
				db.session,
				Rider.query,
				auto_commit=not combined,
			)
			errors.extend(err_num)
		if variants_selected and not errors:
			var_updated, err_var = apply_name_variants(
				variants_selected,
				Rider,
				db.session,
				auto_commit=not combined,
			)
			updated.extend(var_updated)
			errors.extend(err_var)

		if errors:
			db.session.rollback()
			return {"error": "; ".join(errors), "errors": errors}, 400
		if any_writes:
			db.session.commit()

		parts = []
		if created:
			parts.append(f"{len(created)} nya")
		if updated:
			parts.append(f"{len(updated)} nummer uppdaterade")
		message = ", ".join(parts) if parts else "Inget att ändra"
		if conflicts_resolved:
			message += f" ({conflicts_resolved} nummerkonflikt(er) lösta med temp-nummer)"

		return {
			"success": True,
			"created_count": len(created),
			"created": created,
			"updated_count": len(updated),
			"updated": updated,
			"conflicts_resolved": conflicts_resolved,
			"errors": errors,
			"message": message,
		}, 200
	except Exception as e:
		db.session.rollback()
		print(f"entry_list_apply error: {e}")
		traceback.print_exc()
		return {"error": str(e)}, 500


@bp.route("/rider_management/entry_list/apply", methods=["POST"])
@login_required
def entry_list_apply():
	"""Apply only admin-selected rows from entry list review."""
	if not is_admin_user():
		return jsonify({"error": "Unauthorized"}), 401
	body, status = _execute_entry_list_apply()
	return jsonify(body), status

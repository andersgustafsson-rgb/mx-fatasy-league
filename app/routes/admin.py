from __future__ import annotations

from datetime import date, datetime, timedelta
from functools import wraps

from flask import Blueprint, render_template, redirect, url_for, session, jsonify

from models import db, Competition, Rider, User

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

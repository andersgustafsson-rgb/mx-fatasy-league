from __future__ import annotations

from datetime import date, datetime, timedelta
from functools import wraps

from flask import Blueprint, render_template, redirect, url_for, session

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
		riders_450 = Rider.query.filter_by(class_name='450cc').order_by(Rider.rider_number).all()
		riders_250_east = Rider.query.filter_by(class_name='250cc', coast_250='east').order_by(Rider.rider_number).all()
		riders_250_west = Rider.query.filter_by(class_name='250cc', coast_250='west').order_by(Rider.rider_number).all()
		riders_wsx_sx1 = Rider.query.filter_by(class_name='wsx_sx1').order_by(Rider.rider_number).all()
		riders_wsx_sx2 = Rider.query.filter_by(class_name='wsx_sx2').order_by(Rider.rider_number).all()
		return render_template('rider_management.html',
							riders_450=riders_450,
							riders_250_east=riders_250_east,
							riders_250_west=riders_250_west,
							riders_wsx_sx1=riders_wsx_sx1,
							riders_wsx_sx2=riders_wsx_sx2)
	except Exception as e:
		return f"<h1>Database Error</h1><p>{e}</p>"

from __future__ import annotations

import os
from datetime import timedelta
from flask import Flask
from dotenv import load_dotenv

# Load environment variables early
load_dotenv()

# Reuse the existing SQLAlchemy instance and models
from models import db  # noqa: E402


def create_app() -> Flask:
	app = Flask(__name__)

	# Secret key
	app.secret_key = os.getenv('SECRET_KEY', 'din_hemliga_nyckel_har_change_in_production')

	# Database configuration (mirror of main.py logic)
	db_url_env = os.getenv('DATABASE_URL', '')
	if db_url_env and 'postgresql' in db_url_env:
		app.config['SQLALCHEMY_DATABASE_URI'] = db_url_env
	else:
		if os.getenv('RENDER'):
			app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
		else:
			# Default to local SQLite file
			app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///fantasy_mx.db'

	app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

	# Security/session settings similar to main.py
	app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)
	app.config['SESSION_COOKIE_SECURE'] = True
	app.config['SESSION_COOKIE_HTTPONLY'] = True
	app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

	# Engine options
	if 'postgresql' in app.config['SQLALCHEMY_DATABASE_URI']:
		app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
			'pool_pre_ping': True,
			'pool_recycle': 300,
			'pool_size': 10,
			'max_overflow': 20,
		}
	else:
		app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
			'pool_pre_ping': True,
			'pool_recycle': 300,
			'connect_args': {'check_same_thread': False}
		}

	# Max upload size
	app.config['MAX_CONTENT_LENGTH'] = int(os.getenv('MAX_CONTENT_LENGTH', 16 * 1024 * 1024))

	# Initialize db
	db.init_app(app)

	# Register blueprints (optional; can be added incrementally)
	try:
		from .routes.public import bp as public_bp  # noqa: F401
		app.register_blueprint(public_bp)
	except Exception:
		# Allow app to start even if blueprints are not present yet
		pass

	# API blueprint (safe to register even before routes are fully migrated)
	try:
		from .routes.api import bp as api_bp  # noqa: F401
		app.register_blueprint(api_bp)
	except Exception:
		pass

	# Register admin blueprint
	try:
		from .routes.admin import bp as admin_bp  # noqa: F401
		app.register_blueprint(admin_bp)
	except Exception:
		pass

	return app

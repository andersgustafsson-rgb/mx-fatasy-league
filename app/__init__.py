from __future__ import annotations

import os
from datetime import timedelta
from flask import Flask, redirect, url_for
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

	try:
		from .routes.pit_lane import bp as pit_lane_bp  # noqa: F401
		app.register_blueprint(pit_lane_bp)
	except Exception:
		pass

	# Backward-compat endpoint alias so templates using url_for('admin_page') still work
	try:
		if 'admin.admin_page' in app.view_functions and 'admin_page' not in app.view_functions:
			app.add_url_rule('/admin', endpoint='admin_page', view_func=app.view_functions['admin.admin_page'])
	except Exception:
		pass

	@app.get("/favicon.ico")
	def favicon():
		"""Serve favicon at root without redirect — Google prefers a direct 200."""
		from flask import send_from_directory, make_response

		resp = make_response(
			send_from_directory(app.static_folder, "images/mx_fantasy_favicon.png")
		)
		resp.headers["Content-Type"] = "image/png"
		resp.headers["Cache-Control"] = "public, max-age=604800"
		return resp

	@app.get("/sw.js")
	def service_worker():
		"""
		PWA: service worker must live at origin root to control '/'.
		Serve the file from /static, but expose it at /sw.js.
		"""
		from flask import send_from_directory, make_response

		resp = make_response(send_from_directory(app.static_folder, "sw.js"))
		resp.headers["Content-Type"] = "application/javascript; charset=utf-8"
		# Allow root scope even though file is served from static folder.
		resp.headers["Service-Worker-Allowed"] = "/"
		return resp

	@app.get("/google59180a241028d7ad.html")
	def google_site_verification():
		"""Google Search Console ownership verification."""
		from flask import send_from_directory, make_response

		resp = make_response(
			send_from_directory(app.static_folder, "google59180a241028d7ad.html")
		)
		resp.headers["Content-Type"] = "text/html; charset=utf-8"
		return resp

	@app.before_request
	def _redirect_legacy_render_host():
		from flask import redirect, request
		from public_url import is_legacy_render_host, legacy_redirect_url

		if request.path in ("/health", "/healthz"):
			return None
		if is_legacy_render_host(request.host):
			return redirect(legacy_redirect_url(request.full_path), code=301)

	@app.get("/robots.txt")
	def robots_txt():
		"""Tell search engines which pages to crawl."""
		from flask import make_response
		from public_url import get_public_base_url

		base = get_public_base_url()
		body = (
			"User-agent: *\n"
			"Allow: /\n"
			"Disallow: /admin\n"
			"Disallow: /api/\n"
			f"Sitemap: {base}/sitemap.xml\n"
		)
		resp = make_response(body)
		resp.headers["Content-Type"] = "text/plain; charset=utf-8"
		return resp

	@app.get("/sitemap.xml")
	def sitemap_xml():
		"""Sitemap with public pages for Google."""
		from flask import make_response
		from public_url import get_public_base_url

		base = get_public_base_url()
		body = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>{base}/</loc>
    <changefreq>weekly</changefreq>
    <priority>1.0</priority>
  </url>
  <url>
    <loc>{base}/start</loc>
    <changefreq>weekly</changefreq>
    <priority>0.9</priority>
  </url>
  <url>
    <loc>{base}/login</loc>
    <changefreq>monthly</changefreq>
    <priority>0.5</priority>
  </url>
  <url>
    <loc>{base}/privacy</loc>
    <changefreq>yearly</changefreq>
    <priority>0.3</priority>
  </url>
  <url>
    <loc>{base}/terms</loc>
    <changefreq>yearly</changefreq>
    <priority>0.3</priority>
  </url>
  <url>
    <loc>{base}/contact</loc>
    <changefreq>yearly</changefreq>
    <priority>0.4</priority>
  </url>
</urlset>"""
		resp = make_response(body)
		resp.headers["Content-Type"] = "application/xml; charset=utf-8"
		return resp

	return app

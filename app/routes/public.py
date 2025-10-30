from __future__ import annotations

from flask import Blueprint, jsonify, render_template

bp = Blueprint('public', __name__)


@bp.get('/health')
def health():
	return jsonify(status='ok')


@bp.get('/')
def index_root():
	# Try to render index if it exists; otherwise return a simple message
	try:
		return render_template('index.html')
	except Exception:
		return 'MX Fantasy running', 200

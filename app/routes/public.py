from __future__ import annotations

from flask import Blueprint, jsonify

bp = Blueprint('public', __name__)


@bp.get('/health')
def health():
	return jsonify(status='ok')

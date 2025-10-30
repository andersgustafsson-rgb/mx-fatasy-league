from __future__ import annotations

from flask import Blueprint, jsonify, request, session
from models import db, CrossDinoHighScore

bp = Blueprint('api', __name__, url_prefix='/api')


@bp.get('/cross_dino/highscores')
def get_cross_dino_highscores():
	try:
		highscores = (
			CrossDinoHighScore.query
			.order_by(CrossDinoHighScore.score.desc())
			.limit(5)
			.all()
		)
		return jsonify([score.to_dict() for score in highscores])
	except Exception as e:
		print(f"Error getting highscores: {e}")
		return jsonify([])


@bp.post('/cross_dino/highscores')
def submit_cross_dino_highscore():
	try:
		data = request.get_json() or {}
		player_name = data.get('player_name', 'Anonym')
		try:
			score = int(data.get('score', 0))
		except Exception:
			score = 0
		if score <= 0:
			return jsonify({"error": "Invalid score"}), 400

		highscore = CrossDinoHighScore(player_name=player_name, score=score)
		db.session.add(highscore)
		db.session.commit()

		highscores = (
			CrossDinoHighScore.query
			.order_by(CrossDinoHighScore.score.desc())
			.limit(5)
			.all()
		)
		return jsonify([score.to_dict() for score in highscores])
	except Exception as e:
		print(f"Error submitting highscore: {e}")
		db.session.rollback()
		return jsonify({"error": "Failed to submit highscore"}), 500


@bp.post('/cross_dino/reset_highscores')
def reset_cross_dino_highscores():
	try:
		if "user_id" not in session:
			return jsonify({"error": "Not authenticated"}), 401
		CrossDinoHighScore.query.delete()
		db.session.commit()
		return jsonify({"success": True, "message": "All highscores have been reset"})
	except Exception as e:
		print(f"Error resetting highscores: {e}")
		db.session.rollback()
		return jsonify({"error": "Failed to reset highscore"}), 500

from __future__ import annotations

from flask import Blueprint, jsonify, request, session, current_app as app
from models import db, CrossDinoHighScore, Rider, Competition
from datetime import datetime

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


# --- Riders management ---

@bp.route('/riders', methods=['POST'])
def add_rider():
	if session.get("username") != "test":
		return jsonify({'error': 'Unauthorized'}), 401
	season_warning = None
	try:
		from main import is_season_active  # reuse existing logic
		if is_season_active():
			season_warning = "⚠️ VARNING: Säsong är igång. Nya förare kan påverka befintliga picks och säsongsteam."
	except Exception:
		pass

	data = request.get_json() if request.is_json else request.form.to_dict()

	# Optional image upload
	image_url = None
	if 'rider_image' in request.files:
		file = request.files['rider_image']
		if file and file.filename:
			try:
				import os
				from werkzeug.utils import secure_filename
				riders_dir = os.path.join(app.static_folder, 'riders')
				os.makedirs(riders_dir, exist_ok=True)
				original_ext = os.path.splitext(file.filename)[1].lower() or '.jpg'
				filename = secure_filename(f"{data['name'].replace(' ', '_')}_{data['rider_number']}{original_ext}")
				file_path = os.path.join(riders_dir, filename)
				file.save(file_path)
				image_url = f"riders/{filename}"
			except Exception as e:
				print(f"Error saving rider image: {e}")

	# Conflict check
	existing_rider = Rider.query.filter_by(
		rider_number=data['rider_number'],
		class_name=data['class_name']
	).first()
	if existing_rider:
		return jsonify({
			'error': 'conflict',
			'message': f"Nummer {data['rider_number']} finns redan för {existing_rider.name} ({existing_rider.class_name})",
			'existing_rider': {
				'id': existing_rider.id,
				'name': existing_rider.name,
				'class_name': existing_rider.class_name,
				'rider_number': existing_rider.rider_number,
				'bike_brand': existing_rider.bike_brand
			}
		}), 409

	price = data.get('price') or (450000 if data['class_name'] == '450cc' else 50000)
	classes = data.get('classes', data.get('class_name', '250cc'))

	rider = Rider(
		name=data['name'],
		class_name=data.get('class_name', classes.split(',')[0].strip() if classes else '250cc'),
		classes=classes,
		rider_number=data['rider_number'],
		bike_brand=data['bike_brand'],
		coast_250=data.get('coast_250'),
		price=price,
		image_url=image_url,
		series_participation=data.get('series_participation')
	)
	db.session.add(rider)
	db.session.commit()
	response = {'success': True, 'id': rider.id}
	if season_warning:
		response['warning'] = season_warning
	return jsonify(response)


@bp.route('/riders/<int:rider_id>', methods=['PUT'])
def update_rider(rider_id: int):
	if session.get("username") != "test":
		return jsonify({'error': 'Unauthorized'}), 401
	rider = Rider.query.get_or_404(rider_id)
	data = request.get_json() if request.is_json else request.form.to_dict()

	season_warning = None
	try:
		from main import is_season_active
		if is_season_active():
			season_warning = "⚠️ VARNING: Säsong är igång. Ändringar kan påverka befintliga picks och säsongsteam."
	except Exception:
		pass

	# Optional new image
	if 'rider_image' in request.files:
		file = request.files['rider_image']
		if file and file.filename:
			try:
				import os
				from werkzeug.utils import secure_filename
				riders_dir = os.path.join(app.static_folder, 'riders')
				os.makedirs(riders_dir, exist_ok=True)
				original_ext = os.path.splitext(file.filename)[1].lower() or '.jpg'
				filename = secure_filename(f"{data['name'].replace(' ', '_')}_{data['rider_number']}{original_ext}")
				file_path = os.path.join(riders_dir, filename)
				file.save(file_path)
				rider.image_url = f"riders/{filename}"
			except Exception as e:
				print(f"Error saving rider image: {e}")

	new_class_name = rider.class_name
	if 'classes' in data and data['classes']:
		new_class_name = data['classes'].split(',')[0].strip()
	elif 'class_name' in data:
		new_class_name = data['class_name']

	if data['rider_number'] != rider.rider_number or new_class_name != rider.class_name:
		existing_rider = Rider.query.filter_by(
			rider_number=data['rider_number'],
			class_name=new_class_name
		).filter(Rider.id != rider_id).first()
		if existing_rider:
			return jsonify({
				'error': 'conflict',
				'message': f"Nummer {data['rider_number']} finns redan för {existing_rider.name} ({existing_rider.class_name}). Du måste ändra nummer på den andra föraren först.",
				'existing_rider': {
					'id': existing_rider.id,
					'name': existing_rider.name,
					'class_name': existing_rider.class_name,
					'rider_number': existing_rider.rider_number,
					'bike_brand': existing_rider.bike_brand
				}
			}), 409

	rider.name = data['name']
	rider.rider_number = data['rider_number']
	rider.bike_brand = data['bike_brand']
	if 'classes' in data:
		rider.classes = data['classes']
		rider.class_name = data['classes'].split(',')[0].strip() if data['classes'] else '250cc'
		if '250cc' not in data['classes']:
			rider.coast_250 = None
	if 'price' in data:
		rider.price = data['price']
	if 'coast_250' in data:
		rider.coast_250 = data['coast_250']
	for field in ['nickname','hometown','residence','team','manufacturer','team_manager','mechanic','instagram','twitter','facebook','website','bio','achievements']:
		if field in data:
			setattr(rider, field, data[field])
	if 'series_participation' in data:
		rider.series_participation = data['series_participation'] or rider.series_participation
	if 'birthdate' in data:
		try:
			from datetime import datetime as _dt
			rider.birthdate = _dt.strptime(data['birthdate'], '%Y-%m-%d').date() if data['birthdate'] else None
		except Exception:
			pass
	for k in ['height_cm','weight_kg','turned_pro']:
		if k in data:
			try:
				setattr(rider, k, int(data[k]) if data[k] else None)
			except Exception:
				pass
	db.session.commit()
	response = {'success': True}
	if season_warning:
		response['warning'] = season_warning
	return jsonify(response)


@bp.route('/riders/<int:rider_id>', methods=['DELETE'])
def delete_rider(rider_id: int):
	if session.get("username") != "test":
		return jsonify({'error': 'Unauthorized'}), 401
	try:
		season_warning = None
		try:
			from main import is_season_active
			if is_season_active():
				season_warning = "⚠️ VARNING: Säsong är igång. Borttagning kan påverka befintliga picks och säsongsteam."
		except Exception:
			pass
		rider = Rider.query.get_or_404(rider_id)
		from sqlalchemy import text
		try:
			db.session.execute(text("DELETE FROM competition_results WHERE rider_id = :rider_id"), {'rider_id': rider_id})
			db.session.execute(text("DELETE FROM holeshot_results WHERE rider_id = :rider_id"), {'rider_id': rider_id})
			db.session.execute(text("DELETE FROM season_team_riders WHERE rider_id = :rider_id"), {'rider_id': rider_id})
			db.session.execute(text("DELETE FROM race_picks WHERE rider_id = :rider_id"), {'rider_id': rider_id})
			db.session.execute(text("DELETE FROM holeshot_picks WHERE rider_id = :rider_id"), {'rider_id': rider_id})
			db.session.execute(text("DELETE FROM wildcard_picks WHERE rider_id = :rider_id"), {'rider_id': rider_id})
			db.session.execute(text("DELETE FROM competition_rider_status WHERE rider_id = :rider_id"), {'rider_id': rider_id})
			db.session.commit()
		except Exception as e:
			print(f"Error deleting associated data for rider {rider_id}: {e}")
			db.session.rollback()
			raise
		db.session.delete(rider)
		db.session.commit()
		response = {'success': True}
		if season_warning:
			response['warning'] = season_warning
		return jsonify(response)
	except Exception as e:
		print(f"Error deleting rider {rider_id}: {e}")
		db.session.rollback()
		return jsonify({'error': f'Error deleting rider: {str(e)}'}), 500

# --- Competitions management (core CRUD used by admin UI) ---

@bp.route('/competitions/list', methods=['GET'])
def list_competitions():
	if session.get("username") != "test":
		return jsonify({'error': 'Unauthorized'}), 401
	try:
		# Detect presence of optional start_time column
		try:
			db.session.execute(db.text("SELECT start_time FROM competitions LIMIT 1"))
			has_start_time = True
		except Exception:
			has_start_time = False
		competitions = Competition.query.order_by(Competition.event_date).all()
		result = []
		for comp in competitions:
			comp_data = {
				'id': comp.id,
				'name': comp.name,
				'event_date': comp.event_date.isoformat() if comp.event_date else None,
				'series': comp.series,
				'coast_250': comp.coast_250,
				'point_multiplier': comp.point_multiplier,
				'is_triple_crown': comp.is_triple_crown,
				'timezone': comp.timezone,
			}
			if has_start_time and hasattr(comp, 'start_time'):
				comp_data['start_time'] = comp.start_time.isoformat() if comp.start_time else None
			else:
				comp_data['start_time'] = None
			result.append(comp_data)
		return jsonify(result)
	except Exception as e:
		print(f"Error in list_competitions: {e}")
		return jsonify({'error': str(e)}), 500


@bp.route('/competitions/create', methods=['POST'])
def create_competition():
	if session.get("username") != "test":
		return jsonify({'error': 'Unauthorized'}), 401
	data = request.get_json()
	try:
		competition_data = {
			'name': data['name'],
			'event_date': datetime.strptime(data['event_date'], '%Y-%m-%d').date() if data['event_date'] else None,
			'series': data['series'],
			'coast_250': data.get('coast_250'),
			'point_multiplier': data.get('point_multiplier', 1.0),
			'is_triple_crown': data.get('is_triple_crown', False),
			'timezone': data.get('timezone')
		}
		if hasattr(Competition, 'start_time') and data.get('start_time'):
			try:
				time_str = data['start_time']
				competition_data['start_time'] = datetime.strptime(time_str, '%H:%M').time() if len(time_str.split(':')) == 2 else datetime.strptime(time_str, '%H:%M:%S').time()
			except ValueError:
				competition_data['start_time'] = None
		competition = Competition(**competition_data)
		db.session.add(competition)
		db.session.commit()
		return jsonify({'success': True, 'id': competition.id})
	except Exception as e:
		db.session.rollback()
		return jsonify({'error': str(e)}), 500


@bp.route('/competitions/update/<int:competition_id>', methods=['PUT'])
def update_competition(competition_id: int):
	if session.get("username") != "test":
		return jsonify({'error': 'Unauthorized'}), 401
	comp = Competition.query.get_or_404(competition_id)
	data = request.get_json()
	try:
		comp.name = data['name']
		comp.event_date = datetime.strptime(data['event_date'], '%Y-%m-%d').date() if data.get('event_date') else None
		comp.series = data.get('series', comp.series)
		comp.coast_250 = data.get('coast_250')
		comp.point_multiplier = data.get('point_multiplier', comp.point_multiplier)
		comp.is_triple_crown = data.get('is_triple_crown', comp.is_triple_crown)
		comp.timezone = data.get('timezone')
		if hasattr(Competition, 'start_time') and data.get('start_time') is not None:
			try:
				time_str = data['start_time']
				comp.start_time = datetime.strptime(time_str, '%H:%M').time() if len(time_str.split(':')) == 2 else datetime.strptime(time_str, '%H:%M:%S').time()
			except ValueError:
				comp.start_time = None
		db.session.commit()
		return jsonify({'success': True})
	except Exception as e:
		db.session.rollback()
		return jsonify({'error': str(e)}), 500


@bp.route('/competitions/delete/<int:competition_id>', methods=['DELETE'])
def delete_competition(competition_id: int):
	if session.get("username") != "test":
		return jsonify({'error': 'Unauthorized'}), 401
	try:
		from sqlalchemy import text
		force = request.args.get('force') == 'true'
		if force:
			# Best-effort cascading clean-up similar to main.py
			db.session.execute(text("DELETE FROM competition_results WHERE competition_id = :id"), {'id': competition_id})
			db.session.execute(text("DELETE FROM race_picks WHERE competition_id = :id"), {'id': competition_id})
			db.session.execute(text("DELETE FROM holeshot_picks WHERE competition_id = :id"), {'id': competition_id})
			db.session.execute(text("DELETE FROM wildcard_picks WHERE competition_id = :id"), {'id': competition_id})
			db.session.execute(text("DELETE FROM competition_rider_status WHERE competition_id = :id"), {'id': competition_id})
			db.session.commit()
		comp = Competition.query.get_or_404(competition_id)
		db.session.delete(comp)
		db.session.commit()
		return jsonify({'success': True})
	except Exception as e:
		db.session.rollback()
		return jsonify({'error': str(e)}), 500

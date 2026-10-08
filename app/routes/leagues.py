"""User league pages + CRUD (skiva 22).

Same URL paths (no prefix). League digests/helpers stay in main for now
(proxied via _main). Bare endpoint aliases registered in main for url_for.
"""
from __future__ import annotations

import os
from datetime import datetime

from flask import (
    Blueprint,
    current_app,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.utils import secure_filename

from auth_helpers import _redirect_to_login
from models import (
    Competition,
    CompetitionResult,
    League,
    LeagueMembership,
    LeagueRequest,
    User,
    db,
)
from services.league_challenges import (
    _league_challenges_context,
    _league_shame_map,
    _mark_challenge_notifications_read,
)
from services.schema_patches import _ensure_league_membership_unique

bp = Blueprint("leagues", __name__)


def _main():
    import main as _m

    return _m


def _league_summary_for_user(*args, **kwargs):
    return _main()._league_summary_for_user(*args, **kwargs)


def _league_race_matrix(*args, **kwargs):
    return _main()._league_race_matrix(*args, **kwargs)


def _upcoming_competitions(*args, **kwargs):
    return _main()._upcoming_competitions(*args, **kwargs)


def _league_picks_pulse(*args, **kwargs):
    return _main()._league_picks_pulse(*args, **kwargs)


def _league_last_race_digest(*args, **kwargs):
    return _main()._league_last_race_digest(*args, **kwargs)


def _league_rival_card(*args, **kwargs):
    return _main()._league_rival_card(*args, **kwargs)


def _user_avatar_fields(*args, **kwargs):
    return _main()._user_avatar_fields(*args, **kwargs)


def calculate_league_points(*args, **kwargs):
    return _main().calculate_league_points(*args, **kwargs)


def generate_invite_code(*args, **kwargs):
    return _main().generate_invite_code(*args, **kwargs)


def allowed_file(*args, **kwargs):
    return _main().allowed_file(*args, **kwargs)


def init_database(*args, **kwargs):
    return _main().init_database(*args, **kwargs)

@bp.route("/leagues")
def leagues_page():
    if "user_id" not in session:
        return _redirect_to_login()

    uid = session["user_id"]

    # Ensure database is initialized
    try:
        from sqlalchemy import inspect
        if not inspect(db.engine).has_table('leagues'):
            print("Tables missing, reinitializing database...")
            init_database()
    except Exception as e:
        print(f"Database check error: {e}")
        init_database()

    try:
        _ensure_league_membership_unique()
        my_leagues = (
            League.query.join(LeagueMembership)
            .filter(LeagueMembership.user_id == uid)
            .distinct()
            .all()
        )
    except Exception as e:
        print(f"Error getting leagues: {e}")
        my_leagues = []

    public_leagues = db.session.query(
        League,
        db.func.count(db.func.distinct(LeagueMembership.user_id)).label('member_count')
    ).outerjoin(LeagueMembership).filter(
        League.is_public == True
    ).group_by(League.id).order_by(
        League.total_points.desc(),
        League.created_at.desc()
    ).all()

    user_league_ids = [
        lid[0] for lid in db.session.query(LeagueMembership.league_id).filter(
            LeagueMembership.user_id == uid
        ).distinct().all()
    ]
    pending_league_ids = [
        rid[0] for rid in db.session.query(LeagueRequest.league_id).filter(
            LeagueRequest.user_id == uid,
            LeagueRequest.status == 'pending'
        ).all()
    ]

    league_leaderboard = []
    try:
        leagues_with_members = db.session.query(
            League,
            db.func.count(LeagueMembership.user_id).label('member_count')
        ).select_from(League).outerjoin(
            LeagueMembership, League.id == LeagueMembership.league_id
        ).group_by(League.id).order_by(
            League.total_points.desc(),
            League.created_at.desc()
        ).all()
        for row in leagues_with_members:
            league = row[0]
            league_leaderboard.append({
                'id': league.id,
                'name': league.name,
                'member_count': row[1],
                'total_points': league.total_points or 0,
                'is_public': getattr(league, 'is_public', True),
            })
    except Exception as e:
        print(f"Error loading league leaderboard: {e}")

    initial_tab = (request.args.get("tab") or "mine").strip().lower()
    if initial_tab not in ("mine", "create", "join", "explore", "leaderboard"):
        initial_tab = "mine"

    my_league_cards = []
    for league in my_leagues:
        summary = _league_summary_for_user(league.id, uid)
        my_league_cards.append({"league": league, **summary})

    return render_template(
        "leagues.html",
        my_leagues=my_leagues,
        my_league_cards=my_league_cards,
        username=session.get("username", "Gäst"),
        is_logged_in=True,
        public_leagues=public_leagues,
        user_league_ids=user_league_ids,
        pending_league_ids=pending_league_ids,
        league_leaderboard=league_leaderboard,
        initial_tab=initial_tab,
    )

@bp.get("/leagues/browse")
def browse_leagues():
    """Browse all public leagues"""
    if "user_id" not in session:
        return _redirect_to_login()
    return redirect(url_for("leagues_page", tab="explore"))

@bp.get("/leagues/leaderboard")
def leagues_leaderboard():
    """Public league leaderboard sorted by league points."""
    if "user_id" in session:
        return redirect(url_for("leagues_page", tab="leaderboard"))
    is_logged_in = False
    try:
        leagues_with_members = db.session.query(
            League,
            db.func.count(LeagueMembership.user_id).label('member_count')
        ).select_from(League).outerjoin(
            LeagueMembership, League.id == LeagueMembership.league_id
        ).group_by(League.id).order_by(
            League.total_points.desc(),
            League.created_at.desc()
        ).all()

        leaderboard = []
        for row in leagues_with_members:
            league = row[0]
            member_count = row[1]
            leaderboard.append({
                'id': league.id,
                'name': league.name,
                'member_count': member_count,
                'total_points': league.total_points or 0,
                'is_public': getattr(league, 'is_public', True)
            })
    except Exception as e:
        print(f"Error loading league leaderboard: {e}")
        leaderboard = []

    return render_template(
        "league_leaderboard.html",
        leaderboard=leaderboard,
        username=session.get("username", "Gäst"),
        is_logged_in=is_logged_in,
    )

@bp.get("/api/leagues/leaderboard")
def api_leagues_leaderboard():
    """API endpoint for league leaderboard data (JSON)."""
    try:
        leagues_with_members = db.session.query(
            League,
            db.func.count(LeagueMembership.user_id).label('member_count')
        ).select_from(League).outerjoin(
            LeagueMembership, League.id == LeagueMembership.league_id
        ).group_by(League.id).order_by(
            League.total_points.desc(),
            League.created_at.desc()
        ).all()

        leaderboard = []
        for row in leagues_with_members:
            league = row[0]
            member_count = row[1]
            leaderboard.append({
                'id': league.id,
                'name': league.name,
                'member_count': member_count,
                'total_points': league.total_points or 0,
                'is_public': getattr(league, 'is_public', True)
            })
    except Exception as e:
        print(f"Error loading league leaderboard: {e}")
        leaderboard = []

    return jsonify(leaderboard)

@bp.get("/api/leagues/stats")
def api_leagues_stats():
    """API endpoint for user's league statistics (JSON)."""
    if "user_id" not in session:
        return jsonify({"error": "not_logged_in"}), 401
    
    try:
        uid = session["user_id"]
        
        # Get user's leagues
        my_leagues = League.query.join(LeagueMembership).filter(
            LeagueMembership.user_id == uid
        ).all()
        
        if not my_leagues:
            return jsonify({
                "leagues": [],
                "message": "Du är inte medlem i någon liga ännu."
            })
        
        # Get all competitions that have results
        competitions = Competition.query.join(CompetitionResult).distinct().order_by(
            Competition.event_date.asc()
        ).all()
        
        stats = []
        for league in my_leagues:
            summary = _league_summary_for_user(league.id, uid)

            # Calculate points per competition
            competition_history = []
            cumulative_points = 0
            
            for comp in competitions:
                # Calculate league points for this competition
                comp_points = calculate_league_points(league.id, comp.id)
                
                if comp_points > 0:  # Only include competitions with points
                    cumulative_points += comp_points
                    competition_history.append({
                        "competition_id": comp.id,
                        "name": comp.name,
                        "series": comp.series,
                        "date": comp.event_date.strftime("%Y-%m-%d") if comp.event_date else "",
                        "points": round(comp_points, 1),
                        "cumulative": round(cumulative_points, 1)
                    })
            
            standings = summary["standings"]
            my_rank = summary["my_rank"]
            my_points = summary["my_points"]
            gap_above = summary["gap_above"]
            gap_below = summary["gap_below"]
            rival_name = summary["rival_name"]
            leader_name = summary["leader_name"]

            stats.append({
                "league_id": league.id,
                "name": league.name,
                "total_points": league.total_points or 0,
                "member_count": summary["member_count"],
                "competitions": competition_history,
                "best_competition": max(competition_history, key=lambda x: x["points"]) if competition_history else None,
                "standings": standings,
                "my_rank": my_rank,
                "my_points": my_points,
                "gap_above": gap_above,
                "gap_below": gap_below,
                "rival_name": rival_name,
                "leader_name": leader_name,
            })
        
        return jsonify({
            "leagues": stats
        })
        
    except Exception as e:
        print(f"Error loading league statistics: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@bp.route("/leagues/<int:league_id>")
def league_detail_page(league_id):
    if "user_id" not in session:
        return _redirect_to_login()
    league = League.query.get_or_404(league_id)
    is_member = LeagueMembership.query.filter_by(league_id=league_id, user_id=session["user_id"]).first()
    if not is_member:
        flash("Du är inte medlem i denna liga.", "error")
        return redirect(url_for("leagues_page"))

    uid = session["user_id"]
    _mark_challenge_notifications_read(uid, league_id)
    g.league_shame_map = _league_shame_map(league_id)
    summary = _league_summary_for_user(league_id, uid)
    race_matrix = _league_race_matrix(league_id, race_limit=8)
    upcoming_races = _upcoming_competitions(limit=4)
    picks_pulse = _league_picks_pulse(league_id, uid)
    last_race_digest = _league_last_race_digest(league_id, uid, summary)
    rival_card = _league_rival_card(league_id, uid, summary)
    challenges_ctx = _league_challenges_context(league_id, uid)

    member_users = (
        db.session.query(User)
        .join(LeagueMembership, User.id == LeagueMembership.user_id)
        .filter(LeagueMembership.league_id == league_id)
        .order_by(User.username)
        .all()
    )

    season_leaderboard = summary["standings"]

    season_archives = []
    try:
        from league_season_archive import list_archives_for_league

        season_archives = list_archives_for_league(int(league_id))
    except Exception as e:
        print(f"league_detail archives: {e}")

    # Get pending requests if user is league creator
    pending_requests = []
    is_creator = league.creator_id == session["user_id"]
    if is_creator:
        pending_requests = db.session.query(
            LeagueRequest.id,
            LeagueRequest.message,
            LeagueRequest.created_at,
            User.username,
            User.display_name
        ).join(User, LeagueRequest.user_id == User.id).filter(
            LeagueRequest.league_id == league_id,
            LeagueRequest.status == 'pending'
        ).order_by(LeagueRequest.created_at.desc()).all()

    return render_template(
        "league_detail.html",
        league=league,
        members=[
            {
                "user_id": u.id,
                "id": u.id,
                "username": u.username,
                "display_name": u.display_name or u.username,
                **_user_avatar_fields(u),
            }
            for u in member_users
        ],
        season_leaderboard=season_leaderboard,
        summary=summary,
        race_matrix=race_matrix,
        upcoming_races=upcoming_races,
        picks_pulse=picks_pulse,
        last_race_digest=last_race_digest,
        rival_card=rival_card,
        challenges=challenges_ctx,
        pending_requests=pending_requests,
        is_creator=is_creator,
        current_user_id=uid,
        season_archives=season_archives,
    )

@bp.post("/create_league")
def create_league():
    if "user_id" not in session:
        return _redirect_to_login()
    
    try:
        name = (request.form.get("league_name") or "").strip()
        if not name:
            flash("Du måste ange ett liganamn.", "error")
            return redirect(url_for("leagues_page"))

        code = generate_invite_code()
        image_url = None

        file = request.files.get("league_image")
        image_data = None
        image_mime_type = None
        image_url = None  # Legacy support
        
        if file and file.filename and allowed_file(file.filename):
            try:
                # Read file data and convert to base64
                file_data = file.read()
                import base64
                image_data = base64.b64encode(file_data).decode('utf-8')
                image_mime_type = file.content_type or 'image/jpeg'
                
                # Also save to file system for legacy support (optional)
                try:
                    fname = secure_filename(f"{code}_{file.filename}")
                    path = os.path.join(current_app.config["UPLOAD_FOLDER"], fname)
                    file.seek(0)  # Reset file pointer
                    file.save(path)
                    image_url = url_for("static", filename=f"uploads/leagues/{fname}")
                    print(f"League image saved to file: {path}")
                except Exception as e:
                    print(f"Error saving league image to file: {e}")
                    # Continue without file, we have base64 data
                
                print(f"League image saved to database as base64: {len(image_data)} chars")
            except Exception as e:
                print(f"Error processing league image: {e}")
                # Continue without image if processing fails

        league = League(
            name=name, 
            creator_id=session["user_id"], 
            invite_code=code, 
            image_url=image_url,
            image_data=image_data,
            image_mime_type=image_mime_type
        )
        db.session.add(league)
        db.session.flush()
        db.session.add(LeagueMembership(league_id=league.id, user_id=session["user_id"]))
        db.session.commit()
        
        print(f"League created successfully: {name} with code {code}")
        flash("Ligan skapades!", "success")
        return redirect(url_for("leagues_page"))

    except Exception as e:
        db.session.rollback()
        print(f"Error creating league: {e}")
        flash(f"Fel vid skapande av liga: {str(e)}", "error")
        return redirect(url_for("leagues_page"))

@bp.post("/join_league")
def join_league():
    if "user_id" not in session:
        return _redirect_to_login()
    code = (request.form.get("invite_code") or "").strip().upper()
    league = League.query.filter_by(invite_code=code).first()
    if not league:
        flash("Ogiltig inbjudningskod.", "error")
        return redirect(url_for("leagues_page"))
    exists = LeagueMembership.query.filter_by(league_id=league.id, user_id=session["user_id"]).first()
    if exists:
        flash("Du är redan med i denna liga.", "error")
        return redirect(url_for("leagues_page"))
    db.session.add(LeagueMembership(league_id=league.id, user_id=session["user_id"]))
    db.session.commit()
    flash("Du gick med i ligan!", "success")
    return redirect(url_for("league_detail_page", league_id=league.id))

@bp.post("/leagues/<int:league_id>/leave")
def leave_league(league_id):
    if "user_id" not in session:
        return _redirect_to_login()
    league = League.query.get_or_404(league_id)
    if league.creator_id == session["user_id"]:
        flash("Skaparen kan inte lämna sin egen liga. Du kan radera ligan i stället.", "error")
        return redirect(url_for("league_detail_page", league_id=league_id))
    mems = LeagueMembership.query.filter_by(
        league_id=league_id, user_id=session["user_id"]
    ).all()
    if mems:
        for mem in mems:
            db.session.delete(mem)
        db.session.commit()
        flash("Du har lämnat ligan.", "success")
    return redirect(url_for("leagues_page"))

@bp.post("/leagues/<int:league_id>/edit")
def edit_league(league_id):
    if "user_id" not in session:
        return _redirect_to_login()
    
    league = League.query.get_or_404(league_id)
    if league.creator_id != session["user_id"]:
        flash("Endast skaparen kan redigera ligan.", "error")
        return redirect(url_for("league_detail_page", league_id=league_id))
    
    try:
        # Update league name if provided
        new_name = (request.form.get("league_name") or "").strip()
        if new_name and new_name != league.name:
            league.name = new_name
        
        # Handle new image upload
        file = request.files.get("league_image")
        if file and file.filename and allowed_file(file.filename):
            try:
                # Delete old image file if it exists (legacy)
                if league.image_url:
                    try:
                        old_filename = league.image_url.split('/')[-1]
                        old_image_path = os.path.join(current_app.config["UPLOAD_FOLDER"], old_filename)
                        if os.path.exists(old_image_path):
                            os.remove(old_image_path)
                            print(f"Deleted old league image file: {old_image_path}")
                    except Exception as e:
                        print(f"Error deleting old league image file: {e}")
                
                # Read file data and convert to base64
                file_data = file.read()
                import base64
                league.image_data = base64.b64encode(file_data).decode('utf-8')
                league.image_mime_type = file.content_type or 'image/jpeg'
                
                # Also save to file system for legacy support (optional)
                try:
                    fname = secure_filename(f"{league.invite_code}_{file.filename}")
                    path = os.path.join(current_app.config["UPLOAD_FOLDER"], fname)
                    file.seek(0)  # Reset file pointer
                    file.save(path)
                    league.image_url = url_for("static", filename=f"uploads/leagues/{fname}")
                    print(f"New league image saved to file: {path}")
                except Exception as e:
                    print(f"Error saving new league image to file: {e}")
                    # Continue without file, we have base64 data
                
                print(f"New league image saved to database as base64: {len(league.image_data)} chars")
            except Exception as e:
                print(f"Error processing new league image: {e}")
                flash("Fel vid uppladdning av bild. Ligan uppdaterades utan bild.", "warning")
        
        db.session.commit()
        flash("Ligan uppdaterades!", "success")
        
    except Exception as e:
        db.session.rollback()
        print(f"Error editing league: {e}")
        flash(f"Fel vid redigering av liga: {str(e)}", "error")
    
    return redirect(url_for("league_detail_page", league_id=league_id))

@bp.post("/leagues/<int:league_id>/delete")
def delete_league(league_id):
    if "user_id" not in session:
        return _redirect_to_login()
    
    try:
        league = League.query.get_or_404(league_id)
        if league.creator_id != session["user_id"]:
            flash("Endast skaparen kan radera ligan.", "error")
            return redirect(url_for("league_detail_page", league_id=league_id))
        
        # Delete all related data first (same as admin_delete_league)
        LeagueRequest.query.filter_by(league_id=league_id).delete()
        LeagueMembership.query.filter_by(league_id=league_id).delete()
        
        # Delete the league
        db.session.delete(league)
        db.session.commit()
        
        flash("Ligan är raderad.", "success")
        return redirect(url_for("leagues_page"))
        
    except Exception as e:
        db.session.rollback()
        print(f"Error deleting league {league_id}: {e}")
        flash(f"Fel vid radering av liga: {str(e)}", "error")
        return redirect(url_for("league_detail_page", league_id=league_id))

@bp.post("/leagues/<int:league_id>/request")
def request_join_league(league_id):
    """Request to join a league"""
    if "user_id" not in session:
        return jsonify({"error": "not_logged_in"}), 401
    
    league = League.query.get_or_404(league_id)
    
    # Check if user is already a member
    existing_membership = LeagueMembership.query.filter_by(
        league_id=league_id, 
        user_id=session["user_id"]
    ).first()
    
    if existing_membership:
        return jsonify({"error": "already_member"}), 400
    
    # Check if user already has a pending request
    existing_request = LeagueRequest.query.filter_by(
        league_id=league_id,
        user_id=session["user_id"],
        status='pending'
    ).first()
    
    if existing_request:
        return jsonify({"error": "request_already_sent"}), 400
    
    # Create new request
    message = request.form.get("message", "").strip()
    request_obj = LeagueRequest(
        league_id=league_id,
        user_id=session["user_id"],
        message=message if message else None
    )
    
    db.session.add(request_obj)
    db.session.commit()
    
    return jsonify({"message": "Request sent successfully"})

@bp.post("/leagues/<int:league_id>/approve_request/<int:request_id>")
def approve_league_request(league_id, request_id):
    """Approve a league join request (league creator only)"""
    if "user_id" not in session:
        return jsonify({"error": "not_logged_in"}), 401
    
    league = League.query.get_or_404(league_id)
    
    # Check if user is the league creator
    if league.creator_id != session["user_id"]:
        return jsonify({"error": "not_authorized"}), 403
    
    request_obj = LeagueRequest.query.get_or_404(request_id)
    
    if request_obj.league_id != league_id:
        return jsonify({"error": "invalid_request"}), 400
    
    if request_obj.status != 'pending':
        return jsonify({"error": "request_already_processed"}), 400
    
    # Approve the request
    request_obj.status = 'approved'
    request_obj.processed_at = datetime.utcnow()
    
    # Add user to league (skip if already a member — avoids duplicate profile rows)
    already = LeagueMembership.query.filter_by(
        league_id=league_id, user_id=request_obj.user_id
    ).first()
    if not already:
        db.session.add(
            LeagueMembership(league_id=league_id, user_id=request_obj.user_id)
        )
    db.session.commit()
    
    flash("Ansökan godkändes!", "success")
    return redirect(url_for("league_detail_page", league_id=league_id))

@bp.post("/leagues/<int:league_id>/reject_request/<int:request_id>")
def reject_league_request(league_id, request_id):
    """Reject a league join request (league creator only)"""
    if "user_id" not in session:
        return jsonify({"error": "not_logged_in"}), 401
    
    league = League.query.get_or_404(league_id)
    
    # Check if user is the league creator
    if league.creator_id != session["user_id"]:
        return jsonify({"error": "not_authorized"}), 403
    
    request_obj = LeagueRequest.query.get_or_404(request_id)
    
    if request_obj.league_id != league_id:
        return jsonify({"error": "invalid_request"}), 400
    
    if request_obj.status != 'pending':
        return jsonify({"error": "request_already_processed"}), 400
    
    # Reject the request
    request_obj.status = 'rejected'
    request_obj.processed_at = datetime.utcnow()
    db.session.commit()
    
    flash("Ansökan avslås!", "info")
    return redirect(url_for("league_detail_page", league_id=league_id))


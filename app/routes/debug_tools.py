"""Legacy debug / one-shot fix / test-bootstrap routes (skiva 13).

Moved out of main.py. Many are gated by _reject_dev_bootstrap() or is_admin_user().
Same URL paths (no prefix) so bookmarks/admin tools keep working.
"""
from __future__ import annotations

import os
import traceback
from datetime import datetime, timedelta
from pathlib import Path

from flask import (
    Blueprint,
    current_app,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import generate_password_hash

from auth_helpers import (
    _dev_bootstrap_allowed,
    _redirect_to_login,
    _reject_dev_bootstrap,
    is_admin_user,
)
from models import (
    Competition,
    CompetitionResult,
    CompetitionScore,
    GlobalSimulation,
    HoleshotPick,
    HoleshotResult,
    LeaderboardHistory,
    League,
    LeagueMembership,
    RacePick,
    Rider,
    SeasonTeam,
    Series,
    User,
    WildcardPick,
    db,
    rider_query_for_list_ui,
)

bp = Blueprint("debug_tools", __name__)


def _main():
    """Lazy import for helpers that still live in main."""
    import main as _m

    return _m


@bp.post("/admin/push/challenges/test")
def admin_test_challenge_push():
    """Skicka test-push till inloggad admin."""
    if not is_admin_user():
        return jsonify({"error": "admin_only"}), 403
    import push_service as ps

    if not ps.push_configured():
        return jsonify({"error": "push_not_configured"}), 503
    uid = session.get("user_id")
    if not uid:
        return jsonify({"error": "not_logged_in"}), 401
    subs = ps.list_subscriptions_for_user(uid)
    if not subs:
        return jsonify(
            {
                "error": "subscribe_first",
                "hint": "Öppna Pit Lane på samma mobil → Slå på notiser",
            }
        ), 400
    result = ps.send_push_sync(
        uid,
        "🔔 Test — Pit Lane-notis",
        "Push funkar! Du får DM, dueller och Race Control.",
        "/pit-lane",
        tag="push-test",
    )
    if result.get("ok"):
        return jsonify(
            {
                "success": True,
                "message": "Test-push skickad",
                "subscriptions": len(subs),
                "result": result,
            }
        )
    return jsonify(
        {
            "error": result.get("error", "send_failed"),
            "subscriptions": subs,
            "result": result,
        }
    ), 500



@bp.get("/debug_weekly_stats")
def debug_weekly_stats():
    """Debug route to see what's happening with weekly stats"""
    if not is_admin_user():
        return jsonify({"error": "Unauthorized"}), 401
    
    try:
        from sqlalchemy import func
        
        # Check all snapshots
        all_snapshots = db.session.query(
            LeaderboardHistory.created_at,
            func.count(LeaderboardHistory.id).label('count')
        ).group_by(LeaderboardHistory.created_at).order_by(LeaderboardHistory.created_at.desc()).limit(10).all()
        
        week_ago = datetime.utcnow() - timedelta(days=7)
        snapshot_before_week = db.session.query(func.max(LeaderboardHistory.created_at)).filter(
            LeaderboardHistory.created_at <= week_ago
        ).scalar()
        
        latest_snapshot = db.session.query(func.max(LeaderboardHistory.created_at)).scalar()
        
        return jsonify({
            "week_ago": week_ago.isoformat(),
            "snapshot_before_week": snapshot_before_week.isoformat() if snapshot_before_week else None,
            "latest_snapshot": latest_snapshot.isoformat() if latest_snapshot else None,
            "all_snapshots": [
                {"timestamp": s[0].isoformat(), "count": s[1]} 
                for s in all_snapshots
            ]
        })
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500



@bp.route("/test_delta")
def test_delta():
    """Test delta calculation by creating two snapshots"""
    if not is_admin_user():
        return redirect(url_for("index"))
    
    try:
        from sqlalchemy import func
        
        # Clear existing history
        LeaderboardHistory.query.delete()
        db.session.commit()
        
        # Get current leaderboard
        user_scores = (
            db.session.query(
                User.id,
                User.username,
                SeasonTeam.team_name,
                func.coalesce(func.sum(CompetitionScore.total_points), 0).label('total_points')
            )
            .outerjoin(SeasonTeam, SeasonTeam.user_id == User.id)
            .outerjoin(CompetitionScore, CompetitionScore.user_id == User.id)
            .group_by(User.id, User.username, SeasonTeam.team_name)
            .order_by(func.coalesce(func.sum(CompetitionScore.total_points), 0).desc())
            .all()
        )
        
        # Create first snapshot
        result = "Creating test snapshots:\n\n"
        result += "FIRST SNAPSHOT:\n"
        for i, (user_id, username, team_name, total_points) in enumerate(user_scores, 1):
            history_entry = LeaderboardHistory(
                user_id=user_id,
                ranking=i,
                total_points=int(total_points)
            )
            db.session.add(history_entry)
            result += f"{i}. {username}: {total_points} points\n"
        
        db.session.commit()
        result += f"\nFirst snapshot created at: {datetime.utcnow()}\n\n"
        
        # Wait a moment and create second snapshot with different order
        import time
        time.sleep(1)
        
        # Shuffle the order for testing
        shuffled_scores = list(user_scores)
        import random
        random.shuffle(shuffled_scores)
        
        result += "SECOND SNAPSHOT (shuffled order):\n"
        for i, (user_id, username, team_name, total_points) in enumerate(shuffled_scores, 1):
            history_entry = LeaderboardHistory(
                user_id=user_id,
                ranking=i,
                total_points=int(total_points)
            )
            db.session.add(history_entry)
            result += f"{i}. {username}: {total_points} points\n"
        
        db.session.commit()
        result += f"\nSecond snapshot created at: {datetime.utcnow()}\n\n"
        result += "Now refresh the main page to see delta calculations!"
        
        return f"<pre>{result}</pre>"
        
    except Exception as e:
        db.session.rollback()
        return f"Error creating test snapshots: {str(e)}"


@bp.route("/debug_leaderboard")
def debug_leaderboard():
    """Debug route to check leaderboard history"""
    if not is_admin_user():
        return redirect(url_for("index"))
    
    try:
        # Check leaderboard history
        history_entries = db.session.query(LeaderboardHistory).order_by(LeaderboardHistory.created_at.desc()).limit(20).all()
        
        result = "Leaderboard History Debug:\n\n"
        result += f"Total history entries: {len(history_entries)}\n\n"
        
        for entry in history_entries:
            user = User.query.get(entry.user_id)
            result += f"User: {user.username if user else 'Unknown'}, Rank: {entry.ranking}, Points: {entry.total_points}, Time: {entry.created_at}\n"
        
        # Check current leaderboard
        from sqlalchemy import func
        user_scores = (
            db.session.query(
                User.id,
                User.username,
                SeasonTeam.team_name,
                func.coalesce(func.sum(CompetitionScore.total_points), 0).label('total_points')
            )
            .outerjoin(SeasonTeam, SeasonTeam.user_id == User.id)
            .outerjoin(CompetitionScore, CompetitionScore.user_id == User.id)
            .group_by(User.id, User.username, SeasonTeam.team_name)
            .order_by(func.coalesce(func.sum(CompetitionScore.total_points), 0).desc())
            .all()
        )
        
        result += "\n\nCurrent Leaderboard:\n"
        for i, (user_id, username, team_name, total_points) in enumerate(user_scores, 1):
            result += f"{i}. {username}: {total_points} points\n"
        
        return f"<pre>{result}</pre>"
        
    except Exception as e:
        return f"Debug error: {str(e)}"


@bp.route("/test_session")
def test_session():
    """Test what's in session"""
    if not is_admin_user():
        return redirect(url_for("index"))
    
    result = "Session contents:\n\n"
    result += f"Username: {session.get('username')}\n"
    result += f"Previous ranking: {session.get('previous_leaderboard_ranking')}\n"
    result += f"All session keys: {list(session.keys())}\n"
    
    return f"<pre>{result}</pre>"


@bp.route('/api/fix_database_tables', methods=['POST'])
def fix_database_tables():
    """Fix missing database tables and columns"""
    if not is_admin_user():
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        # Create all tables
        db.create_all()
        
        # Manually add missing columns to competitions table
        try:
            # Check and add series_id column
            result = db.session.execute(db.text("SELECT column_name FROM information_schema.columns WHERE table_name='competitions' AND column_name='series_id'"))
            if not result.fetchone():
                db.session.execute(db.text("ALTER TABLE competitions ADD COLUMN series_id INTEGER"))
            
            # Check and add phase column
            result = db.session.execute(db.text("SELECT column_name FROM information_schema.columns WHERE table_name='competitions' AND column_name='phase'"))
            if not result.fetchone():
                db.session.execute(db.text("ALTER TABLE competitions ADD COLUMN phase VARCHAR(20)"))
            
            # Check and add is_qualifying column
            result = db.session.execute(db.text("SELECT column_name FROM information_schema.columns WHERE table_name='competitions' AND column_name='is_qualifying'"))
            if not result.fetchone():
                db.session.execute(db.text("ALTER TABLE competitions ADD COLUMN is_qualifying BOOLEAN DEFAULT FALSE"))
            
            db.session.commit()
        except Exception as col_error:
            db.session.rollback()
        
        # Check and add missing columns to riders table
        try:
            # Check and add series_participation column
            result = db.session.execute(db.text("SELECT column_name FROM information_schema.columns WHERE table_name='riders' AND column_name='series_participation'"))
            if not result.fetchone():
                db.session.execute(db.text("ALTER TABLE riders ADD COLUMN series_participation VARCHAR(50) DEFAULT 'all'"))
            
            # Check and add smx_qualified column
            result = db.session.execute(db.text("SELECT column_name FROM information_schema.columns WHERE table_name='riders' AND column_name='smx_qualified'"))
            if not result.fetchone():
                db.session.execute(db.text("ALTER TABLE riders ADD COLUMN smx_qualified BOOLEAN DEFAULT FALSE"))
            
            # Check and add smx_seed_points column
            result = db.session.execute(db.text("SELECT column_name FROM information_schema.columns WHERE table_name='riders' AND column_name='smx_seed_points'"))
            if not result.fetchone():
                db.session.execute(db.text("ALTER TABLE riders ADD COLUMN smx_seed_points INTEGER DEFAULT 0"))
            # rider_image_data (base64) så förarebilder överlever deploy
            result = db.session.execute(db.text("SELECT column_name FROM information_schema.columns WHERE table_name='riders' AND column_name='rider_image_data'"))
            if not result.fetchone():
                db.session.execute(db.text("ALTER TABLE riders ADD COLUMN rider_image_data TEXT"))
            for col, ddl in (("bio_sv", "TEXT"), ("achievements_sv", "TEXT")):
                result = db.session.execute(
                    db.text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_name='riders' AND column_name=:col"
                    ),
                    {"col": col},
                )
                if not result.fetchone():
                    db.session.execute(db.text(f"ALTER TABLE riders ADD COLUMN {col} {ddl}"))
            
            db.session.commit()
        except Exception as riders_error:
            db.session.rollback()
        
        # rider_image_data (för SQLite eller om information_schema inte finns)
        try:
            db.session.execute(db.text("ALTER TABLE riders ADD COLUMN rider_image_data TEXT"))
            db.session.commit()
        except Exception:
            db.session.rollback()
        
        # Check if global_simulation exists and create default entry
        try:
            if not GlobalSimulation.query.first():
                global_sim = GlobalSimulation(
                    active=False,
                    simulated_time=None,
                    start_time=None,
                    scenario=None
                )
                db.session.add(global_sim)
                db.session.commit()
        except Exception as global_error:
            pass
        
        # Fix all 2025 competitions to 2026
        try:
            competitions_2025 = Competition.query.filter(Competition.event_date.like('2025-%')).all()
            for comp in competitions_2025:
                comp.event_date = comp.event_date.replace(year=2026)
            db.session.commit()
        except Exception as date_error:
            db.session.rollback()
        
        return jsonify({'success': True, 'message': f'Database tables and columns fixed. Updated {len(competitions_2025) if "competitions_2025" in locals() else 0} competitions from 2025 to 2026'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/fix_database')
def fix_database_page():
    """Simple page to fix database issues"""
    if not _dev_bootstrap_allowed():
        _reject_dev_bootstrap()
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Fix Database</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 50px; background: #1a1a1a; color: white; }
            .container { max-width: 600px; margin: 0 auto; }
            button { 
                background: #22d3ee; 
                color: black; 
                border: none; 
                padding: 15px 30px; 
                font-size: 16px; 
                border-radius: 5px; 
                cursor: pointer; 
                margin: 10px;
            }
            button:hover { background: #0891b2; }
            .result { margin: 20px 0; padding: 15px; border-radius: 5px; }
            .success { background: #065f46; border: 1px solid #10b981; }
            .error { background: #7f1d1d; border: 1px solid #ef4444; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🔧 Database Fix Tool</h1>
            <p>This tool will fix missing database tables and columns.</p>
            
            <button onclick="fixDatabase()">Fix Database</button>
            <button onclick="window.location.href='/'">Back to Home</button>
            
            <div id="result"></div>
        </div>
        
        <script>
            async function fixDatabase() {
                const resultDiv = document.getElementById('result');
                resultDiv.innerHTML = '<p>Fixing database...</p>';
                
                try {
                    const response = await fetch('/api/fix_database_tables', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        }
                    });
                    
                    const result = await response.json();
                    
                    if (response.ok) {
                        resultDiv.innerHTML = `
                            <div class="result success">
                                <h3>✅ Success!</h3>
                                <p>${result.message}</p>
                                <p>You can now go back to the admin page.</p>
                            </div>
                        `;
                    } else {
                        resultDiv.innerHTML = `
                            <div class="result error">
                                <h3>❌ Error</h3>
                                <p>${result.error}</p>
                            </div>
                        `;
                    }
                } catch (error) {
                    resultDiv.innerHTML = `
                        <div class="result error">
                            <h3>❌ Network Error</h3>
                            <p>${error.message}</p>
                        </div>
                    `;
                }
            }
        </script>
    </body>
    </html>
    '''


@bp.get("/admin/debug_results/<int:competition_id>")
def admin_debug_results(competition_id):
    """Debug endpoint to see all results for a competition in a readable format"""
    if not is_admin_user():
        return jsonify({"error": "unauthorized"}), 403
    
    try:
        comp = Competition.query.get(competition_id)
        if not comp:
            return jsonify({"error": "Competition not found"}), 404
        
        # Get all results
        results = (
            db.session.query(
                CompetitionResult.rider_id,
                CompetitionResult.position,
                CompetitionResult.rider_points,
                db.func.coalesce(CompetitionResult.class_name, Rider.class_name).label("class_name"),
                Rider.name.label("rider_name"),
                Rider.rider_number.label("rider_number"),
            )
            .join(Rider, Rider.id == CompetitionResult.rider_id)
            .filter(CompetitionResult.competition_id == competition_id)
            .order_by(db.func.coalesce(CompetitionResult.class_name, Rider.class_name).asc(), CompetitionResult.position.asc())
            .all()
        )
        
        # Group by class and calculate points
        is_wsx = comp.series == 'WSX'
        sx1_results = []
        sx2_results = []
        
        for r in results:
            # Calculate points: use rider_points if provided (manual entry), otherwise calculate from position
            get_smx_qualification_points = _main().get_smx_qualification_points
            if is_wsx:
                if r.rider_points is not None:
                    points = r.rider_points
                else:
                    points = get_smx_qualification_points(r.position)
            else:
                points = get_smx_qualification_points(r.position)
            
            result_data = {
                "position": r.position,
                "rider_id": r.rider_id,
                "rider_name": r.rider_name,
                "rider_number": r.rider_number,
                "rider_points": r.rider_points,
                "calculated_points": points,
                "class": r.class_name
            }
            
            if r.class_name in ('450cc', 'wsx_sx1'):
                sx1_results.append(result_data)
            elif r.class_name in ('250cc', 'wsx_sx2'):
                sx2_results.append(result_data)
        
        return jsonify({
            "competition": {
                "id": comp.id,
                "name": comp.name,
                "series": comp.series
            },
            "total_results": len(results),
            "sx1_results": sx1_results,
            "sx2_results": sx2_results
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500



@bp.get("/debug_clear_my_picks")
def debug_clear_my_picks():
    """Clear all picks for the current user - for debugging (admin only)"""
    if not is_admin_user():
        return jsonify({"error": "admin_only"}), 403
    if "user_id" not in session:
        return jsonify({"error": "not_logged_in"}), 401
    
    uid = session["user_id"]
    print(f"DEBUG: debug_clear_my_picks called for user {uid}")
    
    # Delete all picks for this user
    deleted_picks = RacePick.query.filter_by(user_id=uid).delete()
    deleted_holeshots = HoleshotPick.query.filter_by(user_id=uid).delete()
    deleted_wildcards = WildcardPick.query.filter_by(user_id=uid).delete()
    
    db.session.commit()
    
    print(f"DEBUG: Deleted {deleted_picks} picks, {deleted_holeshots} holeshots, {deleted_wildcards} wildcards")
    
    return jsonify({
        "message": f"Cleared {deleted_picks} picks, {deleted_holeshots} holeshots, {deleted_wildcards} wildcards",
        "deleted_picks": deleted_picks,
        "deleted_holeshots": deleted_holeshots,
        "deleted_wildcards": deleted_wildcards
    })


@bp.get("/fix_rider_duplicates")
def fix_rider_duplicates():
    """Fix rider duplicates and coast issues"""
    if not is_admin_user():
        return jsonify({"error": "admin_only"}), 403
    
    try:
        # Find all riders with same name
        from sqlalchemy import func
        duplicates = db.session.query(Rider.name, func.count(Rider.id)).group_by(Rider.name).having(func.count(Rider.id) > 1).all()
        
        fixed_count = 0
        for name, count in duplicates:
            print(f"Found {count} riders named {name}")
            # Keep the first one, delete the rest
            riders = Rider.query.filter_by(name=name).all()
            for rider in riders[1:]:  # Keep first, delete rest
                print(f"Deleting duplicate rider: {rider.name} (ID: {rider.id}, class: {rider.class_name})")
                db.session.delete(rider)
                fixed_count += 1
        
        # Fix Seth Hammaker specifically
        seth_riders = Rider.query.filter_by(name='Seth Hammaker').all()
        if len(seth_riders) > 1:
            print(f"Found {len(seth_riders)} Seth Hammaker riders")
            # Keep the 450cc one, delete the 250cc one
            for rider in seth_riders:
                if rider.class_name == '250cc':
                    print(f"Deleting 250cc Seth Hammaker (ID: {rider.id})")
                    db.session.delete(rider)
                    fixed_count += 1
                elif rider.class_name == '450cc':
                    # Make sure he has no coast_250
                    rider.coast_250 = None
                    print(f"Fixed 450cc Seth Hammaker (ID: {rider.id}) - removed coast_250")
        
        db.session.commit()
        return jsonify({"message": f"Fixed {fixed_count} duplicate riders. Seth Hammaker should now be 450cc only."})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@bp.get("/debug_rider_images")
def debug_rider_images():
    """Debug endpoint to check rider images in database"""
    if not is_admin_user():
        return jsonify({"error": "admin_only"}), 403
    
    try:
        # Get all riders with their image_url
        riders = Rider.query.all()
        rider_data = []
        
        for rider in riders:
            # Check if image file exists
            image_exists = False
            if rider.image_url:
                from pathlib import Path
                image_path = Path(f"static/{rider.image_url}")
                image_exists = image_path.exists()
            
            rider_data.append({
                "id": rider.id,
                "name": rider.name,
                "rider_number": rider.rider_number,
                "class_name": rider.class_name,
                "image_url": rider.image_url,
                "image_exists": image_exists,
                "bike_brand": rider.bike_brand
            })
        
        return jsonify({
            "total_riders": len(riders),
            "riders_with_images": len([r for r in rider_data if r["image_url"]]),
            "riders_with_existing_files": len([r for r in rider_data if r["image_exists"]]),
            "riders": rider_data
        })
        
    except Exception as e:
        print(f"Error in debug_rider_images: {e}")
        return jsonify({"error": str(e)}), 500





@bp.get("/debug_my_points")
def debug_my_points():
    """Debug endpoint for current user to check their points"""
    if not _dev_bootstrap_allowed():
        _reject_dev_bootstrap()
    if "user_id" not in session:
        return jsonify({"error": "not_logged_in"}), 401
    
    user_id = session["user_id"]
    user = User.query.get(user_id)
    
    # Get all CompetitionScore entries for this user
    user_scores = CompetitionScore.query.filter_by(user_id=user_id).all()
    
    # Calculate totals
    total_race_points = sum(score.race_points or 0 for score in user_scores)
    total_holeshot_points = sum(score.holeshot_points or 0 for score in user_scores)
    total_wildcard_points = sum(score.wildcard_points or 0 for score in user_scores)
    total_points = total_race_points + total_holeshot_points + total_wildcard_points
    
    # Build detailed breakdown
    score_breakdown = []
    for score in user_scores:
        score_breakdown.append({
            "competition_id": score.competition_id,
            "total_points": score.total_points,
            "race_points": score.race_points,
            "holeshot_points": score.holeshot_points,
            "wildcard_points": score.wildcard_points,
            "is_penalty": score.competition_id is None  # Penalty entries have no competition_id
        })
    
    return jsonify({
        "username": user.username,
        "user_id": user_id,
        "total_points": total_points,
        "race_points": total_race_points,
        "holeshot_points": total_holeshot_points,
        "wildcard_points": total_wildcard_points,
        "score_entries": score_breakdown,
        "entry_count": len(user_scores)
    })


@bp.get("/debug_user_picks/<string:username>/<int:competition_id>")
def debug_user_picks(username: str, competition_id: int):
    """Debug endpoint to check what picks a user has in database"""
    try:
        if not is_admin_user():
            return jsonify({"error": "admin_only"}), 403
        
        # Decode URL-encoded username
        from urllib.parse import unquote
        username = unquote(username)
        
        user = User.query.filter_by(username=username).first()
        if not user:
            return jsonify({"error": f"User '{username}' not found"}), 404
        
        # Get all picks (including duplicates)
        all_picks = RacePick.query.filter_by(user_id=user.id, competition_id=competition_id).all()
        all_holeshots = HoleshotPick.query.filter_by(user_id=user.id, competition_id=competition_id).all()
        
        picks_info = []
        for pick in all_picks:
            rider = Rider.query.get(pick.rider_id)
            picks_info.append({
                "pick_id": pick.pick_id,
                "rider_id": pick.rider_id,
                "rider_name": rider.name if rider else f"Rider {pick.rider_id}",
                "predicted_position": pick.predicted_position
            })
        
        holeshots_info = []
        for hp in all_holeshots:
            rider = Rider.query.get(hp.rider_id)
            holeshots_info.append({
                "id": hp.id,
                "rider_id": hp.rider_id,
                "rider_name": rider.name if rider else f"Rider {hp.rider_id}",
                "class_name": hp.class_name
            })
        
        return jsonify({
            "username": username,
            "user_id": user.id,
            "competition_id": competition_id,
            "total_picks": len(all_picks),
            "total_holeshots": len(all_holeshots),
            "picks": picks_info,
            "holeshots": holeshots_info
        })
    except Exception as e:
        import traceback
        print(f"ERROR in debug_user_picks: {e}")
        print(traceback.format_exc())
        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500


@bp.get("/debug_user_scores/<string:username>")
def debug_user_scores(username):
    """Debug endpoint to check where a user's points come from"""
    if not is_admin_user():
        return jsonify({"error": "admin_only"}), 403
    
    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({"error": "User not found"}), 404
    
    print(f"DEBUG: Checking scores for user {username} (ID: {user.id})")
    
    # Get all CompetitionScore entries for this user
    competition_scores = CompetitionScore.query.filter_by(user_id=user.id).all()
    
    # Get SeasonTeam info
    season_team = SeasonTeam.query.filter_by(user_id=user.id).first()
    
    # Get all picks for this user
    race_picks = RacePick.query.filter_by(user_id=user.id).all()
    holeshot_picks = HoleshotPick.query.filter_by(user_id=user.id).all()
    wildcard_picks = WildcardPick.query.filter_by(user_id=user.id).all()
    
    result = {
        "user": {
            "id": user.id,
            "username": user.username
        },
        "season_team": {
            "team_name": season_team.team_name if season_team else None,
            "total_points": season_team.total_points if season_team else 0
        },
        "competition_scores": [],
        "picks_summary": {
            "race_picks": len(race_picks),
            "holeshot_picks": len(holeshot_picks),
            "wildcard_picks": len(wildcard_picks)
        }
    }
    
    for score in competition_scores:
        comp = Competition.query.get(score.competition_id)
        result["competition_scores"].append({
            "competition_id": score.competition_id,
            "competition_name": comp.name if comp else "Unknown",
            "points": score.total_points
        })
        print(f"DEBUG: {username} has {score.total_points} points from {comp.name if comp else 'Unknown'}")
    
    total_from_scores = sum(s["points"] for s in result["competition_scores"])
    print(f"DEBUG: {username} total from CompetitionScore: {total_from_scores}")
    print(f"DEBUG: {username} SeasonTeam total_points: {season_team.total_points if season_team else 0}")
    
    return jsonify(result)


@bp.get("/fix_league_images")
def fix_league_images():
    """Fix league images by setting them to None if files don't exist (for Render compatibility)"""
    if not is_admin_user():
        return jsonify({"error": "admin_only"}), 403
    
    print("DEBUG: fix_league_images called")
    
    all_leagues = League.query.all()
    fixed_count = 0
    
    for league in all_leagues:
        if league.image_url:
            # Extract filename from URL
            filename = league.image_url.split('/')[-1]
            image_path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
            
            # If image file doesn't exist, clear the image_url
            if not os.path.exists(image_path):
                print(f"DEBUG: Image file missing for league {league.name}, clearing image_url")
                league.image_url = None
                fixed_count += 1
    
    db.session.commit()
    
    return jsonify({
        "message": f"Fixed {fixed_count} leagues with missing images",
        "fixed_count": fixed_count
    })


@bp.get("/fix_my_league_images")
def fix_my_league_images():
    """Fix league images for current user's leagues only"""
    if not _dev_bootstrap_allowed():
        _reject_dev_bootstrap()
    if "user_id" not in session:
        return jsonify({"error": "not_logged_in"}), 401
    
    print("DEBUG: fix_my_league_images called for user", session["user_id"])
    
    # Get user's leagues
    user_leagues = db.session.query(League).join(LeagueMembership).filter(
        LeagueMembership.user_id == session["user_id"]
    ).all()
    
    fixed_count = 0
    
    for league in user_leagues:
        if league.image_url:
            # Extract filename from URL
            filename = league.image_url.split('/')[-1]
            image_path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
            
            # If image file doesn't exist, clear the image_url
            if not os.path.exists(image_path):
                print(f"DEBUG: Image file missing for user's league {league.name}, clearing image_url")
                league.image_url = None
                fixed_count += 1
    
    db.session.commit()
    
    return jsonify({
        "message": f"Fixed {fixed_count} of your leagues with missing images",
        "fixed_count": fixed_count
    })



@bp.get("/fix_league_memberships_column")
def fix_league_memberships_column():
    """Fix missing joined_at column in league_memberships table"""
    if not _dev_bootstrap_allowed():
        _reject_dev_bootstrap()
    try:
        from sqlalchemy import inspect
        
        if inspect(db.engine).has_table('league_memberships'):
            try:
                # Try to query joined_at column
                db.session.execute(db.text("SELECT joined_at FROM league_memberships LIMIT 1"))
                return "joined_at column already exists in league_memberships table"
            except Exception:
                # Column doesn't exist, add it
                try:
                    db.session.rollback()
                    db.session.execute(db.text("ALTER TABLE league_memberships ADD COLUMN joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"))
                    db.session.commit()
                    return "✅ joined_at column added to league_memberships table successfully"
                except Exception as e:
                    db.session.rollback()
                    return f"❌ Error adding joined_at column: {e}"
        else:
            return "league_memberships table doesn't exist"
            
    except Exception as e:
        return f"❌ Error: {e}"





@bp.get("/fix_profile_columns")
def fix_profile_columns():
    """Fix profile columns - no login required for debugging"""
    if not _dev_bootstrap_allowed():
        _reject_dev_bootstrap()
    print("DEBUG: fix_profile_columns called")
    
    try:
        # Rollback any existing transaction first
        db.session.rollback()
        
        # Add missing columns to users table
        columns_to_add = [
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS display_name VARCHAR(100);",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS profile_picture_url TEXT;",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS bio TEXT;",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS favorite_rider VARCHAR(100);",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS favorite_team VARCHAR(100);",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;"
        ]
        
        for sql in columns_to_add:
            try:
                db.session.execute(db.text(sql))
                print(f"DEBUG: Executed: {sql}")
            except Exception as e:
                print(f"DEBUG: Error executing {sql}: {e}")
        
        db.session.commit()
        
        return jsonify({
            "message": "Profile columns added successfully",
            "columns_added": len(columns_to_add)
        })
    except Exception as e:
        print(f"DEBUG: Error adding profile columns: {e}")
        try:
            db.session.rollback()
        except:
            pass
        return jsonify({"error": str(e)}), 500


@bp.get("/fix_profile_picture_column")
def fix_profile_picture_column():
    """Fix profile_picture_url column to support base64 data"""
    if not is_admin_user():
        return jsonify({"error": "admin_only"}), 403


@bp.get("/fix_column_public")
def fix_column_public():
    """Fix profile_picture_url column - no login required for emergency fix"""
    if not _dev_bootstrap_allowed():
        _reject_dev_bootstrap()
    
    try:
        # Rollback any existing transaction first
        db.session.rollback()
        
        # Check if we need to alter the column type
        if 'postgresql' in str(db.engine.url):
            # PostgreSQL syntax - alter column type
            db.session.execute(db.text("ALTER TABLE users ALTER COLUMN profile_picture_url TYPE TEXT;"))
            print("DEBUG: Changed profile_picture_url column to TEXT")
        else:
            # SQLite doesn't support ALTER COLUMN, but TEXT is default anyway
            print("DEBUG: SQLite detected - TEXT is default for profile_picture_url")
        
        db.session.commit()
        
        return jsonify({
            "message": "Profile picture column updated to support base64 data",
            "column_type": "TEXT",
            "status": "success"
        })
    except Exception as e:
        print(f"DEBUG: Error updating column: {e}")
        try:
            db.session.rollback()
        except:
            pass
        return jsonify({"error": str(e), "status": "failed"}), 500


@bp.get("/fix_existing_riders")
def fix_existing_riders():
    """Fix existing riders in database - update names, numbers, and bike brands"""
    if not is_admin_user():
        return jsonify({"error": "admin_only"}), 403
    
    try:
        # Get all riders from database
        all_riders = Rider.query.all()
        fixed_count = 0
        
        for rider in all_riders:
            original_name = rider.name
            fixed_name = original_name
            
            # Fix name duplicates using the same logic as import function
            if len(fixed_name) > 15:  # Likely has duplicate name
                # Find the middle point and look for capital letters
                mid = len(fixed_name) // 2
                for i in range(mid-3, mid+3):
                    if i < len(fixed_name) and fixed_name[i].isupper() and i > 0:
                        # Check if this looks like a duplicate
                        first_part = fixed_name[:i]
                        second_part = fixed_name[i:]
                        if first_part == second_part:
                            fixed_name = first_part
                            break
                        # Also check if second part starts with first part
                        elif second_part.startswith(first_part):
                            fixed_name = first_part
                            break
            
            # Fix word-level duplicates
            words = fixed_name.split()
            if len(words) >= 4:  # At least 4 words suggests duplication
                mid = len(words) // 2
                first_half = words[:mid]
                second_half = words[mid:]
                if first_half == second_half:
                    fixed_name = ' '.join(first_half)
            
            # Remove any remaining obvious duplicates
            if ' ' in fixed_name:
                parts = fixed_name.split(' ')
                if len(parts) >= 2:
                    # Check if first two words repeat
                    if len(parts) >= 4 and parts[0] == parts[2] and parts[1] == parts[3]:
                        fixed_name = f"{parts[0]} {parts[1]}"
                    # Check if the name is just repeated
                    elif len(parts) == 2 and parts[0] == parts[1]:
                        fixed_name = parts[0]
            
            # Update rider if name was fixed
            if fixed_name != original_name:
                rider.name = fixed_name
                fixed_count += 1
            
            # Fix rider number if it's None or 0
            if rider.rider_number is None or rider.rider_number == 0:
                # Generate a reasonable number based on name hash
                import hashlib
                hash_val = int(hashlib.md5(fixed_name.encode()).hexdigest()[:8], 16)
                rider.rider_number = (hash_val % 999) + 1
            
            # Fix bike brand if it's Unknown
            if rider.bike_brand == 'Unknown':
                bike_brands = ['Yamaha', 'Honda', 'Kawasaki', 'KTM', 'Husqvarna', 'GasGas', 'Suzuki']
                import hashlib
                hash_val = int(hashlib.md5(fixed_name.encode()).hexdigest()[:8], 16)
                rider.bike_brand = bike_brands[hash_val % len(bike_brands)]
        
        db.session.commit()
        
        return jsonify({
            "message": f"Fixed {fixed_count} riders with duplicate names and updated all riders with proper numbers and bike brands",
            "total_riders": len(all_riders),
            "fixed_names": fixed_count
        })
        
    except Exception as e:
        print(f"Error fixing existing riders: {e}")
        return jsonify({"error": str(e)}), 500


@bp.get("/fix_rider_coasts")
def fix_rider_coasts():
    """Fix coast assignments for 250cc riders based on point standings 2025.txt"""
    if not is_admin_user():
        return jsonify({"error": "admin_only"}), 403
    
    try:
        # Read point standings file to get correct coast assignments
        with open('point standings 2025.txt', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Parse the data to extract east/west riders
        sections = content.split('\n\n')
        east_riders = []
        west_riders = []
        current_coast = None
        
        for section in sections:
            lines = section.strip().split('\n')
            if not lines:
                continue
                
            # Check if this is a coast header
            if lines[0].lower() in ['250 west', '250 east']:
                current_coast = lines[0].lower().replace('250 ', '')
                continue
            
            # Parse rider data
            if current_coast and len(lines) > 1:
                for line in lines[1:]:  # Skip header line
                    if not line.strip():
                        continue
                        
                    # Parse format: "1	Haiden DeeganHaiden Deegan	Temecula, CAUnited States	221"
                    parts = line.split('\t')
                    if len(parts) >= 4:
                        try:
                            name_part = parts[1]
                            
                            # Clean up name (remove duplicates) - same logic as import
                            name = name_part.strip()
                            if len(name) > 15:  # Likely has duplicate name
                                mid = len(name) // 2
                                for i in range(mid-3, mid+3):
                                    if i < len(name) and name[i].isupper() and i > 0:
                                        first_part = name[:i]
                                        second_part = name[i:]
                                        if first_part == second_part:
                                            name = first_part
                                            break
                                        elif second_part.startswith(first_part):
                                            name = first_part
                                            break
                            
                            # Additional cleanup
                            if name.endswith(name[:len(name)//2]):
                                name = name[:len(name)//2]
                            
                            words = name.split()
                            if len(words) >= 4:
                                mid = len(words) // 2
                                first_half = words[:mid]
                                second_half = words[mid:]
                                if first_half == second_half:
                                    name = ' '.join(first_half)
                            
                            if ' ' in name:
                                parts = name.split(' ')
                                if len(parts) >= 2:
                                    if len(parts) >= 4 and parts[0] == parts[2] and parts[1] == parts[3]:
                                        name = f"{parts[0]} {parts[1]}"
                                    elif len(parts) == 2 and parts[0] == parts[1]:
                                        name = parts[0]
                            
                            # Add to appropriate coast list
                            if current_coast == 'east':
                                east_riders.append(name)
                            elif current_coast == 'west':
                                west_riders.append(name)
                                
                        except (ValueError, IndexError):
                            continue
        
        # Fix East riders
        east_fixed = 0
        for name in east_riders:
            rider = Rider.query.filter_by(name=name, class_name="250cc").first()
            if rider:
                if rider.coast_250 != "east":
                    rider.coast_250 = "east"
                    east_fixed += 1
        
        # Fix West riders  
        west_fixed = 0
        for name in west_riders:
            rider = Rider.query.filter_by(name=name, class_name="250cc").first()
            if rider:
                if rider.coast_250 != "west":
                    rider.coast_250 = "west"
                    west_fixed += 1
        
        # Set remaining 250cc riders to "both" if they don't have coast set
        remaining_fixed = 0
        all_250_riders = Rider.query.filter_by(class_name="250cc").all()
        for rider in all_250_riders:
            if not rider.coast_250:
                rider.coast_250 = "both"
                remaining_fixed += 1
        
        db.session.commit()
        
        return jsonify({
            "message": f"Fixed coast assignments from point standings: {east_fixed} East riders, {west_fixed} West riders, {remaining_fixed} set to 'both'",
            "east_riders_found": len(east_riders),
            "west_riders_found": len(west_riders),
            "east_fixed": east_fixed,
            "west_fixed": west_fixed,
            "remaining_fixed": remaining_fixed,
            "total_250cc": len(all_250_riders)
        })
        
    except Exception as e:
        print(f"Error fixing rider coasts: {e}")
        return jsonify({"error": str(e)}), 500


@bp.get("/debug_rider_coasts")
def debug_rider_coasts():
    """Debug coast assignments for 250cc riders"""
    if not is_admin_user():
        return jsonify({"error": "admin_only"}), 403
    
    try:
        # Get all 250cc riders
        riders_250 = Rider.query.filter_by(class_name="250cc").all()
        
        # Group by coast
        coast_groups = {}
        for rider in riders_250:
            coast = rider.coast_250 or "None"
            if coast not in coast_groups:
                coast_groups[coast] = []
            coast_groups[coast].append(f"{rider.name} (#{rider.rider_number})")
        
        # Check specific riders
        tom_vialle = Rider.query.filter_by(name="Tom Vialle", class_name="250cc").first()
        haiden_deegan = Rider.query.filter_by(name="Haiden Deegan", class_name="250cc").first()
        
        result = f"""
        <h1>250cc Rider Coast Debug</h1>
        <p><strong>Total 250cc riders:</strong> {len(riders_250)}</p>
        
        <h2>Coast Distribution:</h2>
        """
        
        for coast, riders in coast_groups.items():
            result += f"<h3>{coast}: {len(riders)} riders</h3><ul>"
            for rider in riders[:10]:  # Show first 10
                result += f"<li>{rider}</li>"
            if len(riders) > 10:
                result += f"<li>... and {len(riders) - 10} more</li>"
            result += "</ul>"
        
        result += f"""
        <h2>Specific Riders:</h2>
        <p><strong>Tom Vialle:</strong> {tom_vialle.coast_250 if tom_vialle else 'Not found'}</p>
        <p><strong>Haiden Deegan:</strong> {haiden_deegan.coast_250 if haiden_deegan else 'Not found'}</p>
        """
        
        return result
        
    except Exception as e:
        return f"Error: {str(e)}", 500


@bp.get("/fix_column_now")
def fix_column_now():
    """Emergency fix for profile picture column - no login required"""
    if not _dev_bootstrap_allowed():
        _reject_dev_bootstrap()
    try:
        # Rollback any existing transaction first
        db.session.rollback()
        
        # Check if we need to alter the column type
        if 'postgresql' in str(db.engine.url):
            # PostgreSQL syntax - alter column type
            db.session.execute(db.text("ALTER TABLE users ALTER COLUMN profile_picture_url TYPE TEXT;"))
            print("DEBUG: Changed profile_picture_url column to TEXT")
            db.session.commit()
            return jsonify({
                "message": "Profile picture column updated to TEXT - base64 images will now work!",
                "status": "success"
            })
        else:
            return jsonify({
                "message": "SQLite detected - TEXT is default, column should already support base64",
                "status": "info"
            })
    except Exception as e:
        print(f"DEBUG: Error updating column: {e}")
        try:
            db.session.rollback()
        except:
            pass
        return jsonify({"error": str(e), "status": "failed"}), 500
        
        # Add missing columns to users table
        columns_to_add = [
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS display_name VARCHAR(100);",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS profile_picture_url TEXT;",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS bio TEXT;",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS favorite_rider VARCHAR(100);",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS favorite_team VARCHAR(100);",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;"
        ]
        
        for sql in columns_to_add:
            try:
                db.session.execute(db.text(sql))
                print(f"DEBUG: Executed: {sql}")
            except Exception as e:
                print(f"DEBUG: Error executing {sql}: {e}")
        
        db.session.commit()
        
        return jsonify({
            "message": "Profile columns added successfully",
            "columns_added": len(columns_to_add)
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"DEBUG: Error adding profile columns: {e}")
        return jsonify({
            "error": f"Failed to add profile columns: {str(e)}"
        }), 500


@bp.get("/fix_missing_images")
def fix_missing_images():
    """Fix missing rider images by clearing invalid image_urls"""
    if not is_admin_user():
        return jsonify({"error": "admin_only"}), 403
    
    print("DEBUG: fix_missing_images called")
    
    try:
        riders = Rider.query.all()
        fixed_count = 0
        
        for rider in riders:
            if rider.image_url:
                # Check if image file exists
                image_path = os.path.join(current_app.static_folder, rider.image_url)
                if not os.path.exists(image_path):
                    print(f"DEBUG: Image file missing for {rider.name}: {rider.image_url}")
                    rider.image_url = None
                    fixed_count += 1
        
        db.session.commit()
        
        return jsonify({
            "message": f"Fixed {fixed_count} riders with missing images",
            "fixed_count": fixed_count
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"DEBUG: Error fixing missing images: {e}")
        return jsonify({
            "error": f"Failed to fix missing images: {str(e)}"
        }), 500


@bp.get("/create_user_now")
def create_user_now_route():
    """Create user immediately"""
    if not _dev_bootstrap_allowed():
        _reject_dev_bootstrap()
    try:
        # Create test user
        existing_user = User.query.filter_by(username='test').first()
        if existing_user:
            return f"User 'test' already exists with ID {existing_user.id}"
        
        test_user = User(
            username='test',
            password_hash=generate_password_hash('password')
        )
        
        db.session.add(test_user)
        db.session.commit()
        
        return f"""
        <h1>User Created!</h1>
        <p>Username: test</p>
        <p>Password: password</p>
        <p><a href="/login">Go to Login</a></p>
        """
    except Exception as e:
        return f"<h1>Error:</h1><p>{str(e)}</p>"


@bp.get("/create_test2_user")
def create_test2_user_route():
    """Create test2 user"""
    if not _dev_bootstrap_allowed():
        _reject_dev_bootstrap()
    try:
        # Create test2 user
        existing_user = User.query.filter_by(username='test2').first()
        if existing_user:
            return f"User 'test2' already exists with ID {existing_user.id}"
        
        test2_user = User(
            username='test2',
            password_hash=generate_password_hash('password')
        )
        
        db.session.add(test2_user)
        db.session.commit()
        
        return f"""
        <h1>User Created!</h1>
        <p>Username: test2</p>
        <p>Password: password</p>
        <p><a href="/login">Go to Login</a></p>
        """
    except Exception as e:
        return f"<h1>Error:</h1><p>{str(e)}</p>"


@bp.get("/fix_user_roles")
def fix_user_roles_route():
    """Fix user roles - test=admin, test2=normal user"""
    if not _dev_bootstrap_allowed():
        _reject_dev_bootstrap()
    try:
        # Update test user (admin)
        test_user = User.query.filter_by(username='test').first()
        if test_user:
            test_user.password_hash = generate_password_hash('password')
            db.session.commit()
            test_msg = "Updated test user (admin) with password 'password'"
        else:
            test_user = User(
                username='test',
                password_hash=generate_password_hash('password'),
                email='test@example.com'
            )
            db.session.add(test_user)
            db.session.commit()
            test_msg = "Created test user (admin) with password 'password'"
        
        # Update test2 user (normal)
        test2_user = User.query.filter_by(username='test2').first()
        if test2_user:
            test2_user.password_hash = generate_password_hash('password')
            db.session.commit()
            test2_msg = "Updated test2 user (normal) with password 'password'"
        else:
            test2_user = User(
                username='test2',
                password_hash=generate_password_hash('password'),
                email='test2@example.com'
            )
            db.session.add(test2_user)
            db.session.commit()
            test2_msg = "Created test2 user (normal) with password 'password'"
        
        return f"""
        <h1>User Roles Fixed!</h1>
        <p><strong>Admin User:</strong></p>
        <p>Username: test</p>
        <p>Password: password</p>
        <p>Role: Admin (can access admin page)</p>
        <p>{test_msg}</p>
        <br>
        <p><strong>Normal User:</strong></p>
        <p>Username: test2</p>
        <p>Password: password</p>
        <p>Role: Normal user</p>
        <p>{test2_msg}</p>
        <br>
        <p><a href="/login">Go to Login</a></p>
        """
    except Exception as e:
        return f"<h1>Error:</h1><p>{str(e)}</p>"



@bp.get("/force_create_users")
def force_create_users_route():
    """Force create users - delete and recreate"""
    if not _dev_bootstrap_allowed():
        _reject_dev_bootstrap()
    try:
        # Delete existing users
        User.query.filter(User.username.in_(['test', 'test2'])).delete()
        db.session.commit()
        
        # Create test user (admin)
        test_user = User(
            username='test',
            password_hash=generate_password_hash('password')
        )
        db.session.add(test_user)
        
        # Create test2 user (normal)
        test2_user = User(
            username='test2',
            password_hash=generate_password_hash('password')
        )
        db.session.add(test2_user)
        
        db.session.commit()
        
        # Verify creation
        created_test = User.query.filter_by(username='test').first()
        created_test2 = User.query.filter_by(username='test2').first()
        
        return f"""
        <h1>Users Force Created!</h1>
        <p><strong>Admin User:</strong></p>
        <p>Username: test</p>
        <p>Password: password</p>
        <p>ID: {created_test.id if created_test else 'ERROR'}</p>
        <br>
        <p><strong>Normal User:</strong></p>
        <p>Username: test2</p>
        <p>Password: password</p>
        <p>ID: {created_test2.id if created_test2 else 'ERROR'}</p>
        <br>
        <p><strong>Total users in database:</strong> {User.query.count()}</p>
        <br>
        <p><a href="/login">Go to Login</a></p>
        """
    except Exception as e:
        return f"<h1>Error:</h1><p>{str(e)}</p>"


@bp.get("/fix_database")
def fix_database_route():
    """Fix database by creating all tables and data"""
    if not _dev_bootstrap_allowed():
        _reject_dev_bootstrap()
    try:
        # Create all tables
        db.create_all()
        
        # Create test user
        existing_user = User.query.filter_by(username='test').first()
        if not existing_user:
            test_user = User(
                username='test',
                password_hash=generate_password_hash('password'),
                email='test@example.com'
            )
            db.session.add(test_user)
            db.session.commit()
        
        # Create competitions
        Competition.query.delete()
        competitions = [
            {'name': 'Anaheim 1', 'event_date': '2026-01-04', 'coast_250': 'west', 'series': 'SX', 'point_multiplier': 1.0},
            {'name': 'San Diego', 'event_date': '2026-01-11', 'coast_250': 'west', 'series': 'SX', 'point_multiplier': 1.0},
            {'name': 'Anaheim 2', 'event_date': '2026-01-18', 'coast_250': 'west', 'series': 'SX', 'point_multiplier': 1.0},
            {'name': 'Houston', 'event_date': '2026-01-25', 'coast_250': 'west', 'series': 'SX', 'point_multiplier': 1.0},
            {'name': 'Tampa', 'event_date': '2026-02-01', 'coast_250': 'east', 'series': 'SX', 'point_multiplier': 1.0}
        ]
        
        for comp_data in competitions:
            comp = Competition(
                name=comp_data['name'],
                event_date=datetime.strptime(comp_data['event_date'], '%Y-%m-%d').date(),
                coast_250=comp_data['coast_250'],
                series=comp_data['series'],
                point_multiplier=comp_data['point_multiplier'],
                is_triple_crown=comp_data.get('is_triple_crown', False)
            )
            db.session.add(comp)
        
        # Don't create riders here - use rider management as master list
        # Riders should only be created/updated through rider management interface
        print('DEBUG: Skipping rider creation - use rider management interface instead')
        
        
        db.session.commit()
        
        return f"""
        <h1>Database Fixed!</h1>
        <p>Created all tables and data successfully!</p>
        <p><strong>Competitions:</strong> {len(competitions)}</p>
        <p><strong>Riders:</strong> {len(all_riders)}</p>
        <p><strong>Sim Date:</strong> 2026-10-06</p>
        <p><a href="/admin">Go to Admin</a></p>
        """
    except Exception as e:
        return f"<h1>Error:</h1><p>{str(e)}</p>"


@bp.get("/create_test_user")
def create_test_user_route():
    """Create test user and all data via web route"""
    if not _dev_bootstrap_allowed():
        _reject_dev_bootstrap()
    # Create test user
    existing_user = User.query.filter_by(username='test').first()
    if not existing_user:
        test_user = User(
            username='test',
            password_hash=generate_password_hash('password')
        )
        db.session.add(test_user)
        db.session.commit()
    
    # Create competitions if they don't exist
    if Competition.query.count() == 0:
        competitions = [
            {'name': 'Anaheim 1', 'event_date': '2026-01-04', 'coast_250': 'west', 'series': 'SX', 'point_multiplier': 1.0},
            {'name': 'San Diego', 'event_date': '2026-01-11', 'coast_250': 'west', 'series': 'SX', 'point_multiplier': 1.0},
            {'name': 'Anaheim 2', 'event_date': '2026-01-18', 'coast_250': 'west', 'series': 'SX', 'point_multiplier': 1.0},
            {'name': 'Houston', 'event_date': '2026-01-25', 'coast_250': 'west', 'series': 'SX', 'point_multiplier': 1.0},
            {'name': 'Tampa', 'event_date': '2026-02-01', 'coast_250': 'east', 'series': 'SX', 'point_multiplier': 1.0}
        ]
        
        for comp_data in competitions:
            comp = Competition(
                name=comp_data['name'],
                event_date=datetime.strptime(comp_data['event_date'], '%Y-%m-%d').date(),
                coast_250=comp_data['coast_250'],
                series=comp_data['series'],
                point_multiplier=comp_data['point_multiplier'],
                is_triple_crown=comp_data.get('is_triple_crown', False)
            )
            db.session.add(comp)
        db.session.commit()
    
    # Don't create riders here - use rider management as master list
    # Riders should only be created/updated through rider management interface
    print("DEBUG: Skipping rider creation in create_test_data - use rider management interface instead")
    if False:  # Never create riders here
        riders_450 = [
            {'name': 'Eli Tomac', 'class_name': '450cc', 'bike_brand': 'Yamaha', 'rider_number': 3},
            {'name': 'Cooper Webb', 'class_name': '450cc', 'bike_brand': 'KTM', 'rider_number': 2},
            {'name': 'Chase Sexton', 'class_name': '450cc', 'bike_brand': 'Honda', 'rider_number': 4},
            {'name': 'Aaron Plessinger', 'class_name': '450cc', 'bike_brand': 'KTM', 'rider_number': 7},
            {'name': 'Jett Lawrence', 'class_name': '450cc', 'bike_brand': 'Honda', 'rider_number': 18},
            {'name': 'Kyle Chisholm', 'class_name': '450cc', 'bike_brand': 'Yamaha', 'rider_number': 11},
            {'name': 'Shane McElrath', 'class_name': '450cc', 'bike_brand': 'Yamaha', 'rider_number': 12},
            {'name': 'Dylan Ferrandis', 'class_name': '450cc', 'bike_brand': 'Honda', 'rider_number': 14},
            {'name': 'Dean Wilson', 'class_name': '450cc', 'bike_brand': 'Honda', 'rider_number': 15},
            {'name': 'Tom Vialle', 'class_name': '450cc', 'bike_brand': 'KTM', 'rider_number': 16},
            {'name': 'Joey Savatgy', 'class_name': '450cc', 'bike_brand': 'Kawasaki', 'rider_number': 17},
            {'name': 'Jason Anderson', 'class_name': '450cc', 'bike_brand': 'Kawasaki', 'rider_number': 21},
            {'name': 'Malcolm Stewart', 'class_name': '450cc', 'bike_brand': 'Husqvarna', 'rider_number': 27},
            {'name': 'Christian Craig', 'class_name': '450cc', 'bike_brand': 'Husqvarna', 'rider_number': 28},
            {'name': 'Justin Barcia', 'class_name': '450cc', 'bike_brand': 'GasGas', 'rider_number': 51},
            {'name': 'Max Anstie', 'class_name': '450cc', 'bike_brand': 'Honda', 'rider_number': 37},
            {'name': 'Haiden Deegan', 'class_name': '450cc', 'bike_brand': 'Yamaha', 'rider_number': 38},
            {'name': 'Pierce Brown', 'class_name': '450cc', 'bike_brand': 'GasGas', 'rider_number': 39},
            {'name': 'Dilan Schwartz', 'class_name': '450cc', 'bike_brand': 'KTM', 'rider_number': 40},
            {'name': 'Derek Kelley', 'class_name': '450cc', 'bike_brand': 'KTM', 'rider_number': 41},
            {'name': 'Seth Hammaker', 'class_name': '450cc', 'bike_brand': 'Kawasaki', 'rider_number': 43},
            {'name': 'Justin Hill', 'class_name': '450cc', 'bike_brand': 'KTM', 'rider_number': 44},
            {'name': 'Colt Nichols', 'class_name': '450cc', 'bike_brand': 'Beta', 'rider_number': 45},
            {'name': 'Fredrik Noren', 'class_name': '450cc', 'bike_brand': 'KTM', 'rider_number': 46},
            {'name': 'Levi Kitchen', 'class_name': '450cc', 'bike_brand': 'Kawasaki', 'rider_number': 47},
            {'name': 'Chance Hymas', 'class_name': '450cc', 'bike_brand': 'Honda', 'rider_number': 48},
            {'name': 'Enzo Lopes', 'class_name': '450cc', 'bike_brand': 'Yamaha', 'rider_number': 50},
            {'name': 'Justin Barcia', 'class_name': '450cc', 'bike_brand': 'GasGas', 'rider_number': 51},
            {'name': 'Cullin Park', 'class_name': '450cc', 'bike_brand': 'Yamaha', 'rider_number': 53},
            {'name': 'Mitchell Oldenburg', 'class_name': '450cc', 'bike_brand': 'Honda', 'rider_number': 54},
            {'name': 'Nate Thrasher', 'class_name': '450cc', 'bike_brand': 'Yamaha', 'rider_number': 57},
            {'name': 'Daxton Bennick', 'class_name': '450cc', 'bike_brand': 'Yamaha', 'rider_number': 59},
            {'name': 'Robbie Wageman', 'class_name': '450cc', 'bike_brand': 'Honda', 'rider_number': 59},
            {'name': 'Benny Bloss', 'class_name': '450cc', 'bike_brand': 'Beta', 'rider_number': 60},
            {'name': 'Justin Starling', 'class_name': '450cc', 'bike_brand': 'GasGas', 'rider_number': 60},
            {'name': 'Austin Forkner', 'class_name': '450cc', 'bike_brand': 'Kawasaki', 'rider_number': 64},
            {'name': 'Vince Friese', 'class_name': '450cc', 'bike_brand': 'Honda', 'rider_number': 64},
            {'name': 'Jerry Robin', 'class_name': '450cc', 'bike_brand': 'Yamaha', 'rider_number': 67},
            {'name': 'Stilez Robertson', 'class_name': '450cc', 'bike_brand': 'Yamaha', 'rider_number': 67},
            {'name': 'Joshua Cartwright', 'class_name': '450cc', 'bike_brand': 'Kawasaki', 'rider_number': 69},
            {'name': 'Hardy Munoz', 'class_name': '450cc', 'bike_brand': 'KTM', 'rider_number': 72},
            {'name': 'Ryder DiFrancesco', 'class_name': '450cc', 'bike_brand': 'Kawasaki', 'rider_number': 75},
            {'name': 'Mitchell Harrison', 'class_name': '450cc', 'bike_brand': 'Yamaha', 'rider_number': 79},
            {'name': 'Cade Clason', 'class_name': '450cc', 'bike_brand': 'Honda', 'rider_number': 81},
            {'name': 'Hunter Yoder', 'class_name': '450cc', 'bike_brand': 'KTM', 'rider_number': 85},
            {'name': 'Ken Roczen', 'class_name': '450cc', 'bike_brand': 'Suzuki', 'rider_number': 94},
            {'name': 'Hunter Lawrence', 'class_name': '450cc', 'bike_brand': 'Honda', 'rider_number': 96},
            {'name': 'Anthony Rodriguez', 'class_name': '450cc', 'bike_brand': 'KTM', 'rider_number': 100},
            {'name': 'Grant Harlan', 'class_name': '450cc', 'bike_brand': 'Yamaha', 'rider_number': 109},
            {'name': 'Jett Reynolds', 'class_name': '450cc', 'bike_brand': 'Yamaha', 'rider_number': 124},
            {'name': 'Ryan Breece', 'class_name': '450cc', 'bike_brand': 'Yamaha', 'rider_number': 200},
            {'name': 'Nick Romano', 'class_name': '450cc', 'bike_brand': 'Yamaha', 'rider_number': 511},
            {'name': 'Julien Beaumer', 'class_name': '450cc', 'bike_brand': 'KTM', 'rider_number': 929}
        ]
        
        # Get riders from database instead of hardcoded list
        riders_250 = []
        db_riders_250 = Rider.query.filter_by(class_name='250cc').all()
        for rider in db_riders_250:
            riders_250.append({
                'name': rider.name,
                'class_name': rider.class_name,
                'bike_brand': rider.bike_brand,
                'rider_number': rider.rider_number,
                'coast_250': rider.coast_250
            })
        
        all_riders = riders_450 + riders_250
        for rider_data in all_riders:
            rider = Rider(
                name=rider_data['name'],
                class_name=rider_data['class_name'],
                rider_number=rider_data.get('rider_number'),
                bike_brand=rider_data['bike_brand'],
                price=rider_data.get('price', 50),  # Default price if not specified
                image_url=rider_data.get('image_url', f"riders/{rider_data['rider_number']}_{rider_data['name'].lower().replace(' ', '_')}.png"),
                coast_250=rider_data.get('coast_250')
            )
            db.session.add(rider)
        db.session.commit()
    
    # Count what we have
    comp_count = Competition.query.count()
    rider_count = Rider.query.count()
    user_count = User.query.count()
    
    return f"""
    <h1>Data Created!</h1>
    <p><strong>Users:</strong> {user_count}</p>
    <p><strong>Competitions:</strong> {comp_count}</p>
    <p><strong>Riders:</strong> {rider_count}</p>
    <p><a href="/admin">Go to Admin</a></p>
    """


@bp.get("/create_test_data")
def create_test_data_route():
    """Manually create test data - useful for development"""
    if not _dev_bootstrap_allowed():
        _reject_dev_bootstrap()
    if not is_admin_user():
        return redirect(url_for("login"))
    
    try:
        with current_app.app_context():
            # Check if data already exists
            user_count = User.query.count()
            competition_count = Competition.query.count()
            rider_count = Rider.query.count()
            
            if user_count > 0 or competition_count > 0 or rider_count > 0:
                return f"""
                <h1>Data Already Exists</h1>
                <p>Database has {user_count} users, {competition_count} competitions, and {rider_count} riders.</p>
                <p><a href="/admin">Go to Admin</a></p>
                <p><a href="/force_recreate_data">Force Recreate All Data</a></p>
                """
            
            # Create test data
            _main().create_test_data()
            return """
            <h1>Test Data Created Successfully!</h1>
            <p>Test user, competitions, and riders have been created.</p>
            <p><a href="/admin">Go to Admin</a></p>
            """
    except Exception as e:
        return f"""
        <h1>Error Creating Test Data</h1>
        <p>Error: {e}</p>
        <p><a href="/admin">Go to Admin</a></p>
        """


@bp.get("/debug_riders")
def debug_riders():
    """Debug riders in database"""
    if not _dev_bootstrap_allowed():
        _reject_dev_bootstrap()
    if "user_id" not in session:
        return _redirect_to_login()
    
    try:
        all_riders = Rider.query.all()
        riders_450 = [r for r in all_riders if r.class_name == '450cc']
        riders_250 = [r for r in all_riders if r.class_name == '250cc']
        
        result = f"""
        <h1>Riders Debug</h1>
        <p><strong>Total riders:</strong> {len(all_riders)}</p>
        <p><strong>450cc riders:</strong> {len(riders_450)}</p>
        <p><strong>250cc riders:</strong> {len(riders_250)}</p>
        
        <h2>450cc Riders (first 10):</h2>
        <ul>
        """
        
        for rider in riders_450[:10]:
            result += f"<li>{rider.name} (#{rider.rider_number}) - {rider.bike_brand} - ${rider.price}</li>"
        
        result += "</ul>"
        
        result += """
        <h2>250cc Riders (first 10):</h2>
        <ul>
        """
        
        for rider in riders_250[:10]:
            result += f"<li>{rider.name} (#{rider.rider_number}) - {rider.bike_brand} - ${rider.price} - {rider.coast_250}</li>"
        
        result += "</ul>"
        
        return result
        
    except Exception as e:
        return f"Error: {str(e)}", 500


@bp.get("/debug_users")
def debug_users():
    """Debug route to check which users exist — admin only"""
    if not is_admin_user():
        _reject_dev_bootstrap()
    try:
        users = User.query.all()
        user_list = []
        for user in users:
            user_list.append({
                "id": user.id,
                "username": user.username,
                "display_name": getattr(user, 'display_name', None)
            })
        
        return f"""
        <h1>Users in Database</h1>
        <p>Total users: {len(users)}</p>
        <ul>
        {''.join([f'<li>ID {u["id"]}: {u["username"]} (display: {u["display_name"]})</li>' for u in user_list])}
        </ul>
        """
        
    except Exception as e:
        return f"Error: {str(e)}"


@bp.get("/debug_csv_row/<int:competition_id>/<int:row_number>")
def debug_csv_row(competition_id, row_number):
    """Debug specific CSV row for a competition"""
    if not is_admin_user():
        return jsonify({"error": "admin_only"}), 403
    
    try:
        # Find the competition
        competition = Competition.query.get(competition_id)
        if not competition:
            return jsonify({"error": "Competition not found"}), 404
        
        # Look for CSV files in data directory
        import os
        import glob
        
        csv_files = glob.glob("data/results_*anaheim2*.csv")
        
        result = {
            "competition": {
                "id": competition.id,
                "name": competition.name
            },
            "row_number": row_number,
            "csv_files": [],
            "row_contents": {}
        }
        
        for csv_file in csv_files:
            result["csv_files"].append(csv_file)
            
            try:
                with open(csv_file, 'r', encoding='utf-8') as file:
                    lines = file.readlines()
                
                if row_number <= len(lines):
                    line_content = lines[row_number - 1].strip()
                    result["row_contents"][csv_file] = {
                        "line_number": row_number,
                        "content": line_content,
                        "length": len(line_content),
                        "is_empty": len(line_content) == 0,
                        "starts_with_quote": line_content.startswith('"'),
                        "ends_with_quote": line_content.endswith('"')
                    }
                else:
                    result["row_contents"][csv_file] = {
                        "error": f"Row {row_number} does not exist (file has {len(lines)} lines)"
                    }
                    
            except Exception as e:
                result["row_contents"][csv_file] = {
                    "error": str(e)
                }
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.get("/debug_competitions")
def debug_competitions():
    """List all competitions with their IDs"""
    if not _dev_bootstrap_allowed():
        _reject_dev_bootstrap()
    try:
        competitions = Competition.query.order_by(Competition.event_date.asc()).all()
        
        comp_data = []
        for comp in competitions:
            comp_data.append({
                "id": comp.id,
                "name": comp.name,
                "date": comp.event_date.isoformat() if comp.event_date else None,
                "series": comp.series
            })
        
        return jsonify({
            "competitions": comp_data,
            "total": len(comp_data)
        })
        
    except Exception as e:
        return jsonify({"error": str(e)})


@bp.get("/debug_wildcard/<int:competition_id>")
def debug_wildcard(competition_id):
    """Debug wildcard picks and results for a competition"""
    if not _dev_bootstrap_allowed():
        _reject_dev_bootstrap()
    try:
        # Get competition
        competition = Competition.query.get(competition_id)
        if not competition:
            return jsonify({"error": "Competition not found"})
        
        # Get all wildcard picks for this competition
        wildcard_picks = WildcardPick.query.filter_by(competition_id=competition_id).all()
        
        # Get all results for this competition
        results = CompetitionResult.query.filter_by(competition_id=competition_id).all()
        
        # Get rider names
        wildcard_data = []
        for wc in wildcard_picks:
            rider = Rider.query.get(wc.rider_id)
            wildcard_data.append({
                "user_id": wc.user_id,
                "rider_id": wc.rider_id,
                "rider_name": rider.name if rider else "Unknown",
                "rider_number": rider.rider_number if rider else "Unknown",
                "predicted_position": wc.position
            })
        
        # Get actual results at each position
        results_data = []
        for result in results:
            rider = Rider.query.get(result.rider_id)
            results_data.append({
                "position": result.position,
                "rider_id": result.rider_id,
                "rider_name": rider.name if rider else "Unknown",
                "rider_number": rider.rider_number if rider else "Unknown"
            })
        
        # Check wildcard matches
        matches = []
        for wc in wildcard_data:
            actual_result = next((r for r in results_data if r["position"] == wc["predicted_position"]), None)
            if actual_result:
                is_match = actual_result["rider_id"] == wc["rider_id"]
                matches.append({
                    "user_id": wc["user_id"],
                    "predicted": f"#{wc['rider_number']} {wc['rider_name']} at position {wc['predicted_position']}",
                    "actual": f"#{actual_result['rider_number']} {actual_result['rider_name']} at position {actual_result['position']}",
                    "is_match": is_match
                })
        
        return jsonify({
            "competition": {
                "id": competition.id,
                "name": competition.name
            },
            "wildcard_picks": wildcard_data,
            "actual_results": results_data,
            "wildcard_matches": matches
        })
        
    except Exception as e:
        return jsonify({"error": str(e)})


@bp.get("/debug_database")
def debug_database():
    """Debug database configuration and status"""
    if not is_admin_user():
        _reject_dev_bootstrap()
    
    try:
        with current_app.app_context():
            # Database info
            db_uri = current_app.config['SQLALCHEMY_DATABASE_URI']
            db_type = "PostgreSQL" if "postgresql" in db_uri else "SQLite"
            is_memory = ":memory:" in db_uri
            is_render = bool(os.getenv('RENDER'))
            has_database_url = bool(os.getenv('DATABASE_URL'))
            
            # Check if tables exist
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            
            # Count records in each table
            table_counts = {}
            for table in tables:
                try:
                    result = db.session.execute(db.text(f"SELECT COUNT(*) FROM {table}"))
                    count = result.scalar()
                    table_counts[table] = count
                except Exception as e:
                    table_counts[table] = f"Error: {e}"
            
            # Check specific data for Anaheim 1 (competition_id = 1)
            anaheim1_results = CompetitionResult.query.filter_by(competition_id=1).all()
            anaheim1_holeshots = HoleshotResult.query.filter_by(competition_id=1).all()
            anaheim1_scores = CompetitionScore.query.filter_by(competition_id=1).all()
            anaheim1_picks = RacePick.query.filter_by(competition_id=1).all()
            anaheim1_holeshot_picks = HoleshotPick.query.filter_by(competition_id=1).all()
            anaheim1_wildcard_picks = WildcardPick.query.filter_by(competition_id=1).all()
            
            return f"""
            <h1>Database Debug Information</h1>
            <h2>Configuration:</h2>
            <p><strong>Database Type:</strong> {db_type}</p>
            <p><strong>Database URI:</strong> {db_uri}</p>
            <p><strong>Is Memory Database:</strong> {is_memory}</p>
            <p><strong>Running on Render:</strong> {is_render}</p>
            <p><strong>Has DATABASE_URL:</strong> {has_database_url}</p>
            
            <h2>Tables ({len(tables)}):</h2>
            <ul>
            {''.join([f'<li><strong>{table}:</strong> {table_counts.get(table, "Unknown")} records</li>' for table in tables])}
            </ul>
            
            <h2>Anaheim 1 (Competition ID 1) Data:</h2>
            <ul>
            <li><strong>Results:</strong> {len(anaheim1_results)} records</li>
            <li><strong>Holeshot Results:</strong> {len(anaheim1_holeshots)} records</li>
            <li><strong>Scores:</strong> {len(anaheim1_scores)} records</li>
            <li><strong>Race Picks:</strong> {len(anaheim1_picks)} records</li>
            <li><strong>Holeshot Picks:</strong> {len(anaheim1_holeshot_picks)} records</li>
            <li><strong>Wildcard Picks:</strong> {len(anaheim1_wildcard_picks)} records</li>
            </ul>
            
            <h2>Environment Variables:</h2>
            <p><strong>RENDER:</strong> {os.getenv('RENDER', 'Not set')}</p>
            <p><strong>DATABASE_URL:</strong> {'Set' if os.getenv('DATABASE_URL') else 'Not set'}</p>
            <p><strong>FLASK_ENV:</strong> {os.getenv('FLASK_ENV', 'Not set')}</p>
            
            <hr>
            <p><a href="/admin">Go to Admin</a></p>
            <p><a href="/">Go to Home</a></p>
            <p><a href="/force_recreate_data">Force Recreate All Data</a></p>
            """
    except Exception as e:
        return f"<h1>Error</h1><p>{e}</p>"


@bp.route("/fix_bulletin_columns")
def fix_bulletin_columns():
    """Fix missing columns in bulletin_posts table"""
    if not _dev_bootstrap_allowed():
        _reject_dev_bootstrap()
    if session.get('username') != 'test':
        return jsonify({"error": "admin_only"}), 403
    
    try:
        # Add missing columns to bulletin_posts table
        with db.engine.connect() as conn:
            conn.execute(db.text("ALTER TABLE bulletin_posts ADD COLUMN IF NOT EXISTS category VARCHAR(20) DEFAULT 'general'"))
            conn.execute(db.text("ALTER TABLE bulletin_posts ADD COLUMN IF NOT EXISTS parent_id INTEGER REFERENCES bulletin_posts(id)"))
            
            # Create bulletin_reactions table if it doesn't exist
            conn.execute(db.text("""
                CREATE TABLE IF NOT EXISTS bulletin_reactions (
                    id SERIAL PRIMARY KEY,
                    post_id INTEGER NOT NULL REFERENCES bulletin_posts(id),
                    user_id INTEGER NOT NULL REFERENCES users(id),
                    emoji VARCHAR(10) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(post_id, user_id, emoji)
                )
            """))
            conn.commit()
        
        return jsonify({
            "message": "Bulletin board columns fixed!",
            "added_columns": ["category", "parent_id"],
            "created_table": "bulletin_reactions"
        })
        
    except Exception as e:
        print(f"Error fixing bulletin columns: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route("/fix_database_transaction")
def fix_database_transaction():
    """Fix failed database transactions"""
    if not _dev_bootstrap_allowed():
        _reject_dev_bootstrap()
    try:
        # Rollback any failed transactions
        db.session.rollback()
        
        # Test the connection
        db.session.execute(db.text("SELECT 1"))
        db.session.commit()
        
        return jsonify({
            "message": "Database transaction fixed successfully",
            "status": "fixed"
        })
        
    except Exception as e:
        print(f"Error fixing database transaction: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route("/fix_mx_coast_250")
def fix_mx_coast_250():
    """Fix coast_250 for existing Motocross competitions to 'both'"""
    try:
        if not is_admin_user():
            return jsonify({"error": "admin_only"}), 403
        
        # Update all MX competitions to have coast_250 = "both"
        mx_competitions = Competition.query.filter_by(series="MX").all()
        updated_count = 0
        
        for comp in mx_competitions:
            if comp.coast_250 != "both":
                comp.coast_250 = "both"
                updated_count += 1
        
        db.session.commit()
        
        return jsonify({
            "message": f"Updated {updated_count} Motocross competitions to coast_250='both'",
            "updated_count": updated_count,
            "total_mx_competitions": len(mx_competitions)
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@bp.route("/fix_duplicate_results")
def fix_duplicate_results():
    """Fix duplicate CompetitionResult entries for the same rider in the same competition"""
    try:
        if not is_admin_user():
            return jsonify({"error": "admin_only"}), 403
        
        from sqlalchemy import func
        
        # Find duplicate results (same competition_id and rider_id)
        duplicates = (
            db.session.query(
                CompetitionResult.competition_id,
                CompetitionResult.rider_id,
                func.count(CompetitionResult.result_id).label('count')
            )
            .group_by(CompetitionResult.competition_id, CompetitionResult.rider_id)
            .having(func.count(CompetitionResult.result_id) > 1)
            .all()
        )
        
        fixed_count = 0
        for comp_id, rider_id, count in duplicates:
            # Get all results for this competition/rider combination
            results = CompetitionResult.query.filter_by(
                competition_id=comp_id, 
                rider_id=rider_id
            ).order_by(CompetitionResult.result_id.desc()).all()
            
            # Keep the most recent one (highest result_id), delete the rest
            for result in results[1:]:
                db.session.delete(result)
                fixed_count += 1
        
        db.session.commit()
        
        return jsonify({
            "message": f"Fixed {fixed_count} duplicate results",
            "duplicates_found": len(duplicates)
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@bp.route("/fix_duplicate_scores")
def fix_duplicate_scores():
    """Fix duplicate CompetitionScore entries for the same user and competition"""
    try:
        if not is_admin_user():
            return jsonify({"error": "admin_only"}), 403
        
        from sqlalchemy import func
        
        # Find duplicate scores (same user_id and competition_id)
        duplicates = (
            db.session.query(
                CompetitionScore.user_id,
                CompetitionScore.competition_id,
                func.count(CompetitionScore.score_id).label('count')
            )
            .group_by(CompetitionScore.user_id, CompetitionScore.competition_id)
            .having(func.count(CompetitionScore.score_id) > 1)
            .all()
        )
        
        fixed_count = 0
        for user_id, comp_id, count in duplicates:
            # Get all scores for this user/competition combination
            scores = CompetitionScore.query.filter_by(
                user_id=user_id,
                competition_id=comp_id
            ).order_by(CompetitionScore.score_id.desc()).all()
            
            # Keep the most recent one (highest score_id), delete the rest
            for score in scores[1:]:
                db.session.delete(score)
                fixed_count += 1
        
        db.session.commit()
        
        return jsonify({
            "message": f"Fixed {fixed_count} duplicate scores",
            "duplicates_found": len(duplicates)
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@bp.route("/debug_simulation_status")
def debug_simulation_status():
    """Debug route to check simulation status"""
    if not is_admin_user():
        return jsonify({"error": "Unauthorized"}), 403
    
    try:
        # Check global simulation
        simulation = GlobalSimulation.query.first()
        current_time = _main().get_current_time()

        return jsonify({
            "global_simulation": {
                "id": simulation.id if simulation else None,
                "active": simulation.active if simulation else False,
                "scenario": simulation.scenario if simulation else None,
                "simulated_time": simulation.simulated_time if simulation else None,
                "start_time": simulation.start_time if simulation else None
            },
            "current_time": current_time.isoformat(),
            "current_time_type": str(type(current_time))
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/debug_missing_bike_brands")
def debug_missing_bike_brands():
    """Debug route to check which riders are missing bike_brand"""
    if not is_admin_user():
        return jsonify({"error": "Unauthorized"}), 403
    
    # Find riders with NULL or empty bike_brand
    riders_without_brand = Rider.query.filter(
        (Rider.bike_brand.is_(None)) | (Rider.bike_brand == '') | (Rider.bike_brand == 'Unknown')
    ).all()
    
    # Find riders with bike_brand
    riders_with_brand = Rider.query.filter(
        Rider.bike_brand.isnot(None),
        Rider.bike_brand != '',
        Rider.bike_brand != 'Unknown'
    ).all()
    
    return jsonify({
        "riders_without_brand": [{
            "id": r.id,
            "name": r.name,
            "class": r.class_name,
            "number": r.rider_number,
            "bike_brand": r.bike_brand
        } for r in riders_without_brand],
        "riders_with_brand": [{
            "id": r.id,
            "name": r.name,
            "class": r.class_name,
            "number": r.rider_number,
            "bike_brand": r.bike_brand
        } for r in riders_with_brand],
        "count_without_brand": len(riders_without_brand),
        "count_with_brand": len(riders_with_brand)
    })


@bp.route("/fix_missing_bike_brands")
def fix_missing_bike_brands():
    """Fix all riders that are missing bike_brand"""
    if not is_admin_user():
        return jsonify({"error": "Unauthorized"}), 403
    
    try:
        # Find riders with NULL or empty bike_brand
        riders_without_brand = Rider.query.filter(
            (Rider.bike_brand.is_(None)) | (Rider.bike_brand == '') | (Rider.bike_brand == 'Unknown')
        ).all()
        
        bike_brands = ['Yamaha', 'Honda', 'Kawasaki', 'KTM', 'Husqvarna', 'GasGas', 'Suzuki']
        fixed_count = 0
        
        for rider in riders_without_brand:
            # Assign bike brand based on rider number hash for consistency
            import hashlib
            hash_val = int(hashlib.md5(f"{rider.name}_{rider.rider_number}".encode()).hexdigest()[:8], 16)
            rider.bike_brand = bike_brands[hash_val % len(bike_brands)]
            fixed_count += 1
        
        db.session.commit()
        
        return jsonify({
            "message": f"Fixed {fixed_count} riders with missing bike brands",
            "fixed_count": fixed_count
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


# _SV_MONTHS / schedule helpers → services.picks_lock (skiva 3)




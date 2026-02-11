"""
Emergency script to recalculate scores for Buenos Aires
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import app, db
from models import Competition, CompetitionScore, CompetitionResult

def fix_buenos_aires_scores():
    """Recalculate scores for Buenos Aires competition"""
    with app.app_context():
        try:
            # Find Buenos Aires competition
            buenos_aires = Competition.query.filter(
                Competition.name.ilike('%buenos%aires%')
            ).first()
            
            if not buenos_aires:
                print("❌ Buenos Aires competition not found")
                return
            
            print(f"✅ Found Buenos Aires: {buenos_aires.name} (ID: {buenos_aires.id})")
            
            # Check current results
            results_count = CompetitionResult.query.filter_by(
                competition_id=buenos_aires.id
            ).count()
            print(f"📊 Current results count: {results_count}")
            
            # Check current scores
            scores_count = CompetitionScore.query.filter_by(
                competition_id=buenos_aires.id
            ).count()
            print(f"📊 Current scores count: {scores_count}")
            
            # Recalculate scores
            print(f"\n🔄 Recalculating scores for Buenos Aires...")
            from main import calculate_scores
            calculate_scores(buenos_aires.id)
            
            # Check scores after recalculation
            scores_after = CompetitionScore.query.filter_by(
                competition_id=buenos_aires.id
            ).all()
            
            print(f"\n✅ Recalculation complete!")
            print(f"📊 Scores after recalculation: {len(scores_after)}")
            
            for score in scores_after:
                user = db.session.query(db.text("SELECT username FROM users WHERE id = :id")).params(id=score.user_id).scalar()
                print(f"  User {score.user_id}: {score.total_points} points (Race: {score.race_points}, Holeshot: {score.holeshot_points}, Wildcard: {score.wildcard_points})")
            
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    fix_buenos_aires_scores()




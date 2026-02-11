"""
Emergency script to recover scores from LeaderboardHistory
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import app, db
from models import CompetitionScore, LeaderboardHistory, Competition, User

def recover_scores_from_history():
    """Try to recover scores from LeaderboardHistory if available"""
    with app.app_context():
        print("🔍 Checking for score recovery options...")
        
        # Check if we have LeaderboardHistory
        history_count = LeaderboardHistory.query.count()
        print(f"📊 Found {history_count} leaderboard history entries")
        
        if history_count == 0:
            print("❌ No leaderboard history found - cannot recover from history")
            return
        
        # Show recent history
        recent_history = LeaderboardHistory.query.order_by(
            LeaderboardHistory.created_at.desc()
        ).limit(10).all()
        
        print("\n📋 Recent leaderboard history:")
        for entry in recent_history:
            user = User.query.get(entry.user_id)
            username = user.username if user else f"User {entry.user_id}"
            print(f"  {username}: Rank {entry.ranking}, {entry.total_points} points (at {entry.created_at})")
        
        print("\n⚠️  Note: LeaderboardHistory only stores total points, not per-competition scores.")
        print("   To fully recover, we would need to recalculate scores for all competitions.")
        print("\n💡 Recommendation: Recalculate scores for all competitions that have results.")

if __name__ == "__main__":
    recover_scores_from_history()




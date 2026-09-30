"""One-shot: archive WSX 2025 tippa locally (keep WSX 2026)."""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from dotenv import load_dotenv

load_dotenv(os.path.join(ROOT, ".env"))
os.environ.setdefault("DATABASE_URL", "sqlite:///fantasy_mx_local.db")
os.environ.pop("RENDER", None)

from main import (  # noqa: E402
    app,
    db,
    Competition,
    CompetitionScore,
    FinishedSeriesStats,
    Series,
    User,
    _wsx_competitions_for_year,
    _write_finished_series_stats,
)
from collections import defaultdict  # noqa: E402


def main() -> int:
    year = 2025
    with app.app_context():
        wsx_series = Series.query.filter_by(name="WSX", year=year).first()
        if not wsx_series:
            print(f"FEL: WSX {year} saknas")
            return 1
        comps = _wsx_competitions_for_year(year)
        print(f"WSX {year} comps ({len(comps)}):")
        for c in comps:
            print(f"  id={c.id} {c.event_date} {c.name} series_id={c.series_id}")

        # Show 2026 untouched count before
        comps_2026 = _wsx_competitions_for_year(2026)
        ids_2026 = [c.id for c in comps_2026]
        before_2026 = (
            CompetitionScore.query.filter(CompetitionScore.competition_id.in_(ids_2026)).count()
            if ids_2026
            else 0
        )
        print(f"WSX 2026 CompetitionScore före: {before_2026}")

        ids = [c.id for c in comps]
        scores = CompetitionScore.query.filter(CompetitionScore.competition_id.in_(ids)).all()
        best = {}
        for s in scores:
            key = (int(s.user_id), int(s.competition_id))
            prev = best.get(key)
            if prev is None or int(s.score_id or 0) > int(prev.score_id or 0):
                best[key] = s
        user_stats = defaultdict(
            lambda: {
                "total_points": 0,
                "race_points": 0,
                "holeshot_points": 0,
                "wildcard_points": 0,
                "competitions_participated": 0,
            }
        )
        for s in best.values():
            st = user_stats[s.user_id]
            st["total_points"] += s.total_points or 0
            st["race_points"] += s.race_points or 0
            st["holeshot_points"] += s.holeshot_points or 0
            st["wildcard_points"] += s.wildcard_points or 0
            st["competitions_participated"] += 1

        n = _write_finished_series_stats(wsx_series.id, dict(user_stats))
        db.session.flush()
        deleted = CompetitionScore.query.filter(
            CompetitionScore.competition_id.in_(ids)
        ).delete(synchronize_session=False)
        wsx_series.is_active = False
        db.session.commit()

        after_2026 = (
            CompetitionScore.query.filter(CompetitionScore.competition_id.in_(ids_2026)).count()
            if ids_2026
            else 0
        )
        left_2025 = CompetitionScore.query.filter(
            CompetitionScore.competition_id.in_(ids)
        ).count()
        archived = FinishedSeriesStats.query.filter_by(series_id=wsx_series.id).count()
        me = User.query.filter(User.username.ilike("spliffan")).first()
        my_left = 0
        if me:
            my_left = (
                db.session.query(db.func.coalesce(db.func.sum(CompetitionScore.total_points), 0))
                .filter(CompetitionScore.user_id == me.id)
                .scalar()
            )

        print(f"Arkiverade users: {n} / FinishedSeriesStats rows: {archived}")
        print(f"Raderade CompetitionScore 2025: {deleted} (kvar {left_2025})")
        print(f"WSX 2026 CompetitionScore efter: {after_2026} (ska = {before_2026})")
        print(f"spliffan live tippa-sum kvar: {my_left}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

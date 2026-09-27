"""AMA tippa year totals (SX + MX + SMX) for Fantasy-arkiv and champion posters."""
from __future__ import annotations

from models import (
    Competition,
    CompetitionScore,
    FinishedSeriesStats,
    Series,
    User,
    db,
)

# Tippa series that make up the live AMA highscore (SX + MX + SMX Playoffs).
AMA_TIPPA_SERIES_NAMES = ("Supercross", "Motocross", "SMX Finals")
AMA_TOTAL_SERIES_NAME = "AMA Total"


def ama_series_display_name(name: str | None) -> str:
    n = (name or "").strip()
    if n == "Supercross":
        return "AMA Supercross"
    if n == "Motocross":
        return "Pro Motocross"
    if n == "SMX Finals":
        return "SMX Finals"
    if n == AMA_TOTAL_SERIES_NAME:
        return "Totalställning"
    return n or "Serie"


def _ama_tippa_series_for_year(year: int) -> list:
    """Return Supercross / Motocross / SMX Finals rows for a year (order fixed)."""
    by_name = {
        s.name: s
        for s in Series.query.filter(
            Series.year == int(year),
            Series.name.in_(AMA_TIPPA_SERIES_NAMES),
        ).all()
    }
    return [by_name[n] for n in AMA_TIPPA_SERIES_NAMES if n in by_name]


def _ensure_ama_total_series(year: int) -> Series:
    """Synthetic archive series for AMA tippa year total (SX+MX+SMX)."""
    year = int(year)
    row = Series.query.filter_by(name=AMA_TOTAL_SERIES_NAME, year=year).first()
    if row:
        return row
    parts = _ama_tippa_series_for_year(year)
    end_dates = [s.end_date for s in parts if s.end_date]
    start_dates = [s.start_date for s in parts if s.start_date]
    row = Series(
        name=AMA_TOTAL_SERIES_NAME,
        year=year,
        start_date=min(start_dates) if start_dates else None,
        end_date=max(end_dates) if end_dates else None,
        is_active=False,
        points_system="standard",
    )
    db.session.add(row)
    db.session.flush()
    return row


def _empty_user_score_bucket() -> dict:
    return {
        "total_points": 0,
        "race_points": 0,
        "holeshot_points": 0,
        "wildcard_points": 0,
        "competitions_participated": 0,
    }


def _aggregate_series_user_scores(series: Series) -> dict[int, dict]:
    """Per-user tippa totals for one Series — FinishedSeriesStats first, else live scores."""
    archived_stats = FinishedSeriesStats.query.filter_by(series_id=series.id).all()
    user_scores: dict[int, dict] = {}
    if archived_stats:
        for stat in archived_stats:
            user_scores[stat.user_id] = {
                "total_points": stat.total_points or 0,
                "race_points": stat.race_points or 0,
                "holeshot_points": stat.holeshot_points or 0,
                "wildcard_points": stat.wildcard_points or 0,
                "competitions_participated": stat.competitions_participated or 0,
            }
        return user_scores

    competitions = Competition.query.filter_by(series_id=series.id).all()
    comp_ids = [c.id for c in competitions]
    if not comp_ids:
        return user_scores

    scores = CompetitionScore.query.filter(
        CompetitionScore.competition_id.in_(comp_ids)
    ).all()
    for score in scores:
        bucket = user_scores.setdefault(score.user_id, _empty_user_score_bucket())
        bucket["total_points"] += score.total_points or 0
        bucket["race_points"] += score.race_points or 0
        bucket["holeshot_points"] += score.holeshot_points or 0
        bucket["wildcard_points"] += score.wildcard_points or 0
        bucket["competitions_participated"] += 1
    return user_scores


def _leaderboard_from_user_scores(user_scores: dict[int, dict]) -> list[dict]:
    leaderboard: list[dict] = []
    for user_id, stats in user_scores.items():
        user = User.query.get(user_id)
        if not user:
            continue
        leaderboard.append(
            {
                "user_id": user_id,
                "username": user.username,
                "display_name": getattr(user, "display_name", None) or user.username,
                "profile_picture_url": getattr(user, "profile_picture_url", None),
                **stats,
            }
        )
    leaderboard.sort(key=lambda x: x["total_points"], reverse=True)
    for i, row in enumerate(leaderboard, start=1):
        row["rank"] = i
    return leaderboard


def _build_ama_year_total(year: int) -> dict | None:
    """
    AMA tippa year total = Supercross + Motocross + SMX Finals.
    Prefer frozen AMA Total FinishedSeriesStats after season closeout.
    """
    year = int(year)
    total_series = Series.query.filter_by(name=AMA_TOTAL_SERIES_NAME, year=year).first()
    if total_series:
        archived = FinishedSeriesStats.query.filter_by(series_id=total_series.id).all()
        if archived:
            user_scores = {
                s.user_id: {
                    "total_points": s.total_points or 0,
                    "race_points": s.race_points or 0,
                    "holeshot_points": s.holeshot_points or 0,
                    "wildcard_points": s.wildcard_points or 0,
                    "competitions_participated": s.competitions_participated or 0,
                }
                for s in archived
            }
            parts = _ama_tippa_series_for_year(year)
            total_comps = 0
            for part in parts:
                total_comps += Competition.query.filter_by(series_id=part.id).count()
            leaderboard = _leaderboard_from_user_scores(user_scores)
            return {
                "year": year,
                "series": total_series,
                "display_name": "Totalställning",
                "parts": [
                    {"name": p.name, "display_name": ama_series_display_name(p.name)}
                    for p in parts
                ],
                "total_competitions": total_comps,
                "total_users": len(leaderboard),
                "top_10": leaderboard[:10],
                "all_users": leaderboard,
                "from_archive": True,
            }

    parts = _ama_tippa_series_for_year(year)
    if not parts:
        return None

    combined: dict[int, dict] = {}
    total_comps = 0
    part_meta = []
    for part in parts:
        part_scores = _aggregate_series_user_scores(part)
        n_comps = Competition.query.filter_by(series_id=part.id).count()
        total_comps += n_comps
        part_meta.append(
            {
                "name": part.name,
                "display_name": ama_series_display_name(part.name),
                "series_id": part.id,
                "competitions": n_comps,
                "users": len(part_scores),
            }
        )
        for uid, stats in part_scores.items():
            bucket = combined.setdefault(uid, _empty_user_score_bucket())
            bucket["total_points"] += stats["total_points"]
            bucket["race_points"] += stats["race_points"]
            bucket["holeshot_points"] += stats["holeshot_points"]
            bucket["wildcard_points"] += stats["wildcard_points"]
            bucket["competitions_participated"] += stats["competitions_participated"]

    if not combined:
        return None

    leaderboard = _leaderboard_from_user_scores(combined)
    return {
        "year": year,
        "series": total_series,
        "display_name": "Totalställning",
        "parts": part_meta,
        "total_competitions": total_comps,
        "total_users": len(leaderboard),
        "top_10": leaderboard[:10],
        "all_users": leaderboard,
        "from_archive": False,
    }


def _write_finished_series_stats(series_id: int, user_scores: dict[int, dict]) -> int:
    """Replace FinishedSeriesStats for a series from aggregated user_scores."""
    FinishedSeriesStats.query.filter_by(series_id=series_id).delete()
    count = 0
    for user_id, stats in user_scores.items():
        db.session.add(
            FinishedSeriesStats(
                series_id=series_id,
                user_id=user_id,
                total_points=stats.get("total_points") or 0,
                race_points=stats.get("race_points") or 0,
                holeshot_points=stats.get("holeshot_points") or 0,
                wildcard_points=stats.get("wildcard_points") or 0,
                competitions_participated=stats.get("competitions_participated") or 0,
            )
        )
        count += 1
    return count

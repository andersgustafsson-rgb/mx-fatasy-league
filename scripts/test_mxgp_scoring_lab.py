# -*- coding: utf-8 -*-
"""Isolated MXGP scoring lab — disposable SQLite, never touches prod/local main DB.

Usage (from repo root):
  python scripts/test_mxgp_scoring_lab.py

Sets DATABASE_URL before importing the app so dotenv cannot override.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAB_DB = ROOT / "instance" / "mxgp_score_lab.db"
LAB_DB.parent.mkdir(parents=True, exist_ok=True)
if LAB_DB.exists():
    LAB_DB.unlink()

# Must be set before main/load_dotenv (dotenv does not override existing env).
os.environ["DATABASE_URL"] = f"sqlite:///{LAB_DB.resolve().as_posix()}"
os.environ["FLASK_ENV"] = "development"
os.environ.setdefault("SECRET_KEY", "mxgp-score-lab-only")

sys.path.insert(0, str(ROOT))

print(f"[LAB] DATABASE_URL={os.environ['DATABASE_URL']}")

from werkzeug.security import generate_password_hash

import main as app_main  # noqa: E402 — side-effect: creates tables + seeds on import path
from models import (  # noqa: E402
    Competition,
    CompetitionResult,
    CompetitionScore,
    HoleshotPick,
    HoleshotResult,
    QualifyingPick,
    QualifyingResult,
    RacePick,
    Rider,
    User,
    db,
)
from mxgp_fantasy import ADMIN_TEST_GP_NAME, ensure_mxgp_scaffold  # noqa: E402


def _rider(name: str, class_name: str) -> Rider:
    r = Rider.query.filter_by(name=name, class_name=class_name).first()
    if not r:
        raise RuntimeError(f"Missing rider {name!r} ({class_name})")
    return r


def main() -> int:
    app = app_main.app
    with app.app_context():
        info = ensure_mxgp_scaffold()
        print("[LAB] scaffold", info)

        comp = Competition.query.filter_by(name=ADMIN_TEST_GP_NAME, series="MXGP").first()
        if not comp:
            raise RuntimeError("Admin Test GP missing")
        print(f"[LAB] competition_id={comp.id} series={comp.series}")

        # Fake AMA score that MUST NOT change after MXGP scoring
        ama_comp = Competition.query.filter(
            Competition.series.in_(("SX", "MX", "SMX"))
        ).first()
        if ama_comp is None:
            ama_comp = Competition(name="LAB AMA Dummy", series="SX")
            db.session.add(ama_comp)
            db.session.flush()

        user = User.query.filter_by(username="mxgp_lab_user").first()
        if user is None:
            user = User(
                username="mxgp_lab_user",
                password_hash=generate_password_hash("lab"),
                is_admin=False,
            )
            db.session.add(user)
            db.session.flush()

        ama_score = CompetitionScore.query.filter_by(
            user_id=user.id, competition_id=ama_comp.id
        ).first()
        if ama_score is None:
            ama_score = CompetitionScore(
                user_id=user.id,
                competition_id=ama_comp.id,
                race_points=100,
                holeshot_points=25,
                wildcard_points=15,
                total_points=140,
            )
            db.session.add(ama_score)
        else:
            ama_score.total_points = 140
            ama_score.race_points = 100
            ama_score.holeshot_points = 25
            ama_score.wildcard_points = 15
        db.session.commit()

        ama_before = int(ama_score.total_points or 0)
        ama_total_before = app_main._user_pick_total_points(user.id)
        print(f"[LAB] AMA score before={ama_before} pick_total_before={ama_total_before}")

        # Perfect lineup: pos 1–6 correct + both holeshots + both qualifying
        mxgp = [
            _rider("Romain Febvre", "mxgp"),
            _rider("Jeffrey Herlings", "mxgp"),
            _rider("Tim Gajser", "mxgp"),
            _rider("Tom Vialle", "mxgp"),
            _rider("Andrea Adamo", "mxgp"),
            _rider("Lucas Coenen", "mxgp"),
        ]
        mx2 = [
            _rider("Simon Längenfelder", "mx2"),
            _rider("Sacha Coenen", "mx2"),
            _rider("Camden McLellan", "mx2"),
            _rider("Liam Everts", "mx2"),
            _rider("Guillem Farres", "mx2"),
            _rider("Karlis Alberts Reisulis", "mx2"),
        ]

        RacePick.query.filter_by(user_id=user.id, competition_id=comp.id).delete()
        HoleshotPick.query.filter_by(user_id=user.id, competition_id=comp.id).delete()
        QualifyingPick.query.filter_by(user_id=user.id, competition_id=comp.id).delete()
        CompetitionResult.query.filter_by(competition_id=comp.id).delete()
        HoleshotResult.query.filter_by(competition_id=comp.id).delete()
        QualifyingResult.query.filter_by(competition_id=comp.id).delete()
        CompetitionScore.query.filter_by(
            user_id=user.id, competition_id=comp.id
        ).delete()
        db.session.commit()

        for i, r in enumerate(mxgp, start=1):
            db.session.add(
                RacePick(
                    user_id=user.id,
                    competition_id=comp.id,
                    rider_id=r.id,
                    predicted_position=i,
                )
            )
            db.session.add(
                CompetitionResult(
                    competition_id=comp.id,
                    rider_id=r.id,
                    position=i,
                    class_name="mxgp",
                )
            )
        for i, r in enumerate(mx2, start=1):
            db.session.add(
                RacePick(
                    user_id=user.id,
                    competition_id=comp.id,
                    rider_id=r.id,
                    predicted_position=i,
                )
            )
            db.session.add(
                CompetitionResult(
                    competition_id=comp.id,
                    rider_id=r.id,
                    position=i,
                    class_name="mx2",
                )
            )

        db.session.add(
            HoleshotPick(
                user_id=user.id,
                competition_id=comp.id,
                rider_id=mxgp[0].id,
                class_name="mxgp",
            )
        )
        db.session.add(
            HoleshotPick(
                user_id=user.id,
                competition_id=comp.id,
                rider_id=mx2[0].id,
                class_name="mx2",
            )
        )
        db.session.add(
            HoleshotResult(
                competition_id=comp.id, rider_id=mxgp[0].id, class_name="mxgp"
            )
        )
        db.session.add(
            HoleshotResult(
                competition_id=comp.id, rider_id=mx2[0].id, class_name="mx2"
            )
        )
        db.session.add(
            QualifyingPick(
                user_id=user.id,
                competition_id=comp.id,
                rider_id=mxgp[0].id,
                class_name="mxgp",
            )
        )
        db.session.add(
            QualifyingPick(
                user_id=user.id,
                competition_id=comp.id,
                rider_id=mx2[0].id,
                class_name="mx2",
            )
        )
        db.session.add(
            QualifyingResult(
                competition_id=comp.id, rider_id=mxgp[0].id, class_name="mxgp"
            )
        )
        db.session.add(
            QualifyingResult(
                competition_id=comp.id, rider_id=mx2[0].id, class_name="mx2"
            )
        )
        db.session.commit()

        print("[LAB] running calculate_scores…")
        app_main.calculate_scores(int(comp.id))

        mxgp_score = CompetitionScore.query.filter_by(
            user_id=user.id, competition_id=comp.id
        ).first()
        ama_score = CompetitionScore.query.filter_by(
            user_id=user.id, competition_id=ama_comp.id
        ).first()
        ama_after = int(ama_score.total_points or 0) if ama_score else -1
        ama_total_after = app_main._user_pick_total_points(user.id)

        print("--- RESULT ---")
        if mxgp_score:
            print(
                f"MXGP CompetitionScore: race={mxgp_score.race_points} "
                f"holeshot={mxgp_score.holeshot_points} "
                f"qual_via_wc_col={mxgp_score.wildcard_points} "
                f"total={mxgp_score.total_points}"
            )
        else:
            print("MXGP CompetitionScore: MISSING")
        print(f"AMA CompetitionScore: before={ama_before} after={ama_after}")
        print(f"AMA pick_total (leaderboard): before={ama_total_before} after={ama_total_after}")

        ok = True
        if not mxgp_score:
            ok = False
        else:
            # Perfect top6 both classes → high race points; both HS → 25; both qual → 20
            if int(mxgp_score.holeshot_points or 0) != 25:
                print("FAIL: expected holeshot_points=25")
                ok = False
            if int(mxgp_score.wildcard_points or 0) != 20:
                print("FAIL: expected qualifying (wildcard_points)=20")
                ok = False
            if int(mxgp_score.race_points or 0) <= 0:
                print("FAIL: expected race_points > 0")
                ok = False
        if ama_after != ama_before:
            print("FAIL: AMA CompetitionScore changed")
            ok = False
        if ama_total_after != ama_total_before:
            print("FAIL: AMA leaderboard total changed (MXGP leaked)")
            ok = False
        # AMA total should equal AMA score only (MXGP excluded)
        if ama_total_after != ama_after:
            print(
                f"FAIL: pick_total {ama_total_after} != AMA score {ama_after} "
                "(unexpected other scores or leak)"
            )
            ok = False

        print("[LAB] PASS" if ok else "[LAB] FAIL")
        print(f"[LAB] disposable DB: {LAB_DB}")
        return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

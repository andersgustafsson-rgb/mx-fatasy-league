"""MXGP (FIM Motocross World Championship) tippa-only scaffold.

Public: homepage card shows Under construction.
Admin: can open picks / schema for testing (2026 roster + admin test GP).

Tippa rules (agreed): top 6 MXGP + top 6 MX2 + holeshot Race 1 + qualifying winner
per class. No wildcard. No season team.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from models import Competition, Rider, Series, db

# Flip when ready for public tippa (2027 season).
MXGP_PUBLIC_PLAY = False

SERIES_CODE = "MXGP"
CLASS_MXGP = "mxgp"
CLASS_MX2 = "mx2"

# Core 2026 factory / regulars for admin testing (twins get separate rows from AMA).
# (name, class, number|None, brand|None, team|None)
_MXGP_2026_ROSTER: list[tuple[str, str, int | None, str | None, str | None]] = [
    # MXGP
    ("Jeffrey Herlings", CLASS_MXGP, 84, "Honda", "Honda HRC Petronas"),
    ("Romain Febvre", CLASS_MXGP, 1, "Kawasaki", "Kawasaki Racing Team MXGP"),
    ("Tim Gajser", CLASS_MXGP, 243, "Yamaha", "Monster Energy Yamaha Factory MXGP"),
    ("Tom Vialle", CLASS_MXGP, 16, "Honda", "Honda HRC Petronas"),
    ("Andrea Adamo", CLASS_MXGP, 80, "KTM", "Red Bull KTM Factory Racing"),
    ("Lucas Coenen", CLASS_MXGP, 5, "KTM", "Red Bull KTM Factory Racing"),
    ("Ruben Fernandez", CLASS_MXGP, 70, "Honda", "Honda HRC"),
    ("Maxime Renaux", CLASS_MXGP, 959, "Yamaha", "Monster Energy Yamaha Factory MXGP"),
    ("Pauls Jonass", CLASS_MXGP, 41, "Kawasaki", "Kawasaki Racing Team MXGP"),
    ("Kay de Wolf", CLASS_MXGP, 74, "Husqvarna", "Nestaan Husqvarna Factory Racing"),
    ("Calvin Vlaanderen", CLASS_MXGP, 10, "Ducati", "Ducati Factory"),
    ("Jan Pancar", CLASS_MXGP, 253, "KTM", "Team Honda Motoblouz"),
    ("Kevin Horgmo", CLASS_MXGP, 24, "Honda", "Team Honda Motoblouz"),
    ("Jago Geerts", CLASS_MXGP, 93, "Beta", "MRT Racing Team Beta"),
    ("Jeremy Seewer", CLASS_MXGP, 91, "KTM", "MXGP"),
    ("Brent Van doninck", CLASS_MXGP, 32, "Fantic", "Fantic Factory"),
    ("Isak Gifting", CLASS_MXGP, 517, "Yamaha", "Yamaha"),
    ("Rick Elzinga", CLASS_MXGP, 4, "KTM", "KTM"),
    # MX2
    ("Guillem Farres", CLASS_MX2, 99, "Triumph", "Triumph Racing Factory Team"),
    ("Camden McLellan", CLASS_MX2, 8, "Triumph", "Triumph Racing Factory Team"),
    ("Sacha Coenen", CLASS_MX2, 19, "KTM", "Red Bull KTM Factory Racing"),
    ("Simon Längenfelder", CLASS_MX2, 1, "KTM", "Red Bull KTM Factory Racing"),
    ("Liam Everts", CLASS_MX2, 26, "Husqvarna", "Nestaan Husqvarna Factory Racing"),
    ("Janis Martins Reisulis", CLASS_MX2, 772, "Yamaha", "Monster Energy Yamaha Factory MX2"),
    ("Karlis Alberts Reisulis", CLASS_MX2, 47, "Yamaha", "Monster Energy Yamaha Factory MX2"),
    ("Valerio Lata", CLASS_MX2, 18, "Honda", "Honda HRC"),
    ("Julius Mikula", CLASS_MX2, 20, "KTM", "Osicka MX Team"),
    ("Kay Karssemakers", CLASS_MX2, 33, "Kawasaki", "DRT Kawasaki"),
    ("Mathis Valin", CLASS_MX2, 317, "Kawasaki", "Kawasaki Racing Team MX2"),
    ("Ferruccio Zanchi", CLASS_MX2, 73, "Ducati", "Beddini Racing Ducati"),
    ("Maxime Grau", CLASS_MX2, 83, "Honda", "Honda"),
    ("Noel Zanocz", CLASS_MX2, 716, "KTM", "Van Venrooy KTM"),
]

# Official 2026 calendar (19 GPs) — kept for admin/history series.
_MXGP_2026_CALENDAR: list[tuple[str, date, str]] = [
    ("MXGP of Argentina", date(2026, 3, 8), "America/Argentina/Bariloche"),
    ("MXGP of Andalucia", date(2026, 3, 22), "Europe/Madrid"),
    ("MXGP of Switzerland", date(2026, 3, 29), "Europe/Zurich"),
    ("MXGP of Sardegna", date(2026, 4, 12), "Europe/Rome"),
    ("MXGP of Trentino", date(2026, 4, 19), "Europe/Rome"),
    ("MXGP of France", date(2026, 5, 24), "Europe/Paris"),
    ("MXGP of Germany", date(2026, 5, 31), "Europe/Berlin"),
    ("MXGP of Latvia", date(2026, 6, 7), "Europe/Riga"),
    ("MXGP of Italy", date(2026, 6, 21), "Europe/Rome"),
    ("MXGP of Portugal", date(2026, 6, 28), "Europe/Lisbon"),
    ("MXGP of South Africa", date(2026, 7, 5), "Africa/Johannesburg"),
    ("MXGP of Great Britain", date(2026, 7, 19), "Europe/London"),
    ("MXGP of Czech Republic", date(2026, 7, 26), "Europe/Prague"),
    ("MXGP of Flanders", date(2026, 8, 2), "Europe/Brussels"),
    ("MXGP of Sweden", date(2026, 8, 16), "Europe/Stockholm"),
    ("MXGP of The Netherlands", date(2026, 8, 23), "Europe/Amsterdam"),
    ("MXGP of Turkiye", date(2026, 9, 6), "Europe/Istanbul"),
    ("MXGP of China", date(2026, 9, 13), "Asia/Shanghai"),
    ("MXGP of Australia", date(2026, 9, 20), "Australia/Darwin"),
]

# Provisional 2027 calendar (20 GPs) — FIM/Infront update 17 Sep 2026 (Ziyang added).
# Sunday race day as event_date. Venue TBA rounds have no trackmap yet.
_MXGP_2027_CALENDAR: list[tuple[str, date, str]] = [
    ("MXGP of Andalucia", date(2027, 2, 28), "Europe/Madrid"),  # Almonte
    ("MXGP of Argentina", date(2027, 3, 14), "America/Argentina/Bariloche"),
    ("MXGP of Italy", date(2027, 3, 28), "Europe/Rome"),  # Montevarchi
    ("MXGP of Sardegna", date(2027, 4, 4), "Europe/Rome"),  # Riola Sardo
    ("MXGP of Spain", date(2027, 4, 18), "Europe/Madrid"),  # venue TBA
    ("MXGP of Trentino", date(2027, 4, 25), "Europe/Rome"),  # Pietramurata
    ("MXGP of China", date(2027, 5, 2), "Asia/Shanghai"),  # Shanghai
    ("MXGP of Portugal", date(2027, 5, 23), "Europe/Lisbon"),  # venue TBA
    ("MXGP of France", date(2027, 5, 30), "Europe/Paris"),  # St Jean d'Angély
    ("MXGP of Latvia", date(2027, 6, 13), "Europe/Riga"),  # Kegums
    ("MXGP of Germany", date(2027, 6, 20), "Europe/Berlin"),  # Teutschenthal
    ("MXGP of Great Britain", date(2027, 6, 27), "Europe/London"),  # Foxhills
    ("MXGP of Czech Republic", date(2027, 7, 25), "Europe/Prague"),  # Loket
    ("MXGP of Flanders", date(2027, 8, 1), "Europe/Brussels"),  # Lommel
    ("MXGP of Sweden", date(2027, 8, 15), "Europe/Stockholm"),  # Uddevalla
    ("MXGP of The Netherlands", date(2027, 8, 22), "Europe/Amsterdam"),  # Arnhem
    ("MXGP of Turkiye", date(2027, 9, 5), "Europe/Istanbul"),  # Afyonkarahisar
    ("MXGP of Ziyang", date(2027, 9, 12), "Asia/Shanghai"),
    ("MXGP of Australia", date(2027, 9, 19), "Australia/Darwin"),
    ("MXGP of Switzerland", date(2027, 10, 3), "Europe/Zurich"),  # venue TBA
]

ADMIN_TEST_GP_NAME = "MXGP Admin Test GP"


def is_mxgp_series(series: str | None) -> bool:
    return (series or "").strip().upper() == SERIES_CODE


def mxgp_public_play_enabled() -> bool:
    return bool(MXGP_PUBLIC_PLAY)


def mxgp_user_can_play(*, is_admin: bool) -> bool:
    """Public tippa locked until MXGP_PUBLIC_PLAY; admins always can test."""
    return bool(is_admin) or mxgp_public_play_enabled()


def ensure_mxgp_qualifying_tables() -> None:
    """Ensure QualifyingPick / QualifyingResult tables exist."""
    try:
        from models import QualifyingPick, QualifyingResult

        QualifyingPick.__table__.create(bind=db.engine, checkfirst=True)
        QualifyingResult.__table__.create(bind=db.engine, checkfirst=True)
    except Exception as e:
        print(f"ensure_mxgp_qualifying_tables: {e}")
        try:
            db.session.rollback()
        except Exception:
            pass


def ensure_mxgp_2027_series() -> Series:
    """Public-facing series card for 2027 (under construction until PUBLIC_PLAY)."""
    s = Series.query.filter_by(name="MXGP", year=2027).first()
    if not s:
        s = Series(
            name="MXGP",
            year=2027,
            start_date=date(2027, 2, 28),
            end_date=date(2027, 10, 3),
            is_active=True,
            points_system="mxgp_tippa",
        )
        db.session.add(s)
        db.session.flush()
    else:
        s.is_active = True
        s.start_date = date(2027, 2, 28)
        s.end_date = date(2027, 10, 3)
    return s


def ensure_mxgp_2026_series() -> Series:
    """2026 series for calendar/roster testing (admin)."""
    s = Series.query.filter_by(name="MXGP", year=2026).first()
    if not s:
        s = Series(
            name="MXGP",
            year=2026,
            start_date=date(2026, 3, 8),
            end_date=date(2026, 9, 20),
            is_active=False,
            points_system="mxgp_tippa",
        )
        db.session.add(s)
        db.session.flush()
    return s


def _upsert_mxgp_calendar(
    *, series: Series, calendar: list[tuple[str, date, str]]
) -> dict[str, Any]:
    created = updated = 0
    ids: list[int] = []
    for name, event_date, tz in calendar:
        comp = Competition.query.filter_by(name=name, series_id=series.id).first()
        if comp is None:
            comp = Competition(
                name=name,
                event_date=event_date,
                series=SERIES_CODE,
                series_id=series.id,
            )
            db.session.add(comp)
            created += 1
        else:
            updated += 1
        comp.series = SERIES_CODE
        comp.series_id = series.id
        comp.event_date = event_date
        if hasattr(comp, "timezone"):
            comp.timezone = tz
        db.session.flush()
        ids.append(int(comp.id))
    return {"created": created, "updated": updated, "competition_ids": ids}


def ensure_mxgp_2026_calendar(*, series: Series | None = None) -> dict[str, Any]:
    series = series or ensure_mxgp_2026_series()
    return _upsert_mxgp_calendar(series=series, calendar=_MXGP_2026_CALENDAR)


def ensure_mxgp_2027_calendar(*, series: Series | None = None) -> dict[str, Any]:
    series = series or ensure_mxgp_2027_series()
    return _upsert_mxgp_calendar(series=series, calendar=_MXGP_2027_CALENDAR)


def ensure_mxgp_admin_test_gp(*, series_2027: Series | None = None) -> Competition:
    """Future-dated GP so admin can open picks while 2027 calendar is TBA."""
    series_2027 = series_2027 or ensure_mxgp_2027_series()
    test_date = date.today() + timedelta(days=14)
    comp = Competition.query.filter_by(
        name=ADMIN_TEST_GP_NAME, series_id=series_2027.id
    ).first()
    if comp is None:
        # Prefer orphan by name+series
        comp = Competition.query.filter_by(
            name=ADMIN_TEST_GP_NAME, series=SERIES_CODE
        ).first()
    if comp is None:
        comp = Competition(
            name=ADMIN_TEST_GP_NAME,
            event_date=test_date,
            series=SERIES_CODE,
            series_id=series_2027.id,
        )
        db.session.add(comp)
    else:
        comp.series = SERIES_CODE
        comp.series_id = series_2027.id
        # Keep picks open: bump date if already past
        if not comp.event_date or comp.event_date < date.today():
            comp.event_date = test_date
    if hasattr(comp, "timezone") and not (comp.timezone or "").strip():
        comp.timezone = "Europe/Stockholm"
    db.session.flush()
    return comp


def ensure_mxgp_2026_roster() -> dict[str, Any]:
    """Upsert tippa-only MXGP/MX2 riders (does not touch AMA rows)."""
    created = updated = 0
    for name, class_name, number, brand, team in _MXGP_2026_ROSTER:
        rider = (
            Rider.query.filter_by(name=name, class_name=class_name)
            .filter(Rider.series_participation == "mxgp")
            .first()
        )
        if rider is None:
            # Also match if series_participation unset but class is mxgp/mx2
            rider = Rider.query.filter_by(name=name, class_name=class_name).first()
            if rider and (getattr(rider, "series_participation", None) or "").lower() not in (
                "",
                "mxgp",
            ):
                rider = None
        if rider is None:
            rider = Rider(
                name=name,
                class_name=class_name,
                rider_number=number,
                bike_brand=brand,
                team=team,
                price=1,
                series_participation="mxgp",
            )
            db.session.add(rider)
            created += 1
        else:
            updated += 1
            rider.class_name = class_name
            if number is not None:
                rider.rider_number = number
            if brand:
                rider.bike_brand = brand
            if team:
                rider.team = team
            rider.series_participation = "mxgp"
            if rider.price is None:
                rider.price = 1
    db.session.flush()
    return {"created": created, "updated": updated, "roster_size": len(_MXGP_2026_ROSTER)}


def mxgp_roster_query():
    return Rider.query.filter(
        Rider.class_name.in_((CLASS_MXGP, CLASS_MX2)),
        Rider.series_participation == "mxgp",
    )


def mxgp_official_roster_ids() -> set[int]:
    return {int(r.id) for r in mxgp_roster_query().all()}


def ensure_mxgp_scaffold() -> dict[str, Any]:
    """Idempotent bootstrap: 2027 series+calendar, 2026 history+roster, admin test GP."""
    ensure_mxgp_qualifying_tables()
    s2027 = ensure_mxgp_2027_series()
    s2026 = ensure_mxgp_2026_series()
    cal_2027 = ensure_mxgp_2027_calendar(series=s2027)
    cal_2026 = ensure_mxgp_2026_calendar(series=s2026)
    roster = ensure_mxgp_2026_roster()
    test_gp = ensure_mxgp_admin_test_gp(series_2027=s2027)
    db.session.commit()
    info = {
        "series_2027_id": s2027.id,
        "series_2026_id": s2026.id,
        "admin_test_competition_id": test_gp.id,
        "admin_test_date": test_gp.event_date.isoformat() if test_gp.event_date else None,
        "public_play": mxgp_public_play_enabled(),
        "calendar": cal_2027,
        "calendar_2026": cal_2026,
        "roster": roster,
    }
    print(
        f"[MXGP-SEED] OK 2027={s2027.id} 2026={s2026.id} "
        f"test_gp={test_gp.id} cal2027={len(cal_2027['competition_ids'])} "
        f"roster+={roster['created']}"
    )
    return info

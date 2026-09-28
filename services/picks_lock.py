"""Pick lock / race schedule helpers (refactor skiva 3).

Moved from main.py without behavior change. See docs/REFACTOR.md.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from flask import session

from models import Competition, db


_SV_MONTHS = (
    "",
    "jan",
    "feb",
    "mar",
    "apr",
    "maj",
    "jun",
    "jul",
    "aug",
    "sep",
    "okt",
    "nov",
    "dec",
)


def _parse_start_time_value(val):
    """Parse DB start_time (time object or HH:MM string)."""
    from datetime import time as time_type

    if val is None:
        return None
    if isinstance(val, time_type):
        return val
    if isinstance(val, str):
        s = val.strip()
        if not s:
            return None
        parts = s.split(":")
        if len(parts) < 2:
            return None
        return time_type(
            int(parts[0]),
            int(parts[1]),
            int(parts[2]) if len(parts) > 2 else 0,
        )
    return None


def _tz_display_label(tz_name: str | None) -> str:
    mapping = {
        "Europe/Stockholm": "Stockholm",
        "America/New_York": "Eastern (US)",
        "America/Detroit": "Eastern (US)",
        "America/Chicago": "Central (US)",
        "America/Denver": "Mountain (US)",
        "America/Los_Angeles": "Pacific (US)",
        "America/Phoenix": "Arizona (US)",
    }
    tz = (tz_name or "").strip()
    if tz in mapping:
        return mapping[tz]
    return tz.split("/")[-1].replace("_", " ") if tz else "lokal tid"


def _competition_race_schedule(comp) -> dict:
    """
    Race start + pick deadline in UTC (naive) and labels for countdown UI.
    start_time is interpreted in competition.timezone (banens lokala tidszon).

    Default: picks lock 2h before start_time (gate/race).
    If quali_start_time is set on the competition (admin), lock at that local time.
    Else SMX: if first_quali is set in SMX_RACE_META, lock at that local time
    (qualifying reveals pace — same idea as MXoN locking vs Saturday kval).
    """
    from datetime import date, datetime, time as time_type, timedelta

    raw_date = getattr(comp, "event_date", None)
    if isinstance(raw_date, str):
        event_date = datetime.fromisoformat(raw_date.replace("Z", "+00:00")).date()
    elif isinstance(raw_date, datetime):
        event_date = raw_date.date()
    elif isinstance(raw_date, date):
        event_date = raw_date
    else:
        raise ValueError("competition has no event_date")

    timezone_val = (getattr(comp, "timezone", None) or "America/Los_Angeles").strip()
    start_time = _parse_start_time_value(getattr(comp, "start_time", None))
    # MXoN: lock against Saturday MXGP Qual (~14:30), not Sunday Race 1
    if not start_time and (getattr(comp, "series", None) or "").upper() == "MXON":
        start_time = datetime.min.time().replace(hour=14, minute=30)

    if start_time:
        race_local_naive = datetime.combine(event_date, start_time)
    else:
        race_local_naive = datetime.combine(
            event_date, datetime.min.time().replace(hour=20, minute=0)
        )

    race_datetime_utc = None
    race_aware = None
    try:
        from zoneinfo import ZoneInfo

        tz = ZoneInfo(timezone_val)
        race_aware = race_local_naive.replace(tzinfo=tz)
        race_datetime_utc = race_aware.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
    except Exception:
        try:
            import pytz

            tz = pytz.timezone(timezone_val)
            race_aware = tz.localize(race_local_naive)
            race_datetime_utc = race_aware.astimezone(pytz.UTC).replace(tzinfo=None)
        except Exception:
            # Last resort — approximate offset (summer-aware for common US/EU zones)
            month = event_date.month
            summer = month in (3, 4, 5, 6, 7, 8, 9, 10)
            offsets = {
                "America/Los_Angeles": -7 if summer else -8,
                "America/Denver": -6 if summer else -7,
                "America/Phoenix": -7,
                "America/Chicago": -5 if summer else -6,
                "America/New_York": -4 if summer else -5,
                "America/Detroit": -4 if summer else -5,
                "America/Argentina/Buenos_Aires": -3,
                "Australia/Brisbane": 10,
                "Europe/Stockholm": 2 if summer else 1,
                "Europe/Paris": 2 if summer else 1,
            }
            utc_offset = offsets.get(timezone_val, -8)
            race_datetime_utc = race_local_naive - timedelta(hours=utc_offset)

    deadline_local_naive = race_local_naive - timedelta(hours=2)
    deadline_datetime_utc = race_datetime_utc - timedelta(hours=2)
    deadline_aware = None

    def _apply_absolute_local_deadline(hh: int, mm: int) -> None:
        nonlocal deadline_local_naive, deadline_datetime_utc, deadline_aware
        deadline_local_naive = datetime.combine(event_date, time_type(int(hh), int(mm)))
        try:
            from zoneinfo import ZoneInfo

            deadline_aware = deadline_local_naive.replace(tzinfo=ZoneInfo(timezone_val))
            deadline_datetime_utc = deadline_aware.astimezone(ZoneInfo("UTC")).replace(
                tzinfo=None
            )
        except Exception:
            try:
                import pytz

                deadline_aware = pytz.timezone(timezone_val).localize(deadline_local_naive)
                deadline_datetime_utc = deadline_aware.astimezone(pytz.UTC).replace(
                    tzinfo=None
                )
            except Exception:
                month = event_date.month
                summer = month in (3, 4, 5, 6, 7, 8, 9, 10)
                offsets = {
                    "America/Los_Angeles": -7 if summer else -8,
                    "America/Chicago": -5 if summer else -6,
                    "America/New_York": -4 if summer else -5,
                }
                utc_offset = offsets.get(timezone_val, -7)
                deadline_datetime_utc = deadline_local_naive - timedelta(hours=utc_offset)

    # 1) Admin-set quali lock time on the competition row
    try:
        qst = getattr(comp, "quali_start_time", None)
        if qst is not None:
            _apply_absolute_local_deadline(qst.hour, qst.minute)
        else:
            # 2) SMX meta fallback (hardcoded playoff schedules)
            from trackmap_utils import get_smx_race_meta

            smx_meta = get_smx_race_meta(getattr(comp, "name", "") or "")
            fq = (smx_meta or {}).get("first_quali")
            if fq and len(fq) >= 2:
                _apply_absolute_local_deadline(int(fq[0]), int(fq[1]))
    except Exception as exc:
        print(f"WARNING quali/first_quali deadline override: {exc}")

    tz_label = _tz_display_label(timezone_val)
    m = _SV_MONTHS[event_date.month]
    race_start_display = (
        f"{event_date.day} {m} {event_date.year} kl "
        f"{race_local_naive.strftime('%H:%M')} ({tz_label})"
    )
    pick_deadline_display = (
        f"{deadline_local_naive.day} {m} kl "
        f"{deadline_local_naive.strftime('%H:%M')} ({tz_label})"
    )

    stockholm_display = None
    try:
        from zoneinfo import ZoneInfo

        if race_aware is not None:
            se = race_aware.astimezone(ZoneInfo("Europe/Stockholm"))
            stockholm_display = (
                f"{se.day} {_SV_MONTHS[se.month]} kl {se.strftime('%H:%M')} (Stockholm)"
            )
    except Exception:
        pass

    return {
        "race_utc": race_datetime_utc,
        "deadline_utc": deadline_datetime_utc,
        "timezone": timezone_val,
        "race_start_display": race_start_display,
        "pick_deadline_display": pick_deadline_display,
        "stockholm_display": stockholm_display,
    }

def get_current_time():
    """Get current time - either real or simulated (with time progression)"""
    # Check if we're in simulation mode
    try:
        db.session.rollback()
        result = db.session.execute(db.text("SELECT active, simulated_time, start_time FROM global_simulation WHERE id = 1")).fetchone()
        
        if result and result[0]:  # active is True
            simulated_time_str = result[1] if result[1] else None
            start_time_str = result[2] if result[2] else None
            
            if simulated_time_str and start_time_str:
                # Calculate how much real time has passed since simulation started
                initial_simulated_time = datetime.fromisoformat(simulated_time_str)
                start_time = datetime.fromisoformat(start_time_str)
                real_time_elapsed = datetime.utcnow() - start_time
                
                # Add the elapsed real time to the initial simulated time
                current_simulated_time = initial_simulated_time + real_time_elapsed
                return current_simulated_time
            elif simulated_time_str:
                # Fallback to original simulated time if no start_time
                current_simulated_time = datetime.fromisoformat(simulated_time_str)
                return current_simulated_time
    except Exception as e:
        print(f"DEBUG: Error in get_current_time: {e}")
        db.session.rollback()
    
    # Default to real time
    return datetime.utcnow()

def is_picks_locked(competition):
    """Check if picks are locked for a specific competition"""
    # Rollback any existing transaction to avoid "aborted transaction" errors
    db.session.rollback()
    
    # Handle both Competition objects and competition IDs
    if isinstance(competition, int):
        # If it's an ID, fetch the competition object
        competition_obj = Competition.query.get(competition)
        if not competition_obj:
            return False
        competition_name = f"ID {competition}"
        competition_id = competition
    else:
        # If it's a Competition object
        competition_obj = competition
        competition_name = competition.name if hasattr(competition, 'name') else f"ID {competition.id}"
        competition_id = competition.id

    # Check if we're in simulation mode (use only global database state for consistency)
    simulation_active = False
    
    try:
        # Rollback any existing transaction first
        db.session.rollback()
        
        result = db.session.execute(db.text("SELECT active FROM global_simulation WHERE id = 1")).fetchone()
        simulation_active = result and result[0] if result else False
    except Exception as e:
        # Rollback and fallback to app globals if database table doesn't exist
        db.session.rollback()
        try:
            from main import app as _app
            simulation_active = (
                hasattr(_app, 'global_simulation_active')
                and _app.global_simulation_active
            )
        except Exception:
            simulation_active = False
    
    if simulation_active:
        # Use the same logic as test_countdown for consistency
        # Get the scenario from global database state or use default
        try:
            result = db.session.execute(db.text("SELECT scenario FROM global_simulation WHERE id = 1")).fetchone()
            scenario = result[0] if result and result[0] else 'race_in_3h'
        except Exception as e:
            scenario = session.get('test_scenario', 'race_in_3h')
        
        # Get current time first
        current_time = get_current_time()
        
        # Use the same scenario-based logic as race_countdown
        if scenario and scenario.startswith('active_race_'):
            # Get the initial simulated time when simulation started
            try:
                result = db.session.execute(db.text("SELECT simulated_time FROM global_simulation WHERE id = 1")).fetchone()
                simulated_time_str = result[0] if result and result[0] else current_time.isoformat()
                initial_simulated_time = datetime.fromisoformat(simulated_time_str)
            except Exception as e:
                initial_simulated_time = current_time
            
            # Use actual competition start time if available
            if hasattr(competition_obj, 'start_time') and competition_obj.start_time:
                race_date = competition_obj.event_date or initial_simulated_time.date()
                race_datetime = datetime.combine(race_date, competition_obj.start_time)
                deadline_datetime = race_datetime - timedelta(hours=2)
            else:
                # Fallback to 11 AM
                fake_race_base_time = initial_simulated_time.replace(hour=11, minute=0, second=0, microsecond=0)
                race_datetime = fake_race_base_time
                deadline_datetime = race_datetime - timedelta(hours=2)
        elif scenario == 'race_in_3h':
            # Check if this is the active race
            try:
                result = db.session.execute(db.text("SELECT active_race_id FROM global_simulation WHERE id = 1")).fetchone()
                active_race_id = result[0] if result and result[0] else None
                
                if active_race_id == competition_id:
                    # This is the active race - use simulated time
                    print(f"DEBUG: is_picks_locked - {competition_name} is the ACTIVE race (ID: {competition_id})")
                    if hasattr(competition_obj, 'start_time') and competition_obj.start_time:
                        # Use the competition's actual start time with simulated date
                        race_date = current_time.date()
                        race_datetime = datetime.combine(race_date, competition_obj.start_time)
                        deadline_datetime = race_datetime - timedelta(hours=2)
                    else:
                        # Fallback to 3 hours from simulated time
                        race_datetime = current_time + timedelta(hours=3)
                        deadline_datetime = race_datetime - timedelta(hours=2)
                else:
                    # This is not the active race - use real event date
                    print(f"DEBUG: is_picks_locked - {competition_name} is NOT the active race (ID: {competition_id}, active: {active_race_id})")
                    if hasattr(competition_obj, 'start_time') and competition_obj.start_time:
                        race_date = competition_obj.event_date or current_time.date()
                        race_datetime = datetime.combine(race_date, competition_obj.start_time)
                        deadline_datetime = race_datetime - timedelta(hours=2)
                    else:
                        # Fallback to 3 hours from now
                        race_datetime = current_time + timedelta(hours=3)
                        deadline_datetime = race_datetime - timedelta(hours=2)
            except Exception as e:
                # Fallback to original logic
                if hasattr(competition_obj, 'start_time') and competition_obj.start_time:
                    race_date = competition_obj.event_date or current_time.date()
                    race_datetime = datetime.combine(race_date, competition_obj.start_time)
                    deadline_datetime = race_datetime - timedelta(hours=2)
                else:
                    race_datetime = current_time + timedelta(hours=3)
                    deadline_datetime = race_datetime - timedelta(hours=2)
        elif scenario == 'race_in_1h':
            # Race in 1 hour - use actual competition start time if available
            if hasattr(competition_obj, 'start_time') and competition_obj.start_time:
                race_date = competition_obj.event_date or current_time.date()
                race_datetime = datetime.combine(race_date, competition_obj.start_time)
                deadline_datetime = race_datetime - timedelta(hours=2)
            else:
                race_datetime = current_time + timedelta(hours=1)
                deadline_datetime = race_datetime - timedelta(hours=2)
        elif scenario == 'race_in_30m':
            # Race in 30 minutes - use actual competition start time if available
            if hasattr(competition_obj, 'start_time') and competition_obj.start_time:
                race_date = competition_obj.event_date or current_time.date()
                race_datetime = datetime.combine(race_date, competition_obj.start_time)
                deadline_datetime = race_datetime - timedelta(hours=2)
            else:
                race_datetime = current_time + timedelta(minutes=30)
                deadline_datetime = race_datetime - timedelta(hours=2)
        elif scenario == 'race_in_10m':
            # Race in 10 minutes - use actual competition start time if available
            if hasattr(competition_obj, 'start_time') and competition_obj.start_time:
                race_date = competition_obj.event_date or current_time.date()
                race_datetime = datetime.combine(race_date, competition_obj.start_time)
                deadline_datetime = race_datetime - timedelta(hours=2)
            else:
                race_datetime = current_time + timedelta(minutes=10)
                deadline_datetime = race_datetime - timedelta(hours=2)
        elif scenario == 'race_in_5m':
            # Race in 5 minutes - use actual competition start time if available
            if hasattr(competition_obj, 'start_time') and competition_obj.start_time:
                race_date = competition_obj.event_date or current_time.date()
                race_datetime = datetime.combine(race_date, competition_obj.start_time)
                deadline_datetime = race_datetime - timedelta(hours=2)
            else:
                race_datetime = current_time + timedelta(minutes=5)
                deadline_datetime = race_datetime - timedelta(hours=2)
        elif scenario == 'race_in_1m':
            # Race in 1 minute - use actual competition start time if available
            if hasattr(competition_obj, 'start_time') and competition_obj.start_time:
                race_date = competition_obj.event_date or current_time.date()
                race_datetime = datetime.combine(race_date, competition_obj.start_time)
                deadline_datetime = race_datetime - timedelta(hours=2)
            else:
                race_datetime = current_time + timedelta(minutes=1)
            deadline_datetime = race_datetime - timedelta(hours=2)
        elif scenario == 'race_started':
            # Race has started
            race_datetime = current_time - timedelta(minutes=1)
            deadline_datetime = race_datetime - timedelta(hours=2)
        else:
            # Default to race in 3 hours
            race_datetime = current_time + timedelta(hours=3)
            deadline_datetime = race_datetime - timedelta(hours=2)
        
        # Calculate time differences using simulated time (same as countdown)
        # Get the current simulated time from the same source as countdown
        try:
            result = db.session.execute(db.text("SELECT simulated_time FROM global_simulation WHERE id = 1")).fetchone()
            current_simulated_time_str = result[0] if result and result[0] else current_time.isoformat()
            current_simulated_time = datetime.fromisoformat(current_simulated_time_str)
        except Exception as e:
            current_simulated_time = current_time
        
        time_to_deadline = deadline_datetime - current_simulated_time
        
        # Check if picks are locked (2 hours before race)
        # If time_to_deadline is negative, deadline has passed and picks are locked
        picks_locked = time_to_deadline.total_seconds() <= 0
    else:
        # Check if picks are locked (2 hours before race)
        # Self-heal timezone/start_time for known races if missing
        try:
            needs_commit = False
            if 'australian' in (competition_obj.name or '').lower():
                if hasattr(competition_obj, 'timezone') and not competition_obj.timezone:
                    competition_obj.timezone = 'Australia/Brisbane'
                    needs_commit = True
                if hasattr(competition_obj, 'start_time') and not competition_obj.start_time:
                    from datetime import time as _t
                    competition_obj.start_time = _t(hour=18, minute=0)
                    needs_commit = True
            elif 'swedish' in (competition_obj.name or '').lower():
                if hasattr(competition_obj, 'timezone') and not competition_obj.timezone:
                    competition_obj.timezone = 'Europe/Stockholm'
                    needs_commit = True
                if hasattr(competition_obj, 'start_time') and not competition_obj.start_time:
                    from datetime import time as _t
                    competition_obj.start_time = _t(hour=17, minute=0)
                    needs_commit = True
            elif 'anaheim 1' in (competition_obj.name or '').lower():
                if hasattr(competition_obj, 'timezone') and not competition_obj.timezone:
                    competition_obj.timezone = 'America/Los_Angeles'
                    needs_commit = True
                # Always set start_time to 11:30 for Anaheim 1 (even if it's already set)
                if hasattr(competition_obj, 'start_time'):
                    from datetime import time as _t
                    correct_time = _t(hour=11, minute=30)
                    current_time = competition_obj.start_time
                    if current_time is None or current_time != correct_time:
                        # Race start 11:30 AM PT (11:30) = Sunday Jan 11, 8:30 PM GMT+1, picks deadline 9:30 AM PT (2h before)
                        competition_obj.start_time = correct_time
                        needs_commit = True
            if needs_commit:
                db.session.commit()
                # Refresh the object to get updated values
                db.session.refresh(competition_obj)
        except Exception as _e:
            db.session.rollback()
            print(f"DEBUG: is_picks_locked failed to auto-fix timezone/start_time: {_e}")
        
        race_date = competition_obj.event_date
        
        # Single source of truth with countdown / race hero (incl. SMX first_quali lock).
        try:
            sched = _competition_race_schedule(competition_obj)
            deadline_utc = sched.get("deadline_utc")
            if deadline_utc is not None:
                current_time = get_current_time()
                picks_locked = (deadline_utc - current_time).total_seconds() <= 0
                return picks_locked
        except Exception as sched_exc:
            print(f"DEBUG: is_picks_locked schedule fallback: {sched_exc}")

        # Use start_time from database if available, otherwise default to 8 PM
        if competition_obj.start_time:
            race_datetime_local = datetime.combine(race_date, competition_obj.start_time)
        else:
            race_time_str = "20:00"  # 8pm local time default
            race_hour, race_minute = map(int, race_time_str.split(':'))
            race_datetime_local = datetime.combine(race_date, datetime.min.time().replace(hour=race_hour, minute=race_minute))
        
        # Convert to UTC for countdown calculation
        # Use proper timezone handling with zoneinfo (Python 3.9+) or pytz fallback
        timezone = getattr(competition_obj, 'timezone', 'America/Los_Angeles')
        
        try:
            # Try using zoneinfo (Python 3.9+)
            from zoneinfo import ZoneInfo
            tz = ZoneInfo(timezone)
            # Make race_datetime_local timezone-aware
            race_datetime_aware = race_datetime_local.replace(tzinfo=tz)
            # Convert to UTC
            race_datetime_utc = race_datetime_aware.astimezone(ZoneInfo('UTC')).replace(tzinfo=None)
        except (ImportError, Exception):
            # Fallback to pytz if zoneinfo not available
            try:
                import pytz
                tz = pytz.timezone(timezone)
                # Make race_datetime_local timezone-aware
                race_datetime_aware = tz.localize(race_datetime_local)
                # Convert to UTC
                race_datetime_utc = race_datetime_aware.astimezone(pytz.UTC).replace(tzinfo=None)
            except ImportError:
                # Final fallback: use fixed offsets (not ideal, but works)
                timezone_offsets = {
                    'America/Los_Angeles': -8,  # PST (winter) / -7 PDT (summer)
                    'America/Denver': -7,       # MST (winter) / -6 MDT (summer)
                    'America/Phoenix': -7,      # MST (no DST)
                    'America/Chicago': -6,      # CST (winter) / -5 CDT (summer)
                    'America/New_York': -5,     # EST (winter) / -4 EDT (summer)
                    'America/Argentina/Buenos_Aires': -3,  # ART (no DST)
                    'Australia/Brisbane': 10,  # AEST (no DST)
                    'Europe/Stockholm': 1  # CET (UTC+1 in winter, UTC+2 in summer)
                }
                # For January, use winter offsets
                utc_offset = timezone_offsets.get(timezone, -8)
                race_datetime_utc = race_datetime_local - timedelta(hours=utc_offset)
        
        
        # Check if picks are locked (2 hours before race)
        current_time = get_current_time()
        time_to_deadline = race_datetime_utc - timedelta(hours=2) - current_time
        picks_locked = time_to_deadline.total_seconds() <= 0
    
    return picks_locked

"""Results import helpers (bulk paste, WSX official, entry CSV).

Refactor skiva 4 — moved from main.py without behavior change.
See docs/REFACTOR.md.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime

from models import CompetitionResult, Rider, db


# Historical typos / alt spellings in DB → official roster name (portraits + display).
# Also used when matching official WSX.com results (Michael Alessi, Crockett Myers, …).
_WSX_NAME_ALIASES = {
    "Jason Andersson": "Jason Anderson",
    "Crockett Meyers": "Crockett Myers",
    "Mike Alessi": "Michael Alessi",
    "Mike Alesssi": "Michael Alessi",
    "Hector Assuncao": "Hector Assunção",
    "Cameron Mcadoo": "Cameron McAdoo",
}

# Common first-name variants for results matching (normalized).
_FIRST_NAME_ALIASES = {
    "michael": {"mike", "michael", "mick"},
    "mike": {"mike", "michael", "mick"},
    "william": {"will", "william", "billy"},
    "will": {"will", "william"},
    "robert": {"rob", "robert", "bobby"},
    "rob": {"rob", "robert"},
    "james": {"jim", "james", "jimmy"},
    "jim": {"jim", "james", "jimmy"},
    "joseph": {"joe", "joseph", "joey"},
    "joe": {"joe", "joseph", "joey"},
    "christopher": {"chris", "christopher"},
    "chris": {"chris", "christopher"},
    "alexander": {"alex", "alexander"},
    "alex": {"alex", "alexander"},
    "nicholas": {"nick", "nicholas"},
    "nick": {"nick", "nicholas"},
    "thomas": {"tom", "thomas", "tommy"},
    "tom": {"tom", "thomas", "tommy"},
}


def _canonical_wsx_rider_name(name: str | None) -> str:
    raw = (name or "").strip()
    if not raw:
        return ""
    return _WSX_NAME_ALIASES.get(raw, raw)


def _dedupe_concatenated_name(name: str) -> str:
    name = name.strip()
    if not name:
        return name
    # Remove extra internal whitespace
    name = re.sub(r"\s+", " ", name)

    # Case 1: Entire string is a double repeat: "Justin CooperJustin Cooper"
    m = re.match(r"^(?P<dup>.+?)\1$", name)
    if m:
        return m.group('dup').strip()

    # Case 2: Even-length exact half repeat by characters
    if len(name) % 2 == 0:
        mid = len(name) // 2
        if name[:mid] == name[mid:]:
            return name[:mid].strip()

    # Case 3: Word-level duplication (e.g., "Justin Cooper Justin Cooper")
    words = name.split()
    if len(words) >= 4:
        half = len(words) // 2
        if len(words) % 2 == 0 and words[:half] == words[half:]:
            return ' '.join(words[:half])

    return ' '.join(words)

def _normalize_name(s: str) -> str:
    if not s:
        return ''
    # Strip accents/diacritics
    s = unicodedata.normalize('NFKD', s)
    s = s.encode('ascii', 'ignore').decode('ascii')
    # Lowercase and remove punctuation
    s = s.lower()
    s = s.replace('.', ' ')
    s = re.sub(r"[^a-z\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def _title_case_name(s: str) -> str:
    """Convert 'KEN ROCZEN' to 'Ken Roczen' for better matching"""
    if not s:
        return s
    return ' '.join(word.capitalize() for word in s.split())


_MX_MOTOS_RE = re.compile(
    r"(\d{1,2}|DNS)\s*-\s*(\d{1,2}|DNS)",
    re.IGNORECASE,
)


def _parse_mx_motos_str(text: str) -> tuple[int | None, int | None]:
    """Parse RacerX moto splits like '1 - 1', '5 - 4', 'DNS - 12'."""
    match = _MX_MOTOS_RE.search(text or "")
    if not match:
        return None, None

    def _token(raw: str) -> int | None:
        token = (raw or "").strip().upper()
        if token == "DNS":
            return None
        try:
            return int(token)
        except ValueError:
            return None

    return _token(match.group(1)), _token(match.group(2))


def _parse_bulk_results(pasted_text: str, format_type: str = 'motocross'):
    bike_brands = {"Honda", "Yamaha", "Kawasaki", "Husqvarna", "GasGas", "KTM", "Suzuki", "Triumph"}
    lines = pasted_text.splitlines()
    results = []
    print(f"🔍 DEBUG: Parsing {format_type} format with {len(lines)} lines")
    
    for i, raw in enumerate(lines):
        line = raw.strip()
        if not line:
            continue
        if line in bike_brands:
            continue
        # RacerX table header when copying MX overall (Pos / Rider / Hometown / Motos / Bike)
        if re.match(r"^(?:pos(?:ition)?|#|rider|hometown|motos|bike)\b", line, re.IGNORECASE):
            continue
        
        print(f"🔍 DEBUG: Line {i+1}: '{line}'")
        
        # Handle Supercross format: "JOEY SAVATGY	14	7 (1)	Clermont, FL" or "FREDDIE NOREN	19	LCQ [1 6/6:23.932 (1) H1]	Lidköping, Sweden"
        if format_type == 'supercross':
            # Handle format: "JOEY SAVATGY	14	7 (1)	Clermont, FL"
            # Pattern: rider_name, position, moto_info, location
            supercross_match = re.match(r'^([A-Z\s]+?)\s+(\d+)\s+\d+\s+\([^)]+\)\s+.*$', line)
            if supercross_match:
                rider_name = supercross_match.group(1).strip()
                position = int(supercross_match.group(2))
                print(f"🔍 DEBUG: Supercross match - Position: {position}, Name: '{rider_name}'")
                # Convert "JOEY SAVATGY" to "Joey Savatgy"
                rider_name = _title_case_name(rider_name)
                rider_name = _dedupe_concatenated_name(rider_name)
                if rider_name:
                    results.append({"position": position, "rider_name": rider_name})
                    print(f"🔍 DEBUG: Added: {position}. {rider_name}")
                    continue
            
            # Handle LCQ format: "FREDDIE NOREN	19	LCQ [1 6/6:23.932 (1) H1]	Lidköping, Sweden"
            lcq_match = re.match(r'^([A-Z\s]+?)\s+(\d+)\s+LCQ\s+\[.*?\]\s+.*$', line)
            if lcq_match:
                rider_name = lcq_match.group(1).strip()
                position = int(lcq_match.group(2))
                print(f"🔍 DEBUG: LCQ match - Position: {position}, Name: '{rider_name}'")
                # Convert "FREDDIE NOREN" to "Freddie Noren"
                rider_name = _title_case_name(rider_name)
                rider_name = _dedupe_concatenated_name(rider_name)
                if rider_name:
                    results.append({"position": position, "rider_name": rider_name})
                    print(f"🔍 DEBUG: Added: {position}. {rider_name}")
                    continue
            
            print(f"🔍 DEBUG: No Supercross match for line: '{line}'")
            # Don't fall back to Motocross parser if format is Supercross
            continue
        
        # Handle Motocross/SMX/RacerX format: "1    Jett Lawrence    Australia    Landsborough, Australia    1 - 2    Honda"
        # Or RacerX HTML table format: "1\tEli Tomac\t22:10.248\t1.470\t1:05.367\tCortez, CO\tKTM 450 SX-F Factory Edition"
        # Accept lines like: 1<TAB>Jett Lawrence... or "1   Jett Lawrence ..."
        cols = re.split(r"\t+|\s{2,}", line)
        if len(cols) >= 2 and cols[0].strip().isdigit():
            try:
                position = int(cols[0].strip())
            except ValueError:
                continue
            rider_field = cols[1].strip()
            
            # Clean up rider name - remove common suffixes/prefixes that might come from HTML
            # Remove image flags, links, etc. that might be in the copied text
            rider_field = re.sub(r'\[.*?\]', '', rider_field)  # Remove [link text]
            rider_field = re.sub(r'\(.*?\)', '', rider_field)  # Remove (parentheses content) if it's not part of name
            rider_field = re.sub(r'<.*?>', '', rider_field)  # Remove HTML tags if any
            rider_field = rider_field.strip()
            
            if not rider_field:
                # Fallback: remove leading position from the line
                m = re.match(r"^(\d+)\s+(.*)$", line)
                rider_field = m.group(2) if m else ''
                # Clean up fallback too
                rider_field = re.sub(r'\[.*?\]', '', rider_field)
                rider_field = re.sub(r'\(.*?\)', '', rider_field)
                rider_field = re.sub(r'<.*?>', '', rider_field)
                rider_field = rider_field.strip()
            
            rider_name = _dedupe_concatenated_name(rider_field)
            bike_brand = None
            if len(cols) >= 3:
                tail = " ".join(cols[2:]).strip()
                for brand in bike_brands:
                    if re.search(rf"\b{re.escape(brand)}\b", tail, re.IGNORECASE):
                        bike_brand = brand
                        break
            # Remove everything after the name (time, interval, hometown, bike, etc.)
            # Stop at common patterns that indicate end of name
            rider_name = re.sub(r'\s+\d{1,2}:\d{2}\.\d+.*$', '', rider_name)  # Remove time like "22:10.248"
            rider_name = re.sub(r'\s+\d+\.\d+.*$', '', rider_name)  # Remove interval like "1.470"
            rider_name = re.sub(r'\s+\d+\s+Laps?.*$', '', rider_name)  # Remove "19 Laps"
            rider_name = re.sub(r'\s+[A-Z][a-z]+,\s+[A-Z]{2}.*$', '', rider_name)  # Remove hometown like "Cortez, CO"
            rider_name = re.sub(r'\s+(Honda|Yamaha|Kawasaki|KTM|Husqvarna|GasGas|Suzuki|Triumph|Ducati|Beta).*$', '', rider_name, flags=re.IGNORECASE)  # Remove bike brand
            rider_name = re.sub(r'\s{2,}.*$', "", rider_name).strip()  # Remove everything after double space
            
            if rider_name:
                entry = {"position": position, "rider_name": rider_name}
                if bike_brand:
                    entry["bike_brand"] = bike_brand
                moto_1, moto_2 = _parse_mx_motos_str(line)
                if moto_1 is not None or moto_2 is not None:
                    entry["moto_1"] = moto_1
                    entry["moto_2"] = moto_2
                results.append(entry)
                print(f"🔍 DEBUG: Motocross/SMX/RacerX match - Position: {position}, Name: '{rider_name}'")
                continue

        # RacerX MX overall with single spaces: "1 Seth Hammaker... 2 - 1 Kawasaki"
        # Fantasy uses overall position (col 1), not moto splits — motos are for verification only.
        mx_moto = re.match(
            r"^(\d{1,2})\s+(.+?)\s+"
            r"((?:\d{1,2}\s*-\s*(?:\d{1,2}|DNS))|(?:DNS\s*-\s*\d{1,2}))\s+",
            line,
            re.IGNORECASE,
        )
        if mx_moto:
            position = int(mx_moto.group(1))
            rider_name = _dedupe_concatenated_name(mx_moto.group(2).strip())
            rider_name = re.sub(r"\s+[A-Z][a-z]+,.*$", "", rider_name).strip()
            rider_name = re.sub(
                r"\s+(Honda|Yamaha|Kawasaki|KTM|Husqvarna|GasGas|Suzuki|Triumph).*$",
                "",
                rider_name,
                flags=re.IGNORECASE,
            ).strip()
            if rider_name:
                moto_1, moto_2 = _parse_mx_motos_str(mx_moto.group(0))
                entry = {"position": position, "rider_name": rider_name}
                if moto_1 is not None or moto_2 is not None:
                    entry["moto_1"] = moto_1
                    entry["moto_2"] = moto_2
                results.append(entry)
                print(f"🔍 DEBUG: MX moto-row match - Position: {position}, Name: '{rider_name}'")

    print(f"🔍 DEBUG: Total parsed results: {len(results)}")
    return results


def _match_rider_for_results_import(
    rider_name: str,
    class_name: str,
    *,
    rider_number: int | None = None,
):
    """Match result row to Rider — aliases, number, and first-name variants."""
    raw_name = (rider_name or "").strip()
    if not raw_name and rider_number is None:
        return None

    # Prefer known WSX alt spellings (Mike Alessi → Michael Alessi, Meyers → Myers)
    name_candidates = []
    if raw_name:
        name_candidates.append(raw_name)
        canon = _canonical_wsx_rider_name(raw_name)
        if canon and canon not in name_candidates:
            name_candidates.append(canon)
        # Reverse: if result uses official name but DB still has typo
        for typo, official in _WSX_NAME_ALIASES.items():
            if official == raw_name and typo not in name_candidates:
                name_candidates.append(typo)
            if official == canon and typo not in name_candidates:
                name_candidates.append(typo)

    for candidate in name_candidates:
        target_norm = _normalize_name(candidate)
        rider = Rider.query.filter(
            Rider.name.ilike(candidate),
            Rider.class_name == class_name,
        ).first()
        if rider:
            return rider
        rider = Rider.query.filter(
            Rider.name.contains(candidate),
            Rider.class_name == class_name,
        ).first()
        if rider:
            return rider
        rider = Rider.query.filter(
            Rider.name.like(f"%{candidate}%"),
            Rider.class_name == class_name,
        ).first()
        if rider:
            return rider
        name_parts = candidate.split()
        if len(name_parts) >= 2:
            first_name = name_parts[0]
            last_name = name_parts[-1]
            rider = Rider.query.filter(
                Rider.name.like(f"%{first_name}%{last_name}%"),
                Rider.class_name == class_name,
            ).first()
            if rider:
                return rider
        candidates = Rider.query.filter(Rider.class_name == class_name).all()
        for cand in candidates:
            if _normalize_name(cand.name) == target_norm:
                return cand

    # Number match within class (WSX cards include race number)
    if rider_number is not None:
        try:
            num = int(rider_number)
        except (TypeError, ValueError):
            num = None
        if num is not None:
            by_num = (
                Rider.query.filter(
                    Rider.class_name == class_name,
                    Rider.rider_number == num,
                ).all()
            )
            if len(by_num) == 1:
                return by_num[0]
            if len(by_num) > 1 and raw_name:
                last = raw_name.split()[-1].lower()
                for cand in by_num:
                    if last and last in (cand.name or "").lower():
                        return cand
                # Myers/Meyers soft last-name compare
                for cand in by_num:
                    cand_last = (cand.name or "").split()[-1].lower()
                    if _normalize_name(cand_last) == _normalize_name(last):
                        return cand
                    if {cand_last, last} <= {"myers", "meyers"}:
                        return cand

    # Last name + first-name nickname variants within class
    if raw_name:
        parts = raw_name.split()
        if len(parts) >= 2:
            first_n = _normalize_name(parts[0])
            last_n = _normalize_name(parts[-1])
            first_opts = _FIRST_NAME_ALIASES.get(first_n, {first_n})
            # Myers <-> Meyers
            last_opts = {last_n}
            if last_n in {"myers", "meyers"}:
                last_opts |= {"myers", "meyers"}
            class_riders = Rider.query.filter(Rider.class_name == class_name).all()
            hits = []
            for cand in class_riders:
                cparts = (cand.name or "").split()
                if len(cparts) < 2:
                    continue
                c_first = _normalize_name(cparts[0])
                c_last = _normalize_name(cparts[-1])
                if c_last in last_opts and c_first in first_opts:
                    hits.append(cand)
            if len(hits) == 1:
                return hits[0]

    return None


def _preview_wsx_official_class_rows(raw_rows: list, class_name: str) -> tuple[list, list]:
    rows = []
    missing = []
    for row in raw_rows:
        rider = _match_rider_for_results_import(
            row["rider_name"],
            class_name,
            rider_number=row.get("rider_number"),
        )
        item = {
            "position": row["position"],
            "rider_name": row["rider_name"],
            "rider_number": row.get("rider_number"),
            "team": row.get("team"),
            "points": row.get("points"),
            "race_1": row.get("race_1"),
            "race_2": row.get("race_2"),
            "race_3": row.get("race_3"),
            "found_in_db": rider is not None,
            "rider_id": rider.id if rider else None,
            "db_rider_name": rider.name if rider else None,
            "class_name": class_name,
        }
        rows.append(item)
        if not rider:
            missing.append(
                {
                    "position": row["position"],
                    "rider_name": row["rider_name"],
                    "rider_number": row.get("rider_number"),
                }
            )
    return rows, missing


def _clear_wsx_competition_results(competition_id: int, class_names: set[str] | None = None) -> int:
    """Delete WSX result rows for a competition. If class_names is None, delete all."""
    rows = (
        db.session.query(CompetitionResult, Rider)
        .outerjoin(Rider, Rider.id == CompetitionResult.rider_id)
        .filter(CompetitionResult.competition_id == int(competition_id))
        .all()
    )
    deleted = 0
    for result, rider in rows:
        if class_names is None:
            db.session.delete(result)
            deleted += 1
            continue
        result_class = _normalize_result_class(
            getattr(result, "class_name", None),
            getattr(rider, "class_name", None) if rider else None,
        )
        rider_class = (getattr(rider, "class_name", None) or "").strip() if rider else ""
        if result_class in class_names or rider_class in class_names:
            db.session.delete(result)
            deleted += 1
            continue
        # Orphan / odd class labels still tied to this WSX round
        raw = (getattr(result, "class_name", None) or "").strip().lower()
        if raw in {"sx1", "sx2", "450cc", "250cc", "wsx_sx1", "wsx_sx2"} and (
            ("wsx_sx1" in class_names and raw in {"sx1", "450cc", "wsx_sx1"})
            or ("wsx_sx2" in class_names and raw in {"sx2", "250cc", "wsx_sx2"})
        ):
            db.session.delete(result)
            deleted += 1
    return deleted


def _upsert_wsx_result_row(
    *,
    competition_id: int,
    rider: Rider,
    class_name: str,
    position: int,
    rider_points: int | None = None,
) -> None:
    existing = CompetitionResult.query.filter_by(
        competition_id=competition_id,
        rider_id=rider.id,
    ).first()
    if existing:
        existing.position = int(position)
        existing.class_name = class_name
        if rider_points is not None and hasattr(existing, "rider_points"):
            existing.rider_points = int(rider_points)
    else:
        kwargs = {
            "competition_id": competition_id,
            "rider_id": rider.id,
            "position": int(position),
            "class_name": class_name,
        }
        if rider_points is not None:
            kwargs["rider_points"] = int(rider_points)
        db.session.add(CompetitionResult(**kwargs))


def _normalize_result_class(result_class: str | None, rider_class: str | None) -> str | None:
    """Class at result time. Falls back to current rider class for older rows."""
    raw = (result_class or rider_class or "").strip().lower()
    if raw in {"450", "450cc", "sx1", "wsx_sx1"}:
        return "450cc"
    if raw in {"250", "250cc", "sx2", "wsx_sx2"}:
        return "250cc"
    return None


def parse_csv_simple(csv_path, class_name):
    import csv
    riders = []
    print(f"🔥 SIMPLE PARSER - Starting to parse {csv_path}")
    
    with open(csv_path, 'r', encoding='utf-8') as file:
        reader = csv.reader(file)
        
        for row_num, row in enumerate(reader, 1):
            print(f"🔥 ROW {row_num}: {row}")
            
            # Skip first 7 rows (headers)
            if row_num <= 7:
                print(f"🔥 SKIPPING HEADER {row_num}")
                continue
            
            # Check if row has content
            if not row or len(row) == 0:
                print(f"🔥 EMPTY ROW {row_num}")
                continue
                
            # Get the text from first column
            text = row[0].strip().strip('"')
            print(f"🔥 TEXT: {text}")
            
            # Check if it starts with a number
            if text and text[0].isdigit():
                print(f"🔥 FOUND RIDER ROW: {text}")
                
                # Split by spaces
                parts = text.split()
                print(f"🔥 PARTS: {parts}")
                
                if len(parts) >= 5:
                    # Find bike brand
                    bike_idx = 2
                    for i, part in enumerate(parts[2:], 2):
                        if part in ['KTM', 'Honda', 'Yamaha', 'Kawasaki', 'Suzuki', 'Husqvarna', 'GasGas', 'Beta', 'Triumph']:
                            bike_idx = i
                            break
                    
                    if bike_idx < len(parts):
                        name = ' '.join(parts[1:bike_idx])
                        bike = parts[bike_idx]
                        hometown = ' '.join(parts[bike_idx+1:-1])
                        team = parts[-1]
                        
                        rider_data = {
                            'number': int(parts[0]),
                            'name': name.strip(),
                            'bike_brand': bike,
                            'hometown': hometown.strip(),
                            'team': team.strip(),
                            'class': class_name
                        }
                        riders.append(rider_data)
                        print(f"🔥 ADDED RIDER: {rider_data['number']} - {rider_data['name']}")
                    else:
                        print(f"🔥 NO BIKE BRAND FOUND")
                else:
                    print(f"🔥 NOT ENOUGH PARTS")
            else:
                print(f"🔥 NOT A RIDER ROW")
    
    print(f"🔥 TOTAL RIDERS FOUND: {len(riders)}")
    return riders

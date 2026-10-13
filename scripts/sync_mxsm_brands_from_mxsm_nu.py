"""Sync bike brands from mxsm.nu standings into data/mxsm_2026_roster.csv (+ optional DB).

Sources:
  https://www.mxsm.nu/resultat/MXSM  -> MX1, MX2 (skip Women)
  https://www.mxsm.nu/resultat/USM   -> skip 85CC, take USM 125 U17
"""
from __future__ import annotations

import csv
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "data" / "mxsm_2026_roster.csv"

SOURCES = (
    ("https://www.mxsm.nu/resultat/MXSM", ("mxsm_mx1", "mxsm_mx2")),  # 3rd table = Women
    ("https://www.mxsm.nu/resultat/USM", (None, "mxsm_u17")),  # 1st = 85CC, 2nd = U17
)


def fetch_html(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 MXFantasyBrandSync"})
    with urllib.request.urlopen(req, timeout=45) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _clean_cell(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", text)).strip()


def parse_html_tables(html: str) -> list[list[dict]]:
    tables: list[list[dict]] = []
    for table_html in re.findall(r"<table[\s\S]*?</table>", html, flags=re.I):
        headers = [_clean_cell(h).lower() for h in re.findall(r"<th[^>]*>([\s\S]*?)</th>", table_html, flags=re.I)]
        if not headers:
            continue

        def col(*names: str) -> int | None:
            for i, h in enumerate(headers):
                if any(n in h for n in names):
                    return i
            return None

        i_nr = col("nr", "no", "nummer")
        i_name = col("namn", "name")
        i_brand = col("fabrikat", "brand", "märke")
        i_team = col("team", "sponsor")
        if i_nr is None or i_name is None:
            continue

        rows: list[dict] = []
        for tr in re.findall(r"<tr[\s\S]*?</tr>", table_html, flags=re.I):
            cells = [_clean_cell(c) for c in re.findall(r"<t[dh][^>]*>([\s\S]*?)</t[dh]>", tr, flags=re.I)]
            if len(cells) < 3:
                continue
            if cells[0].lower() in ("pos", "#", "nr"):
                continue
            try:
                number = int(re.sub(r"[^\d]", "", cells[i_nr]) or "0")
            except ValueError:
                continue
            if number <= 0:
                continue
            name = cells[i_name]
            if not name or name.lower() == "namn":
                continue
            brand = cells[i_brand] if i_brand is not None and i_brand < len(cells) else ""
            team = cells[i_team] if i_team is not None and i_team < len(cells) else ""
            rows.append(
                {
                    "number": number,
                    "name": name,
                    "brand": brand.strip(" -") or "",
                    "team": team.strip(" -") or "",
                }
            )
        if rows:
            tables.append(rows)
    return tables


def parse_markdown_tables(text: str) -> list[list[dict]]:
    """Fallback for WebFetch-style pipe tables."""
    tables: list[list[dict]] = []
    blocks = re.split(r"\n(?=\| Pos \|)", text)
    for block in blocks:
        lines = [ln.strip() for ln in block.splitlines() if ln.strip().startswith("|")]
        if len(lines) < 3:
            continue
        headers = [h.strip().lower() for h in lines[0].strip("|").split("|")]
        if "fabrikat" not in headers or "nr" not in headers or "namn" not in headers:
            continue
        i_nr = headers.index("nr")
        i_name = headers.index("namn")
        i_brand = headers.index("fabrikat")
        i_team = headers.index("team") if "team" in headers else None
        rows: list[dict] = []
        for ln in lines[2:]:
            cells = [c.strip() for c in ln.strip("|").split("|")]
            if len(cells) <= max(i_nr, i_name):
                continue
            try:
                number = int(re.sub(r"[^\d]", "", cells[i_nr]) or "0")
            except ValueError:
                continue
            if number <= 0:
                continue
            brand = cells[i_brand].strip(" -") if i_brand < len(cells) else ""
            team = cells[i_team].strip(" -") if i_team is not None and i_team < len(cells) else ""
            rows.append(
                {
                    "number": number,
                    "name": cells[i_name],
                    "brand": brand or "",
                    "team": team or "",
                }
            )
        if rows:
            tables.append(rows)
    return tables


def load_csv() -> list[dict]:
    with CSV_PATH.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def save_csv(rows: list[dict]) -> None:
    with CSV_PATH.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["class", "number", "name", "brand", "team"])
        w.writeheader()
        w.writerows(rows)


def apply_table(roster: list[dict], cls: str, table: list[dict]) -> tuple[int, int, int]:
    by_num: dict[int, list[dict]] = {}
    by_key: dict[tuple[int, str], dict] = {}
    for r in roster:
        if r["class"] != cls:
            continue
        num = int(r["number"])
        by_num.setdefault(num, []).append(r)
        by_key[(num, (r["name"] or "").strip().lower())] = r

    matched = updated_brand = updated_team = 0
    for row in table:
        target = by_key.get((row["number"], row["name"].strip().lower()))
        if target is None:
            cands = by_num.get(row["number"]) or []
            target = cands[0] if len(cands) == 1 else None
        if not target:
            continue
        matched += 1
        if row["brand"] and not (target.get("brand") or "").strip():
            target["brand"] = row["brand"]
            updated_brand += 1
        if row["team"] and not (target.get("team") or "").strip():
            target["team"] = row["team"]
            updated_team += 1
    return matched, updated_brand, updated_team


def cross_fill_by_name(roster: list[dict]) -> int:
    """If same name has exactly one known brand elsewhere, copy it."""
    by_name: dict[str, set[str]] = {}
    for r in roster:
        b = (r.get("brand") or "").strip()
        if b:
            by_name.setdefault(r["name"].strip().lower(), set()).add(b)
    n = 0
    for r in roster:
        if (r.get("brand") or "").strip():
            continue
        brands = by_name.get(r["name"].strip().lower()) or set()
        if len(brands) == 1:
            r["brand"] = next(iter(brands))
            n += 1
    return n


def update_db_via_ensure() -> dict:
    sys.path.insert(0, str(ROOT))
    import main  # noqa: E402
    import mxsm_fantasy  # noqa: E402

    with main.app.app_context():
        stats = mxsm_fantasy.ensure_mxsm_2026_roster()
        from models import db  # noqa: E402

        db.session.commit()
        return stats


def main() -> None:
    roster = load_csv()
    before_empty = sum(1 for r in roster if not (r.get("brand") or "").strip())
    total_matched = total_brand = total_team = 0

    for url, class_map in SOURCES:
        try:
            html = fetch_html(url)
            tables = parse_html_tables(html)
            if not tables:
                tables = parse_markdown_tables(html)
        except Exception as e:
            print(f"fetch failed {url}: {e}")
            continue
        print(f"{url}: {len(tables)} tables sizes={[len(t) for t in tables]}")
        for cls, table in zip(class_map, tables):
            if cls is None:
                continue
            m, b, t = apply_table(roster, cls, table)
            total_matched += m
            total_brand += b
            total_team += t
            print(f"  {cls}: matched={m} brand+={b} team+={t}")

    cross = cross_fill_by_name(roster)
    save_csv(roster)
    after_empty = sum(1 for r in roster if not (r.get("brand") or "").strip())
    print(f"cross-fill: {cross}")
    print(f"totals matched={total_matched} brand+={total_brand} team+={total_team}")
    print(f"empty brand: {before_empty} -> {after_empty}")

    if "--db" in sys.argv:
        stats = update_db_via_ensure()
        print("ensure_mxsm_2026_roster:", stats)


if __name__ == "__main__":
    main()

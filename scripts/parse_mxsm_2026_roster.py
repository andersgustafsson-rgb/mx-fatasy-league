"""Parse pasted MXSM 2026 roster into data/mxsm_2026_roster.csv."""
from __future__ import annotations

import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "mxsm_2026_roster_paste.txt"
OUT = ROOT / "data" / "mxsm_2026_roster.csv"

# Paste order: block1=MX1, block2=MX2, block3=U17 (confirm with user if needed)
BLOCK_MARKERS = (
    (re.compile(r"#496\s+Alve Callemo"), "mxsm_mx2"),
    (re.compile(r"#549\s+Storm Maymann"), "mxsm_u17"),
)

LINE_RE = re.compile(
    r"^#(\d+)\s+(.+?)\s*\|\s*(.*?)\s*\|\s*(.*?)\s*$"
)


def parse_lines(text: str) -> list[dict]:
    cls = "mxsm_mx1"
    rows: list[dict] = []
    seen: set[tuple[str, str, str]] = set()

    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") and " " not in line:
            continue
        for pat, new_cls in BLOCK_MARKERS:
            if pat.search(line):
                cls = new_cls
                break
        m = LINE_RE.match(line)
        if not m:
            # merged lines like "... Berg | - | - #496 Alve ..."
            parts = re.split(r"\s+(?=#\d+\s)", line)
            for part in parts:
                m2 = LINE_RE.match(part.strip())
                if m2:
                    _append_row(rows, seen, cls, m2)
            continue
        _append_row(rows, seen, cls, m)

    return rows


def _append_row(rows, seen, cls, m):
    num, name, brand, team = m.group(1), m.group(2).strip(), m.group(3).strip(), m.group(4).strip()
    brand = None if brand in ("", "-") else brand
    team = None if team in ("", "-") else team
    key = (cls, name.lower(), num)
    if key in seen:
        return
    seen.add(key)
    rows.append(
        {
            "class": cls,
            "number": int(num),
            "name": name,
            "brand": brand or "",
            "team": team or "",
        }
    )


def main() -> None:
    if not RAW.is_file():
        print(f"Missing {RAW}")
        return
    text = RAW.read_text(encoding="utf-8")
    rows = parse_lines(text)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["class", "number", "name", "brand", "team"])
        w.writeheader()
        w.writerows(rows)
    by_cls: dict[str, int] = {}
    for r in rows:
        by_cls[r["class"]] = by_cls.get(r["class"], 0) + 1
    print(f"Wrote {len(rows)} riders to {OUT}")
    for k, v in sorted(by_cls.items()):
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()

"""Test: hämta förarbio från en RacerX-profil (en förare)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from racerx_rider_bio import fetch_racerx_rider_profile


def main() -> None:
    name = (sys.argv[1] if len(sys.argv) > 1 else "Haiden Deegan").strip()
    data = fetch_racerx_rider_profile(name)
    print(json.dumps(data, indent=2, ensure_ascii=False))
    if not data.get("ok"):
        sys.exit(1)


if __name__ == "__main__":
    main()

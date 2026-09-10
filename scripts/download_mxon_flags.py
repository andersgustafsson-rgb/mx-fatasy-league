"""Download MXoN nation flags into static/images/mxon/flags/."""
from __future__ import annotations

import urllib.request
from pathlib import Path

from mxon_fantasy import _CODE_TO_ALPHA2

OUT = Path("static/images/mxon/flags")
OUT.mkdir(parents=True, exist_ok=True)

(OUT / "lam.svg").write_text(
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 48">'
    '<rect width="64" height="48" rx="4" fill="#1e3a5f"/>'
    '<circle cx="32" cy="24" r="12" fill="none" stroke="#67e8f9" stroke-width="2"/>'
    '<path d="M20 24h24M32 12c6 6 6 18 0 24M32 12c-6 6-6 18 0 24" '
    'fill="none" stroke="#94a3b8" stroke-width="1.5"/>'
    "</svg>",
    encoding="utf-8",
)
(OUT / "unknown.svg").write_text(
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 48">'
    '<rect width="64" height="48" rx="4" fill="#334155"/>'
    '<text x="32" y="30" text-anchor="middle" fill="#94a3b8" '
    'font-size="18" font-family="sans-serif">?</text></svg>',
    encoding="utf-8",
)

ok = fail = 0
for _code, a2 in sorted(set(_CODE_TO_ALPHA2.items()), key=lambda x: x[1]):
    dest = OUT / f"{a2.lower()}.png"
    if dest.exists() and dest.stat().st_size > 200:
        ok += 1
        continue
    url = f"https://flagcdn.com/w80/{a2.lower()}.png"
    try:
        urllib.request.urlretrieve(url, dest)
        ok += 1
        print("ok", a2, dest.stat().st_size)
    except Exception as e:
        fail += 1
        print("FAIL", a2, e)

print("done ok=", ok, "fail=", fail, "files=", len(list(OUT.iterdir())))

#!/usr/bin/env python3
"""Generate VAPID keys for Web Push. Paste into Render env vars."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    priv = root / "private_key.pem"
    pub = root / "public_key.pem"
    for p in (priv, pub):
        if p.exists():
            p.unlink()
    subprocess.run([sys.executable, "-m", "py_vapid", "--gen"], check=True, cwd=root)
    out = subprocess.run(
        [sys.executable, "-m", "py_vapid", "--applicationServerKey", "--private-key", str(priv)],
        check=True,
        capture_output=True,
        text=True,
        cwd=root,
    )
    app_key = ""
    for line in out.stdout.splitlines():
        if "Application Server Key" in line:
            app_key = line.split("=", 1)[-1].strip()
    pem = priv.read_text(encoding="utf-8").strip()
    one_line = pem.replace("\n", "\\n")
    print("\n=== Lägg in på Render (Environment) ===\n")
    print(f"VAPID_PUBLIC_KEY={app_key}")
    print(f"VAPID_PRIVATE_KEY={one_line}")
    print("VAPID_SUBJECT=mailto:din@email.se")
    print("\n(Radera private_key.pem / public_key.pem från disk efteråt — committa dem INTE.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Render MXoN crowd power-ranking posters (Facebook + Story).

Usage (repo root, with app context / local DB that has tips):
  py -3 scripts/render_mxon_power_ranking_poster.py
  py -3 scripts/render_mxon_power_ranking_poster.py --competition-id 76
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="Render MXoN power ranking posters")
    parser.add_argument("--competition-id", type=int, default=None)
    args = parser.parse_args()

    from main import app
    from mxon_power_ranking_poster_service import (
        build_mxon_power_ranking_poster_data,
        render_mxon_power_ranking_poster_png,
    )

    out_dir = ROOT / "static" / "posters"
    out_dir.mkdir(parents=True, exist_ok=True)

    with app.app_context():
        data = build_mxon_power_ranking_poster_data(args.competition_id)
        fb = render_mxon_power_ranking_poster_png(data, layout="facebook")
        story = render_mxon_power_ranking_poster_png(data, layout="story")
        caption = data.get("caption") or ""

    fb_path = out_dir / "mxon_power_ranking_fb.png"
    story_path = out_dir / "mxon_power_ranking_story.png"
    caption_path = out_dir / "mxon_power_ranking_caption.txt"
    fb_path.write_bytes(fb)
    story_path.write_bytes(story)
    caption_path.write_text(caption, encoding="utf-8")

    print(f"Wrote {fb_path} ({len(fb)} bytes)")
    print(f"Wrote {story_path} ({len(story)} bytes)")
    print(f"Wrote {caption_path}")
    print("--- Facebook text ---")
    print(caption)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Render power-ranking posters (Facebook + Story) for any series.

Usage:
  py -3 scripts/render_mxon_power_ranking_poster.py --competition-id 76
  py -3 scripts/render_mxon_power_ranking_poster.py --competition-id 70
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="Render power ranking posters")
    parser.add_argument("--competition-id", type=int, default=None)
    args = parser.parse_args()

    from main import app
    from mxon_power_ranking_poster_service import (
        build_power_ranking_poster_data,
        render_power_ranking_poster_png,
    )

    out_dir = ROOT / "static" / "posters"
    out_dir.mkdir(parents=True, exist_ok=True)

    with app.app_context():
        data = build_power_ranking_poster_data(args.competition_id)
        fb = render_power_ranking_poster_png(data, layout="facebook")
        story = render_power_ranking_poster_png(data, layout="story")
        caption = data.get("caption") or ""
        series = (data.get("series") or "race").lower()
        kind = data.get("kind") or "ranking"
        comp_id = data.get("competition_id") or "x"

    stem = f"power_ranking_{series}_{comp_id}"
    fb_path = out_dir / f"{stem}_fb.png"
    story_path = out_dir / f"{stem}_story.png"
    caption_path = out_dir / f"{stem}_caption.txt"
    if kind == "mxon_crowd":
        fb_path = out_dir / "mxon_power_ranking_fb.png"
        story_path = out_dir / "mxon_power_ranking_story.png"
        caption_path = out_dir / "mxon_power_ranking_caption.txt"

    fb_path.write_bytes(fb)
    story_path.write_bytes(story)
    caption_path.write_text(caption, encoding="utf-8")

    print(f"kind={kind} series={data.get('series')} comp={comp_id}")
    print(f"Wrote {fb_path} ({len(fb)} bytes)")
    print(f"Wrote {story_path} ({len(story)} bytes)")
    print(f"Wrote {caption_path}")
    print("--- Facebook text ---")
    print(caption)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

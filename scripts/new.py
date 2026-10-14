"""Start a project from one clip (use join.py first for a folder of phone clips).

python new.py <slug> <clip> ["Title"]   ->  $REEL_HOME/projects/<slug>/

Needs an approved style first (style.py, SKILL.md step 0). --default-style skips that and uses the clean preset.
"""
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import PRESETS, PROJECTS, STYLE_DIR, duration, die, probe, read_json, save_plan, video_stream  # noqa: E402


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) < 2:
        sys.exit(__doc__)
    slug, clip = args[0], os.path.abspath(os.path.expanduser(args[1]))
    title = args[2] if len(args) > 2 else slug.replace("-", " ").title()
    style_file = os.path.join(STYLE_DIR, "style.json")
    if "--default-style" in sys.argv:
        style_file = os.path.join(PRESETS, "clean.json")
    elif not (read_json(style_file) or {}).get("approved"):
        die("no approved style yet: run the style step first (style.py, SKILL.md step 0)")
    if not os.path.isfile(clip):
        die(f"no such clip: {clip}")
    project = os.path.join(PROJECTS, slug)
    if os.path.exists(os.path.join(project, "plan.json")):
        die(f"{project} already exists")
    v = video_stream(probe(clip))
    if not v:
        die("that file has no video")
    for sub in ("media", "fx", "public", "work", "renders", "audio"):
        os.makedirs(os.path.join(project, sub), exist_ok=True)
    shutil.copy(style_file, os.path.join(project, "style.json"))
    plan = {
        "title": title,
        "source": clip,
        "prompt": "",
        "keep": [[0.0, round(duration(clip), 3)]],
        "fixes": {},
        "crop": None,
        "face": None,
        "captions": {"moves": [], "off": []},
        "boxes": [],
        "overlays": [],
        "behind": [],
        "grade": [],
        "fx": [],
        "sfx": [],
        "music": None,
        "vocabulary": [],
        "needs": [],
    }
    save_plan(project, plan)
    rot = next((sd.get("rotation") for sd in v.get("side_data_list", []) if "rotation" in sd), 0)
    print(f"{project}\nsource {v['width']}x{v['height']}{' rotated ' + str(rot) if rot else ''}, "
          f"{duration(clip):.1f}s. Next: transcribe.py {slug}")


if __name__ == "__main__":
    main()

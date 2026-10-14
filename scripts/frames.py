"""Gridded frames, to see where the face is before placing anything (nothing may cover it).

python frames.py <project> [--every 4 | --at 1.5,9,20] [--source]
-> <project>/work/frames.jpg: frames of the cut (or the raw source) side by side, a line every 100 px,
   each labelled with its time. Read the face box off it and put it in plan.face as [x, y, w, h].
"""
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import FONTS, duration, has_filter, load_plan, project_arg, run  # noqa: E402


def main():
    project = project_arg("<project> [--every S | --at T1,T2] [--source]")
    plan = load_plan(project)
    src = plan["source"] if "--source" in sys.argv else os.path.join(project, "public", "clean.mp4")
    total = duration(src)
    if "--at" in sys.argv:
        times = [float(t) for t in sys.argv[sys.argv.index("--at") + 1].split(",")]
    else:
        every = float(sys.argv[sys.argv.index("--every") + 1]) if "--every" in sys.argv else max(total / 8, 1)
        times = [round(every * k + every / 2, 2) for k in range(int(total // every))][:12] or [total / 2]
    font = (glob.glob(os.path.join(FONTS, "*Mono*.ttf")) + glob.glob(os.path.join(FONTS, "*.ttf")) + [""])[0]
    if not has_filter("drawtext"):              # ffmpeg built without freetype: no labels, times listed below
        font = ""
    work = os.path.join(project, "work")
    tiles = []
    for i, t in enumerate(times):
        tile = os.path.join(work, f"grid-{i:02d}.jpg")
        label = f",drawtext=fontfile='{font}':text='{t:.2f}s':x=20:y=20:fontsize=56:fontcolor=yellow:box=1:" \
                f"boxcolor=black@0.6" if font else ""
        vf = (("scale=1080:1920," if "--source" in sys.argv else "") +
              "drawgrid=w=100:h=100:t=2:c=white@0.35" + label + ",scale=360:-2")
        run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", src, "-frames:v", "1", "-vf", vf, tile])
        tiles.append(tile)
    out = os.path.join(work, "frames.jpg")
    cols = min(len(tiles), 6)
    rows = (len(tiles) + cols - 1) // cols
    inputs = sum((["-i", p] for p in tiles), [])
    run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex",
         "".join(f"[{i}]" for i in range(len(tiles))) + f"xstack=inputs={len(tiles)}:layout=" +
         "|".join(f"{(i % cols) * 360}_{(i // cols) * 640}" for i in range(len(tiles))) + ":fill=black"
         if len(tiles) > 1 else "null", out])
    for p in tiles:
        os.remove(p)
    print(f"-> {out} ({len(times)} frames, {cols}x{rows}, left to right: {', '.join(f'{t:.2f}s' for t in times)}; "
          "grid lines every 100 px of the 1080x1920 frame)")


if __name__ == "__main__":
    main()

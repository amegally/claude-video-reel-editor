"""Step 0: find the user's style before editing anything. Everything lands in $REEL_HOME/style/.

python style.py refs <url-or-file> [...]   download 2-3 example videos, pull frames + transcript + pace numbers
                                           -> style/refs/ (Claude reads the sheets and writes style/style.json)
python style.py menu <clip>                one frame of the user's own take in every preset -> style/menu/index.html
python style.py use <preset>               start style/style.json from a preset (clean, editorial, mono, punch, film)
python style.py board <clip>               one frame of the user's take in style/style.json -> style/board.png
python style.py approve                    mark style/style.json approved; every new project copies it
python style.py sounds <folder>            sort the user's own sound effects into roles (sounds.py) and save the map
"""
import glob
import html
import json
import os
import re
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (FPS, PRESETS, PY, STYLE_DIR, die, duration, hf, probe, read_json, run,  # noqa: E402
                    save_plan, video_stream, write_json)

OPUSCAR = "https://lemomo-ai.github.io/lemo-opuscar/"
OPUSCAR_PICKS = [   # the six that work as type, cards and backdrops AROUND a person on camera (linked, never copied)
    ("swiss-motion", "Swiss Motion Graphics", "Clean bold type on a grid, one red accent."),
    ("halftone-dossier", "Halftone Dossier", "Newspaper halftone, case-file stamps, big headlines."),
    ("dark-keynote", "Dark Tech Keynote", "Floating dark glass windows, product-launch polish."),
    ("living-screencast", "Living Screencast", "Real app and terminal windows on warm paper."),
    ("whiteboard", "Whiteboard Explainer", "Hand-drawn marker diagrams and underlines."),
    ("risograph", "Risograph Print", "Two misregistered inks, grain, bright and warm."),
]


def opuscar_links(slug):
    return (f"https://github.com/lemomo-ai/lemo-opuscar/blob/main/styles/{slug}/STYLE.md",
            f"https://raw.githubusercontent.com/lemomo-ai/lemo-opuscar/main/docs/frames/{slug}.jpg")


GALLERIES = [
    ("Lemo-Opuscar", "https://lemomo-ai.github.io/lemo-opuscar/", "43 film styles, each a style prompt plus a demo "
     "film made in code (MIT)"),
    ("HyperFrames", "https://hyperframes.dev", "the engine this skill renders with: examples and blocks (Apache-2.0)"),
    ("onetake", "https://onetakemotion.com", "continuous-camera motion films (non-commercial licence: look, "
     "don't copy)"),
    ("Collage B-roll", "https://github.com/pyang5166/gbro-collage-broll", "halftone paper-collage B-roll (MIT, "
     "uses Gemini)"),
    ("Claude Animation Base", "https://github.com/JohnHeibel/ClaudeAnimationBase", "hand-painted cartoon "
     "animation (MIT)"),
]


# ---------- refs: learn a style from example videos ----------

def fetch(ref, folder, i):
    if os.path.exists(os.path.expanduser(ref)):
        dst = os.path.join(folder, f"ref{i}{os.path.splitext(ref)[1] or '.mp4'}")
        shutil.copy(os.path.expanduser(ref), dst)
        return dst
    out = os.path.join(folder, f"ref{i}.%(ext)s")
    p = subprocess.run([PY, "-m", "yt_dlp", "-q", "--no-playlist", "-f", "mp4/bestvideo*+bestaudio/best",
                        "--merge-output-format", "mp4", "-o", out, ref], capture_output=True, text=True)
    got = glob.glob(os.path.join(folder, f"ref{i}.*"))
    if p.returncode or not got:
        print(f"could not download {ref}: {(p.stderr or '').strip()[-300:]}\n"
              "  (Instagram often needs a login: ask the user to save the video and pass the file instead)")
        return None
    return got[0]


def scene_cuts(path):
    err = run(["ffmpeg", "-hide_banner", "-i", path, "-vf", "scale=270:-2,select='gt(scene,0.32)',showinfo",
               "-an", "-f", "null", "-"]).stderr
    return [float(t) for t in re.findall(r"pts_time:([\d.]+)", err)]


def analyse(path, i, folder):
    dur = duration(path)
    v = video_stream(probe(path))
    cuts = scene_cuts(path)
    shots = [b - a for a, b in zip([0.0] + cuts, cuts + [dur])]
    sheet = os.path.join(folder, f"ref{i}-sheet.jpg")
    step = max(dur / 16, 0.5)
    run(["ffmpeg", "-v", "error", "-y", "-i", path, "-vf", f"fps=1/{step:.3f},scale=270:-2,tile=8x2:padding=6",
         "-frames:v", "1", "-q:v", "3", sheet])
    stills = []
    for k, frac in enumerate((0.12, 0.4, 0.7)):
        out = os.path.join(folder, f"ref{i}-frame{k + 1}.jpg")
        run(["ffmpeg", "-v", "error", "-y", "-ss", f"{dur * frac:.2f}", "-i", path, "-frames:v", "1",
             "-vf", "scale=720:-2", "-q:v", "3", out])
        stills.append(os.path.basename(out))
    words = []
    if any(s["codec_type"] == "audio" for s in probe(path)["streams"]):
        from transcribe import run_model
        words = run_model(path, "")
    return {
        "file": os.path.basename(path), "seconds": round(dur, 1), "size": f"{v['width']}x{v['height']}",
        "cuts": len(cuts), "cuts_per_min": round(len(cuts) / dur * 60, 1),
        "median_shot_s": round(sorted(shots)[len(shots) // 2], 2) if shots else None,
        "words_per_min": round(len(words) / dur * 60) if words else None,
        "transcript": " ".join(w["w"] for w in words), "sheet": os.path.basename(sheet), "frames": stills,
    }


def refs(items):
    folder = os.path.join(STYLE_DIR, "refs")
    os.makedirs(folder, exist_ok=True)
    report = []
    for i, ref in enumerate(items, 1):
        path = fetch(ref, folder, i)
        if path:
            r = analyse(path, i, folder)
            r["from"] = ref
            report.append(r)
            print(f"ref{i}: {r['seconds']}s, {r['cuts_per_min']} cuts/min, median shot {r['median_shot_s']}s, "
                  f"{r['words_per_min']} words/min -> {r['sheet']}, {', '.join(r['frames'])}")
    write_json(os.path.join(folder, "report.json"), report)
    print(f"\n{len(report)} of {len(items)} references in {folder}. Look at every sheet and frame, then write "
          f"{STYLE_DIR}/style.json (start from: python style.py use <closest preset>).")


# ---------- board: one frame of the user's own take in a style ----------

def take_words(clip, limit=7):
    """a few words the user actually says in this clip (the board never shows invented text)"""
    from transcribe import run_model
    snippet = os.path.join(STYLE_DIR, "work", "snippet.wav")
    os.makedirs(os.path.dirname(snippet), exist_ok=True)
    run(["ffmpeg", "-v", "error", "-y", "-i", clip, "-t", "25", "-vn", "-ac", "1", "-ar", "16000", snippet])
    words = run_model(snippet, "")
    return [w["w"] for w in words[:limit]]


def board_project(clip, style, words, name):
    """a one-second project: a still of the take, the style, a caption line and a title box of the user's words"""
    from cut import crop_filter
    proj = os.path.join(STYLE_DIR, "work", name)
    for sub in ("public", "work"):
        os.makedirs(os.path.join(proj, sub), exist_ok=True)
    write_json(os.path.join(proj, "style.json"), style)
    at = duration(clip) * 0.4
    run(["ffmpeg", "-v", "error", "-y", "-ss", f"{at:.2f}", "-i", clip, "-frames:v", "1", "-vf",
         crop_filter({"crop": None}, video_stream(probe(clip))), os.path.join(proj, "work", "still.png")])
    run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-t", "1", "-i", os.path.join(proj, "work", "still.png"),
         "-r", str(FPS), "-c:v", "libx264", "-pix_fmt", "yuv420p", os.path.join(proj, "public", "clean.mp4")])
    cap = words[:style["captions"]["max_words"]]
    write_json(os.path.join(proj, "words.json"),
               [{"w": w, "s": 0.02 + k * 0.06, "e": 0.07 + k * 0.06, "seg": 0} for k, w in enumerate(cap)])
    write_json(os.path.join(proj, "work", "segments.json"), [{"src_s": 0, "src_e": 1, "out_s": 0, "out_e": 1}])
    title = " ".join(words[:3]) if words else ""
    save_plan(proj, {"title": name, "source": clip, "keep": [[0, 1]], "fixes": {}, "captions": {},
                     "boxes": [{"text": html.escape(title), "start": 0, "end": 1, "y": 240}] if title else [],
                     "overlays": [], "behind": [], "grade": [], "fx": [], "sfx": []})
    return proj


def snapshot(proj, at, out_png):
    from build import build
    pub = os.path.dirname(build(proj, need_audio=False))
    shots = os.path.join(proj, "shots")
    shutil.rmtree(shots, ignore_errors=True)
    hf(["snapshot", "-o", shots, "--at", f"{at}", "--no-end", "--describe", "false", pub], cwd=pub)
    pngs = sorted(glob.glob(os.path.join(shots, "frame-*.png")))
    if not pngs:
        die("the snapshot wrote no frame")
    shutil.copy(pngs[0], out_png)
    return out_png


def board(clip, style_path=None, out=None, words=None):
    style = read_json(style_path or os.path.join(STYLE_DIR, "style.json"))
    if not style:
        die("no style yet: python style.py use <preset>, or write style/style.json from refs")
    words = words if words is not None else take_words(clip)
    proj = board_project(clip, style, words, "board-" + style.get("name", "style"))
    out = out or os.path.join(STYLE_DIR, "board.png")
    snapshot(proj, 0.6, out)                         # every word is in, the caption line hasn't ended
    print(f"-> {out}")
    return out


def menu(clip):
    folder = os.path.join(STYLE_DIR, "menu")
    os.makedirs(folder, exist_ok=True)
    words = take_words(clip)
    cards = []
    for path in sorted(glob.glob(os.path.join(PRESETS, "*.json"))):
        st = read_json(path)
        png = board(clip, path, os.path.join(folder, f"{st['name']}.png"), words)
        cards.append(f'<figure><img src="{os.path.basename(png)}"><figcaption><b>{st["name"]}</b>'
                     f'{html.escape(st["about"])}</figcaption></figure>')
    picks = "".join(
        f'<figure><a href="{opuscar_links(slug)[0]}"><img src="{opuscar_links(slug)[1]}" class="wide"></a>'
        f'<figcaption><b>{html.escape(title)}</b>{html.escape(about)} <code>{slug}</code></figcaption></figure>'
        for slug, title, about in OPUSCAR_PICKS)
    links = "".join(f'<li><a href="{u}">{n}</a>: {html.escape(d)}</li>' for n, u, d in GALLERIES)
    with open(os.path.join(folder, "index.html"), "w") as f:
        f.write(f"""<!doctype html><html><head><meta charset="utf-8"><title>Pick a style</title><style>
body{{margin:0;font:16px/1.5 system-ui,sans-serif;background:#111;color:#eee;padding:24px}}
h1{{font-size:22px}}.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:20px}}
figure{{margin:0}}img{{width:100%;border-radius:8px;display:block}}
img.wide{{aspect-ratio:16/9;object-fit:cover}}code{{color:#888}}figcaption{{font-size:14px;color:#bbb;
margin-top:8px}}figcaption b{{display:block;color:#fff;font-size:16px}}a{{color:#9cf}}
</style></head><body><h1>Pick a starting style, then say what to change</h1>
<h2>Six looks that work around a person on camera</h2>
<p>From Lemo-Opuscar. They were made for 16:9 animated films, so Claude adapts the one you pick to a vertical
talking-head video: type, cards and backdrops around you, never over your face. Click one to read its style.</p>
<div class="grid">{picks}</div><p><a href="{OPUSCAR}">See all 43 Lemo-Opuscar styles</a></p>
<h2>Or start from one of these, shown on your own take</h2>
<p>Tell Claude the name, plus anything to make it yours (fonts, colours, captions, pace).</p>
<div class="grid">{''.join(cards)}</div>
<h2>More looks to borrow ideas from</h2><ul>{links}</ul></body></html>""")
    print(f"-> {os.path.join(folder, 'index.html')}")


def use(name):
    src = os.path.join(PRESETS, f"{name}.json")
    if not os.path.exists(src):
        die(f"no preset '{name}': " + ", ".join(os.path.basename(p)[:-5] for p in glob.glob(PRESETS + "/*.json")))
    st = read_json(src)
    st["approved"] = False
    os.makedirs(STYLE_DIR, exist_ok=True)
    write_json(os.path.join(STYLE_DIR, "style.json"), st)
    print(f"-> {STYLE_DIR}/style.json (from {name}; not approved yet)")


def approve():
    path = os.path.join(STYLE_DIR, "style.json")
    st = read_json(path) or die("no style.json to approve")
    st["approved"] = True
    with open(path, "w") as f:
        json.dump(st, f, indent=2)
    print(f"approved: {st.get('name')} ({path})")


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    cmd, rest = sys.argv[1], sys.argv[2:]
    if cmd == "refs" and rest:
        refs(rest)
    elif cmd == "menu" and rest:
        menu(os.path.abspath(os.path.expanduser(rest[0])))
    elif cmd == "board" and rest:
        board(os.path.abspath(os.path.expanduser(rest[0])))
    elif cmd == "use" and rest:
        use(rest[0])
    elif cmd == "approve":
        approve()
    elif cmd == "sounds" and rest:
        subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "sounds.py"), *rest],
                       check=False)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()

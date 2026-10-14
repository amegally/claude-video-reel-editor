"""One-time setup. Run it with the Python you want the venv built from (3.10 or newer):

    python3 scripts/setup.py                 everything, ends with READY
    python3 scripts/setup.py --no-matte      skip PyTorch (no cutout, so nothing can go behind the speaker)
    python3 scripts/setup.py --font "Anton:400"   download one more Google Font

Installs into $REEL_HOME (default ~/reels): a venv, fonts, GSAP and the speech model, then renders a one-second
test video with HyperFrames (which keeps its headless Chrome in ~/.cache/hyperframes). No sound effects ship with
the skill: the style step asks for the user's own folder (sounds.py).
"""
import os
import re
import subprocess
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import FONTS, GSAP, HOME, MODELS, PY, SKILL, VENDOR, VENV, hf, need  # noqa: E402

PACKAGES = ["numpy", "faster-whisper", "yt-dlp"]
MATTE = ["torch"]


def step(msg):
    print(f"-> {msg}", flush=True)


def font_file(family, weight):
    return os.path.join(FONTS, f"{family.replace(' ', '')}-{weight}.ttf")


def get_font(family, weight):
    """download one weight of a Google Font as TTF (the CSS API serves TTF to clients that don't ask for woff2)"""
    path = font_file(family, weight)
    if os.path.exists(path):
        return path
    url = f"https://fonts.googleapis.com/css2?family={family.replace(' ', '+')}:wght@{weight}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/4.0"})
    css = urllib.request.urlopen(req, timeout=30).read().decode()
    found = re.findall(r"url\((https://[^)]+)\)", css)
    if not found:
        raise SystemExit(f"Google Fonts has no '{family}' at weight {weight}")
    os.makedirs(FONTS, exist_ok=True)
    urllib.request.urlretrieve(found[-1], path)    # last block = the latin subset
    return path


def style_fonts():
    """every font the presets use, so the style menu can render each of them"""
    import glob
    import json
    out = []
    for path in sorted(glob.glob(os.path.join(SKILL, "styles", "*.json"))):
        with open(path) as f:
            out += [(v["family"], v["weight"]) for v in json.load(f)["fonts"].values()]
    return list(dict.fromkeys(out))


def self_test():
    """render one second of text: proves Node, Chrome and FFmpeg work together"""
    d = os.path.join(VENDOR, "selftest")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "index.html"), "w") as f:
        f.write("""<!doctype html><html><head><meta charset="utf-8"><script src="gsap.min.js"></script>
<style>body{margin:0;background:#000}#root{position:relative;width:100%;height:100%;overflow:hidden}
#t{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;color:#fff;font:700 120px sans-serif}
</style></head><body><div id="root" data-composition-id="main" data-start="0" data-width="1080" data-height="1920"
data-duration="1"><div id="t" data-start="0" data-duration="1"><span id="w">ready</span></div></div><script>
const tl=gsap.timeline({paused:true});tl.from("#w",{opacity:0,duration:0.5},0);window.__timelines["main"]=tl;
</script></body></html>""")
    import shutil
    shutil.copy(os.path.join(VENDOR, "gsap.min.js"), d)
    out = os.path.join(d, "selftest.mp4")
    if os.path.exists(out):
        os.remove(out)
    hf(["render", "--quality", "draft", "--output", out], cwd=d)
    return out if os.path.exists(out) and os.path.getsize(out) > 0 else None


def main():
    args = sys.argv[1:]
    if "--font" in args:
        fam, _, wt = args[args.index("--font") + 1].partition(":")
        print(get_font(fam, int(wt or 400)))
        return
    if sys.version_info < (3, 10):
        raise SystemExit(f"Python 3.10 or newer, please (this is {sys.version.split()[0]} at {sys.executable}). "
                         "macOS's own python3 is too old: brew install python, then run setup with Homebrew's python3")
    for tool in ("ffmpeg", "ffprobe", "node", "npx"):
        need(tool)
    node = subprocess.run(["node", "--version"], capture_output=True, text=True).stdout.strip()
    if int(node.lstrip("v").split(".")[0]) < 22:
        raise SystemExit(f"HyperFrames needs Node 22 or newer (found {node})")
    encoders = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True).stdout
    if "libvpx-vp9" not in encoders:
        raise SystemExit("this ffmpeg has no libvpx-vp9 encoder (needed for the cutout)")

    os.makedirs(HOME, exist_ok=True)
    if not os.path.exists(PY):
        step(f"venv in {VENV}")
        subprocess.run([sys.executable, "-m", "venv", VENV], check=True)
    pkgs = PACKAGES + ([] if "--no-matte" in args else MATTE)
    step("python packages: " + ", ".join(pkgs) + " (a few minutes, quiet while they download)")
    subprocess.run([PY, "-m", "pip", "install", "-q", "--upgrade", "pip"], check=True)
    subprocess.run([PY, "-m", "pip", "install", "-q", *pkgs], check=True)

    step("fonts from Google Fonts")
    for fam, wt in style_fonts():
        print("   ", os.path.basename(get_font(fam, wt)))

    step(f"GSAP {GSAP}")
    os.makedirs(VENDOR, exist_ok=True)
    gsap = os.path.join(VENDOR, "gsap.min.js")
    if not os.path.exists(gsap):
        urllib.request.urlretrieve(f"https://cdn.jsdelivr.net/npm/gsap@{GSAP}/dist/gsap.min.js", gsap)

    step("speech model (first run downloads ~500 MB; a Hugging Face warning about HF_TOKEN is harmless)")
    root = os.path.join(MODELS, "whisper")
    subprocess.run([PY, "-c", f"from faster_whisper import WhisperModel; WhisperModel('small.en', compute_type='int8', "
                              f"download_root={root!r})"], check=True)

    step("HyperFrames test render (first run downloads a headless Chrome)")
    video = self_test()
    if not video:
        raise SystemExit("the test render produced no file")
    print(f"\nREADY\nTest video (one second, the word 'ready'): open {video}")
    print("Start a new Claude Code session and say: edit this video: <path to your take>")
    print("Guide: https://alfredmakes.com/guides/claude-video-reel-editor (made by alfred.makes)")


if __name__ == "__main__":
    main()

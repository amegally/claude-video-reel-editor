"""Paths, constants and small helpers shared by every script."""
import json
import math
import os
import shutil
import subprocess
import sys

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOME = os.path.abspath(os.path.expanduser(os.environ.get("REEL_HOME", "~/reels")))
VENV = os.path.join(HOME, ".venv")
PY = os.path.join(VENV, "Scripts", "python.exe") if os.name == "nt" else os.path.join(VENV, "bin", "python")
FONTS = os.path.join(HOME, "fonts")
VENDOR = os.path.join(HOME, "vendor")
MODELS = os.path.join(HOME, "models")
PROJECTS = os.path.join(HOME, "projects")
STYLE_DIR = os.path.join(HOME, "style")            # the user's approved style lives here
PRESETS = os.path.join(SKILL, "styles")

HYPERFRAMES = "hyperframes@0.8.139"   # pinned so a reel renders the same way next month
GSAP = "3.12.5"
FPS = 30
W, H = 1080, 1920
SR = 48000


def die(msg):
    sys.exit(f"\nerror: {msg}")


def run(cmd, cwd=None, check=True, env=None):
    """run a command, return its CompletedProcess; on failure print the tail of its output and stop"""
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=env)
    if check and p.returncode != 0:
        tail = ((p.stdout or "") + (p.stderr or ""))[-2500:]
        die(f"{os.path.basename(cmd[0])} {' '.join(cmd[1:4])} ... exited {p.returncode}\n{tail}")
    return p


def hf(args, cwd, check=True):
    """the pinned HyperFrames CLI"""
    npx = "npx.cmd" if os.name == "nt" else "npx"
    return run([npx, "-y", HYPERFRAMES, *args], cwd=cwd, check=check)


def probe(path):
    out = run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", path]).stdout
    return json.loads(out)


def video_stream(info):
    return next((s for s in info["streams"] if s["codec_type"] == "video"), None)


def duration(path):
    return float(probe(path)["format"]["duration"])


def frame(t):
    """the frame that holds time t"""
    return int(round(t * FPS))


def snap(t):
    return frame(t) / FPS


def t_start(t):
    """data-start for the frame holding t, a hair early so the renderer never shows it a frame late"""
    return f"{max(0.0, snap(t) - 0.001):.4f}"


def t_dur(start, end):
    """data-duration covering whole frames, truncated so the renderer's round-up lands on the right frame"""
    n = max(1, frame(end) - frame(start))
    return f"{math.floor(n / FPS * 10000) / 10000:.4f}"


def project_arg(usage="<project>"):
    if len(sys.argv) < 2:
        sys.exit(f"usage: {os.path.basename(sys.argv[0])} {usage}")
    p = sys.argv[1]
    if not os.path.isdir(p):
        p = os.path.join(PROJECTS, p)
    if not os.path.isfile(os.path.join(p, "plan.json")):
        die(f"no plan.json in {p}")
    return os.path.abspath(p)


def load_plan(project):
    with open(os.path.join(project, "plan.json")) as f:
        return json.load(f)


def save_plan(project, plan):
    with open(os.path.join(project, "plan.json"), "w") as f:
        json.dump(plan, f, indent=2, ensure_ascii=False)
        f.write("\n")


def load_style(project=None):
    """the project's copy of the style, else the user's saved style, else the clean preset"""
    for path in (os.path.join(project, "style.json") if project else "", os.path.join(STYLE_DIR, "style.json"),
                 os.path.join(PRESETS, "clean.json")):
        if path and os.path.exists(path):
            with open(path) as f:
                return json.load(f)


def read_json(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path) as f:
        return json.load(f)


def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)


def decode_audio(path, start=None, end=None, channels=2, rate=SR):
    """any audio or video file -> float32 numpy array (samples, channels) at SR, sample 0 = time 0 of the file
    (a late audio start is padded, so sample i always lines up with the video at i / SR)"""
    import numpy as np
    cmd = ["ffmpeg", "-v", "error"]
    if start is not None:
        cmd += ["-ss", f"{start:.4f}"]
    if end is not None:
        cmd += ["-to", f"{end:.4f}"]
    cmd += ["-i", path, "-vn", "-af", "aresample=async=1:first_pts=0", "-ac", str(channels), "-ar", str(rate),
            "-f", "f32le", "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32).reshape(-1, channels).copy()


def write_wav(path, audio):
    """float32 (samples, channels) -> 16-bit wav"""
    import numpy as np
    a = np.clip(audio, -1, 1)
    ch = a.shape[1] if a.ndim > 1 else 1
    p = subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", str(ch), "-i", "-",
                        "-c:a", "pcm_s16le", path], input=a.astype(np.float32).tobytes(), capture_output=True)
    if p.returncode:
        die(p.stderr.decode()[-800:])


def has_filter(name):
    out = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True).stdout
    return any(line.split()[1:2] == [name] for line in out.splitlines() if len(line.split()) > 1)


def need(tool):
    if not shutil.which(tool):
        die(f"{tool} is not on PATH")

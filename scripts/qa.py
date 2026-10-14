"""Check a finished render before anyone sees it -> renders/<name>-qa.txt. Exits 1 on a FAIL.

python qa.py <project> <render.mp4>

FAIL: picture out of sync with the voice (lip sync), sound offset, wrong length, loudness off target.
WARN: on-screen words not in the dictionary (spellcheck), box text the speaker never said, HyperFrames check
findings (layout, text contrast).
"""
import os
import re
import subprocess
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (FPS, H, W, decode_audio, duration, hf, load_plan, load_style, probe, project_arg,  # noqa: E402
                    read_json, video_stream)
from mix import loudness  # noqa: E402

DICTS = ("/usr/share/dict/words", "/usr/dict/words")


def gray(path, t, n, box, pre="", copyts=False):
    """n frames from time t, face box only, small and grey, normalised so a colour grade doesn't matter.
    Also returns each frame's own timestamp (with copyts, the file's real ones)"""
    x, y, w, h = box
    out = subprocess.run(["ffmpeg", "-v", "info", "-ss", f"{max(t, 0):.4f}"] + (["-copyts"] if copyts else []) +
                         ["-i", path, "-frames:v", str(n), "-vf",
                          f"{pre}crop={w}:{h}:{x}:{y},scale=64:64,showinfo,format=gray", "-f", "rawvideo", "-"],
                         capture_output=True)
    f = np.frombuffer(out.stdout, np.uint8).reshape(-1, 64 * 64).astype(np.float32)
    pts = [float(p) for p in re.findall(r"pts_time:([\d.]+)", out.stderr.decode())][:len(f)]   # showinfo runs ahead
    return (f - f.mean(axis=1, keepdims=True)) / (f.std(axis=1, keepdims=True) + 1e-6), pts


def picture_sync(render, plan, segs, box):
    """lip sync against the SOURCE: in the middle of each piece, which source frame does the render show?
    Measured by the source frames' own timestamps, in frames. A phone's uneven frame rate (and the odd dropped
    frame) puts the frame shown up to one frame from its sound, which is in sync; more than that is not.
    (Comparing against the cut would miss a cut that's wrong.)"""
    from cut import crop_filter
    pre = f"{crop_filter(plan, video_stream(probe(plan['source'])))},"
    def sample(sg):                      # mid-piece, outside demo beats (the face is shrunk into a corner there)
        ps = sg.get("pic_s", sg["out_s"])
        a, b = ps, sg["out_e"]
        for d in plan.get("demo", []):
            if d["start"] < b and d["end"] > a:
                a, b = (max(a, d["end"]), b) if d["start"] - a < b - d["end"] else (a, min(b, d["start"]))
        return (a + 0.45 * (b - a)) if b - a > 0.7 else None
    long = [sg for sg in segs if sample(sg) is not None]
    picks = long[:: max(1, len(long) // 8)][:8]
    offs = []
    for sg in picks:
        ps = sg.get("pic_s", sg["out_s"])
        k = round(sample(sg) * FPS)                              # one whole output frame
        src_t = sg.get("pic_src_s", sg["src_s"]) + (k / FPS - ps)
        r, _ = gray(render, (k - 0.5) / FPS, 1, box)             # seeking half a frame early lands on frame k
        c, pts = gray(plan["source"], src_t - 3.5 / FPS, 8, box, pre, copyts=True)
        if len(r) and len(c) and len(pts) == len(c):
            best = int(np.argmin(((c - r[0]) ** 2).mean(axis=1)))
            offs.append(round((pts[best] - src_t) * FPS, 2))
    return offs


def sound_offset(render, master):
    a = decode_audio(render, 0, 20, channels=1)[:, 0]
    b = decode_audio(master, 0, 20, channels=1)[:, 0]
    n = min(len(a), len(b))
    a, b = a[:n] - a[:n].mean(), b[:n] - b[:n].mean()
    size = 1 << (2 * n - 1).bit_length()
    xc = np.fft.irfft(np.fft.rfft(a, size) * np.conj(np.fft.rfft(b, size)), size)
    lag = int(np.argmax(xc))
    lag = lag - size if lag > size // 2 else lag
    return lag / 48000


def screen_words(project, plan):
    texts = [re.sub(r"<[^>]+>", " ", b["text"]) for b in plan.get("boxes", [])]
    for rel in plan.get("fx", []):
        t = open(os.path.join(project, rel)).read()
        t = re.sub(r"<(script|style)\b.*?</\1>|<!--.*?-->", " ", t, flags=re.S)
        texts.append(re.sub(r"<[^>]+>", " ", t))
    return texts


def tokens(text):
    return [w.lower() for w in re.findall(r"[A-Za-z][A-Za-z']+", text)]


def main():
    project = project_arg("<project> <render.mp4>")
    render = os.path.abspath(sys.argv[2])
    plan, style = load_plan(project), load_style(project)
    clean = os.path.join(project, "public", "clean.mp4")
    master = os.path.join(project, "public", "master.wav")
    fails, warns, info = [], [], []

    total, got = duration(clean), duration(render)
    (fails if abs(got - total) > 1.5 / FPS else info).append(f"length {got:.3f}s (cut {total:.3f}s)")

    box = plan.get("face") or [W // 2 - 220, H // 4, 440, 520]
    segs = read_json(os.path.join(project, "work", "segments.json"), [])
    offs = picture_sync(render, plan, segs, box)
    bad = [o for o in offs if abs(o) > 1.05]
    (fails if bad or not offs else info).append(f"lip sync against the source: frame offsets at {len(offs)} pieces "
                                                f"{offs} (up to 1 = in sync)")

    lag = sound_offset(render, master)
    (fails if abs(lag) > 0.02 else info).append(f"sound offset {lag * 1000:.0f} ms")

    lufs, tp = loudness(render)
    target = style["loudness"]["lufs"]
    (fails if abs(lufs - target) > 0.6 else info).append(f"loudness {lufs:.1f} LUFS (target {target}), "
                                                        f"peak {tp:.1f} dBFS")

    said = {w for x in read_json(os.path.join(project, "words.json"), []) for w in tokens(x["w"])}
    vocab = {w.lower() for v in plan.get("vocabulary", []) for w in tokens(v)}
    dictionary = set()
    for d in DICTS:
        if os.path.exists(d):
            dictionary |= {w.strip().lower() for w in open(d, errors="ignore")}
    shown = [w for t in screen_words(project, plan) for w in tokens(t)]
    def known(w):
        if w in dictionary or w in vocab or w.split("'")[0] in dictionary:
            return True
        for suf in ("ings", "ing", "ers", "er", "est", "ed", "ies", "es", "s", "ly"):
            if w.endswith(suf) and len(w) > len(suf) + 2:
                base = w[: -len(suf)]
                cands = {base, base + "e", base + "y", base[:-1] if len(base) > 2 and base[-1] == base[-2] else base}
                if cands & dictionary:
                    return True
        return False

    if dictionary:
        unknown = sorted({w for w in shown + list(said) if not known(w)})
        if unknown:
            warns.append("spellcheck (fix, or add to plan.vocabulary if right): " + ", ".join(unknown))
    else:
        warns.append("no system word list found: spellcheck every on-screen word by eye")
    for b in plan.get("boxes", []):
        extra = [w for w in tokens(re.sub(r"<[^>]+>", " ", b["text"])) if w not in said and w not in vocab]
        if extra:
            warns.append(f"box at {b['start']}s has words the speaker didn't say: {', '.join(extra)}")

    chk = hf(["check"], cwd=os.path.join(project, "public"), check=False)
    out = re.sub(r"\x1b\[[0-9;]*m", "", chk.stdout + chk.stderr)
    found = [ln.strip() for ln in out.splitlines() if re.search(r"error|warn|contrast", ln, re.I)]
    if chk.returncode:
        warns.append("HyperFrames check: " + " | ".join(found[:12]))
    else:
        info.append("HyperFrames check passed" + (f": {' | '.join(found[:6])}" if found else ""))

    report = [f"QA {os.path.basename(render)}", *(f"FAIL {x}" for x in fails), *(f"WARN {x}" for x in warns),
              *(f"ok   {x}" for x in info), "RESULT " + ("FAIL" if fails else "PASS")]
    path = os.path.splitext(render)[0] + "-qa.txt"
    with open(path, "w") as f:
        f.write("\n".join(report) + "\n")
    print("\n".join(report))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()

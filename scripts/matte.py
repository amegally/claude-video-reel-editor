"""Cut the speaker out of the cut: public/clean.mp4 -> public/subject.webm (VP9 with alpha).

python matte.py <project>

Robust Video Matting carries what it learned from frame to frame, so the edge holds still (a model that looks at
each frame on its own flickers and leaves bits of wall behind). Its memory is reset at every cut, then warmed up
on the new shot. The model (GPL-3.0, ~100 MB) is downloaded on first use from its own release page and is never
part of this skill. Only needed when something goes behind the speaker.
"""
import os
import subprocess
import sys
import time
import urllib.request

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import FPS, MODELS, die, probe, project_arg, read_json, video_stream  # noqa: E402

MODEL_URL = "https://github.com/PeterL1n/RobustVideoMatting/releases/download/v1.0.0/rvm_resnet50_fp32.torchscript"
WARMUP = 4


def model_path():
    path = os.path.join(MODELS, os.path.basename(MODEL_URL))
    if not os.path.exists(path):
        os.makedirs(MODELS, exist_ok=True)
        print("downloading the matting model (GPL-3.0, ~100 MB) once ...", flush=True)
        urllib.request.urlretrieve(MODEL_URL, path + ".part")
        os.replace(path + ".part", path)
    return path


def main():
    import torch
    project = project_arg()
    clean = os.path.join(project, "public", "clean.mp4")
    out = os.path.join(project, "public", "subject.webm")
    if not os.path.exists(clean):
        die("run cut.py first")
    v = video_stream(probe(clean))
    w, h = int(v["width"]), int(v["height"])
    total = int(v.get("nb_frames") or 0)
    cuts = {int(round(s.get("pic_s", s["out_s"]) * FPS))           # every picture cut, J-cuts included
            for s in read_json(os.path.join(project, "work", "segments.json"), [])}

    device = "mps" if torch.backends.mps.is_available() else ("cuda" if torch.cuda.is_available() else "cpu")
    model = torch.jit.load(model_path(), map_location=device).eval()
    ratio = min(1.0, 512 / max(w, h))                # the model works on a ~512px copy, refines at full size

    dec = subprocess.Popen(["ffmpeg", "-v", "error", "-i", clean, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                           stdout=subprocess.PIPE)
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{w}x{h}",
                            "-r", str(FPS), "-i", "-", "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-crf", "28",
                            "-b:v", "0", "-row-mt", "1", "-deadline", "good", "-cpu-used", "4", "-auto-alt-ref", "0",
                            out], stdin=subprocess.PIPE)
    size, n, rec, t0 = w * h * 3, 0, [None] * 4, time.time()
    with torch.no_grad():
        while True:
            buf = dec.stdout.read(size)
            if len(buf) < size:
                break
            rgb = np.frombuffer(bytearray(buf), np.uint8).reshape(h, w, 3)
            src = torch.from_numpy(rgb).to(device).permute(2, 0, 1)[None].float() / 255
            if n in cuts:                            # new shot: forget the last one, settle on this one
                rec = [None] * 4
                for _ in range(WARMUP):
                    _, _, *rec = model(src, *rec, ratio)
            fgr, pha, *rec = model(src, *rec, ratio)
            a = pha[0, 0].cpu().numpy()
            f = (fgr[0].permute(1, 2, 0).cpu().numpy() * 255).astype(np.uint8)
            solid = (a > 0.97)[..., None]
            color = np.where(solid, rgb, f)          # the footage's own pixels inside, the model's colour on the edge
            rgba = np.dstack([color, (a * 255).astype(np.uint8)])
            enc.stdin.write(rgba.tobytes())
            n += 1
            if n % 150 == 0:
                fps = n / (time.time() - t0)
                left = f", ~{(total - n) / fps / 60:.0f} min left" if total else ""
                print(f"{n} frames, {fps:.1f} fps{left}", flush=True)
    enc.stdin.close()
    enc.wait()
    dec.wait()
    got = int(video_stream(probe(out)).get("nb_frames") or n)
    if total and abs(got - total) > 1:
        die(f"subject.webm has {got} frames, clean.mp4 has {total}")
    print(f"-> {out} ({n} frames in {(time.time() - t0) / 60:.1f} min on {device})")


if __name__ == "__main__":
    main()

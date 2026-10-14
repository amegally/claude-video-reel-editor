"""Render after the user says go: build, mix, render, QA.

python render.py <project> [name]      -> <project>/renders/<name>.mp4 (default v1) + <name>-qa.txt
python render.py <project> v1 --draft  quick low-quality pass to look at motion
"""
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import PY, SKILL, hf, project_arg, run  # noqa: E402


def main():
    project = project_arg("<project> [name] [--draft]")
    args = [a for a in sys.argv[2:] if not a.startswith("--")]
    name = args[0] if args else "v1"
    scripts = os.path.join(SKILL, "scripts")
    t0 = time.time()
    subprocess.run([PY, os.path.join(scripts, "mix.py"), project], check=True)
    from build import build
    pub = os.path.dirname(build(project))
    lint = hf(["lint"], cwd=pub, check=False)
    if lint.returncode:
        print((lint.stdout + lint.stderr)[-2500:])
        sys.exit("lint errors: fix them before rendering")
    out = os.path.join(project, "renders", f"{name}.mp4")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    quality = "draft" if "--draft" in sys.argv else "delivery"
    print(f"rendering {quality} ...", flush=True)
    raw = os.path.join(project, "work", f"{name}-picture.mp4")
    hf(["render", "--quality", quality, "--output", raw], cwd=pub)
    # the renderer re-mixes the sound (it landed ~1 LU quiet): put the measured master back, same start, same length
    run(["ffmpeg", "-v", "error", "-y", "-i", raw, "-i", os.path.join(pub, "master.wav"), "-map", "0:v", "-map",
         "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-shortest", "-movflags", "+faststart", out])
    print(f"-> {out} in {(time.time() - t0) / 60:.1f} min", flush=True)
    qa = subprocess.run([PY, os.path.join(scripts, "qa.py"), project, out])
    sys.exit(qa.returncode)


if __name__ == "__main__":
    main()

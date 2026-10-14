"""A folder of phone clips -> one SDR clip, in filename order, sound in sync.

python join.py <folder> <out.mp4>

iPhones record many short HDR (HLG) clips. Each is tone-mapped to SDR (ffmpeg's zscale if this build has it,
else macOS avconvert), then given audio exactly as long as its video before joining. Joining the files as they
are carries every clip's audio lead-in, and the sound slides ~0.05s further off per clip.
"""
import glob
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import FPS, die, probe, run, video_stream  # noqa: E402

EXT = (".mov", ".mp4", ".m4v")
HDR = ("arib-std-b67", "smpte2084")
ZSCALE = ("zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=hable:desat=0,"
          "zscale=t=bt709:m=bt709:r=tv,format=yuv420p")


def has_zscale():
    return "zscale" in run(["ffmpeg", "-hide_banner", "-filters"]).stdout


def to_sdr(clip, tmp, i):
    v = video_stream(probe(clip))
    if v.get("color_transfer") not in HDR:
        return clip, ""
    if has_zscale():
        return clip, ZSCALE + ","
    if shutil.which("avconvert"):
        out = os.path.join(tmp, f"sdr-{i:03d}.mov")
        run(["avconvert", "--source", clip, "--preset", "Preset3840x2160", "--output", out, "--replace"])
        return out, ""
    die("HDR clip, but this ffmpeg has no zscale and there is no avconvert: install an ffmpeg built with zimg")


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    folder, out = os.path.expanduser(sys.argv[1]), os.path.abspath(os.path.expanduser(sys.argv[2]))
    clips = sorted(p for p in glob.glob(os.path.join(folder, "*")) if p.lower().endswith(EXT))
    if not clips:
        die(f"no clips in {folder}")
    tmp = tempfile.mkdtemp(prefix="join-")
    norm, offsets, t = [], [], 0.0
    for i, clip in enumerate(clips):
        src, tone = to_sdr(clip, tmp, i)
        vdur = float(video_stream(probe(src)).get("duration") or probe(src)["format"]["duration"])
        part = os.path.join(tmp, f"part-{i:03d}.mov")      # PCM sound: no AAC lead-in to pile up at the joins
        run(["ffmpeg", "-v", "error", "-y", "-i", src, "-vf", f"{tone}fps={FPS},format=yuv420p",
             "-af", f"aresample=async=1:first_pts=0,apad,atrim=0:{vdur:.4f}", "-c:v", "libx264", "-preset", "fast",
             "-crf", "16", "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2", part])
        norm.append(part)
        offsets.append((os.path.basename(clip), round(t, 3)))
        t += float(probe(part)["format"]["duration"])
        print(f"{i + 1}/{len(clips)} {os.path.basename(clip)}", flush=True)
    lst = os.path.join(tmp, "list.txt")
    with open(lst, "w") as f:
        f.writelines(f"file '{p}'\n" for p in norm)
    run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c:v", "copy", "-c:a", "aac",
         "-b:a", "192k", "-movflags", "+faststart", out])
    with open(os.path.splitext(out)[0] + "-offsets.csv", "w") as f:
        f.write("clip,start\n" + "".join(f"{c},{s}\n" for c, s in offsets))
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"-> {out} ({t:.1f}s from {len(clips)} clips; clip start times in -offsets.csv)")


if __name__ == "__main__":
    main()

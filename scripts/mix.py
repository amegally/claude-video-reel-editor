"""Sound: the cut's voice + plan.sfx + plan.music -> public/master.wav at the style's loudness (default -14 LUFS).

python mix.py <project>

plan.sfx entries are [time, "name", gain_db] or [time, "name", gain_db, seconds]. The time is when the sound
should HIT: each file's loudest moment is lined up on it (a whoosh swells for a while before it peaks).
The skill ships no sounds. A name is a role from the style's sound map (pop, whoosh, click...: sounds.py sorts the
user's folder into them) or a file name without its extension, looked up in <project>/audio/ first, then the
style's sound.sfx_dir. "typing" with a length is built from single keystrokes. A sound that can't be found is
skipped with a warning, so a style with no sound folder renders with the voice alone.
Loudness is two passes: measure and normalise, then measure again and correct what's left.
"""
import json
import os
import re
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import SR, decode_audio, die, load_plan, load_style, project_arg, run, write_wav  # noqa: E402


def find_sound(project, style, name):
    """the project's audio/ folder first, then the style's sound folder: by role, then by file name"""
    sound = style.get("sound", {})
    folders = [os.path.join(project, "audio")]
    if sound.get("sfx_dir"):
        folders.append(os.path.expanduser(sound["sfx_dir"]))
    names = [name] + [os.path.splitext(f)[0] for f in sound.get("roles", {}).get(name, [])[:1]]
    for n in names:
        for folder in folders:
            for ext in ("", ".wav", ".ogg", ".mp3", ".m4a", ".aif", ".aiff", ".flac"):
                p = os.path.join(folder, n + ext)
                if os.path.isfile(p):
                    return p
    return None


def load_sound(project, style, name, seconds=None):
    """a sound, peak-normalised so gain_db means the same thing for every file. "typing" with no file of its own
    is strung together from single keystrokes at an uneven pace"""
    path = find_sound(project, style, name)
    if path:
        clip = decode_audio(path)
    elif name == "typing" and find_sound(project, style, "key"):
        key = decode_audio(find_sound(project, style, "key"))
        n = int((seconds or 1.0) * SR)
        clip = np.zeros((n + len(key), 2), np.float32)
        rng, pos = np.random.default_rng(3), 0
        while pos < n:
            clip[pos:pos + len(key)] += key * rng.uniform(0.55, 1.0)
            pos += int(SR * rng.uniform(0.07, 0.15))
    else:
        return None
    peak = float(np.abs(clip).max()) or 1.0
    return clip * (0.9 / peak)


def place(bed, clip, at):
    peak = int(np.argmax(np.abs(clip).max(axis=1)))
    start = int(round(at * SR)) - peak
    a, b = max(0, start), min(len(bed), start + len(clip))
    if b > a:
        bed[a:b] += clip[a - start: b - start]


def duck(music, voice, depth_db=6.0):
    """lower the music while someone talks, smoothly"""
    hop = SR // 20
    n = len(voice) // hop + 1
    lvl = np.array([np.sqrt(np.mean(voice[i * hop:(i + 1) * hop] ** 2) + 1e-12) for i in range(n)])
    talking = (20 * np.log10(lvl) > -40).astype(float)
    k = np.ones(6) / 6
    talking = np.convolve(talking, k, mode="same")
    gain = 10 ** (-depth_db * talking / 20)
    curve = np.interp(np.arange(len(music)), np.arange(n) * hop, gain)
    return music * curve[:, None]


def loudness(path):
    err = run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-af", "ebur128=peak=true", "-f", "null", "-"]).stderr
    i = float(re.findall(r"I:\s+(-?[\d.]+) LUFS", err)[-1])
    tp = float(re.findall(r"Peak:\s+(-?[\d.]+) dBFS", err)[-1])
    return i, tp


def normalise(src, dst, lufs, tp):
    base = f"loudnorm=I={lufs}:TP={tp}:LRA=11"
    err = run(["ffmpeg", "-hide_banner", "-nostats", "-i", src, "-af", base + ":print_format=json", "-f", "null",
               "-"]).stderr
    m = json.loads(err[err.rindex("{"): err.rindex("}") + 1])
    second = (f"{base}:measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}:"
              f"measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true")
    run(["ffmpeg", "-v", "error", "-y", "-i", src, "-af", second, "-ar", str(SR), "-c:a", "pcm_s16le", dst])
    got, _ = loudness(dst)
    if abs(got - lufs) > 0.3:                     # one pass can land half a LU off: correct it with plain gain
        tmp = dst + ".tmp.wav"
        os.replace(dst, tmp)
        run(["ffmpeg", "-v", "error", "-y", "-i", tmp, "-af",
             f"volume={lufs - got:.2f}dB,alimiter=limit={10 ** (tp / 20):.3f}:level=false", "-ar", str(SR),
             "-c:a", "pcm_s16le", dst])
        os.remove(tmp)
    return loudness(dst)


def main():
    project = project_arg()
    plan, style = load_plan(project), load_style(project)
    voice_path = os.path.join(project, "work", "voice.wav")
    if not os.path.exists(voice_path):
        die("run cut.py first")
    voice = decode_audio(voice_path)
    bed = voice.copy()
    placed, missing = 0, []
    for entry in plan.get("sfx", []):
        at, name, gain = entry[0], entry[1], entry[2] if len(entry) > 2 else -14
        clip = load_sound(project, style, name, entry[3] if len(entry) > 3 else None)
        if clip is None:
            missing.append(name)
            continue
        placed += 1
        if len(entry) > 3:
            n = int(entry[3] * SR)
            clip = clip[:n].copy()
            f = min(len(clip), int(0.05 * SR))
            clip[-f:] *= np.linspace(1, 0, f, dtype=np.float32)[:, None]
        place(bed, clip * 10 ** (gain / 20), at)
    music = plan.get("music")
    if music:
        m = decode_audio(music["src"] if os.path.isabs(music["src"]) else os.path.join(project, music["src"]))
        m = np.pad(m, ((0, max(0, len(voice) - len(m))), (0, 0)))[: len(voice)]
        m *= 10 ** (music.get("gain_db", style["sound"]["music_gain_db"]) / 20)
        fade = min(len(m), SR)
        m[-fade:] *= np.linspace(1, 0, fade, dtype=np.float32)[:, None]
        bed += duck(m, voice)
    raw = os.path.join(project, "work", "mix-raw.wav")
    write_wav(raw, bed / max(1.0, float(np.abs(bed).max()) / 0.98))
    out = os.path.join(project, "public", "master.wav")
    lufs, tp = normalise(raw, out, style["loudness"]["lufs"], style["loudness"]["true_peak"])
    print(f"-> {out}: {lufs:.1f} LUFS, peak {tp:.1f} dBFS, {placed} effects{', music' if music else ''}")
    if missing:
        where = "no sound folder in the style (sounds.py <folder>)" if not style.get("sound", {}).get("sfx_dir") \
            else "not in the project's audio/ or the style's sound folder"
        print(f"warning: skipped {len(missing)} sound(s), {where}: {', '.join(sorted(set(missing)))}")


if __name__ == "__main__":
    main()

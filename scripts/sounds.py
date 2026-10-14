"""The user's own sound effects: sort a folder into roles and save the map in their style.

python sounds.py <folder> [project]   -> sound.sfx_dir + sound.roles in style/style.json (and the project's copy)

The skill ships no sounds. Each file gets a role from its name first ("ui-mouse-click" -> mouse, "woosh-2" ->
whoosh). A file whose name says nothing gets one from how it sounds (length, how fast it peaks, how bright it
is) when the name is only generic words and numbers ("sfx_014"). Plans then use role names (pop, whoosh,
click...) or any file's name without its extension.
"""
import os
import re
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import PROJECTS, SR, STYLE_DIR, decode_audio, die, read_json, write_json  # noqa: E402

AUDIO = (".wav", ".mp3", ".ogg", ".m4a", ".aif", ".aiff", ".flac")

# role: (strong words, weak words). Earlier roles win a tie, so the specific ones come first.
ROLES = {
    "typing": (["typing", "keyboard", "typewriter"], []),
    "key": (["keystroke", "key"], []),
    "mouse": (["mouse"], []),
    "shutter": (["shutter", "camera", "photo"], []),
    "paper": (["paper", "page", "flip", "book"], ["slide"]),
    "toggle": (["toggle", "switch"], []),
    "glitch": (["glitch", "static"], []),
    "riser": (["riser", "rise", "build"], []),
    "swoosh-out": (["out", "reverse", "minimize", "close"], []),
    "whoosh": (["whoosh", "woosh", "swoosh", "swish", "swoop", "woop", "sweep"], ["transition", "air", "pass"]),
    "pop": (["pop", "bubble", "plop", "blip", "boop"], ["drop"]),
    "click": (["click", "tap", "button"], ["select"]),
    "tick": (["tick", "clock", "tock"], ["beep"]),
    "ding": (["ding", "notification", "bell", "chime", "alert", "success", "complete", "confirm"], []),
    "thud": (["thud", "boom", "impact", "bass", "low"], []),
    "hit": (["hit", "punch", "slam", "stamp", "bonk", "knock"], []),
}
# joke sounds only stand in for a role when nothing else can
LAST_RESORT = ["meme", "fart", "bruh", "oof", "funny"]
# words that say nothing about the sound: a name made only of these (and numbers) is sorted by how it sounds
GENERIC = {"", "sfx", "sound", "sounds", "audio", "fx", "effect", "effects", "untitled", "track", "clip", "sample",
           "new", "final", "copy", "file", "recording", "take", "mono", "stereo", "wav", "mp", "ogg"}


def words(name):
    return re.split(r"[^a-z]+", os.path.splitext(name)[0].lower())


def by_name(name):
    """(role, score) from the file name, or (None, 0)"""
    w = set(words(name))
    best, score = None, 0
    for role, (strong, weak) in ROLES.items():
        s = 2 * len(w & set(strong)) + len(w & set(weak))
        if role == "swoosh-out" and not w & set(ROLES["whoosh"][0] + ROLES["whoosh"][1]):
            s = 0                               # "out" only means swoosh-out on something that whooshes
        if s > score:
            best, score = role, s
    if best and w & set(LAST_RESORT):
        score -= 1.5
    return best, score


def measure(path):
    """length (s), time to the loudest moment (s), brightness (spectral centroid, Hz)"""
    a = decode_audio(path, channels=1)[:, 0]
    if not len(a) or not np.abs(a).max():
        return None
    env = np.abs(a)
    loud = np.nonzero(env > env.max() * 0.03)[0]
    a = a[loud[0]: loud[-1] + 1]
    spec = np.abs(np.fft.rfft(a[: SR * 2] * np.hanning(min(len(a), SR * 2))))
    freqs = np.fft.rfftfreq(min(len(a), SR * 2), 1 / SR)
    return {"len": len(a) / SR, "peak": int(np.argmax(np.abs(a))) / SR,
            "bright": float((spec * freqs).sum() / (spec.sum() or 1))}


def by_sound(m):
    """a role from measurements, for a file whose name says nothing"""
    if m["peak"] > 0.12 and 0.3 < m["len"] < 3.5:
        return "whoosh"
    if m["len"] < 0.12:
        return "tick" if m["bright"] > 3500 else "click"
    if m["len"] < 0.6 and m["peak"] < 0.03:
        return "click" if m["bright"] > 4000 else ("thud" if m["bright"] < 900 else "pop")
    if m["peak"] < 0.03 and m["len"] >= 0.6:
        return "ding" if m["bright"] > 2000 else "thud"
    return None


def sort_folder(folder):
    files = sorted(f for f in os.listdir(folder) if f.lower().endswith(AUDIO) and not f.startswith("."))
    if not files:
        die(f"no audio files in {folder} ({', '.join(AUDIO)})")
    picks = {}                                   # role -> [(score, file)]
    rows = []
    for f in files:
        role, score = by_name(f)
        m = measure(os.path.join(folder, f))
        if m is None:
            continue
        how = "name"
        if not role and set(words(f)) <= GENERIC:
            role, score, how = by_sound(m), 0.5, "sound"
        rows.append((f, role or "-", how if role else "", m))
        if role:
            picks.setdefault(role, []).append((score, -m["len"] if role == "typing" else m["len"], f))
    roles = {r: [f for _, _, f in sorted(c, key=lambda x: (-x[0], x[1]))] for r, c in picks.items()}
    if "click" not in roles and "mouse" in roles:
        roles["click"] = roles["mouse"][:]
    if "key" not in roles and "click" in roles:
        roles["key"] = roles["click"][:]
    return roles, rows


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    folder = os.path.abspath(os.path.expanduser(sys.argv[1]))
    if not os.path.isdir(folder):
        die(f"not a folder: {folder}")
    roles, rows = sort_folder(folder)
    targets = [os.path.join(STYLE_DIR, "style.json")]
    if len(sys.argv) > 2:
        p = sys.argv[2] if os.path.isdir(sys.argv[2]) else os.path.join(PROJECTS, sys.argv[2])
        targets.append(os.path.join(p, "style.json"))
    for path in targets:
        st = read_json(path) or die(f"no style at {path}: run style.py use <preset> first")
        st.setdefault("sound", {}).update({"sfx_dir": folder, "roles": roles})
        write_json(path, st)
    print(f"{len(rows)} sounds in {folder}\n")
    for f, role, how, m in rows:
        print(f"  {f:44.44} {role:11} {how:6} {m['len']:5.2f}s  peak {m['peak']:4.2f}s  {m['bright']:6.0f} Hz")
    print("\nroles (first file is used; name another file directly in plan.sfx to pick it):")
    for r, fs in sorted(roles.items()):
        print(f"  {r:11} {', '.join(fs[:4])}{' ...' if len(fs) > 4 else ''}")
    missing = [r for r in ROLES if r not in roles]
    if missing:
        print(f"\nno sound for: {', '.join(missing)} (fine: leave those out of plan.sfx)")
    print(f"\nsaved to {', '.join(targets)}")


if __name__ == "__main__":
    main()

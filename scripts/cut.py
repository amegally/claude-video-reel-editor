"""The cut: plan.keep (source seconds, the last clean take of each line) -> public/clean.mp4 + work/voice.wav,
with every pause longer than style.cut.max_pause removed, inside a take as well as between takes.

python cut.py <project> --plan     print the pieces, encode nothing
python cut.py <project>            encode the cut, then map the words
python cut.py <project> --words    only re-map words.json (after editing plan.fixes)

A keep range can carry a hold: [start, end, {"hold": 1.2}] keeps 1.2s of picture after the take's last word, for a
beat that needs time on screen (a demo the speaker points at, a reaction). Every other pause is still cut.

Picture and sound are cut on the same frame boundaries, so lip sync can't drift. At a change of take the
picture switches style.cut.j_lead seconds after the sound (a J-cut): the next line is heard a beat before it's seen.
"""
import os
import re
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (FPS, H, MODELS, SR, W, decode_audio, die, load_plan, load_style, probe,  # noqa: E402
                    project_arg, read_json, run, video_stream, write_json, write_wav)
from transcribe import QUIET_DB, envelope_db  # noqa: E402

SPF = SR // FPS          # audio samples per frame


def levels(env):
    floor = np.percentile(env, 10)
    loud = env > max(floor + QUIET_DB, np.percentile(env, 95) - 22)   # speech, not breaths or room tone
    soft = env > floor + QUIET_DB                                     # quiet word edges ("s", "f", "h")
    return loud, soft


def tighten(words, loud):
    """shrink each word to the loud part of its span: the model often stretches a word over the silence (or the
    breath) next to it, which puts it in the wrong piece and its caption early"""
    out = []
    for w in words:
        a, b = int(w["s"] * 100), int(w["e"] * 100)
        idx = np.nonzero(loud[a:b])[0]
        w = dict(w)
        if len(idx) and b - a > 15:
            w["s"], w["e"] = round((a + idx[0]) / 100, 3), round(max((a + idx[-1] + 1) / 100, w["s"] + 0.05), 3)
        elif b - a > 15:
            w["loose"] = True                        # no clear speech in its span: only count it when mostly in
        out.append(w)
    return out


def pieces(plan, style, words, env):
    """split each keep range at every pause over max_pause and snap the pieces to frames.
    Pauses come from the loudness, not from word times: speech models stretch a word over the silence after
    it, so word gaps miss most pauses. A loud stretch with no word in it (a breath, a click) is dropped."""
    cfg = style["cut"]
    loud, soft = levels(env)
    out = []
    for take, entry in enumerate(plan["keep"]):
        a, b = entry[0], entry[1]
        hold = entry[2].get("hold", 0) if len(entry) > 2 else 0
        inside = [w for w in words if a <= (w["s"] + w["e"]) / 2 < b]
        if not inside:
            out.append([a, b + hold, take])
            continue
        regions, k, end = [], int(a * 100), min(int(b * 100), len(loud))
        while k < end:
            if loud[k]:
                j = k
                while j < end and loud[j]:
                    j += 1
                if regions and k / 100 - regions[-1][1] <= cfg["max_pause"]:
                    regions[-1][1] = j / 100                 # a short gap stays: it's rhythm, not a pause
                else:
                    regions.append([k / 100, j / 100])
                k = j
            else:
                k += 1
        for s, e in regions:
            if any(w["s"] < e and w["e"] > s for w in inside):
                i, j = int(s * 100), int(e * 100)
                while i > int(s * 100) - 8 and i > 0 and soft[i - 1]:            # follow a soft start back
                    i -= 1
                while j < int(e * 100) + 15 and j < len(soft) and soft[j]:      # and a soft ending out
                    j += 1
                out.append([max(a, i / 100 - cfg["lead"]), min(b, j / 100 + cfg["tail"]), take])
        if hold and out and out[-1][2] == take:      # a deliberate beat after the line (a demo, a reaction):
            out[-1][1] += hold                       # the pause rule doesn't apply to it
    merged = []                                      # speaking order is the keep order: never sort
    for s, e, take in out:
        if merged and merged[-1][2] == take and merged[-1][0] <= s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e, take])
    return [(int(np.floor(s * FPS)), int(np.ceil(e * FPS)), take) for s, e, take in merged]


def clipped_ends(project, plan, frames, env, margin=0.08):
    """no piece may end inside a word. A 20-40ms dip inside a word (the closure of a d, t, k or p) can pass for the
    end of the word, and the speech model sometimes splits a line's last word in two ("video." heard as "fire." +
    "See ya."), so a keep end set there clips the word: the viewer hears "vi-". Every piece end still sounding at
    the cut gets the source around it transcribed again (cached in work/tails.json); a word running more than
    `margin` s past the end is a clipped word. plan.tail_ok = [end, ...] lets a deliberate one through."""
    from faster_whisper import WhisperModel
    floor = np.percentile(env, 10)
    ok = {round(t, 2) for t in plan.get("tail_ok", [])}
    path = os.path.join(project, "work", "tails.json")
    cache, model, bad = read_json(path) or {}, None, []
    for k, (sf, ef, _) in enumerate(frames):
        e = ef / FPS
        if round(e, 2) in ok or (k + 1 < len(frames) and frames[k + 1][0] == ef):   # the next piece goes on from here
            continue
        if not (env[int(e * 100): int(e * 100) + 7] > floor + 15).any():           # quiet at the cut: a clean end
            continue
        key = f"{plan['source']}|{e:.3f}"
        if key not in cache:
            model = model or WhisperModel("small.en", device="cpu", compute_type="int8",
                                          download_root=os.path.join(MODELS, "whisper"))
            a0 = max(0.0, e - 2.0)
            clip = decode_audio(plan["source"], a0, e + 1.2, channels=1, rate=16000)[:, 0]
            segs, _ = model.transcribe(clip, language="en", word_timestamps=True, initial_prompt=plan.get("prompt") or None,
                                       condition_on_previous_text=False, vad_filter=False)
            cache[key] = [[round(a0 + w.start, 3), round(a0 + w.end, 3), w.word.strip()] for s in segs for w in s.words]
            write_json(path, cache)
        for ws, we, t in cache[key]:
            if ws < e - 0.05 and we > e + margin:
                bad.append(f'  piece {k + 1} ends at {e:.2f}, inside "{t}" ({ws:.2f}-{we:.2f}): end that keep range '
                           f"after the word's tail, where it's quiet again, or before the word at {ws:.2f}")
                break
    return bad


def segments_from(frames, lead):
    """the sound of each piece in output time, plus where its PICTURE starts: at a change of take the picture
    switches `lead` frames after the sound (a J-cut), so the new take is heard a beat before it is seen"""
    segs, out_f = [], 0
    for k, (sf, ef, take) in enumerate(frames):
        j = lead if k and take != frames[k - 1][2] and ef - sf > 2 * lead else 0
        segs.append({"src_s": sf / FPS, "src_e": ef / FPS, "out_s": out_f / FPS, "out_e": (out_f + ef - sf) / FPS,
                     "take": take, "pic_s": (out_f + j) / FPS, "pic_src_s": (sf + j) / FPS})
        out_f += ef - sf
    return segs


def picture_pieces(frames, segs):
    """source frame ranges for the picture, in speaking order: a J-cut lets the previous take run on"""
    vid = [[sf, ef] for sf, ef, _ in frames]
    for k, sg in enumerate(segs):
        j = round((sg["pic_s"] - sg["out_s"]) * FPS)
        if j:
            vid[k][0] += j
            vid[k - 1][1] += j
    return vid


def encode_piece(src, vf, sf, ef, out):
    run(["ffmpeg", "-v", "error", "-y", "-ss", f"{sf / FPS:.4f}", "-i", src, "-frames:v", str(ef - sf), "-vf", vf,
         "-an", "-c:v", "libx264", "-preset", "fast", "-crf", "16", "-r", str(FPS), out])


def crop_filter(plan, v):
    sw, sh = int(v["width"]), int(v["height"])
    rot = next((abs(int(sd.get("rotation", 0))) for sd in v.get("side_data_list", []) if "rotation" in sd), 0)
    if rot in (90, 270):
        sw, sh = sh, sw
    if plan.get("crop"):
        cw, ch, cx, cy = plan["crop"]
    elif sw / sh > W / H:
        ch, cw = sh, int(sh * W / H) // 2 * 2
        cx, cy = (sw - cw) // 2, 0
    else:
        cw, ch = sw, int(sw * H / W) // 2 * 2
        cx, cy = 0, (sh - ch) // 2
    return f"crop={cw}:{ch}:{cx}:{cy},scale={W}:{H}:flags=lanczos,setsar=1"


def fix_words(words, fixes):
    """plan.fixes: {"word": "Word"} for every match, {"word@12.3": "Word"} for the one nearest 12.3s (source),
    and "" as the value drops the word"""
    def bare(s):
        return re.sub(r"[^\w']", "", s).lower()
    out = [dict(w) for w in words]
    for key, new in fixes.items():
        word, _, at = key.partition("@")
        if at:
            cands = [w for w in out if bare(w["w"]) == bare(word) and abs(w["src"] - float(at)) < 1.0]
            targets = [min(cands, key=lambda w: abs(w["src"] - float(at)))] if cands else []
        else:
            targets = [w for w in out if bare(w["w"]) == bare(word)]
        if not targets:
            print(f"warning: fix '{key}' matched no word")
        for w in targets:
            w["w"] = new
    return [w for w in out if w["w"] != ""]


def overlap(w, s, e):
    """how much of a word falls in [s, e). Word starts run early (the model stretches a word back over the
    silence before it), so a word counts if a real part of it is inside, not its midpoint"""
    o = min(e, w["e"]) - max(s, w["s"])
    need = 0.5 * (w["e"] - w["s"]) if w.get("loose") else min(0.06, 0.5 * (w["e"] - w["s"]))
    return o if o >= need else 0


def map_words(project, plan, segs, words):
    out = []
    for w in words:
        best = max(range(len(segs)), key=lambda i: overlap(w, segs[i]["src_s"], segs[i]["src_e"]))
        sg = segs[best]
        if overlap(w, sg["src_s"], sg["src_e"]) > 0:
            s = sg["out_s"] + max(0.0, w["s"] - sg["src_s"])
            e = min(sg["out_e"], sg["out_s"] + (w["e"] - sg["src_s"]))
            out.append({"w": w["w"], "s": round(s, 3), "e": round(max(e, s + 0.05), 3), "seg": best, "src": w["s"]})
    out.sort(key=lambda w: w["s"])
    out = fix_words(out, plan.get("fixes", {}))
    write_json(os.path.join(project, "words.json"), out)
    return out


def main():
    project = project_arg("<project> [--plan | --words]")
    plan, style = load_plan(project), load_style(project)
    words = read_json(os.path.join(project, "work", "source-words.json"))
    if words is None:
        die("run transcribe.py first")
    seg_path = os.path.join(project, "work", "segments.json")
    src = plan["source"]
    audio = decode_audio(src)
    env = envelope_db(audio)
    words = tighten(words, levels(env)[0])

    if "--words" in sys.argv:
        segs = read_json(seg_path) or die("cut first")
        out = map_words(project, plan, segs, words)
        print(" ".join(w["w"] for w in out))
        return

    frames = pieces(plan, style, words, env)
    segs = segments_from(frames, int(style["cut"].get("j_lead", 0.15) * FPS + 0.5))
    total = segs[-1]["out_e"]
    for sg in segs:
        said = " ".join(w["w"] for w in words if overlap(w, sg["src_s"], sg["src_e"]))
        print(f"{sg['src_s']:8.3f}-{sg['src_e']:8.3f} -> {sg['out_s']:6.2f}  {said}")
    print(f"{len(segs)} pieces, {total:.2f}s")
    bad = clipped_ends(project, plan, frames, env)
    if bad:
        print("\n".join(bad))
        die("CLIPPED WORD: a piece ends inside a word. Move that keep range's end, or add the end to plan.tail_ok if "
            "you meant to cut there (a drawn-out \"a...\" shortened).")
    if "--plan" in sys.argv:
        return

    v = video_stream(probe(src))
    if v.get("color_transfer") in ("arib-std-b67", "smpte2084"):
        print("warning: HDR source. Colours will look washed out: run join.py on the clip(s) first.")
    vf = f"fps={FPS},{crop_filter(plan, v)},format=yuv420p"
    parts_dir = os.path.join(project, "work", "pieces")
    os.makedirs(parts_dir, exist_ok=True)
    vid = picture_pieces(frames, segs)
    names = [os.path.join(parts_dir, f"{k:03d}.mp4") for k in range(len(vid))]
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(3) as pool:          # each piece seeks straight to its frames: any order, no buffering
        list(pool.map(lambda a: encode_piece(src, vf, *a), [(sf, ef, n) for (sf, ef), n in zip(vid, names)]))
    lst = os.path.join(parts_dir, "list.txt")
    with open(lst, "w") as f:
        f.writelines(f"file '{n}'\n" for n in names)
    video = os.path.join(project, "work", "video.mp4")
    run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", video])

    parts, fade = [], int(0.004 * SR)
    ramp = np.linspace(0, 1, fade, dtype=np.float32)[:, None]
    for sf, ef, _ in frames:
        p = audio[sf * SPF: ef * SPF].copy()
        p = np.pad(p, ((0, (ef - sf) * SPF - len(p)), (0, 0)))
        p[:fade] *= ramp
        p[-fade:] *= ramp[::-1]
        parts.append(p)
    voice = os.path.join(project, "work", "voice.wav")
    write_wav(voice, np.concatenate(parts))
    clean = os.path.join(project, "public", "clean.mp4")
    os.makedirs(os.path.dirname(clean), exist_ok=True)
    run(["ffmpeg", "-v", "error", "-y", "-i", video, "-i", voice, "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
         "-movflags", "+faststart", clean])

    n_video = int(video_stream(probe(clean)).get("nb_frames", 0))
    n_cut = sum(ef - sf for sf, ef, _ in frames)
    if n_video and abs(n_video - n_cut) > 1:
        die(f"the cut has {n_video} frames, expected {n_cut}: picture and sound would drift")
    write_json(seg_path, segs)
    out = map_words(project, plan, segs, words)
    print(f"-> {clean} ({total:.2f}s, {len(out)} words). Cut-only preview: open that file.")


if __name__ == "__main__":
    main()

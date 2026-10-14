"""Word-timed transcript of the source clip -> work/source-words.json + work/source-transcript.txt

python transcribe.py <project>                 the whole source
python transcribe.py <project> --range 41 48   redo one stretch with a filler-friendly prompt (when one word is
                                               stretched over a second or more, it is hiding speech)

Words spoken over near-silence are dropped: speech models invent text over quiet gaps ("Thanks for watching!").
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import MODELS, SR, decode_audio, die, load_plan, project_arg, read_json, write_json  # noqa: E402

FILLER_PROMPT = "Um, uh, so, like, you know, I mean. Okay, let me say that again."
QUIET_DB = 8          # a word must sit this far above the clip's noise floor


def envelope_db(audio, hop=480):
    mono = audio.mean(axis=1)
    n = len(mono) // hop
    rms = np.sqrt(np.mean(mono[: n * hop].reshape(n, hop) ** 2, axis=1) + 1e-12)
    return 20 * np.log10(rms)          # one value per 10 ms


def run_model(path, prompt, offset=0.0, model_name="small.en"):
    from faster_whisper import WhisperModel
    model = WhisperModel(model_name, device="cpu", compute_type="int8", download_root=os.path.join(MODELS, "whisper"))
    audio = decode_audio(path, channels=1, rate=16000)[:, 0]     # ffmpeg decodes: no PyAV version trouble
    segments, _ = model.transcribe(audio, language="en" if model_name.endswith(".en") else None,
                                   word_timestamps=True, initial_prompt=prompt or None,
                                   condition_on_previous_text=False, vad_filter=True,
                                   vad_parameters={"min_silence_duration_ms": 400})
    words = []
    for seg in segments:
        for w in seg.words or []:
            text = w.word.strip()
            if text:
                words.append({"w": text, "s": round(w.start + offset, 3), "e": round(w.end + offset, 3),
                              "p": round(w.probability, 2)})
    return join_pieces(words)


def join_pieces(words):
    """the model splits some tokens: "14" + ",000", "step" + "-by" + "-step". Glue them back into one word"""
    out = []
    for w in words:
        if out and (w["w"][0] in ",-" or w["w"][0] == "." and w["w"][1:2].isdigit()) and len(w["w"]) > 1:
            out[-1]["w"] += w["w"]
            out[-1]["e"] = w["e"]
        else:
            out.append(dict(w))
    return out


def drop_quiet(words, env):
    floor = np.percentile(env, 10)
    kept, dropped = [], []
    for w in words:
        a, b = int(w["s"] * 100), max(int(w["e"] * 100), int(w["s"] * 100) + 1)
        level = np.percentile(env[a:b], 90) if b <= len(env) and a < b else floor
        (kept if level > floor + QUIET_DB else dropped).append(w)
    return kept, dropped


def transcript_text(words):
    """one line per stretch of speech, split on pauses over 0.6s, with source times"""
    lines, cur = [], []
    for w in words:
        if cur and w["s"] - cur[-1]["e"] > 0.6:
            lines.append(cur)
            cur = []
        cur.append(w)
    if cur:
        lines.append(cur)
    out = []
    for ln in lines:
        flags = [f"'{w['w']}' stretched {w['e'] - w['s']:.1f}s" for w in ln if w["e"] - w["s"] > 1.0]
        out.append(f"[{ln[0]['s']:7.2f} - {ln[-1]['e']:7.2f}] " + " ".join(w["w"] for w in ln)
                   + (f"   <- check: {', '.join(flags)}" if flags else ""))
    return "\n".join(out) + "\n"


def main():
    project = project_arg("<project> [--range START END]")
    plan = load_plan(project)
    src = plan["source"]
    model = plan.get("whisper", "small.en")
    out = os.path.join(project, "work", "source-words.json")
    audio = decode_audio(src)
    env = envelope_db(audio)

    if "--range" in sys.argv:
        i = sys.argv.index("--range")
        a, b = float(sys.argv[i + 1]), float(sys.argv[i + 2])
        old = read_json(out)
        if old is None:
            die("transcribe the whole source first")
        snippet = os.path.join(project, "work", "snippet.wav")
        from common import write_wav
        write_wav(snippet, audio[int(a * SR): int(b * SR)])
        new = run_model(snippet, FILLER_PROMPT + " " + plan.get("prompt", ""), offset=a, model_name=model)
        words = [w for w in old if w["e"] <= a or w["s"] >= b] + new
        words.sort(key=lambda w: w["s"])
    else:
        words = run_model(src, plan.get("prompt", ""), model_name=model)

    words, dropped = drop_quiet(words, env)
    write_json(out, words)
    with open(os.path.join(project, "work", "source-transcript.txt"), "w") as f:
        f.write(transcript_text(words))
    print(transcript_text(words))
    if dropped:
        print("dropped (spoken over near-silence): " + ", ".join(f"'{w['w']}'@{w['s']}" for w in dropped))
    print(f"{len(words)} words -> {out}")


if __name__ == "__main__":
    main()

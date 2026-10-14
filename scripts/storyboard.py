"""The storyboard: every beat with a real frame, what's said, what's on screen and what you hear, plus a note box.
Nothing renders until the user has read it and said go.

python storyboard.py <project> [--version N]   -> <project>/storyboard/index.html (open it in any browser)
python storyboard.py <project> --list          print the beat ids and lines only

Notes are typed into the page (kept in the browser), then "Copy notes" puts them on the clipboard as
"p03: ..." lines to paste back to Claude.
"""
import glob
import html
import json
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import die, duration, hf, load_plan, load_style, project_arg, read_json  # noqa: E402


def beats(words, segs, total):
    """one beat per spoken sentence (or change of take)"""
    def take(w):
        return segs[w["seg"]].get("take", w["seg"]) if w["seg"] < len(segs) else w["seg"]
    out, cur = [], []
    for w in words:
        if cur and (re.search(r"[.?!]$", cur[-1]["w"]) or take(w) != take(cur[-1])):
            out.append(cur)
            cur = []
        cur.append(w)
    if cur:
        out.append(cur)
    res = []
    for i, b in enumerate(out):
        end = out[i + 1][0]["s"] if i + 1 < len(out) else total
        res.append({"id": f"p{i + 1:02d}", "s": 0.0 if i == 0 else b[0]["s"], "e": end,
                    "says": " ".join(w["w"] for w in b)})
    return res


def events(plan, total):
    """everything visual, as (start, end, description)"""
    ev = []
    for b in plan.get("boxes", []):
        ev.append((b["start"], total if b["end"] == "end" else b["end"], f'box "{re.sub("<[^>]+>", "", b["text"])}"'))
    for o in plan.get("overlays", []):
        ev.append((o["start"], o["end"], f"overlay {os.path.basename(o['src'])}" + (f" ({o['note']})"
                                                                                  if o.get("note") else "")))
    for b in plan.get("behind", []):
        ev.append((b["start"], b["end"], f"behind you: {os.path.basename(b['src'])}" + (f" ({b['note']})"
                                                                                      if b.get("note") else "")))
    for g in plan.get("grade", []):
        ev.append((g["start"], g["end"], f"picture goes {g['look']}"))
    for m in plan.get("marks", []):
        ev.append((m["start"], m["end"], f"{m.get('kind', 'underline')} drawn" + (f" ({m['note']})"
                                                                               if m.get("note") else "")))
    for c in plan.get("camera", []):
        ev.append((c["start"], c.get("end") or c["start"] + c.get("dur", 0.3),
                   f"camera {'settles from' if c.get('from') else 'pushes to'} {c.get('from') or c.get('scale')}"))
    for rel in plan.get("fx", []):
        text = open(os.path.join(plan["_project"], rel)).read()
        m = re.search(r'data-start="([\d.]+)"[^>]*data-duration="([\d.]+)"', text)
        note = re.search(r"<!--\s*(.+?)\s*-->", text)
        if m:
            s = float(m[1])
            ev.append((s, s + float(m[2]), f"effect {os.path.basename(rel)[:-5]}" + (f": {note[1]}" if note else "")))
    return sorted(ev)


def main():
    project = project_arg("<project> [--version N | --list]")
    plan, style = load_plan(project), load_style(project)
    plan["_project"] = project
    words = read_json(os.path.join(project, "words.json")) or die("run cut.py first")
    segs = read_json(os.path.join(project, "work", "segments.json"))
    total = duration(os.path.join(project, "public", "clean.mp4"))
    bts = beats(words, segs, total)
    if "--list" in sys.argv:
        for b in bts:
            print(f"{b['id']}  {b['s']:6.2f}-{b['e']:6.2f}  {b['says']}")
        return
    version = sys.argv[sys.argv.index("--version") + 1] if "--version" in sys.argv else "1"
    ev, sfx = events(plan, total), plan.get("sfx", [])

    times = []
    for b in bts:                                    # show the first thing on screen in the beat, mid-way
        spans = [(max(s, b["s"]), min(e, b["e"])) for s, e, _ in ev if s < b["e"] - 0.2 and e > b["s"] + 0.2]
        a, z = spans[0] if spans else (b["s"], b["e"])
        t = min(a + 0.6, (a + z) / 2)
        b["at"] = round(min(t, b["e"] - 0.05, total - 0.05), 3)
        times.append(b["at"])
    if (plan.get("behind") or any('data-fx-layer="behind"' in open(os.path.join(project, r)).read()
                                  for r in plan.get("fx", []))) \
            and not os.path.exists(os.path.join(project, "public", "subject.webm")):
        die("something goes behind the speaker: wait for matte.py to finish first")
    from build import build
    pub = os.path.dirname(build(project, need_audio=False))
    shots = os.path.join(project, "work", "shots")
    shutil.rmtree(shots, ignore_errors=True)
    hf(["snapshot", "-o", shots, "--at", ",".join(f"{t:.3f}" for t in times), "--no-end", "--describe", "false",
        pub], cwd=pub)
    pngs = sorted(glob.glob(os.path.join(shots, "frame-*.png")),
                  key=lambda p: int(re.search(r"frame-(\d+)", os.path.basename(p))[1]))
    if len(pngs) != len(times):
        die(f"expected {len(times)} frames, got {len(pngs)}")
    out_dir = os.path.join(project, "storyboard")
    frames = os.path.join(out_dir, f"v{version}")
    shutil.rmtree(frames, ignore_errors=True)
    os.makedirs(frames)
    cards = []
    for b, png in zip(bts, pngs):
        name = f"{b['id']}.png"
        shutil.copy(png, os.path.join(frames, name))
        on = [d for s, e, d in ev if s < b["e"] - 0.15 and e > b["s"] + 0.15]
        hear = [f"{x[1]} at {x[0]:.1f}s" for x in sfx if b["s"] <= x[0] < b["e"]]
        cards.append(f"""<section class="beat" id="{b['id']}"><img src="v{version}/{name}" loading="lazy">
<div class="txt"><div class="id">{b['id']} <span>{b['s']:.1f}-{b['e']:.1f}s</span></div>
<p class="says">{html.escape(b['says'])}</p>
<p><b>On screen</b> {html.escape('; '.join(on)) or 'you and the captions'}</p>
<p><b>Sound</b> {html.escape(', '.join(hear)) or 'your voice'}</p>
<textarea data-beat="{b['id']}" placeholder="Note on {b['id']} (or leave empty)"></textarea></div></section>""")
    needs = plan.get("needs", [])
    need_html = "".join(f"<li><b>{html.escape(n[0])}</b> {html.escape(n[1])}</li>" for n in needs) \
        or "<li>Nothing. Read it, leave notes or write go.</li>"
    key = json.dumps(f"reel-notes:{os.path.basename(project)}:v{version}")
    page = f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>{html.escape(plan['title'])} storyboard v{version}</title><style>
:root{{--bg:#101010;--card:#1b1b1b;--ink:#eee;--dim:#9a9a9a;--acc:{style['colors']['accent']}}}
body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,sans-serif}}
header{{padding:20px 16px;max-width:980px;margin:auto}}h1{{font-size:22px;margin:0 0 4px}}
.need{{background:var(--card);border-left:4px solid var(--acc);padding:10px 16px;margin:14px 0}}
.need ul{{margin:6px 0;padding-left:18px}}
main{{max-width:980px;margin:auto;padding:0 16px 120px}}
.beat{{display:flex;gap:18px;background:var(--card);border-radius:10px;padding:14px;margin:14px 0}}
.beat img{{width:200px;height:356px;object-fit:cover;border-radius:6px;flex:none}}
.txt{{flex:1;min-width:0}}.id{{font-weight:700;font-size:18px}}.id span{{color:var(--dim);font-weight:400;
font-size:14px;margin-left:6px}}.says{{font-size:17px;margin:6px 0 10px}}b{{color:var(--dim);font-weight:600;
margin-right:6px}}textarea{{width:100%;box-sizing:border-box;min-height:56px;background:#0d0d0d;color:var(--ink);
border:1px solid #333;border-radius:6px;padding:8px;font:inherit}}
.bar{{position:fixed;left:0;right:0;bottom:0;background:#000d;padding:12px 16px;display:flex;gap:12px;
justify-content:center;align-items:center}}button{{background:var(--acc);border:0;border-radius:6px;
padding:10px 18px;font:600 15px system-ui;cursor:pointer}}#all{{position:absolute;left:-9999px}}
@media (max-width:640px){{.beat{{flex-direction:column}}.beat img{{width:100%;height:auto}}}}
</style></head><body><header><h1>{html.escape(plan['title'])} <span style="color:var(--dim)">storyboard
v{version} · {total:.1f}s · {len(bts)} beats</span></h1>
<div class="need"><b>What I need from you</b><ul>{need_html}</ul></div>
<p>Write a note under any beat you want changed. Write <b>go</b> in the box below when it's ready to render.
Then press Copy notes and paste them to Claude.</p>
<textarea data-beat="overall" placeholder="Overall note, or go"></textarea></header>
<main>{''.join(cards)}</main>
<div class="bar"><button id="copy">Copy notes</button><span id="msg"></span></div>
<textarea id="all" readonly></textarea>
<script>
const KEY = {key};
let saved = {{}};
try {{ saved = JSON.parse(localStorage.getItem(KEY) || "{{}}"); }} catch (e) {{}}
document.querySelectorAll("textarea[data-beat]").forEach(t => {{
  t.value = saved[t.dataset.beat] || "";
  t.addEventListener("input", () => {{
    saved[t.dataset.beat] = t.value;
    try {{ localStorage.setItem(KEY, JSON.stringify(saved)); }} catch (e) {{}}
  }});
}});
document.getElementById("copy").onclick = async () => {{
  const lines = [...document.querySelectorAll("textarea[data-beat]")]
    .filter(t => t.value.trim()).map(t => t.dataset.beat + ": " + t.value.trim());
  const text = lines.length ? "Storyboard v{version} notes\\n" + lines.join("\\n") : "go";
  const box = document.getElementById("all");
  box.value = text;
  try {{ await navigator.clipboard.writeText(text); }}
  catch (e) {{ box.select(); document.execCommand("copy"); }}
  document.getElementById("msg").textContent = lines.length + " notes copied";
}};
</script></body></html>
"""
    out = os.path.join(out_dir, "index.html")
    with open(out, "w") as f:
        f.write(page)
    print(f"-> {out} ({len(bts)} beats)")
    if needs:
        print("needs from you:\n" + "\n".join(f"  {n[0]}: {n[1]}" for n in needs))


if __name__ == "__main__":
    main()

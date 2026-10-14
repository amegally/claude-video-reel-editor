"""plan.json + words.json + fx/*.html -> public/index.html, the HyperFrames composition of the reel.

python build.py <project>            build and lint
python build.py <project> --check    build and run the full HyperFrames check (layout, contrast)

Layers, bottom to top: #picture (the cut, then anything BEHIND the speaker, then the cutout of the speaker on
top of it, then demo beats: the app full screen with the speaker shrunk into a corner; camera moves and grades
act on all of it together), #front (boxes, overlays, marks, front effects),
#captions, #top (effects that must sit over captions).
Every time in plan.json is on the OUTPUT timeline (seconds into the finished video).
"""
import html
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (FONTS, FPS, H, VENDOR, W, die, duration, hf, load_plan, load_style, project_arg,  # noqa: E402
                    read_json, snap, t_dur, t_start)

GRADES = {
    "none": "none",
    "bw": "grayscale(1) contrast(1.08)",
    "warm": "sepia(0.22) saturate(1.12) contrast(1.04) brightness(1.02)",
    "cool": "saturate(0.88) hue-rotate(-8deg) contrast(1.05) brightness(0.98)",
    "film": "sepia(0.12) saturate(0.9) contrast(1.1) brightness(0.97)",
    "moody": "saturate(0.7) contrast(1.15) brightness(0.82)",
}
IMG = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg")


# ---------- style ----------

def font_files(style, plan, pub):
    """copy every font the reel uses into public/fonts: Google Fonts by name, or a local file (a brand font that
    isn't on Google Fonts) given as "file" in the style. Returns [(family, weight, filename)]."""
    os.makedirs(os.path.join(pub, "fonts"), exist_ok=True)
    specs = list(style["fonts"].values())
    for spec in plan.get("fonts", []):
        fam, _, wt = spec.partition(":")
        specs.append({"family": fam, "weight": int(wt or 400)})
    out, seen = [], set()
    for f in specs:
        key = (f["family"], f["weight"])
        if key in seen:
            continue
        seen.add(key)
        if f.get("file"):
            src = os.path.expanduser(f["file"])
            if not os.path.exists(src):
                die(f"font file not found: {src}")
        else:
            src = os.path.join(FONTS, f"{f['family'].replace(' ', '')}-{f['weight']}.ttf")
            if not os.path.exists(src):
                from setup import get_font
                get_font(f["family"], f["weight"])
        name = os.path.basename(src)
        shutil.copy2(src, os.path.join(pub, "fonts", name))
        out.append((f["family"], f["weight"], name))
    return out


def rgba(col, alpha):
    if not col.startswith("#"):
        return col
    h = col.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"


def css(style, fonts):
    c, cap, box, look = style["colors"], style["captions"], style["boxes"], style.get("look", {})
    fam = {k: f"'{v['family']}'" for k, v in style["fonts"].items()}
    wt = {k: v["weight"] for k, v in style["fonts"].items()}
    faces = "".join(f"@font-face{{font-family:'{f}';font-weight:{w};src:url('fonts/{n}')}}\n" for f, w, n in fonts)
    plate = f"background:{rgba(c['box'], 0.78)};padding:8px 22px 12px;"
    shadow = "text-shadow:0 2px 10px rgba(0,0,0,.75),0 0 2px rgba(0,0,0,.9);"
    case = {"upper": "uppercase", "lower": "lowercase"}.get(cap.get("case"), "none")
    lbl = box.get("label_font", box["font"])
    return faces + f"""
:root{{--text:{c['text']};--accent:{c['accent']};--box:{c['box']};--box-text:{c['box_text']};
--dim:{c.get('dim', 'rgba(255,255,255,.45)')};
--font-caption:{fam[cap['font']]};--font-display:{fam[box['font']]};--font-label:{fam[lbl]}}}
body{{margin:0;background:#000}}
#root{{position:relative;width:100%;height:100%;overflow:hidden;background:#000}}
.layer{{position:absolute;inset:0}}
#picture{{position:absolute;inset:0;filter:{GRADES.get(look.get('grade', 'none'), 'none')}}}
.full{{position:absolute;left:0;top:0;width:{W}px;height:{H}px;object-fit:cover}}
.behind-media{{position:absolute;left:0;width:{W}px}}
.fill{{position:absolute;left:0;width:{W}px}}
.cap{{position:absolute;left:60px;right:60px;display:flex;justify-content:center}}
.cap .line{{display:flex;flex-wrap:wrap;justify-content:center;gap:0 .3em;{plate if cap.get('plate') else shadow}
font-family:var(--font-caption);font-weight:{wt[cap['font']]};font-size:{cap['size']}px;line-height:1.15;
color:var(--text);text-transform:{case};text-align:center}}
.cap .line.boxed{{background:var(--box);padding:8px 20px 10px;text-shadow:none}}
.cap .w{{display:inline-block}}
.cap.reveal .w{{opacity:0}}
.cap.karaoke .w{{color:var(--dim)}}
.box{{position:absolute;left:50px;right:50px;display:flex;justify-content:center}}
.box.left{{justify-content:flex-start}}
.box .in{{display:inline-block;background:var(--box);color:var(--box-text);padding:{box.get('pad', '10px 26px 14px')};
font-family:var(--font-display);font-weight:{wt[box['font']]};font-size:{box['size']}px;line-height:1.08;
text-align:center;white-space:pre-line}}
.box.left .in{{text-align:left}}
.box.big .in{{font-size:{box.get('big_size', int(box['size'] * 1.3))}px}}
.box.sub .in{{font-size:{box.get('sub_size', int(box['size'] * 0.62))}px}}
.box.label .in,.box.mono .in{{font-family:var(--font-label);font-weight:{wt[lbl]};font-size:{box['label_size']}px;
padding:{box.get('label_pad', '6px 16px 8px')}}}
.box .acc{{color:var(--accent)}}
.ov{{position:absolute}}
.ov img,.ov video{{width:100%;height:100%;object-fit:contain;display:block}}
.ov.cover img,.ov.cover video{{object-fit:cover}}
.demo{{position:absolute;inset:0;filter:drop-shadow(0 18px 40px rgba(0,0,0,.35))}}
.mark{{position:absolute;transform-origin:0 50%}}
.mark svg{{position:absolute;inset:0;overflow:visible}}
.vignette{{position:absolute;inset:0;background:radial-gradient(ellipse at 50% 42%,transparent 55%,rgba(0,0,0,.55))}}
.bar{{position:absolute;left:0;width:{W}px;height:{look.get('letterbox', 0)}px;background:#000}}
"""


# ---------- helpers ----------

def media_src(project, src):
    """copy a plan asset into public/ and return its path relative to public/"""
    path = src if os.path.isabs(src) else os.path.join(project, src)
    if not os.path.exists(path):
        die(f"missing asset: {src}")
    rel = src if not os.path.isabs(src) else os.path.join("media", os.path.basename(src))
    dst = os.path.join(project, "public", rel)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if not os.path.exists(dst) or os.path.getmtime(dst) < os.path.getmtime(path):
        shutil.copy2(path, dst)
    return rel


def take_of(segs, w):
    sg = segs[w["seg"]] if w.get("seg", -1) < len(segs) else {}
    return sg.get("take", w.get("seg"))


def caption_lines(words, segs, style, plan):
    """short lines: break on max_words or max_chars, after end punctuation, at a pause, at a change of take"""
    cap = style["captions"]
    most, chars = cap.get("max_words", 4), cap.get("max_chars", 26)
    lines, cur = [], []
    for w in words:
        width = sum(len(x["w"]) + 1 for x in cur) + len(w["w"])
        if cur and (len(cur) >= most or width > chars or re.search(r"[.?!,:;]$", cur[-1]["w"])
                    or w["s"] - cur[-1]["e"] > 0.3 or take_of(segs, w) != take_of(segs, cur[-1])):
            lines.append(cur)
            cur = []
        cur.append(w)
    if cur:
        lines.append(cur)
    off = plan.get("captions", {}).get("off", [])
    return [ln for ln in lines if not any(a <= ln[0]["s"] < b for a, b in off)]


def windows(spans):
    out = []
    for s, e in sorted(spans):
        if out and s <= out[-1][1] + 1 / FPS:
            out[-1][1] = max(out[-1][1], e)
        else:
            out.append([s, e])
    return out


def fx_fragment(project, rel):
    path = os.path.join(project, rel)
    if not os.path.exists(path):
        die(f"missing effect file: {rel}")
    text = open(path).read()
    layer = (re.search(r'data-fx-layer="(behind|front|top)"', text) or [None, "front"])[1]
    m = re.search(r'data-start="([\d.]+)"[^>]*data-duration="([\d.]+)"', text)
    span = (float(m[1]), float(m[1]) + float(m[2])) if m else None
    return layer, span, f"<!-- {rel} -->\n{text}\n"


def entrance(sel, kind, t, speed, ease):
    """how a box or overlay arrives: cut (on the frame, nothing moves), pop (a quick scale-up) or rise"""
    if kind == "cut":
        return ""
    if kind == "rise":
        return f'tl.from("{sel}",{{y:24,opacity:0,duration:{speed},ease:"{ease}"}},{t:.4f});'
    return f'tl.fromTo("{sel}",{{scale:.86,opacity:0}},{{scale:1,opacity:1,duration:.2,ease:"back.out(2.2)"}},{t:.4f});'


def mark_html(i, m, accent):
    """a stroke drawn on the word it points at: underline, circle or box, in the accent colour by default"""
    col, size = m.get("color", accent), m.get("size", 6)
    x, y, w = m["x"], m["y"], m["w"]
    h = m.get("h", size)
    kind = m.get("kind", "underline")
    if kind == "underline":
        body = f'<div id="mk{i}d" style="width:{w}px;height:{size}px;background:{col};border-radius:{size}px;' \
               f'transform-origin:0 50%"></div>'
        draw = f'tl.fromTo("#mk{i}d",{{scaleX:0}},{{scaleX:1,duration:{m.get("dur", 0.25)},ease:"power2.out"}},'
    else:
        shape = (f'<ellipse cx="{w / 2}" cy="{h / 2}" rx="{w / 2}" ry="{h / 2}"' if kind == "circle"
                 else f'<rect x="0" y="0" width="{w}" height="{h}"')
        body = f'<svg width="{w}" height="{h}">{shape} id="mk{i}d" fill="none" stroke="{col}" ' \
               f'stroke-width="{size}" stroke-linecap="round" pathLength="1" stroke-dasharray="1" ' \
               f'stroke-dashoffset="1"/></svg>'
        draw = f'tl.to("#mk{i}d",{{attr:{{"stroke-dashoffset":0}},duration:{m.get("dur", 0.35)},ease:"power2.inOut"}},'
    return (f'<div id="mk{i}" class="mark clip" style="left:{x}px;top:{y}px;width:{w}px;height:{h}px" '
            f'data-start="{t_start(m["start"])}" data-duration="{t_dur(m["start"], m["end"])}">{body}</div>',
            draw + f'{snap(m["start"]):.4f});')


# ---------- the composition ----------

def build(project, need_audio=True):
    plan, style = load_plan(project), load_style(project)
    pub = os.path.join(project, "public")
    clean = os.path.join(pub, "clean.mp4")
    if not os.path.exists(clean):
        die("run cut.py first")
    total = duration(clean)
    D = t_dur(0, total)
    words = read_json(os.path.join(project, "words.json"), [])
    segs = read_json(os.path.join(project, "work", "segments.json"), [])
    fonts = font_files(style, plan, pub)
    shutil.copy2(os.path.join(VENDOR, "gsap.min.js"), pub)
    if os.path.isdir(os.path.join(project, "fx")):
        shutil.copytree(os.path.join(project, "fx"), os.path.join(pub, "fx"), dirs_exist_ok=True)
    motion = style.get("motion", {})
    speed, ease = motion.get("speed", 0.3), motion.get("ease", "power3.out")
    box_in = style["boxes"].get("in", "pop")
    ov_in, ov_out = style.get("overlays", {}).get("in", "pop"), style.get("overlays", {}).get("out", "cut")
    tw, behind, front, top, caps = [], [], [], [], []

    # behind the speaker: full-width media, the cutout goes back on top in the same windows
    spans = []
    for i, b in enumerate(plan.get("behind", [])):
        rel, s, e = media_src(project, b["src"]), b["start"], b["end"]
        spans.append((s, e))
        y, fit = b.get("y", 0), b.get("fit", "width")
        if b.get("bg"):
            behind.append(f'<div id="bhfill{i}" class="fill clip" style="top:0;height:{H}px;background:{b["bg"]}" '
                          f'data-start="{t_start(s)}" data-duration="{t_dur(s, e)}"></div>')
        style_attr = f'top:{y}px' + (f';height:{H}px;object-fit:{fit}' if fit in ("cover", "contain") else "")
        if rel.lower().endswith(IMG):
            behind.append(f'<div id="bh{i}" class="clip" data-start="{t_start(s)}" data-duration="{t_dur(s, e)}">'
                          f'<img class="behind-media" style="{style_attr}" src="{rel}"></div>')
        else:
            ms = f' data-media-start="{b.get("media_start", 0):.4f}"'
            behind.append(f'<video id="bh{i}" class="behind-media clip" style="{style_attr}" src="{rel}" muted '
                          f'playsinline data-start="{t_start(s)}" data-duration="{t_dur(s, e)}"{ms}></video>')

    # demo beats: the app full screen behind, the speaker cut out and shrunk into the bottom corner they point
    # from. Their cutout lives in its own wrapper so it can scale without touching anything else
    demos, demo_spans = [], []
    for i, d in enumerate(plan.get("demo", [])):
        rel, s, e = media_src(project, d["src"]), d["start"], d["end"]
        demo_spans.append((s, e))
        fill = d.get("bg", "#000")
        behind.append(f'<div id="dmfill{i}" class="fill clip" style="top:0;height:{H}px;background:{fill}" '
                      f'data-start="{t_start(s)}" data-duration="{t_dur(s, e)}"></div>')
        fit = d.get("fit", "width")
        style_attr = f'top:{d.get("y", 0)}px' + (f';height:{H}px;object-fit:{fit}' if fit in ("cover", "contain") else "")
        if rel.lower().endswith(IMG):
            behind.append(f'<div id="dm{i}" class="clip" data-start="{t_start(s)}" data-duration="{t_dur(s, e)}">'
                          f'<img class="behind-media" style="{style_attr}" src="{rel}"></div>')
        else:
            behind.append(f'<video id="dm{i}" class="behind-media clip" style="{style_attr}" src="{rel}" muted '
                          f'playsinline data-start="{t_start(s)}" data-duration="{t_dur(s, e)}" '
                          f'data-media-start="{d.get("media_start", 0):.4f}"></video>')
        right = d.get("corner", "right") == "right"
        ox, oy = (W - d.get("margin", 0) if right else d.get("margin", 0)), H
        demos.append(f'<div id="demo{i}" class="demo" style="transform-origin:{ox}px {oy}px">'
                     f'<video id="demosub{i}" class="full clip" src="subject.webm" muted playsinline '
                     f'data-start="{t_start(s)}" data-duration="{t_dur(s, e)}" data-media-start="{snap(s):.4f}">'
                     f'</video></div>')
        tw.append(f'tl.fromTo("#demo{i}",{{scale:1}},{{scale:{d.get("scale", 0.5)},duration:{d.get("dur", 0.4)},'
                  f'ease:"{d.get("ease", "power3.inOut")}"}},{snap(s):.4f});')
        tw.append(f'tl.fromTo("#dm{i}",{{opacity:0}},{{opacity:1,duration:{min(0.2, d.get("dur", 0.4))}}},{snap(s):.4f});')

    for layer, span, text in (fx_fragment(project, rel) for rel in plan.get("fx", [])):
        {"behind": behind, "front": front, "top": top}[layer].append(text)
        if layer == "behind" and span:
            spans.append(span)
    subject = os.path.join(pub, "subject.webm")
    # the cutout is split at every picture cut inside a window: a seek across a jump shows one wrong frame
    cuts = sorted(sg.get("pic_s", sg["out_s"]) for sg in segs)
    cut_windows = []
    for s, e in windows(spans):
        for ds, de in demo_spans:                    # the demo wrapper carries the cutout there
            if ds < e and de > s:
                s, e = (de, e) if ds <= s else (s, ds)
        edges = [s] + [c for c in cuts if s < c < e] + [e]
        cut_windows += [(a, b) for a, b in zip(edges, edges[1:]) if b - a > 0.5 / FPS]
    if (cut_windows or demos) and not os.path.exists(subject):
        if need_audio:
            die("something goes behind the speaker: run matte.py first")
        print("warning: no cutout yet (matte.py), so whatever is behind the speaker covers them in this build")
        cut_windows, demos = [], []
    cutout = "".join(
        f'<video id="cutout{n}" class="full clip" src="subject.webm" muted playsinline data-start="{t_start(s)}" '
        f'data-duration="{t_dur(s, e)}" data-media-start="{snap(s):.4f}"></video>\n'
        for n, (s, e) in enumerate(cut_windows))

    # boxes: the speaker's own words, set in a box
    for i, b in enumerate(plan.get("boxes", [])):
        s, e = b["start"], (total if b["end"] == "end" else b["end"])
        kind = b.get("kind", "title")
        pos = f"top:{b.get('y', 220)}px" + (f";left:{b['x']}px;right:auto" if isinstance(b.get("x"), int) else "")
        cls = f"box {kind} clip" + (" left" if b.get("align") == "left" or isinstance(b.get("x"), int) else "")
        front.append(f'<div id="box{i}" class="{cls}" style="{pos}" data-start="{t_start(s)}" '
                     f'data-duration="{t_dur(s, e)}"><span class="in" id="bx{i}">{b["text"]}</span></div>')
        tw.append(entrance(f"#bx{i}", b.get("in", box_in), snap(s), speed, ease))

    # overlays: the real thing, in the open space around the face
    for i, o in enumerate(plan.get("overlays", [])):
        rel, s, e = media_src(project, o["src"]), o["start"], o["end"]
        box = f'left:{o["x"]}px;top:{o["y"]}px;width:{o["w"]}px;height:{o["h"]}px'
        cls = "ov cover" if o.get("fit") == "cover" else "ov"
        if rel.lower().endswith(IMG):
            inner = (f'<div id="ovm{i}" class="clip" data-start="{t_start(s)}" data-duration="{t_dur(s, e)}" '
                     f'style="width:100%;height:100%"><img src="{rel}"></div>')
        else:
            inner = (f'<video id="ovm{i}" class="clip" src="{rel}" muted playsinline data-start="{t_start(s)}" '
                     f'data-duration="{t_dur(s, e)}" data-media-start="{o.get("media_start", 0):.4f}"></video>')
        front.append(f'<div id="ov{i}" class="{cls}" style="{box}">{inner}</div>')
        tw.append(entrance(f"#ov{i}", o.get("in", ov_in), snap(s), speed, ease))
        if o.get("out", ov_out) == "fade":
            tw.append(f'tl.to("#ov{i}",{{opacity:0,duration:.12}},{max(s, snap(e) - 0.12):.4f});')

    # marks: underlines, circles and boxes drawn on the words they point at
    for i, m in enumerate(plan.get("marks", [])):
        el, draw = mark_html(i, m, style["colors"]["accent"])
        front.append(el)
        tw.append(draw)

    # captions: karaoke (the line waits dimmed, each word lights as it's said) or reveal (words appear one by one)
    cap = style["captions"]
    if cap.get("on", True):
        mode = cap.get("mode", "karaoke")
        txt, acc = style["colors"]["text"], style["colors"]["accent"]
        lit = acc if cap.get("current") == "accent" else txt
        lines = caption_lines(words, segs, style, plan)
        moves = plan.get("captions", {}).get("moves", [])
        for li, ln in enumerate(lines):
            s = ln[0]["s"]
            nxt = lines[li + 1][0]["s"] if li + 1 < len(lines) else total
            e = min(nxt, ln[-1]["e"] + 0.6, total)
            mv = next((m for m in moves if m[0] <= s < m[1]), None)
            y = mv[2] if mv else cap["y"]
            boxed = " boxed" if mv and len(mv) > 3 and mv[3] == "box" else ""
            spans_html = "".join(f'<span class="w" id="w{li}_{k}">{html.escape(w["w"])}</span>'
                                 for k, w in enumerate(ln))
            caps.append(f'<div id="cap{li}" class="cap {mode} clip" style="top:{y}px" data-start="{t_start(s)}" '
                        f'data-duration="{t_dur(s, e)}"><div class="line{boxed}">{spans_html}</div></div>')
            for k, w in enumerate(ln):
                at = max(snap(w["s"]), snap(s))
                if mode == "karaoke":
                    tw.append(f'tl.set("#w{li}_{k}",{{color:"{lit}"}},{at:.4f});')
                    if lit != txt:
                        end = ln[k + 1]["s"] if k + 1 < len(ln) else e
                        tw.append(f'tl.set("#w{li}_{k}",{{color:"{txt}"}},{max(snap(end), at + 1 / FPS):.4f});')
                else:
                    tw.append(f'tl.set("#w{li}_{k}",{{opacity:1,color:"{acc}"}},{at:.4f});')
                    end = ln[k + 1]["s"] if k + 1 < len(ln) else e
                    tw.append(f'tl.set("#w{li}_{k}",{{color:"{txt}"}},{max(snap(end), at + 1 / FPS):.4f});')

    # grade windows (black and white, warm, moody...) over the picture only, never over captions
    base = GRADES.get(style.get("look", {}).get("grade", "none"), "none")
    for g in plan.get("grade", []):
        tw.append(f'tl.set("#picture",{{filter:"{GRADES[g["look"]]}"}},{snap(g["start"]):.4f});')
        tw.append(f'tl.set("#picture",{{filter:"{base}"}},{snap(g["end"]):.4f});')

    # camera: push-ins and settles on the whole picture (footage, what's behind, the cutout) around the face
    face = plan.get("face") or [W // 2 - 200, H // 3, 400, 500]
    origin = f"{face[0] + face[2] / 2:.0f}px {face[1] + face[3] / 2:.0f}px"
    for c in plan.get("camera", []):
        org = f'{c["origin"][0]}px {c["origin"][1]}px' if c.get("origin") else origin
        if c.get("from"):                            # a settle: start pushed in, ease back out
            tw.append(f'tl.fromTo("#picture",{{scale:{c["from"]},transformOrigin:"{org}"}},{{scale:{c.get("scale", 1)},'
                      f'duration:{c.get("dur", 0.5)},ease:"{c.get("ease", "power2.out")}"}},{snap(c["start"]):.4f});')
        else:
            tw.append(f'tl.to("#picture",{{scale:{c.get("scale", 1.08)},transformOrigin:"{org}",'
                      f'duration:{c.get("dur", 0.3)},ease:"{c.get("ease", "power2.out")}"}},{snap(c["start"]):.4f});')
        if c.get("end") is not None:
            tw.append(f'tl.set("#picture",{{scale:1}},{snap(c["end"]):.4f});')

    look = style.get("look", {})
    finish = ('<div class="vignette"></div>' if look.get("vignette") else "") + (
        f'<div class="bar" style="top:0"></div><div class="bar" style="bottom:0;top:auto"></div>'
        if look.get("letterbox") else "")
    master = os.path.join(pub, "master.wav")
    if need_audio and not os.path.exists(master):
        die("run mix.py first")
    audio = f'<audio id="master" src="master.wav" data-start="0" data-duration="{D}"></audio>' \
        if os.path.exists(master) else ""

    doc = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width={W}, height={H}">
<title>{html.escape(plan.get('title', 'reel'))}</title>
<script src="gsap.min.js"></script>
<style>{css(style, fonts)}</style>
<script>window.FX=function(f){{(window.__fx=window.__fx||[]).push(f)}};</script>
</head><body>
<div id="root" data-composition-id="reel" data-start="0" data-width="{W}" data-height="{H}" data-duration="{D}">
<div id="picture">
<video id="aroll" class="full clip" src="clean.mp4" muted playsinline data-start="0" data-duration="{D}"></video>
<div id="behind" class="layer">
{chr(10).join(behind)}
</div>
{cutout}{chr(10).join(demos)}
</div>
<div id="front" class="layer">
{chr(10).join(front)}
{finish}
</div>
<div id="captions" class="layer">
{chr(10).join(caps)}
</div>
<div id="top" class="layer">
{chr(10).join(top)}
</div>
{audio}
</div>
<script>
const tl = gsap.timeline({{paused: true}});
{chr(10).join(t for t in tw if t)}
(window.__fx || []).forEach(function (f) {{ f(tl); }});
tl.set({{}}, {{}}, {total:.4f});
window.__timelines["reel"] = tl;
</script>
</body></html>
"""
    out = os.path.join(pub, "index.html")
    with open(out, "w") as f:
        f.write(doc)
    return out


def main():
    project = project_arg("<project> [--check]")
    out = build(project, need_audio=False)
    pub = os.path.dirname(out)
    res = hf(["check" if "--check" in sys.argv else "lint"], cwd=pub, check=False)
    print((res.stdout + res.stderr).strip()[-3000:])
    print(f"-> {out}")
    if res.returncode:
        sys.exit(1)


if __name__ == "__main__":
    main()

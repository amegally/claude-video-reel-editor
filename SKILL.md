---
name: claude-video-reel-editor
description: Turn raw talking-head takes into a finished vertical reel (9:16) - finds your style first from example videos or a style menu, then cuts the takes (last clean take of each line, every pause over 0.2s gone), word-by-word captions, type and screen recordings behind you, effects built fresh for each video, sound effects from their own folder, a storyboard you comment on, and a checked render. Use when someone asks Claude to edit, cut or caption a raw video of themselves talking, to set or change their video style ("new style"), or to render the storyboard after they say go.
model: opus
effort: max
---

# Claude Video Reel Editor

Made by alfred.makes. Guide: https://alfredmakes.com/guides/claude-video-reel-editor

Raw takes in, finished vertical video out. Two stops for the user: approve the style once, then read a storyboard
before every render. Nothing renders until they say **go**.

## Rules that win over everything below
1. **Max effort.** This file's header sets it for the main session. Every subagent you launch for this skill gets
   `model: "opus"` and `effort: "max"`: this skill is the instruction that allows setting effort.
2. **Show off.** Every effect, whether you build it or a subagent does, starts from this brief: *"Show off. This
   beat is your showreel: build the best piece of motion design you can."* Study https://prompt-motion.com first
   as the bar for timing, easing and restraint, then read `FX.md`. Showing off means how well each move is made,
   not how much is on screen.
3. **Never cover the face.** Text, cards, effects and screen recordings sit in the open space around the head.
   Find the face first (`frames.py`) and keep `plan.face` up to date. Small is fine.
4. **Only their words.** Captions come from the transcript. Boxes and on-screen lines use words the speaker said or
   the source they talk about. Never write a hook, claim or call to action they didn't say: ask for it.
5. **Real things first.** Their screen recordings play full size behind them, not as small cropped cards. A brand
   they name gets its real logo (the brand's press kit or Wikimedia Commons), never a redrawn one.
6. **Demo beats.** When they introduce an app or a demo ("they looked like this", "here's the tool"), cut them out,
   shrink them to about half size into the bottom corner they point from, and play the app full screen behind them
   from that word on (`demo`). Big, not a card. Give the beat time: `hold` on that take keeps a second of them
   pointing at it. **Never shrink or cut them out while they hold something up** (a phone, a book, a product): the matte
   drops what they hold, and it vanishes from their hand. Look at the take's frames first. Start the shrink once
   it's lowered and their hands are clear, or, if they hold it through the beat, keep them full size and put the
   app as big as the open space they point at allows (`overlays`), clear of the face and of what they hold.
7. **Spellcheck every on-screen word.** QA flags anything not in the dictionary; clear each one.

## Paths
- `SKILL` = this folder. Never write into it.
- `HOME` = `$REEL_HOME`, default `~/reels`: `style/` (their saved style), `projects/<slug>/`, `fonts/`, `vendor/`,
  `models/`, `.venv/`.
- `PY` = `HOME/.venv/bin/python`. Run every script as `PY SKILL/scripts/<script>.py`. Each one prints its usage.
- First time on a machine: `python3 SKILL/scripts/setup.py` until it prints READY (Python 3.10+, Node 22+,
  ffmpeg with libvpx-vp9). It installs everything into HOME and renders a test frame.
- Matte and render take minutes: start them in the background with a log (`nohup ... > log 2>&1 &`) and check back.
  To run them at low priority, set the niceness to exactly 19 (`nice -n $((19 - $(ps -o nice= -p $$)))`): HyperFrames
  sets its own priority to 19 and fails with EACCES if the shell's niceness plus `nice -n 19` already clamped to 20.

## 0. Style (first use, and whenever they say "new style")
Skip this step only when `HOME/style/style.json` exists with `"approved": true`. Every project copies that file,
so an approved style is never asked about again.

Ask: *"Send me 2-3 videos in a style you like (links or files), or say 'show me styles' and pick one."*

**They send videos.**
1. `PY scripts/style.py refs <link-or-file> <link-or-file> ...` downloads them (yt-dlp) and writes, for each,
   a frame sheet, three full frames, the transcript and pace numbers (cuts per minute, median shot length,
   words per minute) to `HOME/style/refs/`. Instagram often refuses downloads without a login: ask them to save
   the video and send the file.
2. Look at every sheet and frame. Start from the closest preset (`style.py use <clean|editorial|mono|punch|film>`)
   and edit `HOME/style/style.json` to match what you see: fonts (the closest Google Fonts), colours (hex from the
   frames), captions (size, height, words per line, case, plate or shadow), look (grade, vignette, letterbox),
   motion (speed, easing, transitions, how dense the effects are), how boxes and overlays arrive (`boxes.in`,
   `overlays.in`/`out`: cut, pop or rise), caption mode (`karaoke`: the line waits dimmed and lights word by word;
   `reveal`: words appear one by one), sound, and `notes`: pace and cut rate from the numbers, how a big word
   lands, what goes behind the speaker. Set `"source"` to the links. A brand font that isn't on Google Fonts:
   `{"family": "...", "weight": 400, "file": "/path/to/font.otf"}`.
3. `PY scripts/style.py board <one of their takes>` renders one frame of their own take in that style to
   `HOME/style/board.png`. Show it. Change and re-render until they say yes, then `style.py approve`.

**They want to pick.** `PY scripts/style.py menu <one of their takes>` writes `HOME/style/menu/index.html`:
- First, six Lemo-Opuscar styles that work around a person on camera: swiss-motion, halftone-dossier,
  dark-keynote, living-screencast, whiteboard, risograph, then a link to all 43
  (https://lemomo-ai.github.io/lemo-opuscar/). When they pick one, fetch its style at run time from
  `https://raw.githubusercontent.com/lemomo-ai/lemo-opuscar/main/styles/<slug>/STYLE.md` and translate it into
  `style.json`: fonts as the nearest Google Fonts, colours, texture (grade, grain, halftone become look settings or
  effects), motion and sound. Those styles were made for 16:9 animated films: adapt them to a vertical
  talking-head video, as type, cards and backdrops around the speaker and never over the face. Link to it in
  `"source"`; never copy its text, prompts or code into this skill or the project.
- Then the five presets rendered on their own take, and more galleries to borrow ideas from (HyperFrames,
  onetake, Collage B-roll, Claude Animation Base). onetake has a non-commercial licence: look, never copy.
- Then "make it yours": their changes go into `style.json`, `style.py board`, approve.

**Sound effects.** This skill ships no sounds. Once the style is approved, ask: *"Got sound effects you like? Point
me at a folder."* `PY scripts/style.py sounds <folder>` sorts every file into a role (pop, whoosh, swoosh-out,
click, mouse, key, typing, toggle, tick, ding, thud, hit, paper, shutter, glitch, riser) by its name, or by how it
sounds when the name says nothing, and saves `sound.sfx_dir` and `sound.roles` in their style. Show them the role
list and fix any they disagree with in `style.json` (first file in a role is the one used). No folder yet: Mixkit
(https://mixkit.co/free-sound-effects/) and Pixabay (https://pixabay.com/sound-effects/) have free ones they can
download into one. No folder at all is fine: their videos have no sound effects, and they can add them when they
post.

## 1. Intake
- One clip: use it. A folder of phone clips (iPhones record many short HDR clips): `PY scripts/join.py <folder>
  <out.mp4>` tone-maps them to SDR and joins them with the sound in sync.
- `PY scripts/new.py <slug> <clip> "Title"` -> `HOME/projects/<slug>/` with `plan.json` and a copy of the style.
- Ask for the source they talk about (article, post, app) if there is one, and their screen recordings.
- `PY scripts/frames.py <slug> --source --every 5`, look at `work/frames.jpg`. Set `plan.crop` if the default
  centre crop cuts them off, and `plan.face` = `[x, y, w, h]` of the face in the 1080x1920 frame.

## 2. Transcript
- Put names and terms in `plan.prompt`. `PY scripts/transcribe.py <slug>`, then read
  `work/source-transcript.txt` (source seconds, one line per stretch of speech).
- People repeat a line until it lands: keep the **last clean take** of each line. Write `plan.keep` as
  `[start, end]` source-second ranges in speaking order, each starting just before its first word. A take that
  sets up a demo can carry `{"hold": 1.2}` as a third item: that much of them after the last word stays in.
- A line marked `<- check: stretched` hides speech the model skipped (a false start, a retake): run
  `transcribe.py <slug> --range <start> <end>` on that stretch before choosing.

## 3. Cut
- `PY scripts/cut.py <slug> --plan` lists the pieces, `cut.py <slug>` makes `public/clean.mp4`. Every pause longer
  than `style.cut.max_pause` (0.2s) is cut, inside takes too, and each piece's end follows the loudness out so
  soft endings ("s", "f") survive. Picture and sound share frame boundaries, so lip sync can't drift. At a change
  of take the picture switches `style.cut.j_lead` (0.15s) after the sound: `work/segments.json` has each piece's
  `pic_s`. End anything tied to a take (a box, an overlay, a screen behind) at the next take's `pic_s`, not its
  first word.
- Read `words.json`. Wrong words: `plan.fixes` (`{"word": "Word"}`, `{"word@41.2": "Word"}` for one occurrence at
  that source second, `""` to drop it), then `cut.py <slug> --words`. Words spoken over near-silence are dropped
  automatically: speech models invent text there ("Thanks for watching!").
- Watch the cut-only file once. If a join jumps, adjust `keep` and cut again.

## 4. Beats
`PY scripts/storyboard.py <slug> --list` prints beat ids (`p01`, `p02`...: one per sentence). Every time in
`plan.json` is in OUTPUT seconds (`words.json` has them). Fill the plan:

| Field | Shape | Use |
|---|---|---|
| `boxes` | `{text, start, end, y, kind: title/big/sub/mono, x?, align?, in?}` | their words in a box; `<span class="acc">` for the accent colour; `\n` for a second line; `end: "end"` holds to the last frame; `in` overrides the style's entrance (cut/pop/rise) |
| `overlays` | `{src, start, end, x, y, w, h, fit?, media_start?, note}` | screenshots and short clips in the open space around the head |
| `behind` | `{src, start, end, y?, fit?: width/cover/contain, bg?, media_start?, note}` | full-size screen recordings or images behind the speaker (needs the matte) |
| `demo` | `{start, end, src, corner: right/left, scale?: 0.5, fit?, y?, bg?, media_start?, dur?}` | a demo beat: the app full screen behind (`fit: width` with a `bg` fill below, or `cover`), the speaker's cutout shrinking to `scale` into the bottom `corner` over `dur` seconds. Needs the matte. Move the captions off them and their pointing hand for the window. Crop a window border off the recording first: a 2px dark edge shows full screen |
| `grade` | `{start, end, look: bw/warm/cool/film/moody}` | change the picture's look for a stretch; captions and boxes stay in colour |
| `captions` | `{moves: [[start, end, y, "box"?]], off: [[start, end]]}` | move captions (above the head when shot from low or close, `"box"` puts the line on the box colour so it reads against the ceiling) or hide them under an effect |
| `marks` | `{start, end, kind: underline/circle/box, x, y, w, h?, color?, size?}` | a stroke drawn on the word it points at, on a screen recording or a box |
| `camera` | `{start, scale, dur?, ease?, from?, end?, origin?}` | push in (`scale` 1.06-1.12) or settle (`from: 1.08`, back to 1) on the whole picture, around `plan.face`; only if the style moves the camera |
| `fx` | `["fx/<name>.html"]` | effects you write per video (`FX.md`) |
| `sfx` | `[[time, name, gain_db, seconds?]]` | `time` is the hit. `name` is a role from the style's `sound.roles` (pop, whoosh, click, typing...: give `typing` seconds) or any file's name in their sound folder, without the extension; a file in the project's `audio/` wins. Empty when the style has no sound folder |
| `music` | `{src, gain_db?}` or null | ducked under the voice; none unless they give a track |
| `needs` | `[[beat, "exactly what to send"]]` | what only they have |

- Make the edit do what the words say, on the word: the box lands as they say it, the picture turns black and
  white on "black and white".
- **Needs pass, every beat, unasked.** Anything only they have (their screen, their dashboard, a photo, something
  behind a login) goes into `needs` as a request precise enough to shoot without a follow-up question. Build the
  beat with a placeholder anyway; never hold the storyboard for it.
- They hold up a phone or laptop screen: footage that looks mirrored usually isn't, so check the text in a frame.
  Don't flip it; put the real screen up big beside them.
- Shot from low (head low, chin near the caption line): move captions above the head with `captions.moves`.
- Anything in `behind` or a `behind` effect: start `PY scripts/matte.py <slug>` in the background now. The matte
  can't keep things they hold (a phone, a laptop): nothing goes behind those takes, and no demo shrink (rule 6).
- **Effects.** Whatever boxes, overlays, behind and grade can't do is an effect, written fresh for this video
  (`FX.md`). For several, launch one subagent per effect at the same time (rule 1 and rule 2 in every prompt), each
  with: `FX.md`, `style.json`, the effect's file name, layer and window, the words with their output times, the
  face box for that window, the real assets. Review every frame they report at full size; send fixes back.

## 5. Sound
With a sound folder in the style, every visual event gets a sound in the style's density (`style.sound.density`),
always under the voice: pops on things that pop in, whooshes on changes, clicks on boxes. Use only roles and files
the folder has (`sound.roles`); `mix.py` skips and lists any it can't find. Without a sound folder, leave `sfx`
empty. `PY scripts/mix.py <slug>` -> `public/master.wav`,
loudness-matched in two passes (-14 LUFS by default).

## 6. Storyboard, then stop
`PY scripts/storyboard.py <slug> --version 1` -> `storyboard/index.html`: every beat with a real frame, the line,
what's on screen, what you hear and a note box. Open it for them (publish it as an artifact if your tools can,
otherwise give the path or run `open`). In the same message say what you need from them, beat by beat, or
"nothing needed from you". Then stop. The page's Copy notes button gives you their notes as `p03: ...` lines.

## 7. Notes
Their notes are about this video. Apply every one, rebuild, `storyboard.py <slug> --version 2`, show it again.
When a note is about their taste in general ("captions always bigger"), also write it into
`HOME/style/style.json` so the next video starts with it, and tell them you did.

## 8. Render (after go)
`PY scripts/render.py <slug> v1` mixes, builds, lints, renders and runs QA (`renders/v1-qa.txt`). QA must PASS:
lip sync (picture vs the cut, frame by frame), sound offset, length, loudness. Clear every WARN: each flagged
spelling, each box word they didn't say, each HyperFrames check finding (layout, text contrast). Pull a few frames
of the render and look at them before handing it over. Deliver the path to the mp4.

## Gotchas
- J-cuts: the first word of a take is heard 0.15s before its picture. A box on that word after a demo or a
  `behind` window starts at the take's `pic_s` (with its sound), or it lands on the old picture for a few frames.
  Caption moves pick each line by its first word, so end a move at the next line's first word, not at `pic_s`.
- Times on the output timeline are snapped to frames; write them to 2-3 decimals and let the scripts snap.
- The matte resets its memory at every cut. A behind window that starts mid-shot is fine; one that crosses a
  change of framing shows a soft edge for a few frames: start it at the cut.
- Anything behind the speaker must clear before it reaches the parts of them the matte didn't keep (a desk edge).
- An effect's fonts must be in the style or in `plan.fonts` (`["Anton:400"]`); `build.py` downloads them.
- HyperFrames owns playback: no `play()`, no `Math.random()` without a seed, no clocks, no network in an effect.
  Don't tween a timed element's visibility; animate its children. Never put a video inside a timed wrapper.
- Whisper mishears names: put them in `plan.prompt`, fix the rest with `plan.fixes`.

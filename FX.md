# Writing an effect

An effect is one HTML file, `<project>/fx/<name>.html`, listed in `plan.fx`. `build.py` drops it into the reel as
is. Write it fresh for the beat it serves; there is no effect library to start from.

## The brief (it goes first in every effect prompt)
*"Show off. This beat is your showreel: build the best piece of motion design you can."*

Before writing, study https://prompt-motion.com: it is the bar for timing, easing and restraint. Then:
- **One idea per effect,** landing on the word that names it. If the line says "a timer above my head", the timer
  appears above the head as the word "timer" is said.
- **Motion has a reason.** Things enter from where they make sense and leave the way they came. Ease out on
  entry, ease in on exit, nothing linear unless it is a clock.
- **Readable.** Text stays still long enough to read (about 0.8s per short line). Contrast against the footage:
  use the style's box colour, a plate or a shadow.
- **Around the speaker, never over the face.** You get the face box for your window. Use the space above the
  head, beside it, or behind it (`data-fx-layer="behind"`, the cutout of the speaker is drawn on top).
- **The style's tokens, not new ones:** `var(--text)`, `var(--accent)`, `var(--box)`, `var(--box-text)`,
  `var(--font-display)`, `var(--font-caption)`, `var(--font-label)`. Another font: add `"Family:weight"` to
  `plan.fonts`.
- Going all out means how well each move is made, not how many moves there are.

## The file
```html
<!-- what it does, in one line: the storyboard shows this -->
<div id="fx-timer" class="clip" data-fx-layer="front" data-start="7.20" data-duration="32.4">
  <div class="fx-timer-face"></div>
</div>
<style>
  #fx-timer { position: absolute; left: 0; top: 0; width: 1080px; height: 1920px; }
  .fx-timer-face { position: absolute; left: 390px; top: 150px; width: 300px; height: 120px;
    background: var(--box); }
  .fx-timer-face span { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;
    font: 700 88px var(--font-label); color: var(--box-text); opacity: 0; }
</style>
<script>
FX(function (tl) {
  var face = document.querySelector("#fx-timer .fx-timer-face");
  var start = 7.2, length = 32;
  for (var left = length; left >= 0; left--) {       // one span per second, switched with tl.set: seekable
    var d = document.createElement("span");
    d.textContent = Math.floor(left / 60) + ":" + String(left % 60).padStart(2, "0");
    face.appendChild(d);
    var at = start + (length - left);
    tl.set(d, { opacity: 1 }, at);
    if (left > 0) tl.set(d, { opacity: 0 }, at + 1);
  }
  tl.from(face, { y: -40, opacity: 0, duration: 0.35, ease: "power3.out" }, start);
});
</script>
```

- **Root element:** a unique `id` starting `fx-`, `data-fx-layer` = `behind` (behind the speaker), `front` (over the
  picture, under captions) or `top` (over captions), and `data-start` / `data-duration` in output seconds.
  Every selector starts with that id, so two effects can't collide.
- **Timeline:** register with `FX(function (tl) { ... })` and put tweens on `tl` at absolute output times.
- **Assets** go in `fx/<name>/` and are referenced as `fx/<name>/file.png`.
- **Sound:** add the hits to `plan.sfx`, not to the effect.

## What breaks a render
- Anything random or live: `Math.random()` without a seed, `Date`, timers, `fetch`, `requestAnimationFrame`
  loops. The renderer seeks to each frame, so everything must be a function of the timeline.
- Tweening `visibility`, `display` or `autoAlpha` on the root (it is a timed element): animate its children.
- A `<video>` with `data-start` inside an element that also has `data-start`.
- `repeat: -1`: use a finite repeat count.
- `tl.call()` or `onUpdate` for anything visible: the renderer seeks without firing callbacks. Change text and
  visibility with `tl.set()` or tweens, as the timer above does.
- A CSS `transform` on an element you also move with GSAP `x`/`y`: use one or the other.

## Check it before the storyboard
`PY SKILL/scripts/build.py <project>` must lint clean. Then snapshot your window and look at every frame at full
size: `npx hyperframes@0.8.139 snapshot -o /tmp/fx --at <t1>,<t2>,<t3> --no-end --describe false <project>/public`.

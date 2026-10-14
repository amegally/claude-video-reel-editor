# Changelog

Every entry comes from a real edit: something that looked wrong in a finished video, and the change that fixed it.

## 2026-10-13
- **A clean install, README only,** on a throwaway home: Mac only for now, Python 3.10 or newer (Homebrew's is
  3.14), the speech model stays in `~/reels`, and setup says how long it takes and where its test video is.
- **No demo shrink while they hold something up.** A device in the speaker's hand vanished as they shrank into
  the corner: the matte drops held objects. The shrink now waits until it's lowered; if it never is, they stay full
  size and the app goes up big in the space they point at.
- **QA's lip-sync check reads real frame times.** It read "+1 frame" at most pieces of a phone video that was in
  sync: it resampled the phone's uneven frame rate before comparing. It now finds the source frame the render
  shows by that frame's own timestamp, and it skips demo beats, where the face is shrunk into a corner.
- **Nothing lands on the old picture after a demo.** With a J-cut the next line is heard before its picture, so a
  box on that word showed over the app for three frames and its caption stayed at the demo's position. Boxes now
  start with the new take's picture, and caption moves end at the next line's first word.
- **Your own sound effects.** Synthesized sounds sounded fake, and the free recorded set that replaced them still
  wasn't good enough, so the skill ships none. Point it at a folder of sounds you like and it sorts them into roles
  by name, or by how they sound when the name says nothing. With no folder, the video has no sound effects.
- **Demo beats.** When the speaker introduces an app ("they looked like this"), they're cut out and shrunk into the
  bottom corner they point from while the app plays full screen behind them. A take can hold a beat after its last
  word so the demo has time on screen.
- **Takes play in the order they're spoken.** When a later take was used first, the cut put the pictures back in
  filming order while the sound stayed in speaking order. Each piece is now cut on its own, in speaking order.
- **Lip sync is checked against the raw take,** not against the cut, so a wrong cut can't pass.
- **J-cuts:** at a change of take, the next line is heard 0.15s before it's seen.
- **Karaoke captions:** the line waits dimmed and each word lights as it's said. When the shot is close and the
  chin sits on the caption line, the line moves above the head in a box.
- **Brand fonts that aren't on Google Fonts** can be a local file in the style.
- **Boxes and overlays arrive the way the style says** (cut, pop or rise), and new box sizes (big, sub, mono).
- **Underlines, circles and boxes drawn on words,** and camera push-ins and settles, for styles that use them.
- **Your style comes first.** Before the first edit, the skill learns your look from 2-3 example videos you send
  (downloaded, frame sheets, transcript, cut rate, words per minute), or from a menu: six Lemo-Opuscar styles that
  work around a person on camera, five presets shown on your own take, and links to more galleries. It renders one
  frame of your take in the style and saves it only after you approve. Every video after that reuses it.
- **Words nobody said are dropped.** The speech model wrote "Thanks for watching!" over a silent gap between takes.
  Any word spoken over near-silence is now removed before it can become a caption.
- **Stretched words get flagged.** A single word stretched over a second or more was hiding a retake the model
  skipped. The transcript marks them, and `transcribe.py --range` redoes that stretch.
- **Phone screens aren't flipped.** Footage that looked mirrored wasn't: the phone's text read correctly. When
  someone holds up a screen, the real screen now goes up big beside them instead.
- **Captions move above the head when the shot is from low,** where the usual caption line covered the chin.
- **Real logos for named brands,** from the brand's press kit or Wikimedia Commons, never redrawn.
- **Every on-screen word is spellchecked** in QA. A finished reel once shipped "Seperate".
- **The storyboard works anywhere:** a local page with a note box per beat and a Copy notes button.

## 2026-10-12
- **Every pause over 0.2s is cut,** inside a take as well as between takes. Some gaps in a finished cut still
  dragged. The end of each piece now follows the loudness out, so soft endings like "s" aren't clipped.
- **The last clean take of each line** is the one that's kept.
- **Screen recordings play full size behind the speaker.** Small cropped cards in a narrow column showed too little
  of the actual tool.
- **A steady cutout.** Cutting the speaker out frame by frame made the edge flicker and left bits of wall in.
  The matte now carries memory from frame to frame (Robust Video Matting), resets at every cut and uses the
  footage's own pixels inside the edge.
- **iPhone HDR clips join in sync.** Joining many short clips as they were slid the sound ~0.05s further off per
  clip. Each clip is now tone-mapped to SDR and given sound exactly as long as its picture before joining.
- **Loudness in two passes.** One pass landed at -14.6 LUFS. A second measurement now corrects what's left.
- **Nothing covers the face,** not even for a second.
- **Max effort and a showreel brief** for every effect, with prompt-motion.com as the bar.

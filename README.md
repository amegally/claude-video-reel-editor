# Claude Video Reel Editor

Made by [alfred.makes](https://www.instagram.com/alfred.makes/). Full guide:
[alfredmakes.com/guides/claude-video-reel-editor](https://alfredmakes.com/guides/claude-video-reel-editor)

A Claude Code skill that edits raw talking-head takes into finished vertical reels. You film and it finds your
style, keeps the last clean take of each line, captions every word, puts your screen recordings behind you, builds
effects for each video and adds your sound effects. It shows you a storyboard and renders once you say go.

## What you need
- A Mac (tested on Apple silicon; Linux and Windows aren't tested yet)
- [Claude Code](https://claude.com/claude-code)
- [Homebrew](https://brew.sh), then `brew install git python node ffmpeg`: Python 3.10 or newer (tested on 3.13
  and 3.14), Node 22 or newer, ffmpeg with the `libvpx-vp9` encoder (Homebrew's has it). Check with
  `python3 --version`: macOS's own `python3` is 3.9, so Homebrew's must come first in your `PATH`.
- About 2.5 GB of disk: Python packages, the speech and matting models, a headless Chrome, and download caches

## Install
```bash
git clone https://github.com/amegally/claude-video-reel-editor ~/.claude/skills/claude-video-reel-editor
python3 ~/.claude/skills/claude-video-reel-editor/scripts/setup.py
```
Setup takes 5-20 minutes, mostly downloads, and is quiet for a few minutes while PyTorch downloads. A Hugging Face
warning about `HF_TOKEN` is harmless. It installs into `~/reels`: a Python environment, fonts and the speech model
(HyperFrames keeps its headless Chrome in `~/.cache/hyperframes`). To put it elsewhere, add
`export REEL_HOME=/your/path` to your shell profile before running setup, so Claude Code sees it too.

It ends with a one-second test video and prints `READY` and the video's path: `open` it to check it plays.

## First video
Start a new Claude Code session (skills load when a session starts), then:

> Edit this video: ~/Movies/my-take.mov

1. **Style.** The first time, Claude asks for 2-3 videos in a style you like (links or files), or shows you a menu
   of styles rendered on your own face. You approve one frame and it's saved for every video after.
2. **Storyboard.** Claude cuts the takes, plans every beat and opens a storyboard page: a frame per beat, what you
   say, what's on screen, what you hear. Type a note under any beat, press **Copy notes**, paste them back.
3. **Go.** Write go. Claude renders, checks lip sync, loudness and spelling, and gives you the mp4.

## Sound effects
The skill ships no sounds. After you approve a style, Claude asks for a folder of sound effects you like and sorts
every file into a role (pop, whoosh, click, typing and so on) by its name, or by how it sounds when the name says
nothing. You can fix the list in your style. If you don't have any, [Mixkit](https://mixkit.co/free-sound-effects/) and
[Pixabay](https://pixabay.com/sound-effects/) have free ones. With no folder, your videos come out without sound
effects and you add them where you post.

Say **new style** any time to start the style step again. Notes about your taste ("bigger captions, always") are
saved into your style.

## What's inside
| | |
|---|---|
| `SKILL.md` | the process Claude follows |
| `FX.md` | how Claude writes each video's effects |
| `styles/` | five starting presets |
| `scripts/` | setup, style, sounds, join, new, transcribe, cut, frames, matte, mix, build, storyboard, render, qa |

## Built on
[HyperFrames](https://hyperframes.dev) (renders HTML to video), [GSAP](https://gsap.com),
[faster-whisper](https://github.com/SYSTRAN/faster-whisper), [yt-dlp](https://github.com/yt-dlp/yt-dlp),
[Google Fonts](https://fonts.google.com), and [Robust Video Matting](https://github.com/PeterL1n/RobustVideoMatting)
for the cutout. The matting model is GPL-3.0: it is downloaded from its own release page the first time you need
it and is not part of this repo.

Style galleries the style step links to: [Lemo-Opuscar](https://lemomo-ai.github.io/lemo-opuscar/),
[HyperFrames](https://hyperframes.dev), [onetake](https://onetakemotion.com) (non-commercial licence),
[Collage B-roll](https://github.com/pyang5166/gbro-collage-broll),
[Claude Animation Base](https://github.com/JohnHeibel/ClaudeAnimationBase).

## Changelog
It gets better with every video edited with it: see [CHANGELOG.md](CHANGELOG.md).

## License
MIT. Made by [alfred.makes](https://www.instagram.com/alfred.makes/).

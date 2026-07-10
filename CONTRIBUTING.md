# Contributing to Voxa

Thanks for wanting to help. Voxa is a single-module CLI with a small, deliberately boring
test suite — you should be able to get productive in a few minutes.

## Setup

```bash
git clone https://github.com/akshinmrv/Voxa
cd Voxa
python3 -m venv venv && source venv/bin/activate

pip install -e ".[dev]"       # voxa + pytest + ruff
```

You also need **ffmpeg** on your PATH (`sudo apt install ffmpeg`, `brew install ffmpeg`).

For the pure-logic test suite you do **not** need torch, whisper or any TTS engine — those
imports are guarded. `pip install pytest numpy soundfile openai` is enough, which is exactly
what CI installs.

## Before you open a pull request

```bash
ruff check .      # lint — CI enforces this
pytest            # 93 tests, ~10 seconds
```

Both must pass. If a test needs an engine you don't have installed, skip it (`pytest.skip`)
rather than making it a hard dependency.

## The golden tests

`tests/test_golden.py` locks the composed behaviour of the deterministic pipeline —
word-onset refinement, non-speech filtering, sentence merging, translation length budgets,
SRT timestamps and the anchored placement maths. Unit tests check functions alone; the
golden files check them together, which is where regressions actually hide.

If you change that behaviour **on purpose**:

```bash
UPDATE_GOLDEN=1 pytest tests/test_golden.py
git diff tests/golden/          # review every line before committing
```

A golden diff you can't explain is a bug, not a formatting change.

## Verify against real audio

Unit tests cannot hear. Anything that touches synthesis, timing or mixing should also be run
on a real file before you send it:

```bash
voxa some_video.mp4 --target_lang ru --whisper_model tiny
ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 some_video_dubbed_ru.mp4
```

Say in the PR what you ran and what you observed. "Tests pass" is not evidence that a dub
still lines up with the source.

## Adding a TTS engine

All four engines share one loop (`synthesize_timeline`), so an engine only has to say how a
single line of text becomes a WAV file:

1. Write `async def _tts_<name>(subs, args, work_dir, video_path, gate_asr, logger)`.
   Perform your setup (model load, client, voice lookup), raise `TTSError` with a useful
   message if it can't proceed, and call `synthesize_timeline(...)` with a `render` callback.
2. Add one line to the `TTS_PROVIDERS` registry.
3. `--tts` picks the new name up automatically; it is generated from the registry.

Please do **not** re-implement the timeline, the silence padding, the placement or the drift
tracking inside your engine. That duplication is exactly what let Piper silently miss two
years of fixes.

The same shape applies to translation backends via `LLM_PROVIDERS`.

## Dependencies

Voxa is MIT and intends to stay installable without copyleft obligations.

- **Do not add a GPL-licensed required dependency.** `pysrt` (GPL-3.0) was removed for this
  reason and replaced with a 40-line SubRip parser.
- Anything only one engine needs belongs in an **extra**, not in `dependencies`.
- If a package pins its own dependencies aggressively (Coqui did, Chatterbox does), prefer
  talking to it over HTTP — see `--openai-tts-base-url` — rather than importing it.

New third-party licenses must be recorded in [NOTICE.md](NOTICE.md).

## Commits

Explain *why*, not *what* — the diff already says what. If you fixed a bug, say what the
broken behaviour was and how you know it's fixed now.

## Reporting bugs

Include the exact command, the tail of `<video>_work/voxa.log`, your OS, Python version, and
`ffmpeg -version`. If the dub drifts out of sync, the log's `⏱️ max sync drift` line and the
`.srt` timestamps are usually enough to diagnose it.

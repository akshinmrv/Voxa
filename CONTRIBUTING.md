# Contributing to Voxa

Thanks for wanting to help. The dubbing pipeline is one module, `voxa.py`; the server, the
Studio window and the console sit around it (see [ARCHITECTURE.md](docs/ARCHITECTURE.md)).
The test suite is deliberately boring, so you should be productive within a few minutes.

## Setup

```bash
git clone https://github.com/akshinmrv/Voxa
cd Voxa
python3 -m venv venv && source venv/bin/activate

pip install -e ".[dev,serve]"   # voxa, its server, pytest and ruff
```

You also need **ffmpeg** on your PATH (`sudo apt install ffmpeg`, `brew install ffmpeg`).

For the tests you do **not** need torch, Whisper or any speech engine; those imports are
guarded. `pip install pytest numpy soundfile openai` runs the pipeline's tests, and adding
`fastapi httpx python-multipart` runs the server's too. That is what CI installs.

Working on the console? It lives in [`web/`](web/): `npm ci`, then `npm run dev` next to
`voxa serve`. `npm run build:console` builds the copy that ships inside the package.

## Before you open a pull request

```bash
ruff check .      # lint, enforced by CI
pytest            # about 670 tests; some skip without FFmpeg or an engine
```

Both must pass. If a test needs an engine you don't have installed, skip it (`pytest.skip`)
rather than making it a hard dependency.

If you changed the console, also run in `web/`:

```bash
npm run lint && npx tsc --noEmit
npm run check:messages     # en, az and tr have the same keys, nothing left in English
npm run check:contrast     # every text colour passes WCAG AA in both themes
```

and the browser tests, which drive the real server with the pipeline faked and run axe on
every page:

```bash
pip install playwright==1.55.0 && python -m playwright install chromium   # with [serve] above
npm run build:console      # in web/
VOXA_E2E=1 pytest tests/test_e2e.py
```

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

Every engine shares one loop (`synthesize_timeline`), so an engine only has to say how a
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

Voxa is MIT and intends to stay installable without GPL obligations.

- **Do not add a GPL-licensed required dependency.** `pysrt` (GPL-3.0) was removed for this
  reason and replaced with a 40-line SubRip parser.
- **Adding a Piper voice?** Copy its licence from the voice's `MODEL_CARD` into the table in
  [NOTICE.md](NOTICE.md#41-piper-voices). When a language has a CC0, public-domain or CC BY
  voice, prefer it — many Piper voices are non-commercial.
- Anything only one engine needs belongs in an **extra**, not in `dependencies`.
- If a package pins its own dependencies hard (Chatterbox and VoxCPM2 pin PyTorch and
  transformers), don't import it. Give it an environment of its own in `voxa_engines` with a
  worker script, as those two have, or talk to it over HTTP through `--openai-tts-base-url`.

New third-party licenses must be recorded in [NOTICE.md](NOTICE.md).

## Commits

Explain *why*, not *what* — the diff already says what. If you fixed a bug, say what the
broken behaviour was and how you know it's fixed now.

## Reporting bugs

Include the exact command, the tail of `<video>_work/voxa.log`, your OS, Python version, and
`ffmpeg -version`. If the dub drifts out of sync, the log's `⏱️ max sync drift` line and the
`.srt` timestamps are usually enough to diagnose it.

# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] — 2026-07-10

First public release. Voxa was developed privately for some time before being opened; the
version number restarts at 1.0.0 rather than continuing a history nobody can see.

### Added

- **One-command dubbing.** `voxa video.mp4 --target_lang ru` transcribes, translates,
  synthesizes and mixes, with no API key required by default.
- **Four TTS engines** behind a `TTS_PROVIDERS` registry: `edge` (Microsoft neural voices),
  `openai` (instructable delivery), `piper` (fully offline), `xtts` (voice cloning).
- **Four translation backends** behind an `LLM_PROVIDERS` registry: `google`, `ollama`
  (local, private), `openai` and `anthropic`. LLM translation is context-aware — lines are
  translated in blocks so pronouns, gender, names and tone stay consistent — with automatic
  per-line fallback when a block response is malformed.
- **Anchored placement.** Each clip occupies the slot between its own source onset and the
  next line's onset. Over-runs are trimmed, short clips are padded, and the cursor is
  assigned rather than accumulated — so the dub cannot drift out of sync with the speaker.
- **Duration-matched translation.** The translator receives a character budget per line
  (`--speech-rate`), so a line fits its slot at a natural pace instead of being sped up.
- **No-slowdown fitting.** Clips are only ever sped up to fit; a short clip is padded with
  silence rather than stretched, which sounds dragged.
- **Word-onset refinement.** Segment starts are tightened to the first word's timestamp, so
  the dub doesn't begin before the speaker does.
- **Non-speech filtering.** Segments Whisper flags as likely non-speech (music intros it
  transcribed as phantom text) are dropped before synthesis.
- **Quality gate** (`--quality-gate`): each synthesized segment is transcribed back and
  scored for word error rate, clipping, near-silence and pacing, with a per-job report.
- **XTTS auto-regeneration**: XTTS sampling is stochastic, so a flagged segment is
  re-synthesized up to twice and the best-scoring take is kept.
- **LLM delivery direction** (`--detect-emotion`): an LLM tags each line with a short
  emotion/energy/pace instruction for OpenAI TTS, cached per job.
- **Self-hosted speech** (`--openai-tts-base-url`): route synthesis to any server exposing
  OpenAI's `/v1/audio/speech` — Chatterbox, LocalAI, Kokoro-FastAPI — with no API key and no
  extra Python dependency. This is the license-clean route to voice cloning.
- **`faster-whisper` backend** (`--whisper-backend faster`): 2-4× quicker, no torch, with
  built-in VAD.
- **Resumable runs.** Every step is checkpointed in `<video>_work/`; an interrupted job
  resumes. `--no-resume` forces a fresh start.
- **Preflight validation.** Missing input files and a missing ffmpeg are reported before any
  work begins, and ffmpeg's own error output is surfaced when it fails.
- **Structured logging** (`--log-format json`), `.env` loading, and JSON config defaults
  (`--config`).
- **Golden regression harness** covering the deterministic pipeline end to end, with no
  engine, network or API key required.
- Community health files, CI (lint + tests on Python 3.9–3.12), and Dependabot.

### Licensing

- Voxa is MIT and requires **no copyleft dependency**. The GPL-3.0 `pysrt` requirement was
  removed in favour of a built-in SubRip parser.
- Third-party engine licenses, the non-commercial status of the XTTS-v2 weights, and the
  unofficial nature of the `edge-tts` and `deep-translator` endpoints are documented in
  [NOTICE.md](NOTICE.md).

### Known limitations

- `--tts xtts` requires `coqui-tts`, whose model weights are **non-commercial** (CPML), and
  Coqui Inc. no longer exists to sell a commercial licence. Use `--openai-tts-base-url` with
  an MIT engine for commercial cloning.
- `--parallel` applies to the `google` and `ollama` translators only; LLM translators already
  batch whole blocks in one call.
- Synthesis requests are issued sequentially. For network-bound engines this is the main
  remaining performance headroom.

[Unreleased]: https://github.com/akshinmrv/Voxa/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/akshinmrv/Voxa/releases/tag/v1.0.0

# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.6.4] - 2026-07-29

### Fixed

- **A closing line that breathes past the source audio is no longer cut off.** The last-line pacing
  (1.6.1) can extend the final line to the end of the *video*, but the mix ended it at the source
  *audio* stream — which can be shorter than the video — truncating the sentence. The mix now runs
  to the longer of the two, so the closing line always finishes.

### Added

- **Per-speaker voices for XTTS and Piper, plus a `--speaker-voices` override.** Under `--diarize`,
  XTTS now clones each speaker from where they talk in the source, so every dubbed speaker keeps the
  original speaker's voice. `--speaker-voices "SPEAKER_00=voice,SPEAKER_01=voice"` pins a voice per
  speaker for any engine — Edge/OpenAI voice names, Piper model files (the only way to get
  per-speaker Piper, whose pool is one voice per language), or XTTS reference wavs. Unlisted
  speakers keep the automatic voice.

## [1.6.3] - 2026-07-28

### Added

- **The operator console runs diarization.** The `voxa serve` job form now has a "Speakers" toggle
  that gives each speaker their own voice, with an optional speaker count — mirroring the CLI's
  `--diarize`. It appears only when the `diarize` extra is installed, and the Hugging Face token is
  read from the server's environment, just like the OpenAI key.

### Changed

- **Diarization folds a voice it accidentally split.** In auto mode (no `--num-speakers` or
  `--max-speakers`), pyannote can split one clean voice into two speakers; Voxa now merges speakers
  whose voice embeddings are near-identical back into one, so a two-person clip isn't dubbed in
  three voices. It merges by voice, not by timing, so it never mislabels the way a positional guess
  would, and setting a count or bound keeps pyannote's own clustering untouched.

## [1.6.2] - 2026-07-28

### Added

- **`--min-speakers` / `--max-speakers` for `--diarize`.** Bound the speaker count when you don't
  know it exactly — pyannote clusters within the bounds, which curbs the over-splitting a clean or
  short recording can produce. `--num-speakers` still wins when you do know the exact count.

### Changed

- **Diarization is steadier.** Sub-quarter-second diarization turns (a clipped word, a brief
  misattribution to a new speaker) are dropped before speakers are assigned, and a segment that
  overlaps no turn now takes the nearest turn's speaker instead of an arbitrary one.

## [1.6.1] - 2026-07-28

### Changed

- **The final line now finishes at a natural pace.** The last line has nothing after it to overlap,
  so it is no longer compressed to its own spoken window — it plays out to the end of the media
  (its start still anchored to the source), which keeps a wordier final line from sounding rushed.
  Earlier lines already breathe into the pause that follows them, added in 1.6.0.

### Documentation

- The README (all three languages) now documents speaker diarization (`--diarize`) and its
  per-speaker voices, and notes that the most natural pacing comes from an LLM translator.
  `NOTICE.md` records the pyannote diarization model: MIT, gated on Hugging Face, no commercial
  restriction.

## [1.6.0] - 2026-07-28

### Added

- **Speaker diarization with per-speaker voices (`--diarize`).** Detects who speaks when
  (pyannote.audio), keeps every sentence within one speaker, and gives each speaker a **distinct
  voice** — Edge picks different voices from the language's pool, OpenAI cycles its voice set.
  Optional extra (`pip install 'voxa-dub[diarize]'`) with a Hugging-Face-gated model: MIT-licensed
  and free to ship, but you accept its terms and pass a token (`--hf-token` / `HF_TOKEN`). Optional
  `--num-speakers` hint. Default off, so runs without `--diarize` are byte-for-byte unchanged.
  Piper/XTTS stay single-voice for now, and it isn't yet combinable with `--subtitles`
  (diarization needs the source audio).

### Changed

- **Dubbed lines now breathe into the pause before the next line.** When the target language is
  wordier than the source (Turkish or Russian for English, say), a line no longer has to be sped
  up to fit only its original spoken window — it may extend into the following silence, up to a
  short gap before the next line's onset, so the pace stays natural instead of sounding rushed.
  The start of every line is still anchored to the source timeline, so nothing drifts and lines
  never overlap. This pairs with an LLM translator's per-line length budget for the most natural
  result; with the plain `google` translator a very verbose line can still be compressed to fit.

## [1.5.0] - 2026-07-27

### Added

- **Import subtitles with `--subtitles file.srt`.** Skip Whisper and dub from a source-language
  SRT you already have — hand-corrected captions, or accurate subtitles that shipped with the
  source. The lines are still translated and spoken; audio extraction and transcription are
  skipped, and editing the SRT re-runs the stages that depend on it. Local files and the normal
  transcribe-first flow are unchanged.

## [1.4.0] - 2026-07-27

### Added

- **Dub straight from a URL.** `voxa <video-url> --target_lang de` downloads the video with
  yt-dlp and then runs the normal pipeline on it. It is an optional extra —
  `pip install 'voxa-dub[url]'` — because downloading may breach the source platform's Terms
  of Service: the CLI prints a notice and **you are responsible for having the right to the
  content**. Local files behave exactly as before, and `--dry-run` reports the pending
  download without fetching anything.

## [1.3.1] - 2026-07-27

### Added

- **`voxa --version`.** Prints the version and exits.

### Fixed

- The version now comes from the package metadata (a single source of truth built from
  `pyproject.toml`) instead of a hard-coded "v1.0" string, so the `--help` banner, the startup
  configuration box and `--version` all report the real release (e.g. 1.3.0) instead of a stale
  number.

## [1.3.0] - 2026-07-26

### Changed

- **Network TTS now synthesises in parallel.** OpenAI and Edge speech ran one HTTP request
  per segment, sequentially — the single biggest bottleneck on a long dub, and one a GPU
  cannot help because the work is remote. Synthesis and placement are now separated: segments
  are synthesised concurrently (bounded by `--tts-workers`, default 4) while the
  order-dependent anchored placement pass stays sequential, so timing and drift are unchanged.
  On a measured run (2.4-min clip, 37 segments, RTX-class VPS) the speech step dropped from
  57.5s to 18.5s for OpenAI TTS at the default 4 workers (3.1×), and to 12.7s at 8 workers
  (4.5×); Edge TTS went 44.0s → 17.1s (2.6×) → 13.6s (3.2×). Longer, more network-bound clips
  gain more. Offline engines (Piper, XTTS) stay sequential since they are CPU/GPU-bound. Use
  `--tts-workers 1` for the old one-at-a-time behaviour, or raise it if your API tier allows.

### Added

- OpenAI TTS requests now retry with exponential backoff on rate-limit / 5xx errors, so the
  added concurrency rides out a 429 instead of dropping that segment's audio.
- **The operator console exposes the parallel-synthesis worker count.** Settings → Advanced has
  a "Parallel speech requests" field (1–16) that drives `--tts-workers` for console jobs, so the
  concurrency can be raised or lowered without touching the CLI.

## [1.2.0] - 2026-07-26

### Added

- **OpenRouter translator.** `--translator openrouter` reaches OpenRouter's OpenAI-compatible
  gateway, so a single `OPENROUTER_API_KEY` unlocks models from many vendors (DeepSeek,
  Gemini, Llama, and OpenAI/Anthropic too) with no extra to install — the `openai` client is
  already a core dependency. Model names are vendor-prefixed, e.g. `--openrouter_model
  deepseek/deepseek-chat`. It works everywhere the other LLM translators do: as a
  `--fallback-translator`, in the operator console's provider settings and connection test,
  and in `--dry-run` plans. Adding it was one chat adapter and one registry line — the
  extensibility the provider registries were built for.
- **Batch progress with ETA.** In multi-video runs, each finished video now prints an overall
  progress line — `📊 Batch progress: 7/20 videos · elapsed 21m00s · ~39m00s left` — with the
  ETA estimated from the average wall-time per completed video, and the summary reports the
  total. It's a plain line, not a rewriting progress bar, so it stays readable in the log file
  and when the output is piped; the per-video banner is unchanged.

## [1.1.0] - 2026-07-18

### Added

- **`--dry-run`.** Prints what a run would do — transcription model, translator and target,
  speech engine and voice, output path — and, most usefully, which cached steps it would
  reuse, so dubbing the same video into a second language shows up front that only
  translation and speech will rerun. It reports every blocker at once (a missing API key, a
  missing voice sample) instead of failing on the first, returns non-zero when it finds any,
  and writes nothing at all: no workspace, no log file.
- **Container image.** `docker run --rm -v "$PWD:/data" ghcr.io/akshinmrv/voxa clip.mp4
  --target_lang ru` — no Python, torch or ffmpeg on the host. Published to GHCR on each
  tagged release.
- **Speech-quality benchmark.** `scripts/benchmark.py` dubs one clip into several languages
  under `--quality-gate` and collects the round-trip word error rate per language;
  `docs/BENCHMARK.md` records a run across six languages together with its limitations.

## [1.0.1] - 2026-07-18

### Changed

- **The distribution is now published as `voxa-dub`.** The `voxa` name on PyPI belongs to an
  unrelated, abandoned package, so `pip install voxa` installed the wrong project entirely.
  Install with `pipx install voxa-dub` (or run it without installing: `uvx voxa-dub …`). The
  command it puts on your PATH is still **`voxa`**, and the import module is still `voxa`, so
  nothing changes once it is installed. Tagged releases now publish to PyPI automatically via
  Trusted Publishing.

### Added

- **Web frontend (`web/`).** A trilingual (EN/AZ/TR) public landing plus a local operator
  app, built with Next.js, Tailwind and next-intl. The landing is tuned for search and AI
  answer engines (hreflang, OpenGraph, JSON-LD, sitemap, robots, `llms.txt`); the operator
  app runs against `voxa serve`. A `public` build target swaps the app for a "run locally"
  notice so the landing can be deployed on its own.
- **`voxa serve`.** An optional FastAPI operator backend (behind the `[serve]` extra) that
  drives the pipeline per job and streams the seven-step progress over Server-Sent Events:
  `GET /api/options`, `POST /api/upload`, `POST /api/jobs`, `GET /api/jobs/{id}/events`, and
  result downloads. The core dubbing pipeline is unchanged — `serve` is a thin dispatch in
  the CLI.
- **CI** now also lints and builds the web frontend.

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

[Unreleased]: https://github.com/akshinmrv/Voxa/compare/v1.6.4...HEAD
[1.6.4]: https://github.com/akshinmrv/Voxa/compare/v1.6.3...v1.6.4
[1.6.3]: https://github.com/akshinmrv/Voxa/compare/v1.6.2...v1.6.3
[1.6.2]: https://github.com/akshinmrv/Voxa/compare/v1.6.1...v1.6.2
[1.6.1]: https://github.com/akshinmrv/Voxa/compare/v1.6.0...v1.6.1
[1.6.0]: https://github.com/akshinmrv/Voxa/compare/v1.5.0...v1.6.0
[1.5.0]: https://github.com/akshinmrv/Voxa/compare/v1.4.0...v1.5.0
[1.4.0]: https://github.com/akshinmrv/Voxa/compare/v1.3.1...v1.4.0
[1.3.1]: https://github.com/akshinmrv/Voxa/compare/v1.3.0...v1.3.1
[1.3.0]: https://github.com/akshinmrv/Voxa/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/akshinmrv/Voxa/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/akshinmrv/Voxa/compare/v1.0.1...v1.1.0
[1.0.1]: https://github.com/akshinmrv/Voxa/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/akshinmrv/Voxa/releases/tag/v1.0.0

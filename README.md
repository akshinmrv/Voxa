# Voxa — Automatic Video Translation & Dubbing

[![CI](https://github.com/akshinmrv/Voxa/actions/workflows/ci.yml/badge.svg)](https://github.com/akshinmrv/Voxa/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)

Transcribe a video, translate it, speak it in the target language, and mix the result back
over the original — in one command.

```bash
voxa talk.mp4 --target_lang ru
# -> talk_dubbed_ru.mp4  +  subtitles_ru.srt
```

Voxa is a single-file CLI. Four TTS engines, four translation backends, and one thing it
takes seriously: **the dub stays in sync with the source.**

---

## Quick Start

```bash
# 1. ffmpeg must be on your PATH
sudo apt install ffmpeg          # macOS: brew install ffmpeg

# 2. Install (CPU-only torch keeps this much smaller)
python3 -m venv venv && source venv/bin/activate
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install .

# 3. Dub a video
voxa video.mp4 --target_lang ru
```

That's it — no API key needed. The defaults (Whisper + Google Translate + Edge TTS) work out
of the box. Add a key only when you want LLM translation or OpenAI voices.

> Not installing? `python voxa.py video.mp4 --target_lang ru` works the same.

---

## Why it exists

Naive dubbing tools concatenate synthesized clips one after another. Every clip that runs
slightly long pushes the next one later, and by minute three the dub is a sentence behind the
speaker. Voxa places each clip **anchored to the source timeline**: the slot for a line is
`[its onset, the next line's onset]`. A clip that over-runs is trimmed to fit; a short one is
padded. The cursor always lands on the next line's true onset, so **drift cannot accumulate.**

Three more things follow from that:

- **Duration-matched translation.** The translator is given a character budget per line, so
  the translation is speakable inside its slot at a natural pace instead of being sped up.
- **Never slow speech down.** A clip shorter than its slot is padded with silence, not
  stretched — stretched speech sounds dragged.
- **Word-onset refinement.** Whisper's segment starts are coarse; Voxa tightens each segment
  to its first word's timestamp, so the dub doesn't start before the speaker does.

---

## Pipeline

```
1  Extract audio          ffmpeg -> 16 kHz mono WAV
2  Denoise                the SOURCE audio, never the synthesized speech
3  Transcribe             Whisper (openai-whisper or faster-whisper)
                          + word-onset refinement, + drop non-speech (music intros)
4  Merge into sentences   punctuation | >0.5 s pause | max duration
5  Translate -> SRT       context-aware LLM batches, length-budgeted per line
6  Synthesize             one shared timeline driver, four interchangeable engines
                          fit (speed up only) -> anchored placement -> optional scoring
7  Assemble               2-pass loudnorm, then amix(original * 0.05 + dub * 1.5)
```

Every step is checkpointed in `<video>_work/`, so an interrupted run resumes instead of
starting over (`--no-resume` to force a fresh start).

---

## Requirements

- **ffmpeg** on your PATH (Voxa checks at startup and tells you if it's missing)
- Python 3.9+

Optional engines are **extras** — install only what you use:

| Command | Enables |
|---------|---------|
| `pip install "voxa[faster]"` | `--whisper-backend faster` — 2-4× quicker, no torch |
| `pip install "voxa[piper]"` | `--tts piper` — fully offline |
| `pip install "voxa[anthropic]"` | `--translator anthropic` |
| `pip install "voxa[xtts]"` | `--tts xtts` voice cloning — ⚠️ **non-commercial weights**, see [NOTICE.md](NOTICE.md) |

`voxa[xtts]` installs [`coqui-tts`](https://github.com/idiap/coqui-ai-TTS), the maintained
community fork; the original `TTS` package has been unmaintained since Coqui shut down in
January 2024.

---

## Speech engines

| Engine | Speed | Offline | Languages | Notes |
|--------|-------|:-------:|-----------|-------|
| **edge** (default) | fast | ✗ | 100+ | Microsoft neural voices. Uses an **unofficial** endpoint — see [NOTICE.md](NOTICE.md) |
| **openai** | fast | ✗ | many | Instructable delivery. Needs `OPENAI_API_KEY`, or point it at your own server (below) |
| **piper** | very fast | ✓ | 15 | Fully offline; robotic but dependable |
| **xtts** | slow | ✓ | 17 | Voice cloning from a short sample. **Non-commercial weights** |

### Which engine for which language?

Measured with `--quality-gate --gate-model base` (ASR round-trip word error rate — lower is
better). Don't assume the cloud engine wins:

| Language | Engine | WER | Verdict |
|----------|--------|-----|---------|
| English | OpenAI TTS | 0.02 | ✅ excellent |
| Azerbaijani (`az`) | Edge (`az-AZ` native voice) | **0.41** | ✅ use this |
| Azerbaijani (`az`) | OpenAI TTS | 0.81 | ❌ foreign accent |

**Rule of thumb:** if a language has a dedicated native neural voice in Edge, prefer it.
OpenAI TTS is strongest for major languages and for anything XTTS cannot clone.

> Score your own combination before deciding — and for a low-resource language use
> `--gate-model base`: the `tiny` gate model false-positives (it scored the same Azerbaijani
> audio 0.74 instead of 0.41).

### Voice cloning (XTTS)

```bash
voxa video.mp4 --tts xtts --target_lang en                       # sample auto-extracted
voxa video.mp4 --tts xtts --voice-sample my_voice.wav            # or bring your own
```

XTTS sampling is stochastic. With `--quality-gate`, a segment that scores badly is
re-synthesized up to twice and the best take is kept.

### OpenAI TTS

```bash
voxa video.mp4 --tts openai --target_lang en --openai-voice nova
voxa video.mp4 --tts openai --openai-tts-instructions "Warm, upbeat narrator."
```

Voices: alloy, echo, fable, onyx, nova, shimmer, ash, ballad, coral, sage, verse.

Add `--detect-emotion` and an LLM tags each line with a short delivery direction (emotion,
energy, pace), passed to the engine as a per-line instruction — one cheap call per job,
cached, falling back to a punctuation heuristic if unavailable.

### Self-hosted / OpenAI-compatible endpoints

`--openai-tts-base-url` points speech requests at any server that speaks OpenAI's
`/v1/audio/speech` API — **no API key, no extra Python dependency**. This is the recommended
route to **license-clean voice cloning**, since XTTS's weights are non-commercial while
[Chatterbox](https://github.com/resemble-ai/chatterbox) is MIT.

```bash
# Run e.g. Chatterbox-TTS-Server (MIT, CPU or GPU), then:
voxa video.mp4 --target_lang tr \
     --tts openai --openai-tts-base-url http://localhost:8004/v1
```

Also works with LocalAI, Kokoro-FastAPI, or anything else exposing that route; set
`OPENAI_TTS_BASE_URL` to avoid repeating the flag. Note that Chatterbox embeds an inaudible
watermark and does not support Azerbaijani.

---

## Translation backends

| Backend | Cost | Offline | Quality |
|---------|------|:-------:|---------|
| `google` (default) | free | ✗ | literal, fine for gist |
| `ollama` | free | ✓ | contextual, local LLM — nothing leaves your machine |
| `openai` / `anthropic` | paid | ✗ | context-aware, natural, consistent |

LLM translation is **context-aware**: lines are translated in blocks, not one by one, so
pronouns, gender, names, terminology and tone stay consistent across a scene. Each block
carries a short overlap of the previous one. If a block response is malformed, Voxa falls back
to per-line translation automatically.

```bash
export OPENAI_API_KEY="sk-..."
voxa video.mp4 --translator openai --target_lang ru
voxa video.mp4 --translator anthropic --anthropic_model claude-sonnet-5

# Local, private, free
ollama pull llama3
voxa video.mp4 --translator ollama --ollama_model llama3
```

Transient rate-limit and 5xx errors are retried with exponential backoff, and token usage is
logged. Add your model's prices to the `LLM_PRICING` table in `voxa.py` to also print a cost
estimate.

| Option | What it does | Default |
|--------|--------------|---------|
| `--openai_model` / `--anthropic_model` | Model id | `gpt-5` / `claude-opus-4-8` |
| `--llm_batch_size` | Lines translated together per call | `25` |
| `--speech-rate` | Chars/sec used to length-budget each translation | `15` |

Adding a provider is one adapter plus one line in the `LLM_PROVIDERS` registry — see
[CONTRIBUTING.md](CONTRIBUTING.md).

---

## Quality gate

```bash
voxa video.mp4 --quality-gate --gate-model base
```

Each synthesized segment is transcribed back and compared to what it was supposed to say
(word error rate), then checked for clipping, near-silence and implausible pacing. You get a
per-job report of which segments to look at — a number instead of a hunch.

---

## Configuration

**API keys.** Copy `.env.example` to `.env` (gitignored) and fill it in; Voxa loads it on
startup. Real environment variables always win. Prefer this over `--openai_api_key`, which
lands in your shell history and the process list.

**Defaults.** Put common options in a JSON file and pass `--config`. Keys are the long option
names with dashes as underscores; explicit flags override the file.

```json
{ "translator": "openai", "target_lang": "ru", "tts": "edge", "llm_batch_size": 30 }
```

A fuller one lives in [`examples/config.json`](examples/config.json):
`voxa video.mp4 --config examples/config.json`

**Logging.** `--log-format json` emits one JSON object per line for log pipelines.
`--verbose` raises the level to DEBUG and also surfaces third-party libraries.

**All options:** `voxa --help`. It is generated from the code, so unlike a README table it is
never out of date.

---

## Audio mixing

- Original audio at 5% — a faint ambience bed, ~35 dB under the dub, so the source speech is
  not intelligible (`--background-volume`; `0.0` mutes it entirely)
- Dubbed voice at 150% (`--voice-volume`)
- Combined with `amix`, which halves each input, so the mix does not clip
- Output: AAC 192 kbps, video stream copied without re-encoding

---

## Output

| File | Contents |
|------|----------|
| `<video>_dubbed_<lang>.mp4` | The dubbed video |
| `subtitles_<lang>.srt` | Translated subtitles |
| `<video>_work/` | Checkpoints, intermediate audio, `voxa.log` (removed unless `--keep-temp`) |

---

## Troubleshooting

**`❌ FFmpeg not found`** — install it and make sure it's on your PATH. Voxa checks before
doing any work rather than failing halfway through.

**The dub speaks over a music intro** — Whisper transcribes non-speech as phantom text. Voxa
drops segments with `no_speech_prob > 0.6`; lower `--no-speech-threshold` to 0.4, or use
`--whisper-backend faster`, whose built-in VAD removes non-speech at the source.

**The dub drifts out of sync** — it shouldn't; that's the point of anchored placement. Check
the `⏱️  max sync drift` line in `<video>_work/voxa.log` and open an issue with it.

**Edge TTS fails with `403 Invalid response status`** — Microsoft tightened the endpoint;
older clients are rejected. `pip install -U "edge-tts>=7.0"`.

**Piper model missing** — models are looked up in `~/.piper_models`. Download the one for your
language from the Piper releases page first.

**XTTS runs out of memory** — use CPU, or split long videos.

**`"TorchCodec is required"`** — already patched; if you still see it, `pip install --upgrade torch`.

---

## Contributing

Issues and pull requests welcome. [CONTRIBUTING.md](CONTRIBUTING.md) covers the test suite,
the golden files, how to add a TTS engine in two steps, and the dependency rules (no GPL;
engine-specific packages go in extras).

- Architecture and design decisions: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- Code of conduct: [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)
- Security issues: please report privately — [SECURITY.md](SECURITY.md)

---

## License

Voxa is released under the [MIT License](LICENSE).

**Voxa ships no model weights and vendors no third-party code**, but the engines it drives
have their own licenses — and some are stricter than Voxa's. Before using Voxa commercially,
read [NOTICE.md](NOTICE.md). The short version:

| Configuration | Commercial use |
|---|:---:|
| `--tts piper` + `--translator ollama` (fully offline) | ✅ |
| `--tts openai` + `--translator openai` (paid APIs) | ✅ |
| `--tts edge` / `--translator google` (defaults, unofficial endpoints) | ⚠️ grey area |
| `--tts xtts` (XTTS-v2 weights are CPML) | ❌ non-commercial only |

## Credits

- [OpenAI Whisper](https://github.com/openai/whisper) — speech recognition (MIT)
- [Edge-TTS](https://github.com/rany2/edge-tts) — Microsoft TTS (LGPL-3.0, unofficial endpoint)
- [Piper](https://github.com/rhasspy/piper) — offline neural TTS (MIT)
- [coqui-tts](https://github.com/idiap/coqui-ai-TTS) — maintained fork of Coqui TTS, used for XTTS

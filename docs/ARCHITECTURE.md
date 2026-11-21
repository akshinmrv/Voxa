# Voxa architecture

The dubbing itself is one module, `voxa.py`: the pipeline, the engines, the registries and the
command line. Everything else is around it:

| Part | What it is |
|---|---|
| `voxa.py` | The pipeline and the `voxa` command |
| `voxa_server.py` | `voxa serve`: a FastAPI server that runs each dub as a `voxa` subprocess, keeps their history in `.voxa_serve/`, and serves the console |
| `voxa_studio.py` | `voxa studio`: starts the server and shows the console in a pywebview window, with the taskbar progress and the close prompt |
| `voxa_engines/` | Engines with dependencies Voxa can't share (Chatterbox, VoxCPM2, Demucs), each installed in an environment of its own and driven through a worker script |
| `voxa_ui/static/` | The console, built from `web/` into the package |
| `web/` | The source of the console and of voxa.servoogle.com (Next.js) |
| `installer/` | VoxaSetup.exe (NSIS) and its tests |

Because the server only ever shells out to `voxa`, the console can't do anything the command
line can't, and the two can't drift apart. This document explains how the pipeline is
organised, why the non-obvious decisions were made, and where to put new code.

---

## The pipeline

`process_video()` runs seven steps, each checkpointed in `<video>_work/` so an interrupted
run resumes rather than restarts.

| # | Step | Key functions |
|---|------|---------------|
| 1 | Extract audio | `run_ffmpeg` |
| 2 | Denoise the **source** | `reduce_noise` |
| 3 | Transcribe | `transcribe_audio`, `_refine_bounds`, `filter_nonspeech_segments` |
| 4 | Merge into sentences | `merge_segments_into_sentences` |
| 5 | Translate → SRT | `translate_llm_batch`, `_duration_to_max_chars`, `format_timestamp` |
| 6 | Synthesize | `TTS_PROVIDERS` → `synthesize_timeline` |
| 7 | Assemble | `normalize_audio`, `run_ffmpeg` |

Step 2 denoises the *source* audio only. Synthesized speech is already clean; running
stationary noise reduction over it introduces musical-noise artifacts.

---

## Timing: why the dub does not drift

This is the part worth understanding before changing anything in step 6.

A naive dubber appends clips end to end. A clip that runs 200 ms long pushes every later clip
200 ms late, and the errors add up. Voxa instead anchors each clip to the **source** timeline.

For subtitle *i*, the slot is `[start_i, start_{i+1}]` — from this line's onset to the *next
line's* onset:

```python
trim_ms, pad_ms = _plan_anchored_block(actual_ms, start_ms, next_start_ms)
```

- The clip over-runs the slot → it is trimmed (with a fade) to fit.
- The clip is shorter → trailing silence pads the remainder.
- Either way the cursor becomes `next_start_ms` exactly.

Because the cursor is *assigned*, not *accumulated*, drift is structurally impossible. The
last segment has no next onset to protect, so it pads to its own window and may over-run.

Two supporting rules:

- **Never slow speech down** (`stretch_audio_smart(..., allow_slowdown=False)`). Speeding up
  to fit sounds fine; slowing down sounds dragged. Short clips get silence, not stretching.
- **Length-budget the translation** (`_duration_to_max_chars`). The translator is told roughly
  how many characters fit in each line's slot, so the fix happens in the text rather than in
  the tempo. Trimming is the safety net, not the plan.

`_plan_block` and `_plan_anchored_block` are pure functions. They are unit-tested *and*
exercised by the golden harness — and `_place_speech_block` calls them, rather than
re-implementing the maths, precisely so those tests protect the real code path.

---

## Two registries

Both follow the same shape: a dict of name → adapter. Adding a provider means writing one
adapter and one line. Nothing else in the codebase learns its name.

### `LLM_PROVIDERS` — translation

```python
LLM_PROVIDERS = {
    "openai":    {"chat": _openai_chat_text, "default_model": ..., "env_key": "OPENAI_API_KEY"},
    "anthropic": {"chat": _anthropic_chat_text, ...},
}
```

An adapter is `(system, user, model, want_json, api_key) -> text`. `--translator` choices are
generated from the registry.

### `TTS_PROVIDERS` — speech

```python
TTS_PROVIDERS = {
    "chatterbox": {"synthesize": _tts_chatterbox},
    "edge":       {"synthesize": _tts_edge},
    "openai":     {"synthesize": _tts_openai},
    "piper":      {"synthesize": _tts_piper},
    "voxcpm":     {"synthesize": _tts_voxcpm},
    "xtts":       {"synthesize": _tts_xtts},
}
```

An adapter is
`async (subs, args, work_dir, video_path, gate_asr, logger) -> (concat_list, temp_files)`.
It performs its own setup — model load, HTTP client, voice lookup — raises `TTSError` with a
useful message if it can't proceed, and delegates the loop to `synthesize_timeline`.
`--tts` choices are generated from the registry.

Chatterbox and VoxCPM2 pin versions of PyTorch and transformers that would break Voxa's own,
so their adapters don't import them. `voxa_engines` installs each into an environment under
`~/.voxa/engines/<name>` and starts its worker script there (`start_worker`); the adapter sends
it one line at a time and gets a WAV back. To the timeline they look like any other engine.
Demucs (`--separate`) runs the same way, before transcription.

---

## `synthesize_timeline`: the Template Method

Every engine needs the same loop: leading silence, cached synthesis, fit-to-window, anchored
placement, drift tracking, optional quality scoring. That loop lives in exactly one place.

An engine supplies only:

```python
render(i, text, final_file, target_duration) -> bool     # sync or async
on_ready(i, text, final_file, target_duration) -> score  # optional
```

`render` turns one line of text into one WAV. `on_ready` runs after synthesis and before
placement; XTTS uses it to re-roll a badly-scored take (see below).

**This is not decoration.** Each engine used to carry its own copy of the loop, and Piper's
copy silently missed both the no-slowdown fix and the anchored-placement fix — while hiding a
resume bug where cached segments were dropped from the concat list. One loop, one place to fix.

If you are writing a new engine and find yourself computing `start_ms` from a subtitle, you
are in the wrong function.

---

## Quality gate

`--quality-gate` transcribes each synthesized clip back with faster-whisper and compares it to
what it was supposed to say (`word_error_rate`), then checks clipping, near-silence and
characters-per-second. `log_quality_report` summarises the job.

Two things learned the hard way, both documented in the CLI help:

- The `tiny` gate model **false-positives on low-resource languages**. The same Azerbaijani
  audio scored 0.74 with `tiny` and 0.41 with `base`. Use `--gate-model base` there.
- XTTS is **stochastic**, so a bad take is a dice roll rather than a defect. With the gate on,
  a flagged XTTS segment is re-synthesized up to `XTTS_REGEN_ATTEMPTS` times and the best take
  (`_score_better`: passes the gate > fewer failed checks > lower WER) is kept. Scoring happens
  *before* placement, because placement trims over-runs and that would skew the round-trip.

OpenAI TTS gets one retry of its own: when a line was rendered with a style or an emotion
hint and scores badly, it is rendered once more with neutral delivery, and the better take is
kept. Edge and Piper are effectively deterministic, so re-rolling them would return the same
audio.

---

## Guarded imports

Heavy dependencies (torch, whisper, edge-tts, soundfile) are imported through `_try_import`,
which records what is missing instead of raising. `_check_runtime_deps()` refuses to run the
pipeline when a **required** one is absent; optional ones (`torchaudio`, `noisereduce`) simply
disable the feature that needs them.

The payoff: the test suite imports `voxa` and exercises all the pure logic without installing
torch. `pip install pytest numpy soundfile openai` is enough for it.

`soundfile` and `noisereduce` are guarded **separately**. They once shared a try block, so an
environment with soundfile but no noisereduce lost soundfile too — and with it every audio
path in the module.

---

## Logging

All library logging goes through `_LOG = logging.getLogger("voxa")`. The `Logger` class
configures *that* logger — handlers, level, `propagate = False` — and never touches the root
logger, so embedding Voxa in another application doesn't clobber its logging setup. Only
`--verbose` attaches handlers to root, which is what makes third-party libraries visible.

---

## Clients

`get_openai_client(api_key, base_url)` caches one client per `(api_key, base_url)` pair, not
one per process. Translation and speech can therefore target different endpoints — which is
exactly what `--openai-tts-base-url` needs to drive a self-hosted, OpenAI-compatible TTS
server while translation still goes to OpenAI.

---

## Subtitles

Voxa writes its own SRT and reads it back with `read_srt()` before synthesis. That round-trip
used to pull in `pysrt`, whose GPL-3.0 licence is incompatible with shipping an MIT project as
a bundled artifact, so it was replaced with a small SubRip parser covering the subset Voxa
writes plus the variations found in the wild (BOM, CRLF, absent index line, multi-line cues).

`Subtitle` and `SubTime` are NamedTuples exposing the same `.text` / `.start` / `.end` fields
the engines already read, so no engine code changed.

---

## Tests

| Layer | What it protects |
|-------|------------------|
| `tests/test_voxa.py` | Individual functions: parsing, timing maths, scoring, registries, adapters |
| `tests/test_golden.py` | The same functions composed, which is where cross-stage regressions hide |
| `tests/test_*_server.py`, `test_job_control.py`, `test_history.py`, ... | `voxa serve`: jobs, review, preview, stopping, history, access |
| `tests/test_studio.py` | The Studio window's process handling (the Windows Job Object is tested for real on Windows) |
| `tests/test_smoke.py`, `test_review.py`, `test_preview.py`, `test_subtitles.py` | The real FFmpeg assembly, run by CI's smoke job |
| `tests/test_e2e.py` | The console in a real browser against the real server, with the pipeline faked, plus axe on every page (`VOXA_E2E=1`) |

The golden harness runs a canonical transcript (a music intro, a segment starting before its
first word, a line closed by punctuation and one closed by a pause) through the deterministic
chain and compares every intermediate result against a recorded file. It is deliberately
engine-free: no whisper, no ffmpeg, no network, no API key.

Re-record with `UPDATE_GOLDEN=1 pytest tests/test_golden.py` and review the diff. It has
already caught a real bug: `infer_delivery` was being handed the TTS-normalised line, in which
`…` has been folded to `.`, so the trailing-off delivery hint could never fire.

Unit tests cannot hear. Anything touching synthesis, timing or mixing gets verified on a real
video before it lands — see [CONTRIBUTING.md](../CONTRIBUTING.md).

---

## Where things live

| Concern | Look for |
|---------|----------|
| CLI, argparse, preflight | `main()`, `cli()`, `_check_external_tools`, `_check_input_videos` |
| Orchestration | `process_video` |
| Transcription | `transcribe_audio`, `_refine_bounds`, `filter_nonspeech_segments` |
| Translation | `LLM_PROVIDERS`, `translate_llm_batch`, `_llm_translate_chunk` |
| Speech | `TTS_PROVIDERS`, `synthesize_timeline`, `generate_*` |
| Timeline maths | `_plan_block`, `_plan_anchored_block`, `_place_speech_block` |
| Audio | `stretch_audio_smart`, `_fit_to_window`, `normalize_audio`, `_apply_micro_fades` |
| Quality | `score_speech`, `_score_better`, `log_quality_report` |
| Infrastructure | `_try_import`, `Logger`, `StateManager`, `load_dotenv`, `run_ffmpeg` |
| Engines in their own environments | `voxa_engines.ENGINES`, `start_worker`, `voxa_engines/workers/` |
| The server | `voxa_server.py`: `_run_job`, `_run_steps`, the `/api/...` routes, `load_history` |
| The window | `voxa_studio.py`: `open_window`, `Taskbar`, `watch_jobs` |

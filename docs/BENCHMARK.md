# Speech quality benchmark

Most dubbing tools ask you to judge the output by ear. Voxa measures it: every synthesized
clip can be transcribed back with a second ASR model and compared against the text that was
supposed to be spoken. The result is a **round-trip word error rate** — 0.00 means the engine
said exactly what it was given, 0.80 means most of it came back wrong.

This is not a measure of how *pleasant* a voice sounds. It measures whether the words survive,
which is what actually breaks in a dub: a voice that does not really cover the target language
mangles it into something an ASR model — and a listener — cannot recover.

## Reproducing it

```bash
pip install faster-whisper                       # the gate ASR
python scripts/benchmark.py \
    --video web/public/demo/original.mp4 \
    --langs tr az fr ru es de \
    --engines edge \
    --whisper-model base --gate-model base
```

No API key is required for the defaults (`google` translation, `edge` speech). The runs share
one working directory, so the clip is transcribed once and only translation and synthesis are
repeated per language.

## Results

**Source:** `web/public/demo/original.mp4` — 14.7 s of English speech, 2 subtitle segments.
**Transcription:** `base` · **Gate ASR:** `base` · **Translator:** `google` · **Date:** 2026-07-18

| Language | Engine | Segments | Flagged | avg WER |
|---|---|---|---|---|
| 🇫🇷 French (`fr`) | edge | 2 | 0 | **0.04** |
| 🇷🇺 Russian (`ru`) | edge | 2 | 0 | **0.08** |
| 🇩🇪 German (`de`) | edge | 2 | 0 | **0.09** |
| 🇪🇸 Spanish (`es`) | edge | 2 | 0 | **0.11** |
| 🇹🇷 Turkish (`tr`) | edge | 2 | 0 | **0.32** |
| 🇦🇿 Azerbaijani (`az`) | edge | 2 | **1** | **0.82** |

### What this shows

The well-resourced European languages come back nearly intact (0.04–0.11). Turkish is
noticeably worse. Azerbaijani is the outlier by a wide margin, and the gate flagged half of
its segments — the same property the pipeline is designed to surface rather than hide.

That ordering is the useful signal: **the further a language sits from the engine's training
centre of gravity, the more you should measure instead of assume.**

## Limitations — read before quoting these numbers

This is a **pilot run, not an authoritative benchmark.** Specifically:

1. **The sample is two segments.** One bad word moves the average enormously. These numbers
   cannot support a confident per-language ranking.
2. **WER is content-dependent.** This clip contains a proper noun ("Venus") that several
   engines render as a loan word; a different script would produce different numbers for the
   same engine.
3. **One engine only.** Comparing `edge` against `openai` needs an API key, so it is not part
   of the default run.
4. **One take per cell.** Nothing here is averaged over repeated runs.

An earlier internal measurement recorded `az` + edge at **0.41** on a different source clip —
half of what this run reports. Both numbers are probably "correct" for their own clip, which
is exactly the point: **a WER figure without its source material attached is not a claim you
can defend.** Any published figure should state the clip, the models and the date, as the
table above does.

## Extending it

Adding a language costs one run:

```bash
python scripts/benchmark.py --video clip.mp4 --langs uz --engines edge
```

Useful directions, roughly in order of value:

- **Longer source material** — a 3–5 minute clip with 30+ segments, so a single word stops
  dominating the average.
- **Engine comparison** — `--engines edge openai` on the same clip (needs `OPENAI_API_KEY`).
- **Low-resource languages** — `az`, `ka`, `hy`, `uz`, `kk`, `sw`, `vi`. These are where the
  differences are large and where almost nobody publishes numbers.
- **Gate sensitivity** — `--gate-model tiny` vs `base` vs `small`. A weak gate model
  misreads a good voice, so the gate itself needs calibrating per language.

Contributions of measured numbers are welcome — please include the source clip (or a link to
it) alongside the table so the run can be reproduced.

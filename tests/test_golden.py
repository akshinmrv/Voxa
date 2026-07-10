"""Golden-set regression harness (C2).

Locks the deterministic, engine-free half of the pipeline against a recorded golden
output: transcription hygiene (word-onset refinement SY5, non-speech filtering SY4),
sentence merging, translation length budgets (A1), SRT timestamps, and the anchored
placement math (SY2). No whisper / ffmpeg / TTS / network / API key is needed, so this
runs everywhere — including CI.

Unit tests check each function alone; this harness checks them *composed*, which is
where cross-stage regressions actually hide.

Re-record after an intentional behaviour change, then review the diff before committing:

    UPDATE_GOLDEN=1 pytest tests/test_golden.py
"""
import json
import os
from pathlib import Path

import voxa

GOLDEN_DIR = Path(__file__).parent / "golden"
UPDATE = os.environ.get("UPDATE_GOLDEN") == "1"

# Synthetic speaking rates used to derive a dub duration from a line's length, so the
# placement math is exercised without synthesizing audio. 15 cps ≈ natural (clips fit);
# 8 cps ≈ a verbose translation that over-runs its slot and must be trimmed.
NATURAL_CPS = 15.0
VERBOSE_CPS = 8.0


def _load(name):
    return json.loads((GOLDEN_DIR / name).read_text(encoding="utf-8"))


def _check(name, actual):
    """Compare against the golden file, or re-record it when UPDATE_GOLDEN=1."""
    path = GOLDEN_DIR / name
    if UPDATE:
        path.write_text(json.dumps(actual, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    expected = json.loads(path.read_text(encoding="utf-8"))
    assert actual == expected, (
        f"golden mismatch for {name}. If this change is intentional, re-record with "
        f"UPDATE_GOLDEN=1 pytest tests/test_golden.py and review the diff."
    )


def _r(value, digits=3):
    return round(float(value), digits)


def _plans(merged, cps):
    """Anchored placement plan per block (SY2), given a synthetic dub duration."""
    plans = []
    for i, m in enumerate(merged):
        actual_ms = len(m["text"]) / cps * 1000.0
        start_ms = m["start"] * 1000.0
        if i + 1 < len(merged):
            next_start_ms = merged[i + 1]["start"] * 1000.0
            trim_ms, pad_ms = voxa._plan_anchored_block(actual_ms, start_ms, next_start_ms)
            cursor_ms = next_start_ms
        else:
            # Last block has no next onset to protect: pad to its own window, never trim.
            trim_ms = 0.0
            pad_ms, cursor_ms = voxa._plan_block(actual_ms, start_ms, m["end"] * 1000.0)
        plans.append({"trim_ms": _r(trim_ms, 1), "pad_ms": _r(pad_ms, 1),
                      "cursor_ms": _r(cursor_ms, 1)})
    return plans


def run_transcript_pipeline(raw_segments):
    """The deterministic pre-TTS chain, in the same order as process_video."""
    # SY5: tighten each segment to its first/last word onset.
    refined = [
        {
            "start": voxa._refine_bounds(s["start"], s["end"], s.get("words") or [])[0],
            "end": voxa._refine_bounds(s["start"], s["end"], s.get("words") or [])[1],
            "text": s["text"],
            "no_speech_prob": s.get("no_speech_prob", 0.0),
        }
        for s in raw_segments
    ]
    # SY4: drop what Whisper itself flags as non-speech (music/intro phantom text).
    kept = voxa.filter_nonspeech_segments(refined, threshold=0.6)
    # Merge into sentences (punctuation, >0.5s pause, or max duration).
    merged = voxa.merge_segments_into_sentences(kept, max_duration=10.0)
    # A1: per-line translation length budget so the dub fits at a natural pace.
    budgets = [voxa._duration_to_max_chars(m["end"] - m["start"]) for m in merged]
    # SRT block timing.
    srt = [f"{voxa.format_timestamp(m['start'])} --> {voxa.format_timestamp(m['end'])}"
           for m in merged]
    return {
        "kept": len(kept),
        "dropped": len(refined) - len(kept),
        "refined_starts": [_r(s["start"]) for s in refined],
        "merged": [{"text": m["text"], "start": _r(m["start"]), "end": _r(m["end"])}
                   for m in merged],
        "max_chars": budgets,
        "srt": srt,
        "plans_natural": _plans(merged, NATURAL_CPS),
        "plans_verbose": _plans(merged, VERBOSE_CPS),
    }


def run_tts_text_pipeline(lines):
    """The deterministic text preparation each TTS engine performs per subtitle line."""
    out = []
    for raw in lines:
        normalized = voxa.normalize_tts_text(raw)
        out.append({
            "raw": raw,
            "normalized": normalized,
            "chunks": voxa.split_for_tts(normalized),
            # Delivery is inferred from the RAW line: normalization folds '…' to '.'.
            "delivery": voxa._delivery_hint(0, [], raw),
        })
    return out


def test_golden_transcript_scene():
    _check("scene_intro.expected.json",
           run_transcript_pipeline(_load("scene_intro.input.json")))


def test_golden_tts_text():
    _check("tts_text.expected.json",
           run_tts_text_pipeline(_load("tts_text.input.json")))

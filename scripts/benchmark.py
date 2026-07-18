"""Reproducible speech-quality benchmark for Voxa.

Dubs one source clip into several languages with several speech engines, each run under
``--quality-gate``, and collects the round-trip word error rate the gate reports. The gate
transcribes every synthesized clip back with faster-whisper and compares it to the text that
was meant to be spoken, so a high WER means the engine did not say what it was given —
a wrong accent, a mangled loan word, a language the voice does not really cover.

Every run shares one working directory, so the source is transcribed once and only the
language-dependent stages are repeated (see the resume logic in voxa.py).

Usage::

    python scripts/benchmark.py --video clip.mp4 --langs tr az fr --engines edge
    python scripts/benchmark.py --video clip.mp4 --langs az --engines edge openai   # needs a key

Requires ``faster-whisper`` (the gate ASR) and whatever the chosen engines need. The default
engine, ``edge``, and the default translator, ``google``, need no API key.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

# "🔎 Quality report (edge): 12 segments, 1 flagged, avg WER 0.24"
REPORT_RE = re.compile(
    r"Quality report \((?P<engine>[^)]+)\): (?P<segments>\d+) segments, "
    r"(?P<flagged>\d+) flagged(?:, avg WER (?P<wer>[\d.]+))?"
)


def run_one(video: Path, lang: str, engine: str, work_dir: Path, *,
            whisper_model: str, gate_model: str, translator: str) -> dict:
    """Dub `video` into `lang` with `engine` and return the gate's numbers."""
    cmd = [
        sys.executable, str(Path(__file__).resolve().parent.parent / "voxa.py"),
        video.name,
        "--target_lang", lang,
        "--translator", translator,
        "--tts", engine,
        "--whisper_model", whisper_model,
        "--quality-gate",
        "--gate-model", gate_model,
    ]
    started = time.perf_counter()
    # voxa logs to stderr, so fold it into stdout and read one stream. Forcing UTF-8 in the
    # child keeps its emoji log lines readable on a legacy console codepage.
    proc = subprocess.run(cmd, cwd=work_dir, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          encoding="utf-8", errors="replace",
                          env={**os.environ, "PYTHONUTF8": "1"})
    elapsed = time.perf_counter() - started

    row = {"lang": lang, "engine": engine, "seconds": round(elapsed, 1),
           "segments": None, "flagged": None, "wer": None, "ok": proc.returncode == 0}
    if proc.returncode != 0:
        tail = [ln for ln in proc.stdout.splitlines() if " - ERROR - " in ln]
        row["error"] = tail[-1].split(" - ERROR - ")[-1] if tail else f"exit {proc.returncode}"
        return row

    match = None
    for line in proc.stdout.splitlines():
        found = REPORT_RE.search(line)
        if found:
            match = found          # keep the last report of the run
    if match:
        row["segments"] = int(match.group("segments"))
        row["flagged"] = int(match.group("flagged"))
        row["wer"] = float(match.group("wer")) if match.group("wer") else None
    return row


def to_markdown(rows: list[dict], meta: dict) -> str:
    lines = [
        "| Language | Engine | Segments | Flagged | **avg WER** | Time |",
        "|---|---|---|---|---|---|",
    ]
    for r in sorted(rows, key=lambda x: (x["lang"], x["engine"])):
        if not r["ok"]:
            lines.append(f"| `{r['lang']}` | {r['engine']} | — | — | **failed** | "
                         f"{r['seconds']}s |")
            continue
        wer = f"**{r['wer']:.2f}**" if r["wer"] is not None else "n/a"
        lines.append(f"| `{r['lang']}` | {r['engine']} | {r['segments']} | {r['flagged']} | "
                     f"{wer} | {r['seconds']}s |")
    lines.append("")
    lines.append(f"<sub>Source: {meta['video']} ({meta['duration']}) · "
                 f"transcription `{meta['whisper_model']}` · gate `{meta['gate_model']}` · "
                 f"translator `{meta['translator']}` · generated {meta['date']}</sub>")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video", required=True, help="source clip to dub")
    ap.add_argument("--langs", nargs="+", required=True, help="target language codes")
    ap.add_argument("--engines", nargs="+", default=["edge"], help="TTS engines to compare")
    ap.add_argument("--translator", default="google", help="translator (default: google)")
    ap.add_argument("--whisper-model", default="base", help="transcription model")
    ap.add_argument("--gate-model", default="base",
                    help="gate ASR model — use base or larger for low-resource languages")
    ap.add_argument("--work-dir", default="benchmark_work",
                    help="scratch directory (reused, so the clip is transcribed once)")
    ap.add_argument("--out", default=None, help="write the markdown table here")
    args = ap.parse_args()

    video = Path(args.video).resolve()
    if not video.exists():
        print(f"Source clip not found: {video}")
        return 1

    work_dir = Path(args.work_dir).resolve()
    work_dir.mkdir(parents=True, exist_ok=True)
    if not (work_dir / video.name).exists():
        shutil.copy2(video, work_dir / video.name)

    rows = []
    total = len(args.langs) * len(args.engines)
    for i, lang in enumerate(args.langs):
        for j, engine in enumerate(args.engines):
            n = i * len(args.engines) + j + 1
            print(f"[{n}/{total}] {lang} · {engine} …", flush=True)
            row = run_one(video, lang, engine, work_dir,
                          whisper_model=args.whisper_model, gate_model=args.gate_model,
                          translator=args.translator)
            rows.append(row)
            status = (f"WER {row['wer']}" if row["wer"] is not None
                      else row.get("error", "no gate report"))
            print(f"      → {status} ({row['seconds']}s)", flush=True)

    duration = "?"
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                              "-of", "csv=p=0", str(video)], capture_output=True, text=True)
        duration = f"{float(out.stdout.strip()):.1f}s"
    except Exception:
        pass

    table = to_markdown(rows, {
        "video": video.name, "duration": duration, "whisper_model": args.whisper_model,
        "gate_model": args.gate_model, "translator": args.translator,
        "date": time.strftime("%Y-%m-%d"),
    })
    print("\n" + table)
    if args.out:
        Path(args.out).write_text(table + "\n", encoding="utf-8")
        print(f"\nWrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Stands in for voxa.py when the console's end-to-end tests run a dub: the server starts it
with the same arguments and reads its output the same way, but nothing is transcribed,
translated or voiced. It prints the seven steps, writes the files a real run leaves where a
real run leaves them (the lines to review, the dubbed video, the captions), and fails on
purpose for Japanese, so a failed dub can be tested too."""
import argparse
import json
import shutil
import sys
import time
from pathlib import Path

STEPS = ["Extracting audio", "Denoising", "Transcribing", "Merging sentences", "Translating",
         "Synthesizing", "Assembling"]
SOURCE = ["Welcome to the test video.", "This line is spoken second.",
          "And this one closes it."]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source")
    parser.add_argument("--target_lang", default="tr")
    parser.add_argument("--output-dir", default=".")
    parser.add_argument("--preview", type=int)
    parser.add_argument("--review", action="store_true")
    parser.add_argument("--translation")
    args, _ = parser.parse_known_args()

    lang = args.target_lang
    source = Path(args.source)
    stem = source.stem + (f".preview{args.preview}s" if args.preview else "")
    out = Path(args.output_dir)
    work = out / f"{stem}_work"
    work.mkdir(parents=True, exist_ok=True)

    def step(n: int) -> None:
        print(f"[{n}/7] {STEPS[n - 1]}…", flush=True)
        time.sleep(0.25)
        print(f"[{n}/7] ✓ {STEPS[n - 1]}", flush=True)

    if args.translation:
        lines = json.loads(Path(args.translation).read_text(encoding="utf-8"))
        lines = lines["lines"] if isinstance(lines, dict) else lines
        steps = range(6, 8)
    else:
        lines = [{"start": 0.5 + 2 * i, "end": 2.2 + 2 * i, "text": f"[{lang}] {text}"}
                 for i, text in enumerate(SOURCE)]
        steps = range(1, 6) if args.review else range(1, 8)

    for n in steps:
        if lang == "ja" and n == 5:
            print("❌ Translation failed: the test asked for it to fail", flush=True)
            return 1
        step(n)
        if n == 4:
            merged = [{"start": line["start"], "end": line["end"], "text": text}
                      for line, text in zip(lines, SOURCE)]
            (work / "merged_sentences.json").write_text(json.dumps(merged), encoding="utf-8")
        if n == 5 or (args.translation and n == 6):
            (work / "translated.json").write_text(json.dumps(
                [{"start": line["start"], "end": line["end"], "text": line["text"]}
                 for line in lines], ensure_ascii=False), encoding="utf-8")

    if args.review:
        print("⏸  Stopped for review", flush=True)
        return 0
    shutil.copyfile(source, out / f"{stem}_dubbed_{lang}.mp4")
    (work / f"captions_{lang}.srt").write_text("".join(
        f"{i + 1}\n00:00:0{int(line['start'])},000 --> 00:00:0{int(line['end'])},000\n"
        f"{line['text']}\n\n" for i, line in enumerate(lines)), encoding="utf-8")
    print("✅ Done", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

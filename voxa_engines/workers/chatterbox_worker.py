"""Chatterbox worker for Voxa. It runs in Chatterbox's own environment (see voxa_engines),
so it imports nothing from Voxa, and answers one JSON request per line:

  {"cmd": "load", "device": null}
      -> {"ok": true, "sample_rate": 24000, "device": "cpu"}
  {"cmd": "speak", "text": "...", "language": "tr", "reference": "ref.wav" or null,
   "out": "line.wav", "cfg_weight": 0.0, "exaggeration": 0.5}
      -> {"ok": true, "seconds": 3.2}
  {"cmd": "quit"}
      -> {"ok": true}

A failed request answers {"ok": false, "error": "..."} and the worker keeps serving.
"""
import json
import os
import sys
import traceback


def main() -> None:
    # The protocol gets the real stdout to itself; anything the libraries print (progress
    # bars, notices) is sent to stderr instead, where it can't corrupt a reply.
    sys.stdin.reconfigure(encoding="utf-8")   # requests are UTF-8 whatever the locale
    replies = os.fdopen(os.dup(1), "w", encoding="utf-8", buffering=1)
    os.dup2(2, 1)
    sys.stdout = sys.stderr

    model = None
    for line in sys.stdin:
        if not line.strip():
            continue
        request = json.loads(line)
        command = request.get("cmd")
        try:
            if command == "load":
                import torch
                from chatterbox.mtl_tts import ChatterboxMultilingualTTS
                device = request.get("device") or ("cuda" if torch.cuda.is_available() else "cpu")
                model = ChatterboxMultilingualTTS.from_pretrained(device=device)
                reply = {"ok": True, "sample_rate": model.sr, "device": device}
            elif command == "speak":
                if model is None:
                    raise RuntimeError("load the model first")
                import soundfile as sf
                wav = model.generate(
                    request["text"],
                    language_id=request["language"],
                    audio_prompt_path=request.get("reference"),
                    cfg_weight=request.get("cfg_weight", 0.5),
                    exaggeration=request.get("exaggeration", 0.5),
                )
                samples = wav.squeeze(0).detach().cpu().numpy()
                sf.write(request["out"], samples, model.sr, subtype="PCM_16")
                reply = {"ok": True, "seconds": round(len(samples) / model.sr, 3)}
            elif command == "quit":
                replies.write(json.dumps({"ok": True}) + "\n")
                break
            else:
                raise ValueError(f"unknown command {command!r}")
        except Exception as e:
            traceback.print_exc()                 # the full story goes to the worker's log
            reply = {"ok": False, "error": f"{type(e).__name__}: {e}"}
        replies.write(json.dumps(reply) + "\n")


if __name__ == "__main__":
    main()

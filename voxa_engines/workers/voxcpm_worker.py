"""VoxCPM2 worker for Voxa. It runs in VoxCPM's own environment (see voxa_engines), so it
imports nothing from Voxa, and answers one JSON request per line:

  {"cmd": "load", "device": null}
      -> {"ok": true, "sample_rate": 48000, "device": "cpu"}
  {"cmd": "speak", "text": "...", "reference": "ref.wav" or null, "out": "line.wav"}
      -> {"ok": true, "seconds": 3.2}
  {"cmd": "quit"}
      -> {"ok": true}

VoxCPM2 reads the language from the text, so a request names none. A failed request
answers {"ok": false, "error": "..."} and the worker keeps serving.
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
                from voxcpm import VoxCPM
                device = request.get("device") or ("cuda" if torch.cuda.is_available() else "cpu")
                # torch.compile is used on CUDA only; elsewhere `optimize` would just spend
                # a warm-up generation (half a minute on a laptop CPU) on nothing.
                model = VoxCPM.from_pretrained(request.get("model") or "openbmb/VoxCPM2",
                                               load_denoiser=False, device=device,
                                               optimize=device.startswith("cuda"))
                reply = {"ok": True, "sample_rate": model.tts_model.sample_rate,
                         "device": device}
            elif command == "speak":
                if model is None:
                    raise RuntimeError("load the model first")
                import soundfile as sf
                wav = model.generate(text=request["text"],
                                     reference_wav_path=request.get("reference"))
                rate = model.tts_model.sample_rate
                sf.write(request["out"], wav, rate, subtype="PCM_16")
                reply = {"ok": True, "seconds": round(len(wav) / rate, 3)}
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

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


def guard_short_lines() -> None:
    """Chatterbox (0.1.7), once a line is said, looks for repetition among its text's tokens
    but the last five (A[..., :-5]). On a line of five tokens or fewer ("3.", "Evet.") that is
    nothing, and it raises IndexError, so such a line was never voiced. There the step goes on
    without the repetition check, still ending the line by Chatterbox's own rule for a last
    token held too long (200 ms); Voxa measures and checks the clip itself."""
    try:
        import torch
        from chatterbox.models.t3.inference.alignment_stream_analyzer import AlignmentStreamAnalyzer
    except ImportError:
        return
    step = AlignmentStreamAnalyzer.step
    if getattr(step, "voxa_guarded", False):
        return

    def guarded(self, logits, *args, **kwargs):
        try:
            return step(self, logits, *args, **kwargs)
        except IndexError:
            spoken = self.alignment
            if spoken.shape[1] > 5 or not self.complete:
                raise
            if spoken[self.completed_at:, -3:].sum(dim=0).max() >= 5:
                logits = -(2 ** 15) * torch.ones_like(logits)
                logits[..., self.eos_idx] = 2 ** 15
            self.curr_frame_pos += 1
            return logits

    guarded.voxa_guarded = True
    AlignmentStreamAnalyzer.step = guarded


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
                guard_short_lines()
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

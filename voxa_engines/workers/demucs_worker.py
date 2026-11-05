"""Demucs worker for Voxa. It runs in Demucs' own environment (see voxa_engines), so it
imports nothing from Voxa, and answers one JSON request per line:

  {"cmd": "load", "model": "htdemucs", "device": null}
      -> {"ok": true, "sample_rate": 44100, "channels": 2, "device": "cpu"}
  {"cmd": "separate", "input": "mix.wav", "background": "bg.wav", "speech": "sp.wav" or null}
      -> {"progress": 0.4} lines while it works, then {"ok": true, "seconds": 812.4}
  {"cmd": "quit"}
      -> {"ok": true}

The input is a 16-bit WAV at the model's sample rate and channel count. It is separated two
minutes at a time, so a long video needs no more memory than a short one (about 1.7 GB on a
CPU); each piece starts a little before the last one ended, and the overlap is crossfaded, so
no seam is heard. The background is every stem but the vocals: music, effects and ambience.

A failed request answers {"ok": false, "error": "..."} and the worker keeps serving.
"""
import json
import os
import sys
import traceback
import wave

CHUNK_SECONDS = 120
OVERLAP_SECONDS = 5


def _read(src, frames):
    import numpy as np
    data = np.frombuffer(src.readframes(frames), dtype="<i2").reshape(-1, src.getnchannels())
    return data.T.astype(np.float32) / 32768


def _pcm(wav):
    import numpy as np
    return (np.clip(wav, -1, 1).T * 32767).round().astype("<i2").tobytes()


def separate(split, rate, channels, request, send, chunk_seconds=CHUNK_SECONDS,
             overlap_seconds=OVERLAP_SECONDS):
    """Write the background (and, if asked, the speech) of request["input"]. `split` turns a
    [channels, frames] float32 array into {stem name: array of the same shape}."""
    import numpy as np
    chunk, overlap = int(chunk_seconds * rate), int(overlap_seconds * rate)
    with wave.open(request["input"], "rb") as src:
        if (src.getframerate(), src.getnchannels(), src.getsampwidth()) != (rate, channels, 2):
            raise ValueError(f"the input must be a 16-bit, {channels}-channel WAV at {rate} Hz")
        total = src.getnframes()
        if not total:
            raise ValueError("the input has no audio")
        paths = [request["background"]] + ([request["speech"]] if request.get("speech") else [])
        outs = [wave.open(path, "wb") for path in paths]
        try:
            for out in outs:
                out.setnchannels(channels)
                out.setsampwidth(2)
                out.setframerate(rate)
            carry = tails = None       # the overlap: the last input frames, and their output
            while True:
                fresh = _read(src, chunk if carry is None else chunk - overlap)
                piece = fresh if carry is None else np.concatenate([carry, fresh], 1)
                last = src.tell() >= total
                stems = split(piece)
                tracks = [sum(wav for name, wav in stems.items() if name != "vocals")]
                if len(outs) > 1:
                    tracks.append(stems["vocals"])
                if tails is not None:
                    fade = np.linspace(0, 1, overlap, dtype=np.float32)
                    for track, tail in zip(tracks, tails):
                        track[:, :overlap] = tail * (1 - fade) + track[:, :overlap] * fade
                if last:
                    for out, track in zip(outs, tracks):
                        out.writeframes(_pcm(track))
                    break
                for out, track in zip(outs, tracks):
                    out.writeframes(_pcm(track[:, :-overlap]))
                tails = [track[:, -overlap:].copy() for track in tracks]
                carry = piece[:, -overlap:]
                send({"progress": round(src.tell() / total, 3)})
        finally:
            for out in outs:
                out.close()
    return round(total / rate, 3)


def main() -> None:
    # The protocol gets the real stdout to itself; anything the libraries print (progress
    # bars, notices) is sent to stderr instead, where it can't corrupt a reply.
    sys.stdin.reconfigure(encoding="utf-8")   # requests are UTF-8 whatever the locale
    replies = os.fdopen(os.dup(1), "w", encoding="utf-8", buffering=1)
    os.dup2(2, 1)
    sys.stdout = sys.stderr

    def send(message):
        replies.write(json.dumps(message) + "\n")

    separator = None
    for line in sys.stdin:
        if not line.strip():
            continue
        request = json.loads(line)
        command = request.get("cmd")
        try:
            if command == "load":
                import torch
                from demucs.api import Separator
                device = request.get("device") or ("cuda" if torch.cuda.is_available() else "cpu")
                separator = Separator(model=request.get("model") or "htdemucs", device=device)
                reply = {"ok": True, "sample_rate": separator.samplerate,
                         "channels": separator.audio_channels, "device": device}
            elif command == "separate":
                if separator is None:
                    raise RuntimeError("load the model first")
                import torch

                def split(wav):
                    stems = separator.separate_tensor(torch.from_numpy(wav))[1]
                    return {name: stem.numpy() for name, stem in stems.items()}
                seconds = separate(split, separator.samplerate, separator.audio_channels,
                                   request, send)
                reply = {"ok": True, "seconds": seconds}
            elif command == "quit":
                send({"ok": True})
                break
            else:
                raise ValueError(f"unknown command {command!r}")
        except Exception as e:
            traceback.print_exc()                 # the full story goes to the worker's log
            reply = {"ok": False, "error": f"{type(e).__name__}: {e}"}
        send(reply)


if __name__ == "__main__":
    main()

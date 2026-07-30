"""Smoke tests that run the *real* ffmpeg assembly, not a stub.

The unit and golden suites are deliberately engine-free, so ffmpeg's own behaviour — the final
mix in particular — is never exercised there; that is exactly where the "final line truncated"
regression hid. These run the real thing on tiny synthetic clips (no network, no models, no keys)
and are skipped when ffmpeg is absent, so the default lean CI test job is unaffected. A dedicated
CI job installs ffmpeg and runs them.
"""
import shutil
import subprocess

import pytest

import voxa

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")


def _run(cmd):
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)


def _audio_seconds(path) -> float:
    """Audio duration by decoding (the mp4 aac stream duration tag is unreliable)."""
    wav = f"{path}.probe.wav"
    _run(["ffmpeg", "-y", "-i", str(path), "-vn", "-acodec", "pcm_s16le", wav])
    out = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                   "-of", "default=nw=1:nk=1", wav]).decode().strip()
    return float(out)


def test_assemble_final_video_produces_valid_output(tmp_path):
    src = tmp_path / "src.mp4"
    _run(["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=320x240:d=3",
          "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
          "-c:v", "libx264", "-c:a", "aac", "-pix_fmt", "yuv420p", str(src)])
    vo = tmp_path / "vo.wav"
    _run(["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=330:duration=3",
          "-ar", "22050", "-ac", "1", str(vo)])
    out = tmp_path / "out.mp4"
    voxa._assemble_final_video(str(src), str(vo), str(out), 0.3, 1.0)
    assert out.exists()
    streams = subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type",
         "-of", "csv=p=0", str(out)]).decode()
    assert "video" in streams and "audio" in streams


def test_assemble_does_not_truncate_a_long_final_line(tmp_path):
    # A source with 6s of video but only 4s of audio (audio ends before the video does).
    src = tmp_path / "src.mp4"
    _run(["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=320x240:d=6",
          "-f", "lavfi", "-i", "sine=frequency=440:duration=4",
          "-c:v", "libx264", "-c:a", "aac", "-pix_fmt", "yuv420p", str(src)])
    # A voiceover that runs to 5.5s — past the 4s source audio, as a breathing final line can.
    vo = tmp_path / "vo.wav"
    _run(["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=330:duration=5.5",
          "-ar", "22050", "-ac", "1", str(vo)])
    out = tmp_path / "out.mp4"
    voxa._assemble_final_video(str(src), str(vo), str(out), 0.3, 1.0)
    # The dubbed track must not be clipped to the 4s source audio (duration=first would do that).
    assert _audio_seconds(out) >= 5.4

"""Shared test setup.

Voxa asks PyPI once a day whether a newer version is out (voxa.latest_version). No test may
do that for real or touch the developer's ~/.voxa/update.json: every test gets an empty cache
in its own tmp dir and a PyPI that can't be reached. Tests of the update check give PyPI an
answer themselves.

The tests that run the pipeline end to end (test_review.py, test_preview.py) share a stand-in
speech engine (`speech`) and a Voxa without the packages they don't use (`lean_voxa`).
"""
import shutil
import sys

import pytest


@pytest.fixture(autouse=True)
def _no_pypi(monkeypatch, tmp_path):
    voxa = sys.modules.get("voxa")
    if voxa is None:
        return

    def unreachable(timeout):
        raise OSError("tests don't reach PyPI")

    monkeypatch.setattr(voxa, "_ask_pypi", unreachable)
    monkeypatch.setattr(voxa, "_update_cache", lambda: tmp_path / ".voxa" / "update.json")
    monkeypatch.delenv("VOXA_NO_UPDATE_CHECK", raising=False)


@pytest.fixture(autouse=True)
def _keep_voxa_logging(monkeypatch):
    """voxa.main() points Voxa's logger at the run's log file and stops it propagating. Put it
    back afterwards, or later tests' caplog no longer hears it."""
    voxa = sys.modules.get("voxa")
    if voxa is None:
        yield
        return
    log = voxa._LOG
    monkeypatch.setattr(log, "handlers", list(log.handlers))
    monkeypatch.setattr(log, "propagate", log.propagate)
    monkeypatch.setattr(log, "level", log.level)
    yield
    for handler in log.handlers:        # the run's, before monkeypatch restores the list
        handler.close()


@pytest.fixture
def lean_voxa(monkeypatch):
    """Voxa without the packages a run from given subtitles and lines doesn't use (Whisper,
    torch, the translators, Edge), as CI's test jobs don't install them; no API keys."""
    import voxa
    for key in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(voxa, "_MISSING_DEPS", [])
    for module in ("whisper", "torch", "edge_tts", "GoogleTranslator", "requests", "nr"):
        monkeypatch.setattr(voxa, module, None)
    monkeypatch.setattr(voxa, "tqdm", voxa._NoProgress)
    return voxa


@pytest.fixture
def speech(monkeypatch):
    """A speech engine ("fake") that hums, quickly, for as long as its line would take to say
    (14 characters a second, 0.4 s at least), and records what it was given. Like Edge, it
    keeps what it said (fake_raw_<i>.wav) and reuses it when it's there. It hums rather than
    staying silent: a silent or too short clip fails the check every clip passes."""
    import numpy as np
    import soundfile as sf

    import voxa
    said = []

    async def _tts_fake(subs, args, work_dir, video_path, gate_asr, logger):
        concat_list, temp_files = [], []

        def render(i, text, final_file, target_duration):
            raw = work_dir / f"fake_raw_{i}.wav"
            if not raw.exists():
                said.append(text)
                rate = 22050
                seconds = max(0.4, len(text) / 14)
                hum = 0.3 * np.sin(2 * np.pi * 220 * np.arange(int(seconds * rate)) / rate)
                sf.write(str(raw), hum.astype("float32"), rate, subtype="PCM_16")
            shutil.copyfile(raw, final_file)
            return True

        await voxa.synthesize_timeline(
            subs, engine="fake", prefix="fake", sample_rate=22050, work_dir=work_dir,
            concat_list=concat_list, temp_files=temp_files, render=render,
            text_of=lambda s: s.text.strip(), desc="Fake")
        return concat_list, temp_files

    monkeypatch.setitem(voxa.TTS_PROVIDERS, "fake", {"synthesize": _tts_fake})
    return said

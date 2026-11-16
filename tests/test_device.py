"""
Where the models run (--device): "auto" stays CUDA-or-CPU, Apple's GPU (MPS) only when asked
for, and every model that tries it falls back to the CPU when it fails there.

No Mac runs these, and GitHub's macOS runners have no usable GPU, so torch, Whisper, pyannote,
Coqui and the engines' workers are stand-ins: the tests check what Voxa asks of them and what
it does when they fail, not that MPS itself works.

Run:  pytest -q tests/test_device.py
"""
import logging
import sys
from types import ModuleType, SimpleNamespace

import pytest

import voxa


class FakeTorch:
    """torch as far as choosing a device goes."""

    def __init__(self, cuda=False, mps=False, allocates=True):
        self.cuda = SimpleNamespace(is_available=lambda: cuda)
        self.backends = SimpleNamespace(mps=SimpleNamespace(is_available=lambda: mps))
        self.allocates = allocates

    def zeros(self, n, device):
        if device == "mps" and not self.allocates:
            raise RuntimeError("MPS backend out of memory")
        return [0] * n

    @staticmethod
    def device(name):
        return name

    @staticmethod
    def load(*args, **kwargs):          # what _allow_unsafe_torch_load wraps
        return None


@pytest.fixture
def machine(monkeypatch):
    def use(**kw):
        monkeypatch.setattr(voxa, "torch", FakeTorch(**kw))
    return use


# ── choosing ─────────────────────────────────────────────
def test_auto_is_cuda_or_the_cpu_never_apples_gpu(machine):
    machine(cuda=True)
    assert voxa.pick_device("auto") == "cuda"
    machine(mps=True)
    assert voxa.pick_device("auto") == "cpu"            # experimental: only when asked
    assert voxa.pick_device("cpu") == "cpu"


def test_apples_gpu_when_asked_and_usable(machine, caplog):
    machine(mps=True)
    assert voxa.pick_device("mps") == "mps"
    # GitHub's macOS runners: torch says yes, and can't put two numbers on it.
    machine(mps=True, allocates=False)
    with caplog.at_level(logging.WARNING):
        assert voxa.pick_device("mps") == "cpu"
    assert "Apple's GPU isn't usable here" in caplog.text
    machine(mps=False)
    assert voxa.pick_device("mps") == "cpu"


def test_cuda_asked_for_without_one(machine, caplog):
    machine(cuda=False)
    with caplog.at_level(logging.WARNING):
        assert voxa.pick_device("cuda") == "cpu"
    assert "no CUDA GPU here" in caplog.text


def test_without_torch_its_the_cpu(monkeypatch):
    monkeypatch.setattr(voxa, "torch", None)
    assert voxa.pick_device("mps") == "cpu" and not voxa.mps_usable()


# ── Whisper ──────────────────────────────────────────────
class FakeWhisperModel:
    def __init__(self):
        self._buffers = {"alignment_heads": "sparse heads"}
        self.device = "cpu"

    def to(self, device):
        # MPS can't hold a sparse tensor: the buffer must be gone before the model moves.
        if device == "mps":
            assert "alignment_heads" not in self._buffers
        self.device = device
        return self


def test_whisper_moves_to_apples_gpu_without_its_sparse_buffer(monkeypatch):
    loads = []

    def load_model(name, device):
        loads.append(device)
        return FakeWhisperModel()

    monkeypatch.setattr(voxa, "whisper", SimpleNamespace(load_model=load_model))
    model = voxa._load_whisper("base", "mps")
    assert loads == ["cpu"] and model.device == "mps"
    assert model.alignment_heads == "sparse heads"      # kept, for word timing
    voxa._load_whisper("base", "cuda")
    assert loads[-1] == "cuda"


def test_the_sparse_heads_stay_a_plain_attribute_a_move_leaves_alone():
    torch = pytest.importorskip("torch")
    model = torch.nn.Module()
    model.register_buffer("alignment_heads", torch.eye(2).to_sparse(), persistent=False)
    heads = model._buffers.pop("alignment_heads")
    model.alignment_heads = heads
    assert "alignment_heads" not in dict(model.named_buffers())
    model.to("cpu")
    assert model.alignment_heads.indices().T.tolist() == [[0, 0], [1, 1]]


def test_transcription_falls_back_to_the_cpu(caplog):
    tried = []

    def transcribe(device):
        tried.append(device)
        if device == "mps":
            raise NotImplementedError("aten::_sparse_coo_tensor on SparseMPS")
        return [{"start": 0, "end": 1, "text": "hi"}], "en"

    with caplog.at_level(logging.WARNING):
        assert voxa.transcribe_on("mps", transcribe, logging.getLogger("t"))[1] == "en"
    assert tried == ["mps", "cpu"] and "transcribing on the CPU instead" in caplog.text
    tried.clear()
    with pytest.raises(RuntimeError):                    # elsewhere a failure is a failure
        voxa.transcribe_on("cuda", lambda d: (_ for _ in ()).throw(RuntimeError("x")),
                           logging.getLogger("t"))


def test_faster_whisper_stays_on_the_cpu(monkeypatch):
    made = {}

    class WhisperModel:
        def __init__(self, name, device, compute_type):
            made.update(device=device, compute_type=compute_type)

        def transcribe(self, path, **kw):
            return iter([]), SimpleNamespace(language="en")

    monkeypatch.setitem(sys.modules, "faster_whisper", SimpleNamespace(WhisperModel=WhisperModel))
    voxa.transcribe_audio("a.wav", "base", "faster", "mps")
    assert made == {"device": "cpu", "compute_type": "int8"}


# ── XTTS, diarization, the engines ───────────────────────
def test_xtts_never_goes_to_apples_gpu(machine, monkeypatch):
    machine(cuda=True, mps=True)
    moved = []

    class TTS:
        def __init__(self, name):
            pass

        def to(self, device):
            moved.append(device)
            return self

    api = ModuleType("TTS.api")
    api.TTS = TTS
    monkeypatch.setitem(sys.modules, "TTS", ModuleType("TTS"))
    monkeypatch.setitem(sys.modules, "TTS.api", api)
    voxa.load_xtts_model("mps")
    voxa.load_xtts_model("cpu")
    voxa.load_xtts_model("auto")
    assert moved == ["cpu", "cpu", "cuda"]


def test_diarization_falls_back_to_the_cpu(machine, monkeypatch, caplog):
    machine(mps=True)
    moves = []

    class Annotation:
        def itertracks(self, yield_label):
            yield SimpleNamespace(start=0.0, end=2.0), None, "SPEAKER_00"

    class Pipeline:
        device = "cpu"

        @classmethod
        def from_pretrained(cls, name, token):
            return cls()

        def to(self, device):
            moves.append(device)
            self.device = device

        def __call__(self, path, **opts):
            if self.device == "mps":
                raise RuntimeError("not implemented for MPS")
            return Annotation()

    audio = ModuleType("pyannote.audio")
    audio.Pipeline = Pipeline
    monkeypatch.setitem(sys.modules, "pyannote", ModuleType("pyannote"))
    monkeypatch.setitem(sys.modules, "pyannote.audio", audio)
    with caplog.at_level(logging.WARNING):
        out = voxa.diarize_segments("a.wav", [{"start": 0.0, "end": 2.0, "text": "hi"}],
                                    num_speakers=1, hf_token="hf_x", device="mps")
    assert moves == ["mps", "cpu"] and out[0]["speaker"] == "SPEAKER_00"
    assert "diarizing on the CPU instead" in caplog.text


def test_engines_are_asked_for_the_device_they_run_on(machine):
    machine(mps=True)
    args = SimpleNamespace(device="mps")
    assert voxa.engine_device(args, runs_on_mps=True) == "mps"
    assert voxa.engine_device(args, runs_on_mps=False) == "cpu"
    assert voxa.engine_device(SimpleNamespace(device="auto"), runs_on_mps=True) is None
    assert voxa.engine_device(SimpleNamespace(device="cpu"), runs_on_mps=True) == "cpu"
    machine(mps=True, allocates=False)
    assert voxa.engine_device(args, runs_on_mps=True) == "cpu"


@pytest.fixture
def workers(monkeypatch):
    """Engine workers that won't load, or won't separate, on Apple's GPU."""
    import voxa_engines
    log = []

    class Worker:
        def __init__(self, engine_id, log_path=None):
            self.engine_id = engine_id
            self.device = None

        def start(self, device=None):
            log.append(("start", self.engine_id, device))
            if device == "mps" and self.engine_id == "chatterbox":
                raise voxa_engines.EngineError("aten::something isn't on MPS")
            self.device = device or "cpu"
            return {"device": self.device, "sample_rate": 44100, "channels": 2}

        def request(self, on_progress=None, **payload):
            log.append((payload["cmd"], self.engine_id, self.device))
            if self.device == "mps":
                raise voxa_engines.EngineError("FFT isn't on MPS")
            return {"ok": True}

        def close(self):
            log.append(("close", self.engine_id, self.device))

    monkeypatch.setattr(voxa_engines, "Worker", Worker)
    monkeypatch.setattr(voxa_engines, "get", lambda e: SimpleNamespace(label=e.capitalize()))
    return log


def test_an_engine_that_wont_load_on_apples_gpu_starts_on_the_cpu(workers, tmp_path, caplog):
    with caplog.at_level(logging.WARNING):
        worker, info = voxa.start_worker("chatterbox", tmp_path / "w.log", "mps",
                                         logging.getLogger("t"))
    assert info["device"] == "cpu"
    assert workers == [("start", "chatterbox", "mps"), ("close", "chatterbox", None),
                       ("start", "chatterbox", "cpu")]
    assert "Chatterbox wouldn't load on Apple's GPU" in caplog.text


def test_an_engine_that_wont_load_elsewhere_says_so(workers, monkeypatch, tmp_path):
    import voxa_engines

    def fail(self, device=None):
        raise voxa_engines.EngineError("not installed right")

    monkeypatch.setattr(voxa_engines.Worker, "start", fail)
    with pytest.raises(voxa_engines.EngineError, match="not installed right"):
        voxa.start_worker("chatterbox", tmp_path / "w.log", None, logging.getLogger("t"))
    assert [e for e in workers if e[0] == "start"] == []          # no second try


def test_a_separation_that_fails_on_apples_gpu_runs_on_the_cpu(workers, monkeypatch,
                                                             tmp_path, caplog):
    monkeypatch.setattr(voxa, "run_ffmpeg", lambda *a, **kw: None)
    monkeypatch.setattr(voxa, "_free_ollama", lambda *a, **kw: None)
    monkeypatch.setattr(voxa, "tqdm", voxa._NoProgress)      # as in CI, without tqdm
    with caplog.at_level(logging.WARNING):
        voxa.separate_audio(tmp_path / "v.mp4", tmp_path / "bg.wav", tmp_path / "sp.wav",
                            tmp_path, logging.getLogger("t"), device="mps")
    assert [e for e in workers if e[0] == "separate"] == [("separate", "demucs", "mps"),
                                                         ("separate", "demucs", "cpu")]
    assert "separating on the CPU instead" in caplog.text


def test_the_progress_stand_in_works_as_tqdm_is_used():
    # Without tqdm, a `with tqdm(total=100) as bar` must work as `for x in tqdm(...)` does.
    with voxa._NoProgress(total=100, desc="x") as bar:
        bar.update(40)
        bar.update(100 - bar.n)
    assert bar.n == 100
    assert list(voxa._NoProgress([1, 2])) == [1, 2]


# ── voxa doctor, and the console ─────────────────────────
def test_doctor_points_a_mac_at_its_gpu(machine, monkeypatch):
    machine(mps=True)
    monkeypatch.setattr(voxa.sys, "platform", "darwin")
    monkeypatch.setattr(voxa.shutil, "which", lambda name: None)
    monkeypatch.setattr(voxa, "_ollama_models", lambda timeout=2.0: None)
    gpu = next(c for c in voxa.doctor_checks() if c.name == "GPU")
    assert gpu.status == "warn" and "Apple's GPU (MPS) is here" in gpu.detail
    assert "--device mps" in gpu.fix


def test_the_console_setting_reaches_voxa():
    pytest.importorskip("fastapi")
    import voxa_server as srv
    assert srv.advanced_timing_args({"advanced": {"device": "mps"}}) == ["--device", "mps"]
    assert srv.advanced_timing_args({"advanced": {"device": "auto"}}) == []
    assert srv.advanced_timing_args({"advanced": {"device": None}}) == []


def test_the_console_refuses_a_device_it_doesnt_know(tmp_path, monkeypatch):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    import voxa_server as srv
    monkeypatch.setattr(srv, "SETTINGS_FILE", tmp_path / "settings.json")
    srv.app.dependency_overrides[srv.require_local] = lambda: None
    try:
        client = TestClient(srv.app)
        assert client.put("/api/settings",
                          json={"advanced": {"device": "tpu"}}).status_code == 422
        r = client.put("/api/settings", json={"advanced": {"device": "mps"}})
        assert r.status_code == 200 and r.json()["advanced"]["device"] == "mps"
    finally:
        srv.app.dependency_overrides.pop(srv.require_local, None)

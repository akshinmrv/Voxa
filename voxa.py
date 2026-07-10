#!/usr/bin/env python3
"""
Voxa v1.0 — Professional Video Translation and Dubbing

Pipeline: extract audio -> Whisper transcription -> translate -> TTS -> mux.
Translation: Google, Ollama, or an LLM provider (OpenAI / Anthropic) with
context-aware batch translation. TTS: Edge (online), OpenAI (instructable),
Piper (offline), or XTTS (voice cloning). Transcription backends: openai-whisper
or faster-whisper.
"""
import sys, os, asyncio, subprocess, argparse, json, re, time, logging, shutil, functools, random, contextlib, inspect
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, NamedTuple, Optional, Tuple
from datetime import timedelta, datetime

# Heavy / third-party dependencies are guarded so the module can still be imported
# (e.g. for unit tests) when they are not installed. They are required to actually
# run the pipeline — this is enforced in main() via _check_runtime_deps().
_MISSING_DEPS: List[str] = []


def _try_import(name, attr=None, optional: bool = False):
    """Import a module (or attribute). Returns it, or None when absent.

    Missing *required* modules are recorded so _check_runtime_deps() can refuse to run.
    Optional ones belong to an extra (e.g. torchaudio, only used by the XTTS path) and
    their absence must not stop a default install from working.
    """
    try:
        mod = __import__(name)
        return getattr(mod, attr) if attr else mod
    except ImportError:
        if not optional:
            _MISSING_DEPS.append(name)
        return None


np = _try_import("numpy")
requests = _try_import("requests")
whisper = _try_import("whisper")
edge_tts = _try_import("edge_tts")
torch = _try_import("torch")                        # pulled in by openai-whisper
torchaudio = _try_import("torchaudio", optional=True)   # only the XTTS path patches it
try:
    import soundfile as sf
    import noisereduce as nr
except ImportError:
    sf = nr = None
    _MISSING_DEPS.append("soundfile/noisereduce")
try:
    from deep_translator import GoogleTranslator
except ImportError:
    GoogleTranslator = None
    _MISSING_DEPS.append("deep-translator")
try:
    from tqdm import tqdm
except ImportError:
    _MISSING_DEPS.append("tqdm")
    def tqdm(iterable=None, **kwargs):   # no-op fallback keeps loops working
        return iterable if iterable is not None else []

# ─────────────────────────────────────────────
#  OpenAI translation config
# ─────────────────────────────────────────────
# Default models — easily swappable. Override at runtime with --<provider>_model.
DEFAULT_OPENAI_MODEL = "gpt-5"
DEFAULT_ANTHROPIC_MODEL = "claude-opus-4-8"

# Language map for Ollama
LANG_MAP = {
    'af': 'Afrikaans', 'ar': 'Arabic', 'az': 'Azerbaijani', 'be': 'Belarusian',
    'bg': 'Bulgarian', 'bn': 'Bengali', 'bs': 'Bosnian', 'ca': 'Catalan',
    'cs': 'Czech', 'cy': 'Welsh', 'da': 'Danish', 'de': 'German',
    'el': 'Greek', 'en': 'English', 'eo': 'Esperanto', 'es': 'Spanish',
    'et': 'Estonian', 'eu': 'Basque', 'fa': 'Persian', 'fi': 'Finnish',
    'fr': 'French', 'gl': 'Galician', 'gu': 'Gujarati', 'he': 'Hebrew',
    'hi': 'Hindi', 'hr': 'Croatian', 'hu': 'Hungarian', 'hy': 'Armenian',
    'id': 'Indonesian', 'is': 'Icelandic', 'it': 'Italian', 'ja': 'Japanese',
    'ka': 'Georgian', 'kk': 'Kazakh', 'km': 'Khmer', 'kn': 'Kannada',
    'ko': 'Korean', 'ky': 'Kyrgyz', 'la': 'Latin', 'lo': 'Lao',
    'lt': 'Lithuanian', 'lv': 'Latvian', 'mk': 'Macedonian', 'ml': 'Malayalam',
    'mn': 'Mongolian', 'mr': 'Marathi', 'ms': 'Malay', 'mt': 'Maltese',
    'my': 'Burmese', 'ne': 'Nepali', 'nl': 'Dutch', 'no': 'Norwegian',
    'pa': 'Punjabi', 'pl': 'Polish', 'pt': 'Portuguese', 'ro': 'Romanian',
    'ru': 'Russian', 'si': 'Sinhala', 'sk': 'Slovak', 'sl': 'Slovenian',
    'sq': 'Albanian', 'sr': 'Serbian', 'sv': 'Swedish', 'sw': 'Swahili',
    'ta': 'Tamil', 'te': 'Telugu', 'th': 'Thai', 'tl': 'Tagalog',
    'tr': 'Turkish', 'uk': 'Ukrainian', 'ur': 'Urdu', 'uz': 'Uzbek',
    'vi': 'Vietnamese', 'zh': 'Chinese'
}

# XTTS supported languages
XTTS_SUPPORTED_LANGS = {
    'en', 'es', 'fr', 'de', 'it', 'pt', 'pl', 'tr', 'ru', 'nl',
    'cs', 'ar', 'zh', 'hu', 'ko', 'ja', 'hi'
}

# Piper voice models mapping
PIPER_VOICES = {
    'ru': ('ru_RU', 'ruslan', 'medium'),
    'en': ('en_US', 'lessac', 'medium'),
    'es': ('es_ES', 'davefx', 'medium'),
    'fr': ('fr_FR', 'siwis', 'medium'),
    'de': ('de_DE', 'thorsten', 'medium'),
    'it': ('it_IT', 'riccardo', 'x_low'),
    'pt': ('pt_BR', 'edresson', 'low'),
    'pl': ('pl_PL', 'darkman', 'medium'),
    'uk': ('uk_UA', 'ukrainian_tts', 'medium'),
    'zh': ('zh_CN', 'huayan', 'x_low'),
    'ja': ('ja_JP', 'hikari', 'medium'),
    'ko': ('ko_KR', 'kss', 'medium'),
    'nl': ('nl_NL', 'rdh', 'medium'),
    'tr': ('tr_TR', 'dfki', 'medium'),
    'vi': ('vi_VN', 'vivos', 'x_low'),
}

EMOTION_STYLES = ['angry', 'cheerful', 'excited', 'friendly', 'hopeful', 'sad',
                  'shouting', 'terrified', 'unfriendly', 'whispering']

def forced_load(uri, **kwargs):
    """Fixed audio loading with proper format handling"""
    data, samplerate = sf.read(uri, dtype='float32')
    tensor = torch.from_numpy(data).float()
    if tensor.ndim == 1:
        tensor = tensor.unsqueeze(0)
    else:
        tensor = tensor.transpose(0, 1)
    return tensor, samplerate


def _apply_runtime_patches():
    """Apply library patches needed at runtime (safe no-op when deps are absent)."""
    if torchaudio is not None:
        torchaudio.load = forced_load
    os.environ["COQUI_TOS_AGREED"] = "1"


@contextlib.contextmanager
def _allow_unsafe_torch_load():
    """Temporarily allow full (weights_only=False) torch.load for TRUSTED local model
    checkpoints (XTTS / Whisper) that store non-tensor objects, then restore the safe
    default. This replaces the former process-wide patch, which left arbitrary-pickle
    deserialization enabled for every torch.load in the process."""
    if torch is None:
        yield
        return
    original = torch.load
    torch.load = functools.partial(torch.load, weights_only=False)
    try:
        yield
    finally:
        torch.load = original


# Library-level logging goes to this named logger. Voxa never configures the root
# logger, so importing it (or embedding it in another app) leaves that app's
# logging configuration untouched.
_LOG = logging.getLogger("voxa")


def _check_runtime_deps() -> bool:
    """Return True if all runtime dependencies are importable, else print guidance."""
    if _MISSING_DEPS:
        print("❌ Missing required packages: " + ", ".join(_MISSING_DEPS) +
              "\n   Install them first:  pip install -r requirements.txt")
        return False
    return True


FFMPEG_INSTALL_HINT = (
    "   Install FFmpeg and make sure it is on your PATH:\n"
    "     Ubuntu/Debian : sudo apt install ffmpeg\n"
    "     Fedora/RHEL   : sudo dnf install ffmpeg\n"
    "     macOS         : brew install ffmpeg\n"
    "     Windows       : winget install Gyan.FFmpeg"
)


def _check_external_tools() -> bool:
    """Verify the external binaries the pipeline shells out to. Checked before any work
    so a missing FFmpeg fails with an actionable message instead of an exit-code dump."""
    if shutil.which("ffmpeg") is None:
        print("❌ FFmpeg not found.\n" + FFMPEG_INSTALL_HINT)
        return False
    return True


def _check_input_videos(videos: List[str]) -> bool:
    """Verify every input path exists, is a file and is non-empty, before creating a
    workspace or loading any model."""
    ok = True
    for v in videos:
        p = Path(v)
        if not p.exists():
            print(f"❌ Input video not found: {v}")
            ok = False
        elif not p.is_file():
            print(f"❌ Input path is not a file: {v}")
            ok = False
        elif p.stat().st_size == 0:
            print(f"❌ Input video is empty: {v}")
            ok = False
    return ok


class FFmpegError(RuntimeError):
    """An ffmpeg invocation failed. Carries the tail of ffmpeg's own stderr, which is
    almost always the only useful part of the diagnosis."""


def run_ffmpeg(cmd: List[str], what: str, *, stderr_lines: int = 5) -> None:
    """Run ffmpeg, and on failure raise FFmpegError quoting what ffmpeg actually said.
    The bare `check=True` this replaces discarded stderr, leaving users with nothing but
    a numeric exit status. `-hide_banner` keeps the build blurb out of the diagnosis and
    `-nostdin` stops ffmpeg from swallowing the terminal's input."""
    if cmd and cmd[0] == "ffmpeg":
        cmd = [cmd[0], "-hide_banner", "-nostdin", *cmd[1:]]
    proc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        tail = [ln for ln in (proc.stderr or "").strip().splitlines() if ln.strip()]
        detail = "\n".join(f"   {ln}" for ln in tail[-stderr_lines:]) or "   (no stderr output)"
        raise FFmpegError(f"{what} failed (ffmpeg exit {proc.returncode}):\n{detail}")


def load_dotenv(path: str = ".env") -> int:
    """Minimal, zero-dependency .env loader. Sets os.environ for each `KEY=VALUE`
    line whose key isn't already set (existing env vars win). Returns the count loaded."""
    p = Path(path)
    if not p.exists():
        return 0
    loaded = 0
    try:
        for raw in p.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            if key.startswith("export "):
                key = key[len("export "):].strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val
                loaded += 1
    except Exception as e:
        _LOG.warning(f"Failed to read {path}: {e}")
    return loaded


def load_config_defaults(path: str) -> Dict:
    """Load a JSON config file of default option values (argparse dest names, e.g.
    {"translator": "openai", "target_lang": "ru"}). Returns {} on missing/invalid."""
    p = Path(path)
    if not p.exists():
        _LOG.warning(f"Config file not found: {path}")
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception as e:
        _LOG.warning(f"Failed to parse config {path}: {e}")
        return {}


def _has_content(path: Path, min_bytes: int = 1) -> bool:
    """True if the file exists and is at least min_bytes. Treats a stale 0-byte
    artifact (e.g. left by a failed run) as absent so it gets regenerated."""
    try:
        return path.exists() and path.stat().st_size >= min_bytes
    except OSError:
        return False


_TTS_WS_RE = re.compile(r"\s+")


def normalize_tts_text(text: str) -> str:
    """Light, engine-agnostic cleanup before synthesis: flatten newlines, collapse
    whitespace, fold typographic quotes/dashes/ellipsis to speakable equivalents, and
    guarantee terminal punctuation. XTTS in particular drags or hallucinates on text
    with no sentence end, so this measurably stabilizes delivery."""
    if not text:
        return ""
    t = text.replace("\n", " ").replace("\r", " ")
    for a, b in (("“", '"'), ("”", '"'), ("‘", "'"), ("’", "'"),
                 ("—", ", "), ("–", ", "), ("…", ".")):
        t = t.replace(a, b)
    t = _TTS_WS_RE.sub(" ", t).strip()
    if not t:
        return ""
    if t[-1] not in ".!?,:;":
        t += "."
    return t


def split_for_tts(text: str, max_chars: int = 220) -> List[str]:
    """Split text into synthesis chunks no longer than ~max_chars, preferring sentence
    then clause boundaries. Keeps XTTS-class models out of their long-input failure mode
    (slowdown / vowel drag / truncation on long, unpunctuated inputs)."""
    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]
    chunks, cur = [], ""
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        parts = re.split(r"(?<=[,;:])\s+", sentence) if len(sentence) > max_chars else [sentence]
        for p in parts:
            if not p:
                continue
            if cur and len(cur) + 1 + len(p) > max_chars:
                chunks.append(cur.strip())
                cur = p
            else:
                cur = (cur + " " + p).strip() if cur else p
    if cur.strip():
        chunks.append(cur.strip())
    # Hard-wrap any chunk with no punctuation to break on.
    out: List[str] = []
    for c in chunks:
        while len(c) > max_chars:
            cut = c.rfind(" ", 0, max_chars)
            cut = cut if cut > 0 else max_chars
            out.append(c[:cut].strip())
            c = c[cut:].strip()
        if c:
            out.append(c)
    return out


# ─────────────────────────────────────────────
#  XTTS v2 — voice cloning
# ─────────────────────────────────────────────

def load_xtts_model():
    """Load XTTS v2 model (downloaded automatically on first run)"""
    try:
        from TTS.api import TTS
        _LOG.info("🔄 Loading XTTS v2 model (first run may take a while)...")
        device = "cuda" if torch.cuda.is_available() else "cpu"
        # XTTS checkpoints store config objects, so they need weights_only=False —
        # scoped to this trusted local load only (see _allow_unsafe_torch_load).
        with _allow_unsafe_torch_load():
            tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)
        _LOG.info(f"✓ XTTS v2 loaded on {device.upper()}")
        return tts
    except ImportError:
        _LOG.error("❌ Coqui TTS not found. Install with: pip install 'voxa[xtts]'")
        return None
    except Exception as e:
        _LOG.error(f"❌ Failed to load XTTS model: {e}")
        return None


def _voice_sample_filter() -> str:
    """ffmpeg filter chain for cloning-reference hygiene: high-pass out rumble/hum,
    trim silences to maximize speech content, and loudness-normalize for a consistent
    conditioning signal."""
    return ("highpass=f=80,"
            "silenceremove=start_periods=1:start_silence=0.1:start_threshold=-38dB:"
            "stop_periods=-1:stop_silence=0.35:stop_threshold=-38dB,"
            "loudnorm=I=-20:TP=-2:LRA=11")


def extract_voice_sample(video_path: str, output_wav: str,
                         duration: float = 18.0, skip_start: float = 1.0) -> bool:
    """Extract a *cleaned* reference clip for voice cloning. A clean, consistent
    reference is the single biggest lever on cloned-voice quality — a raw blind grab
    of the first N seconds (music, room tone, second speakers, wildly varying level)
    is the main cause of 'heavy / deep / unstable' cloned timbre. Skips a short intro,
    high-passes, trims silence, and loudness-normalizes; falls back to a plain grab if
    cleaning leaves too little audio."""
    try:
        subprocess.run([
            "ffmpeg", "-y", "-ss", str(skip_start), "-i", video_path,
            "-vn", "-af", _voice_sample_filter(),
            "-ar", "22050", "-ac", "1", "-t", str(duration), output_wav
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        try:
            cleaned_dur = sf.info(output_wav).duration
        except Exception:
            cleaned_dur = None
        if cleaned_dur is not None and cleaned_dur < 3.0:
            _LOG.warning("Cleaned reference < 3s; falling back to a plain 30s extraction")
            subprocess.run([
                "ffmpeg", "-y", "-i", video_path, "-vn", "-acodec", "pcm_s16le",
                "-ar", "22050", "-ac", "1", "-t", "30", output_wav
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        _LOG.info(f"✓ Extracted cleaned voice sample: {output_wav}")
        return True
    except Exception as e:
        _LOG.error(f"❌ Failed to extract voice sample: {e}")
        return False


def _xtts_call(tts_model, text: str, speaker_wav: str, lang: str, out_path: str):
    """One XTTS synthesis call with stability-tuned parameters, falling back to plain
    defaults if the installed Coqui version doesn't accept the kwargs. Lower temperature
    + repetition penalty reduce the run-to-run variance and vowel drag; we disable the
    model's internal splitting because we chunk the text ourselves (split_for_tts)."""
    try:
        tts_model.tts_to_file(text=text, speaker_wav=speaker_wav, language=lang,
                              file_path=out_path, split_sentences=False,
                              temperature=0.5, repetition_penalty=2.0, length_penalty=1.0)
    except TypeError:
        tts_model.tts_to_file(text=text, speaker_wav=speaker_wav, language=lang,
                              file_path=out_path)


def _xtts_synthesize_segment(tts_model, text: str, speaker_wav: str, lang: str,
                             out_file: Path, work_dir: Path, tag, sample_rate: int) -> bool:
    """Synthesize one subtitle line: normalize, split into safe-length chunks, synthesize
    each, and concatenate into `out_file`. Returns True on non-empty output."""
    chunks = split_for_tts(normalize_tts_text(text))
    if not chunks:
        return False
    pieces = []
    for ci, chunk in enumerate(chunks):
        cf = work_dir / f"xtts_raw_{tag}_{ci}.wav"
        try:
            _xtts_call(tts_model, chunk, speaker_wav, lang, str(cf))
        except Exception as e:
            _LOG.error(f"XTTS chunk {tag}.{ci} error: {e}")
            continue
        if _has_content(cf, 1000):
            try:
                data, _ = sf.read(str(cf), dtype="float32")
                pieces.append(data)
            except Exception as e:
                _LOG.warning(f"XTTS chunk {tag}.{ci} read failed: {e}")
    if not pieces:
        return False
    joined = pieces[0] if len(pieces) == 1 else np.concatenate(pieces)
    sf.write(str(out_file), joined, sample_rate, subtype="PCM_16")
    return _has_content(out_file, 1000)


XTTS_REGEN_ATTEMPTS = 2   # A3: max quality-gate re-synthesis attempts per flagged XTTS segment


def _safe_unlink(*paths) -> None:
    """Delete paths if present, ignoring missing-file / OS errors (temp cleanup)."""
    for p in paths:
        try:
            Path(p).unlink()
        except OSError:
            pass


def _score_better(cand: Dict, best: Dict) -> bool:
    """True if speech score `cand` beats `best`: prefer passing the gate, then fewer failed
    checks, then lower WER. Used by A3 to keep the best of several stochastic XTTS takes."""
    if bool(cand.get("ok")) != bool(best.get("ok")):
        return bool(cand.get("ok"))
    cr, br = len(cand.get("reasons", [])), len(best.get("reasons", []))
    if cr != br:
        return cr < br
    return cand.get("wer", 1.0) < best.get("wer", 1.0)


def _xtts_fit_candidate(tts_model, text: str, speaker_wav: str, xtts_lang: str,
                        raw_path: Path, fin_path: Path, work_dir: Path, tag,
                        sample_rate: int, target_duration: float,
                        enable_stretch: bool) -> bool:
    """Synthesize + no-slowdown-fit one XTTS candidate into fin_path (A3 regeneration).
    Mirrors the first-attempt path; returns True on non-empty output."""
    if not _xtts_synthesize_segment(tts_model, text, speaker_wav, xtts_lang,
                                    raw_path, work_dir, tag, sample_rate):
        return False
    if enable_stretch:
        if not stretch_audio_smart(str(raw_path), str(fin_path), target_duration,
                                   work_dir, sample_rate, allow_slowdown=False):
            sf.write(str(fin_path), *sf.read(str(raw_path)), subtype="PCM_16")
    else:
        sf.write(str(fin_path), *sf.read(str(raw_path)), subtype="PCM_16")
    return _has_content(fin_path, 1000)


async def generate_xtts(subs, tts_model, speaker_wav: str, lang_code: str,
                        concat_list: list, temp_files: list,
                        work_dir: Path, enable_stretch: bool,
                        quality_gate: bool = False, asr_model=None):
    """Cloned speech with XTTS v2. Timeline, placement and scoring come from
    synthesize_timeline; A3 quality-gate regeneration runs in the on_ready hook."""
    sample_rate = 24000
    xtts_lang = lang_code[:2].lower()
    if xtts_lang not in XTTS_SUPPORTED_LANGS:
        _LOG.warning(f"⚠️  XTTS may not support '{xtts_lang}', attempting anyway")
    if not Path(speaker_wav).exists():
        _LOG.error(f"❌ Speaker WAV not found: {speaker_wav}")
        return

    _LOG.info(f"🎙️  XTTS voice cloning from: {speaker_wav}")
    _LOG.info(f"🌍 Target language: {xtts_lang}")

    def _render(i, text, final_file, target_duration):
        raw_file = work_dir / f"xtts_raw_{i}.wav"
        if not _xtts_synthesize_segment(tts_model, text, speaker_wav, xtts_lang,
                                        raw_file, work_dir, i, sample_rate):
            _LOG.warning(f"XTTS produced empty output for segment {i}: {text[:40]}")
            return False
        temp_files.append(str(raw_file))
        return _fit_to_window(raw_file, final_file, target_duration, work_dir,
                              sample_rate, enable_stretch)

    def _regenerate(i, text, final_file, target_duration):
        """A3: XTTS sampling is stochastic, so a flagged take can be improved by re-rolling.
        Scored BEFORE placement, because placement trims over-runs and that would skew the
        ASR round-trip. Only active with --quality-gate (it needs the gate ASR model)."""
        if not (quality_gate and asr_model is not None and _has_content(final_file, 1000)):
            return None
        best = score_speech(str(final_file), text, asr_model=asr_model, lang=xtts_lang)
        attempt = 0
        while not best["ok"] and attempt < XTTS_REGEN_ATTEMPTS:
            attempt += 1
            cand_raw = work_dir / f"xtts_rawcand_{i}_{attempt}.wav"
            cand_fin = work_dir / f"xtts_fincand_{i}_{attempt}.wav"
            if not _xtts_fit_candidate(tts_model, text, speaker_wav, xtts_lang,
                                       cand_raw, cand_fin, work_dir, f"{i}c{attempt}",
                                       sample_rate, target_duration, enable_stretch):
                _safe_unlink(cand_raw, cand_fin)
                continue
            cand = score_speech(str(cand_fin), text, asr_model=asr_model, lang=xtts_lang)
            if _score_better(cand, best):
                shutil.copyfile(str(cand_fin), str(final_file))
                best = cand
            _safe_unlink(cand_raw, cand_fin)
        if attempt:
            _LOG.info(f"♻️  segment {i}: regenerated {attempt}x → "
                         f"{'ok' if best['ok'] else 'best-effort'} "
                         f"(wer {best.get('wer', 'n/a')})")
        return best

    await synthesize_timeline(
        subs, engine="xtts", prefix="xtts", sample_rate=sample_rate, work_dir=work_dir,
        concat_list=concat_list, temp_files=temp_files, render=_render, on_ready=_regenerate,
        text_of=lambda s: s.text.strip(), desc="XTTS Synthesis", unit="phrase",
        quality_gate=quality_gate, asr_model=asr_model, gate_lang=xtts_lang)
def infer_delivery(text: str) -> str:
    """Language-agnostic delivery hint from a line's punctuation/structure (questions,
    exclamations, trailing-off), appended to the TTS instruction. A cheap structural tier;
    LLM-tagged per-line emotion is the planned upgrade (A2 T1)."""
    t = (text or "").strip()
    if not t:
        return ""
    if t.endswith("?") or t.endswith(("?\"", "?»", "?'")):
        return "Deliver this line as a genuine question, with natural rising intonation."
    if t.endswith("!") or (len(t) > 8 and t.isupper()):
        return "Deliver this line with lively, energetic emphasis."
    if t.endswith(("...", "…")):
        return "Let this line trail off softly and thoughtfully."
    return ""


# A2 T1: cheap text model used only to infer per-line delivery directions.
DEFAULT_DELIVERY_MODEL = "gpt-4o-mini"


def _parse_delivery_json(raw: str, expected: int) -> List[str]:
    """Parse a {"deliveries": [...]} response into exactly `expected` strings. Returns a
    list of '' (neutral) on any parse/shape/count failure — never raises."""
    if not raw:
        return [""] * expected
    s = raw.strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z]*\s*", "", s).rstrip("`").strip()
    try:
        data = json.loads(s)
    except Exception:
        return [""] * expected
    if isinstance(data, dict):
        arr = data.get("deliveries")
    elif isinstance(data, list):
        arr = data
    else:
        arr = None
    if not isinstance(arr, list) or len(arr) != expected:
        return [""] * expected
    return [str(x).strip().strip('"').strip() for x in arr]


def _delivery_hint(index: int, deliveries: List[str], raw_text: str) -> str:
    """Delivery direction for one line: the LLM tag (A2 T1) when present, else the
    structural hint (T0). Inferred from the RAW subtitle line, never the TTS-normalized
    one — normalization folds '…' to '.', which would silently hide the trailing-off hint."""
    if 0 <= index < len(deliveries) and deliveries[index]:
        return deliveries[index]
    return infer_delivery(raw_text)


def infer_delivery_llm(texts: List[str], client, *,
                       model: str = DEFAULT_DELIVERY_MODEL) -> List[str]:
    """A2 T1: one batched LLM pass that tags each line with a SHORT delivery direction
    (emotion / energy / pace / tone) for expressive TTS — richer than the structural
    infer_delivery() heuristic. Returns a list aligned to `texts`; entries are '' where
    neutral or on any failure, so the caller cleanly falls back to the heuristic.
    Best-effort and self-contained: never raises, one API call for the whole job."""
    n = len(texts)
    if n == 0 or client is None:
        return [""] * n
    numbered = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(texts))
    system = (
        "You are a voice-acting director for a text-to-speech engine. For each numbered "
        "line, write a SHORT delivery direction (at most 10 words) describing the emotion, "
        "energy, pace and tone for reading THAT line aloud — e.g. 'warm and reassuring, "
        "unhurried' or 'urgent, tense, clipped'. Do NOT repeat, quote or translate the "
        "line. If a line is plain and neutral, return an empty string for it. Return ONLY "
        'JSON: {"deliveries": [...]} with exactly ' + str(n) + " items, in the given order."
    )
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": numbered}],
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content
    except Exception as e:
        _LOG.debug(f"delivery LLM failed ({e}); falling back to structural hints")
        return [""] * n
    return _parse_delivery_json(raw, n)


async def generate_openai_tts(subs, client, voice: str, model: str, instructions: str,
                             lang_code: str, concat_list: list, temp_files: list,
                             work_dir: Path, enable_stretch: bool,
                             quality_gate: bool = False, asr_model=None,
                             emotion_detection: bool = False):
    """Speech via OpenAI TTS (gpt-4o-mini-tts): multilingual, instructable delivery, no
    cloning. With emotion_detection an LLM tags each line with a delivery direction (A2 T1).
    Timeline, placement and scoring come from synthesize_timeline."""
    sample_rate = 24000

    # A2 T1: one cached LLM pass over the whole job, before any synthesis.
    deliveries: List[str] = []
    if emotion_detection:
        cache = work_dir / "deliveries.json"
        if cache.exists():
            try:
                deliveries = json.loads(cache.read_text(encoding="utf-8"))
            except Exception:
                deliveries = []
        if not isinstance(deliveries, list) or len(deliveries) != len(subs):
            _LOG.info("🎭 Inferring per-line delivery directions (LLM)...")
            deliveries = infer_delivery_llm([s.text for s in subs], client)
            try:
                cache.write_text(json.dumps(deliveries, ensure_ascii=False), encoding="utf-8")
            except Exception:
                pass

    def _render(i, text, final_file, target_duration):
        raw_file = work_dir / f"otts_raw_{i}.wav"
        hint = _delivery_hint(i, deliveries, subs[i].text)
        seg_instr = " ".join(x for x in (instructions, hint) if x).strip()
        kwargs = {"model": model, "voice": voice, "input": text, "response_format": "wav"}
        if seg_instr:
            kwargs["instructions"] = seg_instr
        try:
            resp = client.audio.speech.create(**kwargs)
        except TypeError:
            # Older openai SDK without the `instructions` parameter.
            kwargs.pop("instructions", None)
            resp = client.audio.speech.create(**kwargs)
        Path(raw_file).write_bytes(resp.content)
        if not _has_content(raw_file, 1000):
            _LOG.warning(f"OpenAI TTS returned empty audio for segment {i}: {text[:40]}")
            return False
        temp_files.append(str(raw_file))
        return _fit_to_window(raw_file, final_file, target_duration, work_dir,
                              sample_rate, enable_stretch)

    await synthesize_timeline(
        subs, engine="openai", prefix="otts", sample_rate=sample_rate, work_dir=work_dir,
        concat_list=concat_list, temp_files=temp_files, render=_render,
        text_of=lambda s: normalize_tts_text(s.text),
        desc="OpenAI TTS", unit="phrase",
        quality_gate=quality_gate, asr_model=asr_model, gate_lang=lang_code)
# ─────────────────────────────────────────────
#  Existing code below — unchanged
# ─────────────────────────────────────────────

class _JsonFormatter(logging.Formatter):
    """Emit each log record as a single JSON object (structured logging)."""
    def format(self, record):
        return json.dumps({
            "ts": datetime.now().isoformat(timespec="seconds"),
            "level": record.levelname,
            "message": record.getMessage(),
        }, ensure_ascii=False)


class Logger:
    """Configure the "voxa" logger for one CLI run: a file in the workspace plus the console.

    Only that named logger is touched. This used to call logging.basicConfig(force=True),
    which silently replaced the root logger's handlers — acceptable in a script, hostile in
    an importable module. With --verbose the same handlers are additionally attached to the
    root logger so third-party libraries (httpx, openai) become visible; at normal levels
    their chatter stays out of the way.
    """
    def __init__(self, work_dir: Path, level: int = logging.INFO, json_format: bool = False):
        self.log_file = work_dir / "voxa.log"
        formatter = _JsonFormatter() if json_format else \
            logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handlers = [
            logging.FileHandler(self.log_file, encoding='utf-8'),
            logging.StreamHandler(),
        ]
        for h in handlers:
            h.setFormatter(formatter)

        self.logger = _LOG
        self.logger.setLevel(level)
        for h in list(self.logger.handlers):   # a batch run reconfigures within one process
            self.logger.removeHandler(h)
        for h in handlers:
            self.logger.addHandler(h)
        self.logger.propagate = False

        if level <= logging.DEBUG:
            root = logging.getLogger()
            root.setLevel(level)
            for h in handlers:
                root.addHandler(h)

    def info(self, msg): self.logger.info(msg)
    def warning(self, msg): self.logger.warning(msg)
    def error(self, msg): self.logger.error(msg)
    def debug(self, msg): self.logger.debug(msg)


class StateManager:
    """Manages processing state for smart resume"""
    def __init__(self, work_dir: Path):
        self.state_file = work_dir / "state.json"
        self.state = self.load_state()

    def load_state(self) -> Dict:
        if self.state_file.exists():
            with open(self.state_file, 'r') as f:
                return json.load(f)
        return {'steps_completed': [], 'last_update': None}

    def save_state(self):
        self.state['last_update'] = datetime.now().isoformat()
        with open(self.state_file, 'w') as f:
            json.dump(self.state, f, indent=2)

    def mark_completed(self, step: str):
        if step not in self.state['steps_completed']:
            self.state['steps_completed'].append(step)
        self.save_state()

    def is_completed(self, step: str) -> bool:
        return step in self.state['steps_completed']


def create_silence_wav(duration_seconds: float, output_file: str, sample_rate: int = 22050):
    try:
        num_samples = int(duration_seconds * sample_rate)
        silence = np.zeros(num_samples, dtype=np.float32)
        sf.write(output_file, silence, sample_rate, subtype='PCM_16')
        return True
    except Exception as e:
        _LOG.error(f"Failed to create silence: {e}")
        return False


def download_piper_model(lang_code: str, models_dir: Path) -> Optional[Path]:
    if 'ru' in lang_code:
        model_name = "ru_RU-ruslan-medium.onnx"
    else:
        model_name = "en_US-lessac-medium.onnx"
    manual_path = Path.home() / ".piper_models" / model_name
    if manual_path.exists():
        _LOG.info(f"✓ Found manual model: {manual_path}")
        return manual_path
    else:
        _LOG.error(f"❌ Model file missing: {manual_path}")
        _LOG.error("👉 Please run the wget commands from the instructions to download the model manually!")
        return None


async def generate_piper(subs, model_path: Path, concat_list: list, temp_files: list,
                         work_dir: Path, enable_stretch: bool, lang_code: str = "",
                         quality_gate: bool = False, asr_model=None):
    """Offline speech via the Piper binary. Timeline, placement and scoring come from
    synthesize_timeline; this only turns one line of text into one WAV."""
    piper_cmd = shutil.which("piper")
    if not piper_cmd:
        possible_path = Path(sys.executable).parent / "piper"
        if possible_path.exists():
            piper_cmd = str(possible_path)
    if not piper_cmd:
        _LOG.error("❌ Piper command not found!")
        return

    _LOG.info(f"🎙️ Using Piper binary: {piper_cmd}")
    _LOG.info(f"📂 Model path: {model_path}")
    sample_rate = 22050

    def _render(i, text, final_file, target_duration):
        raw_file = work_dir / f"piper_raw_{i}.wav"
        cmd = [piper_cmd, "--model", str(model_path), "--output_file", str(raw_file)]
        process = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        _, stderr = process.communicate(input=text.encode("utf-8"))
        if not _has_content(raw_file, 1000):
            _LOG.warning(f"Piper produced no audio for segment {i}: {text[:40]} "
                            f"({stderr.decode(errors='replace')[:100]})")
            return False
        temp_files.append(str(raw_file))
        return _fit_to_window(raw_file, final_file, target_duration, work_dir,
                              sample_rate, enable_stretch)

    await synthesize_timeline(
        subs, engine="piper", prefix="piper", sample_rate=sample_rate, work_dir=work_dir,
        concat_list=concat_list, temp_files=temp_files, render=_render,
        text_of=lambda s: normalize_tts_text(s.text).replace('"', "").replace("'", ""),
        desc="Piper Synthesis", unit="phrase",
        quality_gate=quality_gate, asr_model=asr_model, gate_lang=lang_code or None)
async def get_edge_voice(lang_code: str, emotion: Optional[str] = None) -> Tuple[str, bool]:
    try:
        voices = await edge_tts.VoicesManager.create()
        suitable = voices.find(Locale=lang_code)
        if not suitable:
            suitable = [v for v in voices.voices if v['Locale'].startswith(lang_code[:2])]
        if suitable:
            for voice in suitable:
                if 'StyleList' in voice and voice['StyleList']:
                    return voice['Name'], True
            return suitable[0]['Name'], False
    except Exception as e:
        print(f"⚠️ Voice search error: {e}")
    return "en-US-ChristopherNeural", False


def format_timestamp(seconds: float) -> str:
    td = timedelta(seconds=seconds)
    hours = td.seconds // 3600
    minutes = (td.seconds % 3600) // 60
    secs = td.seconds % 60
    millis = td.microseconds // 1000
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


# ── SRT reading ─────────────────────────────────────────────────────────────
# Voxa writes its own SRT (see format_timestamp above) and reads it back before
# synthesis. That round-trip used to pull in `pysrt`, whose GPL-3.0 license is
# incompatible with shipping this MIT project as a bundled artifact. The parser
# below covers the SubRip subset Voxa produces, plus the common variations found
# in externally supplied files (BOM, CRLF, missing index line, multi-line text).

class SubTime(NamedTuple):
    """SubRip timestamp, exposing the same fields the TTS engines already read."""
    hours: int
    minutes: int
    seconds: int
    milliseconds: int


class Subtitle(NamedTuple):
    index: int
    start: SubTime
    end: SubTime
    text: str


_SRT_TIME_RE = re.compile(r"(\d+):(\d{2}):(\d{2})[,.](\d{1,3})")


def _parse_srt_time(value: str) -> Optional[SubTime]:
    m = _SRT_TIME_RE.search(value)
    if not m:
        return None
    h, mnt, sec, frac = m.groups()
    return SubTime(int(h), int(mnt), int(sec), int(frac.ljust(3, "0")))


def read_srt(path) -> List[Subtitle]:
    """Parse an SRT file into Subtitle records. Blocks that carry no usable timestamp
    are skipped rather than raising, so one malformed cue cannot abort a whole dub."""
    raw = Path(path).read_text(encoding="utf-8-sig")
    subs: List[Subtitle] = []
    for block in re.split(r"\r?\n[ \t]*\r?\n", raw.strip()):
        lines = [ln.rstrip("\r") for ln in block.split("\n") if ln.strip()]
        if not lines:
            continue
        cursor = 0
        index = len(subs) + 1
        if lines[0].strip().isdigit() and len(lines) > 1 and "-->" in lines[1]:
            index = int(lines[0].strip())
            cursor = 1
        if cursor >= len(lines) or "-->" not in lines[cursor]:
            continue
        left, _, right = lines[cursor].partition("-->")
        start, end = _parse_srt_time(left), _parse_srt_time(right)
        if start is None or end is None:
            continue
        text = "\n".join(lines[cursor + 1:]).strip()
        subs.append(Subtitle(index, start, end, text))
    return subs


def detect_emotion(text: str) -> Optional[str]:
    text_lower = text.lower()
    if any(word in text_lower for word in ['angry', 'hate', 'terrible', 'worst', 'stupid', 'damn', 'hell']):
        return 'angry'
    if any(word in text_lower for word in ['sad', 'unfortunately', 'sorry', 'tragic', 'died', 'death', 'crying']):
        return 'sad'
    exclamation_count = text.count('!')
    if exclamation_count >= 2 or any(word in text_lower for word in ['wow', 'amazing', 'awesome', 'fantastic', 'incredible', 'wonderful']):
        return 'excited'
    elif exclamation_count == 1 or any(word in text_lower for word in ['great', 'good', 'nice', 'happy', 'excellent']):
        return 'cheerful'
    if any(word in text_lower for word in ['scared', 'terrified', 'afraid', 'panic', 'scream']):
        return 'terrified'
    if text.isupper() and len(text) > 10:
        return 'shouting'
    if any(word in text_lower for word in ['whisper', 'quietly', 'secret', 'shh']):
        return 'whispering'
    if any(word in text_lower for word in ['hello', 'hi', 'welcome', 'thanks', 'thank you', 'please']):
        return 'friendly'
    if any(word in text_lower for word in ['hope', 'maybe', 'perhaps', 'possibly', 'wish']):
        return 'hopeful'
    return None


def translate_with_retry(text: str, target_lang: str, translator_type: str,
                         ollama_model: str, max_retries: int = 3,
                         llm_model: Optional[str] = None,
                         llm_api_key: Optional[str] = None) -> str:
    for attempt in range(max_retries):
        try:
            if translator_type == "google":
                translated = GoogleTranslator(source='auto', target=target_lang).translate(text)
                if translated and translated != text:
                    return translated
            elif translator_type == "ollama":
                translated = translate_ollama(text, target_lang, ollama_model)
                if translated and translated != text:
                    return translated
            elif translator_type in LLM_PROVIDERS:
                translated = translate_llm(text, target_lang, translator_type,
                                           llm_model, llm_api_key)
                # Accept any non-empty result: an identical translation (e.g. proper
                # nouns/numbers) is legitimate, unlike the google/ollama echo-on-failure.
                if translated and translated.strip():
                    return translated
        except Exception as e:
            if attempt == max_retries - 1:
                _LOG.warning(f"Translation failed after {max_retries} attempts: {e}")
    try:
        if translator_type == "google":
            _LOG.info("Falling back to Ollama translator")
            return translate_ollama(text, target_lang, ollama_model)
        else:
            _LOG.info("Falling back to Google translator")
            return GoogleTranslator(source='auto', target=target_lang).translate(text)
    except Exception as e:
        _LOG.error(f"All translation methods failed for '{text[:50]}...': {e}")
        return text


def translate_ollama(text: str, target_lang: str, model_name: str) -> str:
    url = "http://localhost:11434/api/generate"
    full_lang = LANG_MAP.get(target_lang.lower(), target_lang)
    prompt = (
        f"Translate the following text into {full_lang}. "
        f"Match the tone and style of the original. "
        f"Output ONLY the translation without quotes or explanations.\n\n"
        f"Text: {text}"
    )
    payload = {
        "model": model_name,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.2, "top_p": 0.9, "stop": ["\n\n", "Note:", "Explanation:"]}
    }
    try:
        response = requests.post(url, json=payload, timeout=60)
        if response.status_code == 200:
            res = response.json().get('response', '').strip()
            return res.strip('"').strip("'").strip()
        return text
    except Exception as e:
        _LOG.warning(f"Ollama error: {e}")
        return text


# ─────────────────────────────────────────────
#  LLM translation providers (OpenAI, Anthropic, …)
# ─────────────────────────────────────────────

# Clients are cached per (api_key, base_url) rather than as one global instance:
# translation and speech may legitimately target different endpoints — for example a
# local, OpenAI-compatible TTS server — with different credentials.
_openai_clients: Dict[Tuple[str, str], object] = {}
_anthropic_client = None


def get_openai_client(api_key: Optional[str] = None, base_url: Optional[str] = None):
    """Return an OpenAI client for one endpoint, creating it on first use.

    Clients are cached per (api_key, base_url). The previous single global instance meant
    the first caller won: once translation had built a client, speech could not point at a
    different endpoint or use a different key. `base_url` targets any OpenAI-compatible
    server; such servers usually ignore the key, so one is not required in that case.
    """
    try:
        from openai import OpenAI
    except ImportError:
        _LOG.error("❌ 'openai' package not installed. Run: pip install openai")
        return None

    key = api_key or os.environ.get("OPENAI_API_KEY")
    url = base_url or None
    if not key and not url:
        _LOG.error("❌ OpenAI API key not found. "
                   "Set the OPENAI_API_KEY environment variable or pass --openai_api_key")
        return None

    cache_key = (key or "", url or "")
    if cache_key in _openai_clients:
        return _openai_clients[cache_key]

    try:
        # A self-hosted endpoint still needs a non-empty key to satisfy the SDK.
        client = OpenAI(api_key=key or "not-needed", base_url=url) if url else OpenAI(api_key=key)
    except Exception as e:
        _LOG.error(f"❌ Failed to initialize OpenAI client: {e}")
        return None
    _openai_clients[cache_key] = client
    return client


def get_anthropic_client(api_key: Optional[str] = None):
    """Lazily create and cache a single Anthropic client instance."""
    global _anthropic_client
    if _anthropic_client is not None:
        return _anthropic_client
    try:
        import anthropic
    except ImportError:
        _LOG.error("❌ 'anthropic' package not installed. Run: pip install 'voxa[anthropic]'")
        return None
    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        _LOG.error("❌ Anthropic API key not found. "
                      "Set the ANTHROPIC_API_KEY environment variable or pass --anthropic_api_key")
        return None
    try:
        _anthropic_client = anthropic.Anthropic(api_key=key, max_retries=5)
    except Exception as e:
        _LOG.error(f"❌ Failed to initialize Anthropic client: {e}")
        return None
    return _anthropic_client


# ── Usage / cost tracking (per provider) ─────────────────
_llm_usage: Dict[str, Dict[str, int]] = {}

# Optional price table: model prefix -> ($ per 1M input tokens, $ per 1M output tokens).
# Left empty by default because pricing changes over time — fill in the models you use to
# get cost estimates. When a model is not listed, only token counts are reported.
LLM_PRICING: Dict[str, Tuple[float, float]] = {
    # "gpt-5": (1.25, 10.0),
    # "claude-opus-4-8": (5.0, 25.0),
}


def _record_llm_usage(provider: str, input_tokens: int, output_tokens: int):
    u = _llm_usage.setdefault(provider, {"calls": 0, "input_tokens": 0, "output_tokens": 0})
    u["calls"] += 1
    u["input_tokens"] += input_tokens or 0
    u["output_tokens"] += output_tokens or 0


def _estimate_llm_cost(model: str, input_tokens: int, output_tokens: int) -> Optional[float]:
    for prefix, (in_price, out_price) in LLM_PRICING.items():
        if model.startswith(prefix):
            return (input_tokens / 1e6) * in_price + (output_tokens / 1e6) * out_price
    return None


def log_llm_usage_summary(provider: str, model: str):
    u = _llm_usage.get(provider)
    if not u or u["calls"] == 0:
        return
    total = u["input_tokens"] + u["output_tokens"]
    cost = _estimate_llm_cost(model, u["input_tokens"], u["output_tokens"])
    cost_str = f", est. cost ${cost:.4f}" if cost is not None else " (set LLM_PRICING for cost)"
    _LOG.info(f"💰 {provider} usage: {u['calls']} calls, {total} tokens "
                 f"(input {u['input_tokens']}, output {u['output_tokens']}){cost_str}")


# ── OpenAI request helper: param degradation + exponential backoff ──
_OPENAI_TRANSIENT = ("rate limit", "ratelimit", "429", "timeout", "timed out", "overloaded",
                     "temporarily unavailable", "503", "502", "500", "504",
                     "connection", "econnreset")
_OPENAI_PARAM_ERR = ("temperature", "response_format", "max_tokens", "max_completion_tokens",
                     "unsupported parameter", "unsupported value")


def _is_transient_error(err) -> bool:
    status = getattr(err, "status_code", None) or getattr(err, "code", None)
    if status in (429, 500, 502, 503, 504):
        return True
    s = str(err).lower()
    return any(m in s for m in _OPENAI_TRANSIENT)


def _is_param_error(err) -> bool:
    s = str(err).lower()
    return any(m in s for m in _OPENAI_PARAM_ERR)


def _openai_chat(client, messages, model: str, want_json: bool = False,
                 max_backoff_retries: int = 5) -> str:
    """One OpenAI chat completion with graceful parameter degradation and exponential
    backoff on rate-limit / 5xx errors. Records token usage. Raises on unrecoverable failure."""
    combos = [(True, want_json), (False, want_json)]
    if want_json:
        combos += [(True, False), (False, False)]   # drop json mode if unsupported
    seen, ordered = set(), []
    for c in combos:
        if c not in seen:
            seen.add(c)
            ordered.append(c)

    last_err = None
    for include_temp, use_json in ordered:
        backoff = 2.0
        for attempt in range(max_backoff_retries):
            try:
                kwargs = {"model": model, "messages": messages}
                if include_temp:
                    kwargs["temperature"] = 0.3
                if use_json:
                    kwargs["response_format"] = {"type": "json_object"}
                resp = client.chat.completions.create(**kwargs)
                usage = getattr(resp, "usage", None)
                _record_llm_usage("openai", getattr(usage, "prompt_tokens", 0),
                                  getattr(usage, "completion_tokens", 0))
                return resp.choices[0].message.content or ""
            except Exception as e:
                last_err = e
                if _is_transient_error(e) and attempt < max_backoff_retries - 1:
                    wait = backoff + random.uniform(0, 1)
                    _LOG.warning(f"OpenAI transient error (try {attempt + 1}/{max_backoff_retries}): "
                                    f"{e}; retrying in {wait:.1f}s")
                    time.sleep(wait)
                    backoff = min(backoff * 2, 60)
                    continue
                break   # non-transient: decide below whether degrading can help
        # Only a rejected *parameter* is worth retrying with a reduced request. An auth
        # failure or an unknown model fails identically for every combination, so stop
        # rather than burn three more calls proving it.
        if not _is_param_error(last_err):
            break
    raise last_err if last_err else RuntimeError("OpenAI request failed")


# ── Provider chat adapters: (system, user, model, want_json, api_key) -> text ──

def _openai_chat_text(system: str, user: str, model: str, want_json: bool,
                      api_key: Optional[str]) -> str:
    client = get_openai_client(api_key)
    if client is None:
        raise RuntimeError("OpenAI client unavailable (missing package or API key)")
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    return _openai_chat(client, messages, model, want_json=want_json)


def _anthropic_chat_text(system: str, user: str, model: str, want_json: bool,
                         api_key: Optional[str]) -> str:
    # want_json is advisory only — Claude has no JSON mode; the prompt requests JSON.
    client = get_anthropic_client(api_key)
    if client is None:
        raise RuntimeError("Anthropic client unavailable (missing package or API key)")
    # No temperature: current Claude models (Opus 4.x) reject sampling params.
    # The SDK retries 429/5xx automatically (max_retries set on the client).
    resp = client.messages.create(
        model=model,
        max_tokens=4096,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    usage = getattr(resp, "usage", None)
    _record_llm_usage("anthropic", getattr(usage, "input_tokens", 0),
                      getattr(usage, "output_tokens", 0))
    parts = [getattr(b, "text", "") for b in (resp.content or [])
             if getattr(b, "type", None) == "text"]
    return "".join(parts)


# Provider registry — register a new LLM by adding its chat adapter here.
LLM_PROVIDERS: Dict[str, Dict] = {
    "openai": {"chat": _openai_chat_text, "default_model": DEFAULT_OPENAI_MODEL,
               "env_key": "OPENAI_API_KEY"},
    "anthropic": {"chat": _anthropic_chat_text, "default_model": DEFAULT_ANTHROPIC_MODEL,
                  "env_key": "ANTHROPIC_API_KEY"},
}


_TRANSLATION_PREFIX_RE = re.compile(
    r'^\s*(translation|translated|перевод|traduction|翻译|çeviri|tərcümə)\s*[:：\-]\s*',
    re.IGNORECASE)


def _clean_line(text: str) -> str:
    """Strip surrounding quotes and common leaked prefixes like 'Translation:' from a line."""
    t = (text or "").strip()
    t = _TRANSLATION_PREFIX_RE.sub("", t)
    return t.strip().strip('"').strip("'").strip()


def _llm_translate_single(text: str, target_lang: str, model: str, chat_fn,
                          api_key: Optional[str] = None) -> str:
    """Translate one subtitle line via any provider chat adapter. Returns the source
    text on failure so the caller's retry/fallback chain can take over."""
    full_lang = LANG_MAP.get(target_lang.lower(), target_lang)
    system_prompt = (
        f"You are a professional subtitle translator and native-level localization expert "
        f"for {full_lang}. Translate the user's line into {full_lang} so it sounds completely "
        f"natural, fluent and idiomatic — as if originally written and spoken by a native "
        f"speaker. Preserve the exact meaning, tone, emotion and register (formal/informal) "
        f"of the source. Avoid literal, word-for-word or machine-like phrasing. Keep the length "
        f"natural for spoken dubbing (similar speaking duration to the source). "
        f"Do NOT add quotes, notes, explanations, transliteration or any extra text — "
        f"output ONLY the translated line."
    )
    try:
        result = chat_fn(system_prompt, text, model, False, api_key)
    except Exception as e:
        _LOG.warning(f"LLM translate error: {e}")
        return text
    result = _clean_line(result)
    return result if result else text


# ─────────────────────────────────────────────
#  Context-aware batch translation (Task C)
# ─────────────────────────────────────────────
DEFAULT_LLM_BATCH_SIZE = 25   # subtitle lines translated together per API call
_LLM_CONTEXT_OVERLAP = 3      # previous lines passed as context across chunk boundaries


def _parse_batch_translations(raw: str, expected: int) -> Optional[List[str]]:
    """Parse the model's JSON response into exactly `expected` translation strings.
    Returns None if the response can't be parsed or the count doesn't match."""
    if not raw:
        return None
    s = raw.strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z]*\s*", "", s).rstrip("`").strip()
    try:
        data = json.loads(s)
    except Exception:
        return None
    arr = None
    if isinstance(data, list):
        arr = data
    elif isinstance(data, dict):
        arr = data.get("translations")
        if arr is None:
            arr = data.get("lines")
    if not isinstance(arr, list) or len(arr) != expected:
        return None
    return [_clean_line(str(x)) for x in arr]


def _llm_translate_chunk(chunk: List[str], full_lang: str, target_lang: str, model: str,
                         chat_fn, api_key: Optional[str],
                         context_pairs: List[Tuple[str, str]],
                         chunk_max_chars: Optional[List[int]] = None) -> List[str]:
    """Translate one contiguous chunk of subtitle lines in a single API call, with mutual
    context. When chunk_max_chars is given, each translation is length-budgeted so it stays
    speakable within the source segment's time (isochrony). Falls back to per-line."""
    budget_note = ""
    if chunk_max_chars:
        budget_note = (
            " Each input line is an object with 'text' and a 'max_chars' budget: keep that "
            "line's translation at most about 'max_chars' characters so it is naturally "
            "speakable within the original segment's duration (this is a dub — matched timing "
            "matters). If a literal translation would exceed the budget, condense it with "
            "shorter, more natural phrasing — but NEVER drop information or meaning. Still "
            "produce exactly one translation per input line, in order."
        )
    system_prompt = (
        f"You are a professional subtitle translator and native-level localization expert "
        f"for {full_lang}. You receive a contiguous block of subtitle lines from a single video "
        f"and translate ALL of them into {full_lang}. Use the surrounding lines (and any provided "
        f"'context' lines) to keep pronouns, gender, names, terminology, tone and style perfectly "
        f"consistent and natural across the whole block. Each translation must sound like a native "
        f"speaker wrote it and fit roughly the same speaking duration as the source (for dubbing)."
        f"{budget_note} "
        f"Never merge, split, reorder, add or drop lines, and never translate the 'context' lines. "
        f"Respond ONLY with a JSON object of the form {{\"translations\": [\"...\", \"...\"]}} "
        f"containing EXACTLY {len(chunk)} items, in the same order as the input 'lines'."
    )
    if chunk_max_chars:
        lines = [{"text": t, "max_chars": c} for t, c in zip(chunk, chunk_max_chars)]
    else:
        lines = chunk
    user_obj: Dict = {"lines": lines}
    if context_pairs:
        user_obj["context"] = [{"source": s, "translation": t} for s, t in context_pairs]
    user = json.dumps(user_obj, ensure_ascii=False)

    try:
        raw = chat_fn(system_prompt, user, model, True, api_key)
    except Exception as e:
        _LOG.warning(f"LLM batch error: {e} — falling back to per-line for this chunk")
        return [_llm_translate_single(t, target_lang, model, chat_fn, api_key) for t in chunk]

    parsed = _parse_batch_translations(raw, len(chunk))
    if parsed is not None:
        return parsed
    _LOG.warning("LLM batch: response count/parse mismatch — falling back to per-line for this chunk")
    return [_llm_translate_single(t, target_lang, model, chat_fn, api_key) for t in chunk]


def _llm_translate_batch(texts: List[str], target_lang: str, model: str, chat_fn,
                         api_key: Optional[str] = None,
                         batch_size: int = DEFAULT_LLM_BATCH_SIZE,
                         max_chars: Optional[List[int]] = None) -> List[str]:
    """Translate a full list of subtitle lines using context-aware chunked LLM calls.
    Output length and order always match the input; falls back to the source on failure.
    `max_chars` (parallel to texts) length-budgets each line for dub isochrony."""
    full_lang = LANG_MAP.get(target_lang.lower(), target_lang)
    if batch_size < 1:
        batch_size = DEFAULT_LLM_BATCH_SIZE

    results: List[str] = []
    for start in tqdm(range(0, len(texts), batch_size),
                      desc="LLM batch translate", unit="chunk"):
        chunk = texts[start:start + batch_size]
        chunk_max_chars = max_chars[start:start + batch_size] if max_chars else None

        # Carry a short tail of the previous chunk as cross-boundary context.
        context_pairs: List[Tuple[str, str]] = []
        if start > 0 and _LLM_CONTEXT_OVERLAP > 0:
            ctx_src = texts[max(0, start - _LLM_CONTEXT_OVERLAP):start]
            ctx_tr = results[max(0, start - _LLM_CONTEXT_OVERLAP):start]
            context_pairs = list(zip(ctx_src, ctx_tr))

        translated = _llm_translate_chunk(chunk, full_lang, target_lang, model,
                                          chat_fn, api_key, context_pairs, chunk_max_chars)
        if len(translated) != len(chunk):   # final alignment safety net
            translated = [_llm_translate_single(t, target_lang, model, chat_fn, api_key)
                          for t in chunk]
        results.extend(translated)

    return results


DEFAULT_SPEECH_RATE_CPS = 15.0   # rough natural speaking rate (chars/sec) for length budgets


def _duration_to_max_chars(seconds: float, cps: float = DEFAULT_SPEECH_RATE_CPS) -> int:
    """Character budget for a translation to stay speakable within `seconds` at ~cps
    chars/second. Floored so very short segments still get a usable budget."""
    return max(20, int(seconds * cps))


def translate_llm(text: str, target_lang: str, provider: str, model: Optional[str] = None,
                  api_key: Optional[str] = None) -> str:
    """Single-line translation via the named LLM provider from LLM_PROVIDERS."""
    p = LLM_PROVIDERS[provider]
    return _llm_translate_single(text, target_lang, model or p["default_model"],
                                 p["chat"], api_key)


def translate_llm_batch(texts: List[str], target_lang: str, provider: str,
                        model: Optional[str] = None, api_key: Optional[str] = None,
                        batch_size: int = DEFAULT_LLM_BATCH_SIZE,
                        max_chars: Optional[List[int]] = None) -> List[str]:
    """Context-aware batch translation via the named LLM provider from LLM_PROVIDERS.
    `max_chars` length-budgets each line for dub timing (SY3)."""
    p = LLM_PROVIDERS[provider]
    return _llm_translate_batch(texts, target_lang, model or p["default_model"],
                                p["chat"], api_key, batch_size, max_chars)


def merge_segments_into_sentences(segments: List[Dict], max_duration: float = 10.0) -> List[Dict]:
    sentence_endings = re.compile(r'[.!?;:]\s*$')
    merged = []
    current_group = {'text': '', 'start': None, 'end': None}

    for i, seg in enumerate(segments):
        text = seg['text'].strip()
        if not text:
            continue
        if current_group['start'] is None:
            current_group['start'] = seg['start']
        current_group['text'] = (current_group['text'] + ' ' + text).strip()
        current_group['end'] = seg['end']
        duration = current_group['end'] - current_group['start']
        has_sentence_end = sentence_endings.search(text)
        has_pause = False
        if i + 1 < len(segments):
            has_pause = (segments[i + 1]['start'] - seg['end']) > 0.5
        if has_sentence_end or duration >= max_duration or has_pause:
            merged.append({
                'text': current_group['text'],
                'start': current_group['start'],
                'end': current_group['end']
            })
            current_group = {'text': '', 'start': None, 'end': None}

    if current_group['text']:
        merged.append(current_group)
    return merged


def _plan_block(actual_ms: float, start_ms: float, end_ms: float) -> Tuple[float, float]:
    """Pure timeline math for placing one speech block on the concat timeline.
    Returns (pad_ms, next_cursor_ms): `pad_ms` of trailing silence so a shorter-than-window
    clip still reaches the window end; `next_cursor_ms` is where the timeline stands after
    the block (past the window on an over-run, so the following gap shrinks to compensate)."""
    window_ms = end_ms - start_ms
    if actual_ms < window_ms - 20:
        return (window_ms - actual_ms), float(end_ms)
    return 0.0, float(start_ms) + max(actual_ms, float(window_ms))


def _plan_anchored_block(actual_ms: float, start_ms: float, next_start_ms: float) -> Tuple[float, float]:
    """Pure math for the anchored slot [start_ms, next_start_ms] (Pillar 1). Returns
    (trim_ms, pad_ms): trim if the clip over-runs the slot, else pad the remainder."""
    room = float(next_start_ms) - float(start_ms)
    if room > 0 and actual_ms > room:
        return (actual_ms - room), 0.0
    return 0.0, max(0.0, room - actual_ms)


def _sub_start_ms(sub) -> int:
    t = sub.start
    return (t.hours * 3600 + t.minutes * 60 + t.seconds) * 1000 + t.milliseconds


def _sub_end_ms(sub) -> int:
    t = sub.end
    return (t.hours * 3600 + t.minutes * 60 + t.seconds) * 1000 + t.milliseconds


def _fit_to_window(src: Path, dst: Path, target_duration: float, work_dir: Path,
                   sample_rate: int, enable_stretch: bool) -> bool:
    """Fit a freshly synthesized clip into its source window: speed it up when it over-runs
    (S0 — never slow it down, that sounds dragged), otherwise copy it through unchanged and
    let placement pad the remainder."""
    if enable_stretch and stretch_audio_smart(str(src), str(dst), target_duration,
                                              work_dir, sample_rate, allow_slowdown=False):
        return True
    try:
        sf.write(str(dst), *sf.read(str(src)), subtype="PCM_16")
    except Exception as e:
        _LOG.error(f"Could not write {dst.name}: {e}")
        return False
    return True


async def _maybe_await(value):
    """Allow an engine's render callback to be either a coroutine (edge) or a plain
    function (piper / xtts / openai)."""
    return await value if inspect.isawaitable(value) else value


async def synthesize_timeline(subs, *, engine: str, prefix: str, sample_rate: int,
                              work_dir: Path, concat_list: list, temp_files: list,
                              render, text_of, desc: str, unit: str = "segment",
                              min_bytes: int = 1000, quality_gate: bool = False,
                              asr_model=None, gate_lang=None, on_ready=None) -> int:
    """Drive one TTS engine across the subtitle timeline (Template Method).

    Every engine shares this loop — leading silence, cached synthesis, absolute-anchor
    placement, drift tracking and optional quality scoring — and supplies only `render`:
    how one line of text becomes one WAV file. Duplicating this loop per engine is what
    let Piper silently miss both the no-slowdown and the anchored-placement fixes, and
    hide a resume bug for months; there is now exactly one copy of it.

    `render(i, text, final_file, target_duration) -> bool` may be sync or async.
    `on_ready(i, text, final_file, target_duration) -> Optional[Dict]` runs after synthesis
    and before placement (XTTS re-rolls a flagged take there), returning a gate score if it
    already computed one. Returns the number of segments placed.
    """
    scores: List[Dict] = []
    generated = 0
    cursor_ms = 0.0
    max_drift = 0.0

    for i, sub in enumerate(tqdm(subs, desc=desc, unit=unit)):
        start_ms = _sub_start_ms(sub)
        end_ms = _sub_end_ms(sub)
        text = text_of(sub)
        if not text:
            continue
        target_duration = (end_ms - start_ms) / 1000.0

        # ── Silence up to this segment's source onset ───────
        sil_ms = start_ms - cursor_ms
        if sil_ms > 100:
            sil_file = work_dir / f"{prefix}_sil_{i}.wav"
            if create_silence_wav(sil_ms / 1000.0, str(sil_file), sample_rate) and sil_file.exists():
                concat_list.append(f"file '{sil_file}'")
                temp_files.append(str(sil_file))
                cursor_ms += sil_ms
        max_drift = max(max_drift, cursor_ms - start_ms)

        final_file = work_dir / f"{prefix}_fin_{i}.wav"
        if not _has_content(final_file, min_bytes):
            try:
                ok = await _maybe_await(render(i, text, final_file, target_duration))
            except Exception as e:
                _LOG.error(f"{engine} segment {i} error: {e}")
                ok = False
            if not ok:
                cursor_ms = end_ms
                continue

        gate_score = on_ready(i, text, final_file, target_duration) if on_ready else None

        if _has_content(final_file, min_bytes):
            next_start_ms = _sub_start_ms(subs[i + 1]) if i + 1 < len(subs) else None
            cursor_ms = _place_speech_block(final_file, start_ms, end_ms, next_start_ms,
                                            sample_rate, work_dir, i, concat_list, temp_files)
            generated += 1
            if quality_gate:
                scores.append(gate_score if gate_score is not None
                              else score_speech(str(final_file), text, asr_model=asr_model,
                                                lang=gate_lang))
        else:
            cursor_ms = end_ms

    _LOG.info(f"✓ {engine} generated {generated}/{len(subs)} segments")
    _log_sync_drift(max_drift, engine)
    if quality_gate:
        log_quality_report(scores, engine)
    return generated


def _fade_ends(data, sr, fade_ms: float = 8.0):
    """Fade the first/last few ms of an audio array in place (declick); returns it."""
    n = int(sr * fade_ms / 1000.0)
    if n > 0 and len(data) > 2 * n:
        ramp = np.linspace(0.0, 1.0, n, dtype=np.float32)
        if data.ndim == 1:
            data[:n] *= ramp
            data[-n:] *= ramp[::-1]
        else:
            data[:n] *= ramp[:, None]
            data[-n:] *= ramp[::-1][:, None]
    return data


def _apply_micro_fades(path: Path, fade_ms: float = 8.0):
    """Apply a few-ms fade-in/out in place to remove click/pop discontinuities where
    segments butt against silence or each other in the concatenated track."""
    try:
        data, sr = sf.read(str(path), dtype="float32")
        sf.write(str(path), _fade_ends(data, sr, fade_ms), sr, subtype="PCM_16")
    except Exception as e:
        _LOG.debug(f"micro-fade skipped for {path}: {e}")


def _trim_wav(path: Path, max_ms: float):
    """Trim a clip to at most max_ms (with a fade at the new end) so an over-run stays
    inside its slot and cannot push the next segment past its source onset."""
    try:
        data, csr = sf.read(str(path), dtype="float32")
        max_samples = int(max_ms / 1000.0 * csr)
        cut = len(data) - max_samples
        if cut > 0 and max_samples > 0:
            sf.write(str(path), _fade_ends(data[:max_samples], csr), csr, subtype="PCM_16")
            _LOG.info(f"✂️  trimmed {cut / csr * 1000:.0f}ms over-run to keep sync "
                         f"(translation longer than its window)")
    except Exception as e:
        _LOG.debug(f"trim failed for {path}: {e}")


def _place_speech_block(final_file: Path, start_ms: float, end_ms: float, next_start_ms,
                        sr: int, work_dir: Path, tag, concat_list: list,
                        temp_files: list) -> float:
    """Place one speech clip ANCHORED to the source timeline (Pillar 1). When the next
    segment's source onset is known, the slot is [start_ms, next_start_ms]: an over-running
    clip is trimmed to fit (so it can never delay the next segment) and a short clip is
    padded with trailing silence. Returns the cursor = next_start_ms, so drift cannot
    accumulate. The last segment (no next onset) simply pads to its window."""
    try:
        actual_ms = sf.info(str(final_file)).duration * 1000.0
    except Exception:
        actual_ms = float(end_ms - start_ms)

    if next_start_ms is not None:
        # The slot maths lives in _plan_anchored_block so that the unit tests and the
        # golden harness exercise the very code this path runs, not a copy of it.
        trim_ms, pad_ms = _plan_anchored_block(actual_ms, float(start_ms), float(next_start_ms))
        if trim_ms > 0:
            _trim_wav(final_file, actual_ms - trim_ms)   # trim to exactly fit the slot (+ fades)
        else:
            _apply_micro_fades(final_file)
        concat_list.append(f"file '{final_file}'")
        temp_files.append(str(final_file))
        if pad_ms > 20:
            sil = work_dir / f"fill_{tag}.wav"
            if create_silence_wav(pad_ms / 1000.0, str(sil), sr) and sil.exists():
                concat_list.append(f"file '{sil}'")
                temp_files.append(str(sil))
        return float(next_start_ms)

    # Last segment: no next onset to protect — pad to window, no trim.
    _apply_micro_fades(final_file)
    concat_list.append(f"file '{final_file}'")
    temp_files.append(str(final_file))
    pad_ms, cursor = _plan_block(actual_ms, float(start_ms), float(end_ms))
    if pad_ms > 20:
        sil = work_dir / f"fill_{tag}.wav"
        if create_silence_wav(pad_ms / 1000.0, str(sil), sr) and sil.exists():
            concat_list.append(f"file '{sil}'")
            temp_files.append(str(sil))
    return cursor


# S0 scope: the safe, unambiguous win is "never slow down" — shorter-than-window speech
# keeps its natural pace and the remainder is padded with silence instead of being dragged
# out into long vowels. The speed-up ceiling stays at the previous 2.5x so long translations
# still fit without truncation; tightening it toward ~1.25x is deferred to Phase S3, where
# LLM length-aware translation shortens over-long lines so tempo isn't the only lever.
STRETCH_MAX_SPEEDUP = 2.5


def calculate_speed_factor(original_duration: float, target_duration: float,
                           allow_slowdown: bool = True) -> float:
    """Return the atempo factor to fit `original_duration` into `target_duration`.
    ratio > 1 speeds up (speech longer than the window); ratio < 1 slows down.
    With allow_slowdown=False, never slows below natural speed (pad silence instead)
    and caps speed-up at STRETCH_MAX_SPEEDUP to avoid unnatural fast delivery."""
    if target_duration <= 0:
        return 1.0
    ratio = original_duration / target_duration
    if 0.95 <= ratio <= 1.05:
        return 1.0
    if not allow_slowdown:
        if ratio < 1.0:
            return 1.0                       # shorter than window → keep natural pace
        return min(ratio, STRETCH_MAX_SPEEDUP)
    return max(0.5, min(2.5, ratio))


def stretch_audio_smart(input_file: str, output_file: str, target_duration: float,
                        work_dir: Path, target_sr: int = 22050,
                        allow_slowdown: bool = True) -> bool:
    try:
        data, sr = sf.read(input_file, dtype='float32')
        current_duration = len(data) / sr
        if current_duration == 0:
            return False
        ratio = calculate_speed_factor(current_duration, target_duration, allow_slowdown)
        if ratio == 1.0:
            if sr != target_sr:
                subprocess.run([
                    "ffmpeg", "-y", "-i", input_file,
                    "-ar", str(target_sr), "-ac", "1", output_file
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            else:
                sf.write(output_file, data, sr, subtype='PCM_16')
            return True
        filter_chain = []
        remaining_ratio = ratio
        while remaining_ratio > 2.0:
            filter_chain.append("atempo=2.0")
            remaining_ratio /= 2.0
        while remaining_ratio < 0.5:
            filter_chain.append("atempo=0.5")
            remaining_ratio /= 0.5
        filter_chain.append(f"atempo={max(0.5, min(2.0, remaining_ratio)):.4f}")
        subprocess.run([
            "ffmpeg", "-y", "-i", input_file,
            "-filter:a", ",".join(filter_chain),
            "-ar", str(target_sr), "-ac", "1", output_file
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return True
    except Exception as e:
        _LOG.warning(f"Audio stretching failed: {e}, using original")
        try:
            subprocess.run([
                "ffmpeg", "-y", "-i", input_file,
                "-ar", str(target_sr), "-ac", "1", output_file
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            return True
        except Exception as e:
            _LOG.warning(f"Audio stretch fallback failed: {e}")
            return False


def reduce_noise(input_file: str, output_file: str) -> bool:
    try:
        data, rate = sf.read(input_file, dtype='float32')
        reduced_noise = nr.reduce_noise(y=data, sr=rate, stationary=True, prop_decrease=0.8)
        sf.write(output_file, reduced_noise, rate, subtype='PCM_16')
        return True
    except Exception as e:
        _LOG.warning(f"Noise reduction failed: {e}")
        try:
            sf.write(output_file, *sf.read(input_file))
        except Exception:
            shutil.copy(input_file, output_file)
        return False


def normalize_audio(input_file: str, output_file: str, target_level: float = -20.0) -> bool:
    """Two-pass EBU R128 loudness normalization (measure, then apply with measured stats
    for accurate linear correction). Falls back to single-pass, then to a plain copy."""
    base = f"loudnorm=I={target_level}:TP=-1.5:LRA=11"
    second = base
    try:
        p1 = subprocess.run(
            ["ffmpeg", "-y", "-i", input_file, "-af", base + ":print_format=json", "-f", "null", "-"],
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        m = re.search(r"\{[\s\S]*\}", p1.stderr or "")
        if m:
            s = json.loads(m.group(0))
            second = (f"{base}:measured_I={s['input_i']}:measured_TP={s['input_tp']}:"
                      f"measured_LRA={s['input_lra']}:measured_thresh={s['input_thresh']}:"
                      f"offset={s['target_offset']}:linear=true")
    except Exception as e:
        _LOG.debug(f"loudnorm measure pass failed, using single-pass: {e}")
    try:
        subprocess.run([
            "ffmpeg", "-y", "-i", input_file, "-af", second,
            "-ar", "44100", "-ac", "1", output_file
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return True
    except Exception as e:
        _LOG.warning(f"Audio normalization failed: {e}")
        shutil.copy(input_file, output_file)
        return False


async def generate_tts_edge(text: str, voice: str, output_file: str,
                            emotion: Optional[str] = None,
                            rate: str = "+0%",
                            has_emotion_support: bool = False) -> bool:
    try:
        if emotion and has_emotion_support and emotion in EMOTION_STYLES:
            communicate = edge_tts.Communicate(text, voice, rate=rate, style=emotion)
        else:
            communicate = edge_tts.Communicate(text, voice, rate=rate)
        await communicate.save(output_file)
        if _has_content(Path(output_file)):
            return True
        _LOG.warning("Edge TTS produced an empty file; retrying")
    except Exception as e:
        _LOG.error(f"Edge TTS failed: {e}")
    # Retry once without the emotion style (also covers the empty-output case).
    try:
        communicate = edge_tts.Communicate(text, voice, rate=rate)
        await communicate.save(output_file)
        if _has_content(Path(output_file)):
            return True
    except Exception as e:
        _LOG.debug(f"Edge TTS retry failed: {e}")
    return False


def parallel_translate(segments: List[Dict], target_lang: str, translator_type: str,
                       ollama_model: str, max_workers: int = 4,
                       llm_model: Optional[str] = None,
                       llm_api_key: Optional[str] = None) -> List[Dict]:
    def translate_segment(seg_data):
        idx, seg = seg_data
        text = seg['text'].strip()
        if not text:
            return idx, seg
        translated = translate_with_retry(text, target_lang, translator_type, ollama_model,
                                          llm_model=llm_model,
                                          llm_api_key=llm_api_key)
        return idx, {'text': translated, 'start': seg['start'], 'end': seg['end']}

    results = [None] * len(segments)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(translate_segment, (i, seg)): i
                   for i, seg in enumerate(segments)}
        for future in tqdm(as_completed(futures), total=len(segments),
                           desc="Translating", unit="segment"):
            try:
                idx, translated_seg = future.result()
                results[idx] = translated_seg
            except Exception as e:
                _LOG.error(f"Translation failed: {e}")
    return [r for r in results if r is not None]


async def synthesize_speech_batch(subs, voice: str, work_dir: Path,
                                  enable_stretch: bool, emotion_detection: bool,
                                  rate_adjust: bool, has_emotion_support: bool = False,
                                  quality_gate: bool = False, asr_model=None,
                                  gate_lang=None) -> Tuple[List[str], List[str]]:
    """Speech via Microsoft Edge voices. Timeline, placement and scoring come from
    synthesize_timeline; this only turns one line of text into one WAV."""
    concat_list, temp_files = [], []
    target_sr = 44100
    emotion_stats: Dict[str, int] = {}

    async def _render(i, txt, final_file, target_duration):
        raw_file = work_dir / f"edge_raw_{i}.mp3"
        wav_file = work_dir / f"edge_cnv_{i}.wav"

        emotion = None
        if emotion_detection and has_emotion_support:
            emotion = detect_emotion(txt)
            if emotion:
                emotion_stats[emotion] = emotion_stats.get(emotion, 0) + 1

        rate = "+0%"
        if rate_adjust and target_duration > 0:
            words = len(txt.split())
            estimated_duration = (words / 150) * 60
            if estimated_duration > 0:
                rate_factor = max(-0.5, min(0.5, (estimated_duration / target_duration) - 1))
                rate = f"{rate_factor * 100:+.0f}%"

        if not _has_content(raw_file):
            if not await generate_tts_edge(txt, voice, str(raw_file), emotion, rate,
                                           has_emotion_support):
                return False
        temp_files.append(str(raw_file))

        if not _has_content(wav_file):
            run_ffmpeg(["ffmpeg", "-y", "-i", str(raw_file),
                        "-ar", str(target_sr), "-ac", "1", str(wav_file)],
                       f"Segment {i} MP3 to WAV conversion")
        temp_files.append(str(wav_file))

        # S0: no noise reduction on clean synthetic speech - stationary NR on a clean
        # TTS signal only risks musical-noise artifacts. Fit straight from the WAV.
        return _fit_to_window(wav_file, final_file, target_duration, work_dir,
                              target_sr, enable_stretch)

    await synthesize_timeline(
        subs, engine="edge", prefix="edge", sample_rate=target_sr, work_dir=work_dir,
        concat_list=concat_list, temp_files=temp_files, render=_render,
        text_of=lambda s: normalize_tts_text(s.text),
        desc="Edge TTS", unit="sentence", min_bytes=100,
        quality_gate=quality_gate, asr_model=asr_model, gate_lang=gate_lang)

    if emotion_stats:
        _LOG.info(f"🎭 Emotion usage: {emotion_stats}")
    return concat_list, temp_files
def transcribe_audio(audio_path: str, model_name: str, backend: str, device: str) -> Tuple[List[Dict], str]:
    """Transcribe audio and return (segments, detected_language). `segments` is a list
    of dicts each having at least 'start', 'end', 'text' — normalized across backends.
    backend: 'openai' (openai-whisper, default) or 'faster' (faster-whisper)."""
    if backend == "faster":
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            raise RuntimeError("faster-whisper not installed. Run: pip install 'voxa[faster]'")
        compute_type = "float16" if device == "cuda" else "int8"
        # faster-whisper names the turbo model 'large-v3-turbo'.
        fw_model = "large-v3-turbo" if model_name == "turbo" else model_name
        model = WhisperModel(fw_model, device=device, compute_type=compute_type)
        # vad_filter drops non-speech regions (music/silence intros) at the source;
        # word_timestamps give an accurate speech onset per segment (see _refine_bounds).
        seg_iter, info = model.transcribe(audio_path, vad_filter=True, word_timestamps=True)
        segments = []
        for s in seg_iter:
            words = [(w.start, w.end) for w in (getattr(s, "words", None) or [])]
            start, end = _refine_bounds(s.start, s.end, words)
            segments.append({"start": start, "end": end, "text": s.text,
                             "no_speech_prob": getattr(s, "no_speech_prob", 0.0)})
        return segments, getattr(info, "language", "unknown")

    # Default: openai-whisper. Loads a trusted local checkpoint (weights_only scoped).
    with _allow_unsafe_torch_load():
        model = whisper.load_model(model_name, device=device)
    result = model.transcribe(audio_path, fp16=(device == "cuda"), verbose=False,
                              word_timestamps=True)
    for seg in result["segments"]:
        words = [(w["start"], w["end"]) for w in (seg.get("words") or [])]
        seg["start"], seg["end"] = _refine_bounds(seg["start"], seg["end"], words)
    # openai-whisper segments already carry no_speech_prob for downstream filtering.
    return result["segments"], result.get("language", "unknown")


def _refine_bounds(seg_start: float, seg_end: float, words) -> Tuple[float, float]:
    """Tighten a segment to its first/last word onset. Word timestamps are far more
    accurate than Whisper's coarse segment bounds — especially the first segment after a
    non-speech intro, where the segment start is often placed too early (causing the dub
    to begin before the original speech). `words` is a list of (start, end) tuples."""
    if words:
        return words[0][0], words[-1][1]
    return seg_start, seg_end


def filter_nonspeech_segments(segments: List[Dict], threshold: float = 0.6) -> List[Dict]:
    """Drop segments Whisper itself flags as likely non-speech (no_speech_prob > threshold)
    — the music/silence intro it transcribed as phantom text. threshold >= 1.0 disables."""
    if threshold >= 1.0:
        return segments
    kept = [s for s in segments if s.get("no_speech_prob", 0.0) <= threshold]
    dropped = len(segments) - len(kept)
    if dropped:
        _LOG.info(f"🔇 Dropped {dropped} non-speech segment(s) "
                     f"(no_speech_prob > {threshold}) — likely music/intro phantom text")
    return kept


# ─────────────────────────────────────────────
#  Speech quality gate (S1) — measure synthesized segments
# ─────────────────────────────────────────────

_COMPARE_RE = re.compile(r"[^\w\s]", re.UNICODE)
_gate_asr_model = None
_gate_asr_name = None


def _normalize_for_compare(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace — for ASR round-trip comparison."""
    return _TTS_WS_RE.sub(" ", _COMPARE_RE.sub(" ", (text or "").lower())).strip()


def _edit_distance(a: List[str], b: List[str]) -> int:
    """Levenshtein distance between two token sequences."""
    m, n = len(a), len(b)
    if m == 0:
        return n
    dp = list(range(n + 1))
    for i in range(1, m + 1):
        prev, dp[0] = dp[0], i
        for j in range(1, n + 1):
            prev, dp[j] = dp[j], min(dp[j] + 1, dp[j - 1] + 1, prev + (a[i - 1] != b[j - 1]))
    return dp[n]


def word_error_rate(reference: str, hypothesis: str) -> float:
    """Token-level WER of an ASR transcript vs the text we asked the TTS to speak.
    A high value flags hallucination / wrong pronunciation / truncation."""
    ref = _normalize_for_compare(reference).split()
    hyp = _normalize_for_compare(hypothesis).split()
    if not ref:
        return 0.0 if not hyp else 1.0
    return _edit_distance(ref, hyp) / len(ref)


def _clipping_ratio(data) -> float:
    return float(np.mean(np.abs(data) >= 0.999)) if len(data) else 0.0


def _silence_ratio(data, thresh: float = 1e-3) -> float:
    return float(np.mean(np.abs(data) < thresh)) if len(data) else 1.0


def _get_gate_asr(model_name: str = "tiny"):
    """Load a faster-whisper model once for the round-trip check (None if absent).
    A bigger model gives reliable WER for low-resource languages (tiny mis-transcribes
    e.g. Azerbaijani even when the speech is correct → false positives)."""
    global _gate_asr_model, _gate_asr_name
    if _gate_asr_model is not None and _gate_asr_name == model_name:
        return _gate_asr_model
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        _LOG.warning("Quality gate needs faster-whisper (pip install 'voxa[faster]'); "
                        "scoring without ASR round-trip")
        return None
    device = "cuda" if (torch is not None and torch.cuda.is_available()) else "cpu"
    _gate_asr_model = WhisperModel(model_name, device=device,
                                   compute_type="float16" if device == "cuda" else "int8")
    _gate_asr_name = model_name
    return _gate_asr_model


def score_speech(audio_path: str, expected_text: str, *, asr_model=None, lang=None,
                 wer_thresh: float = 0.6, clip_thresh: float = 0.02,
                 silence_thresh: float = 0.6) -> Dict:
    """Score one synthesized clip. Returns {ok, reasons, dur, clip, silence, cps[, wer]}.
    Reasons are the failed checks (empty = passed). ASR round-trip is skipped if no model."""
    result: Dict = {"ok": True, "reasons": []}
    try:
        data, sr = sf.read(audio_path, dtype="float32")
    except Exception:
        return {"ok": False, "reasons": ["unreadable"], "wer": 1.0}
    if data.ndim > 1:
        data = data[:, 0]
    dur = len(data) / sr if sr else 0.0
    result["dur"] = round(dur, 2)
    result["clip"] = round(_clipping_ratio(data), 4)
    result["silence"] = round(_silence_ratio(data), 3)
    exp = _normalize_for_compare(expected_text)
    result["cps"] = round(len(exp) / dur, 1) if dur > 0 else 0.0
    if result["clip"] > clip_thresh:
        result["reasons"].append("clipping")
    if result["silence"] > silence_thresh:
        result["reasons"].append("mostly_silence")
    if dur < 0.1:
        result["reasons"].append("too_short")
    if asr_model is not None and exp:
        try:
            segs, _ = asr_model.transcribe(audio_path, language=lang)
            wer = word_error_rate(expected_text, " ".join(s.text for s in segs))
            result["wer"] = round(wer, 2)
            if wer > wer_thresh:
                result["reasons"].append("asr")
        except Exception as e:
            _LOG.debug(f"gate ASR failed: {e}")
    result["ok"] = not result["reasons"]
    return result


def _log_sync_drift(max_drift_ms: float, engine: str):
    """Pillar-0 diagnostic: report the worst point at which a segment was placed later
    than its source onset (accumulated timeline drift). > ~400ms is audibly out of sync."""
    if max_drift_ms > 1:
        level = _LOG.warning if max_drift_ms > 400 else _LOG.info
        level(f"⏱️  {engine}: max sync drift {max_drift_ms:.0f}ms")


def log_quality_report(scores: List[Dict], engine: str):
    """Log a per-job speech-quality summary from collected per-segment scores."""
    if not scores:
        return
    n = len(scores)
    flagged = [s for s in scores if not s["ok"]]
    wers = [s["wer"] for s in scores if "wer" in s]
    avg_wer = f", avg WER {sum(wers) / len(wers):.2f}" if wers else ""
    _LOG.info(f"🔎 Quality report ({engine}): {n} segments, {len(flagged)} flagged{avg_wer}")
    for idx, s in enumerate(scores):
        if not s["ok"]:
            _LOG.info(f"   ⚠️  segment {idx}: {', '.join(s['reasons'])} "
                         f"(dur {s.get('dur')}s, wer {s.get('wer', 'n/a')})")
    if n and len(flagged) / n > 0.10:
        _LOG.warning(f"⚠️  {len(flagged)}/{n} segments flagged — check reference/voice/language")


# ── TTS provider registry ────────────────────────────────────────────────────
# Mirrors LLM_PROVIDERS: each engine is a small adapter that performs its own
# setup (voice lookup / model load / client / language check) and returns
# (concat_list, temp_files). Adding a new engine = one adapter + one registry
# line. Adapters raise TTSError on an unrecoverable setup failure; the dispatch
# in process_video logs it and aborts. All adapters share one signature and are
# async so the dispatch is uniform (edge is natively async; the others simply
# don't await — identical to the previous inline calls).
class TTSError(Exception):
    """Raised by a TTS adapter when speech synthesis cannot proceed."""


async def _tts_edge(subs, args, work_dir, video_path, gate_asr, logger):
    logger.info(f"🔎 Finding voice for: {args.target_lang}")
    voice, has_emotions = await get_edge_voice(args.target_lang)
    logger.info(f"🎙️  Selected: {voice} (Emotions: {'Yes' if has_emotions else 'No'})")
    return await synthesize_speech_batch(
        subs, voice, work_dir,
        enable_stretch=not args.no_stretch,
        emotion_detection=args.detect_emotion,
        rate_adjust=args.auto_rate,
        has_emotion_support=has_emotions,
        quality_gate=args.quality_gate, asr_model=gate_asr,
        gate_lang=args.target_lang[:2].lower()
    )


async def _tts_piper(subs, args, work_dir, video_path, gate_asr, logger):
    logger.info(f"🔎 Loading Piper model for: {args.target_lang}")
    model_path = download_piper_model(args.target_lang, Path.home() / ".piper_models")
    if not model_path:
        raise TTSError("Failed to download Piper model")
    logger.info("🎙️  Using Piper (offline mode)")
    concat_list, temp_files = [], []
    await generate_piper(subs, model_path, concat_list, temp_files, work_dir,
                   enable_stretch=not args.no_stretch,
                   lang_code=args.target_lang[:2].lower(),
                   quality_gate=args.quality_gate, asr_model=gate_asr)
    return concat_list, temp_files


async def _tts_xtts(subs, args, work_dir, video_path, gate_asr, logger):
    # ── XTTS voice cloning ───────────────────────────
    lang_code = args.target_lang[:2].lower()
    if lang_code not in XTTS_SUPPORTED_LANGS:
        raise TTSError(f"❌ XTTS does not support language '{lang_code}'. "
                       f"Supported: {sorted(XTTS_SUPPORTED_LANGS)}")

    # Determine speaker reference wav
    speaker_wav = args.voice_sample
    if not speaker_wav:
        # Auto-extract from source video
        auto_sample = work_dir / "auto_voice_sample.wav"
        if not auto_sample.exists():
            logger.info("🎤 No --voice-sample provided, extracting from source video...")
            if not extract_voice_sample(str(video_path), str(auto_sample)):
                raise TTSError("Failed to extract voice sample")
        speaker_wav = str(auto_sample)
    else:
        if not Path(speaker_wav).exists():
            raise TTSError(f"❌ Voice sample not found: {speaker_wav}")
        logger.info(f"🎤 Using provided voice sample: {speaker_wav}")

    # Load model
    tts_model = load_xtts_model()
    if tts_model is None:
        raise TTSError("Failed to load XTTS model")

    concat_list, temp_files = [], []
    await generate_xtts(
        subs, tts_model, speaker_wav, lang_code,
        concat_list, temp_files, work_dir,
        enable_stretch=not args.no_stretch,
        quality_gate=args.quality_gate, asr_model=gate_asr
    )
    return concat_list, temp_files


async def _tts_openai(subs, args, work_dir, video_path, gate_asr, logger):
    base_url = getattr(args, "openai_tts_base_url", None)
    client = get_openai_client(args.openai_api_key, base_url)
    if client is None:
        raise TTSError("OpenAI TTS requires an API key (OPENAI_API_KEY or --openai_api_key), "
                       "or an --openai-tts-base-url pointing at a compatible server")
    where = base_url or "api.openai.com"
    logger.info(f"🎙️  OpenAI TTS: {args.openai_tts_model} / voice '{args.openai_voice}' "
                f"@ {where}")
    concat_list, temp_files = [], []
    await generate_openai_tts(
        subs, client, args.openai_voice, args.openai_tts_model,
        args.openai_tts_instructions, args.target_lang[:2].lower(),
        concat_list, temp_files, work_dir,
        enable_stretch=not args.no_stretch,
        quality_gate=args.quality_gate, asr_model=gate_asr,
        emotion_detection=args.detect_emotion
    )
    return concat_list, temp_files


TTS_PROVIDERS: Dict[str, Dict] = {
    "edge":   {"synthesize": _tts_edge},
    "piper":  {"synthesize": _tts_piper},
    "xtts":   {"synthesize": _tts_xtts},
    "openai": {"synthesize": _tts_openai},
}


async def process_video(video_path: str, args, logger: Logger):
    """Main video processing pipeline"""
    video_path = Path(video_path)
    video_basename = video_path.stem
    work_dir = Path.cwd() / f"{video_basename}_work"
    work_dir.mkdir(exist_ok=True)
    logger.info(f"📂 Workspace: {work_dir}")

    state = StateManager(work_dir)
    if not args.resume:
        logger.info("♻️  --no-resume: ignoring previous checkpoint, starting fresh")
        state.state['steps_completed'] = []
        state.save_state()

    # Resume validation: invalidate the checkpoint if the source video changed
    # (guards against reusing stale results for a different video with the same name).
    try:
        vstat = video_path.stat()
        video_sig = f"{vstat.st_size}:{int(vstat.st_mtime)}"
    except OSError:
        video_sig = None
    if video_sig and state.state.get('input_sig') not in (None, video_sig):
        logger.info("🔄 Source video changed since last run — restarting pipeline from scratch")
        state.state['steps_completed'] = []
    if video_sig:
        state.state['input_sig'] = video_sig
        state.save_state()

    audio_wav       = work_dir / "original_audio.wav"
    audio_clean     = work_dir / "audio_clean.wav"
    transcript_json = work_dir / "transcript.json"
    merged_json     = work_dir / "merged_sentences.json"
    translated_json = work_dir / "translated.json"
    srt_file        = work_dir / f"subtitles_{args.target_lang}.srt"
    concat_list_file= work_dir / "concat_list.txt"
    voiceover_wav   = work_dir / "voiceover.wav"
    voiceover_norm  = work_dir / "voiceover_normalized.wav"
    out_dir = Path(args.output_dir) if args.output_dir else Path.cwd()
    out_dir.mkdir(parents=True, exist_ok=True)
    output_file     = out_dir / f"{video_basename}_dubbed_{args.target_lang}.mp4"

    start_time = time.time()

    # Step 1: Extract audio
    if state.is_completed('extract_audio') and audio_wav.exists():
        logger.info("[1/7] ✓ Audio extraction already completed")
    else:
        logger.info("[1/7] Extracting audio...")
        run_ffmpeg([
            "ffmpeg", "-y", "-i", str(video_path),
            "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", str(audio_wav)
        ], "Audio extraction")
        state.mark_completed('extract_audio')

    # Step 2: Audio enhancement
    if state.is_completed('audio_enhancement') and audio_clean.exists():
        logger.info("[2/7] ✓ Audio enhancement already completed")
    else:
        logger.info("[2/7] Enhancing audio (noise reduction)...")
        reduce_noise(str(audio_wav), str(audio_clean))
        state.mark_completed('audio_enhancement')

    # Step 3: Transcription
    segments = []
    if state.is_completed('transcription') and transcript_json.exists():
        logger.info("[3/7] ✓ Transcription already completed")
        with open(transcript_json, 'r', encoding='utf-8') as f:
            segments = json.load(f)
    else:
        logger.info(f"[3/7] Transcribing with Whisper ({args.whisper_model}, "
                    f"backend: {args.whisper_backend})...")
        device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"⚙️  Using device: {device.upper()}")
        try:
            segments, detected_lang = transcribe_audio(
                str(audio_clean), args.whisper_model, args.whisper_backend, device)
            logger.info(f"🌍 Detected language: {detected_lang}")
            with open(transcript_json, 'w', encoding='utf-8') as f:
                json.dump(segments, f, ensure_ascii=False, indent=2)
            state.mark_completed('transcription')
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return 1

    # Transcription hygiene: drop non-speech (music/intro) segments Whisper hallucinated,
    # so the dub doesn't speak over the source's silent/intro sections.
    segments = filter_nonspeech_segments(segments, args.no_speech_threshold)

    # Step 4: Merge into sentences
    merged_segments = []
    if state.is_completed('merge_sentences') and merged_json.exists():
        logger.info("[4/7] ✓ Sentence merging already completed")
        with open(merged_json, 'r', encoding='utf-8') as f:
            merged_segments = json.load(f)
    else:
        logger.info("[4/7] Merging segments into sentences...")
        merged_segments = merge_segments_into_sentences(segments, args.max_sentence_duration)
        logger.info(f"✨ Merged {len(segments)} segments → {len(merged_segments)} sentences")
        with open(merged_json, 'w', encoding='utf-8') as f:
            json.dump(merged_segments, f, ensure_ascii=False, indent=2)
        state.mark_completed('merge_sentences')

    # Step 5: Translation
    translated_segments = []
    if state.is_completed('translation') and translated_json.exists():
        logger.info("[5/7] ✓ Translation already completed")
        with open(translated_json, 'r', encoding='utf-8') as f:
            translated_segments = json.load(f)
    else:
        logger.info(f"[5/7] Translating to {args.target_lang} with {args.translator}...")
        if args.translator in LLM_PROVIDERS:
            llm_model = getattr(args, f"{args.translator}_model")
            llm_api_key = getattr(args, f"{args.translator}_api_key")
            logger.info(f"🤖 Context-aware {args.translator} batch translation "
                        f"(model: {llm_model}, batch: {args.llm_batch_size})")
            indexed = [seg for seg in merged_segments if seg['text'].strip()]
            texts = [seg['text'].strip() for seg in indexed]
            # SY3: length-budget each line to its source duration so the dub fits at a
            # natural pace (isochrony) — minimizes downstream time-stretch and trimming.
            max_chars = [_duration_to_max_chars(max(0.0, seg['end'] - seg['start']),
                                                args.speech_rate) for seg in indexed]
            translated_texts = translate_llm_batch(
                texts, args.target_lang, args.translator, model=llm_model,
                api_key=llm_api_key, batch_size=args.llm_batch_size, max_chars=max_chars
            )
            translated_segments = [
                {'text': tt or seg['text'].strip(), 'start': seg['start'], 'end': seg['end']}
                for seg, tt in zip(indexed, translated_texts)
            ]
            log_llm_usage_summary(args.translator, llm_model)
        elif args.parallel and len(merged_segments) > 10:
            logger.info("🚀 Using parallel translation")
            translated_segments = parallel_translate(
                merged_segments, args.target_lang, args.translator,
                args.ollama_model, max_workers=args.workers
            )
        else:
            translated_segments = []
            for seg in tqdm(merged_segments, desc="Translating", unit="segment"):
                text = seg['text'].strip()
                if not text:
                    continue
                translated = translate_with_retry(text, args.target_lang, args.translator, args.ollama_model)
                translated_segments.append({'text': translated, 'start': seg['start'], 'end': seg['end']})
        with open(translated_json, 'w', encoding='utf-8') as f:
            json.dump(translated_segments, f, ensure_ascii=False, indent=2)
        state.mark_completed('translation')

    # Generate SRT
    with open(srt_file, 'w', encoding='utf-8') as f:
        for i, seg in enumerate(translated_segments):
            f.write(f"{i+1}\n")
            f.write(f"{format_timestamp(seg['start'])} --> {format_timestamp(seg['end'])}\n")
            f.write(f"{seg['text']}\n\n")

    # Subtitles-only mode: stop after producing the translated SRT (no TTS / no video).
    if args.subtitles_only:
        final_srt = out_dir / srt_file.name
        if final_srt.resolve() != srt_file.resolve():
            shutil.copy(str(srt_file), str(final_srt))
        elapsed_time = time.time() - start_time
        logger.info(f"✅ Subtitles-only completed in {elapsed_time/60:.1f} minutes!")
        logger.info(f"📝 Subtitles: {final_srt}")
        return 0

    # Step 6: Speech synthesis
    if state.is_completed('synthesis') and voiceover_norm.exists():
        logger.info("[6/7] ✓ Speech synthesis already completed")
    else:
        logger.info("[6/7] Synthesizing speech...")
        subs = read_srt(srt_file)
        gate_asr = _get_gate_asr(args.gate_model) if args.quality_gate else None

        spec = TTS_PROVIDERS.get(args.tts)
        if spec is None:
            logger.error(f"Unknown TTS engine: {args.tts}")
            return 1
        try:
            concat_list, temp_files = await spec["synthesize"](
                subs, args, work_dir, video_path, gate_asr, logger)
        except TTSError as exc:
            logger.error(str(exc))
            return 1

        if not concat_list:
            logger.error("No audio generated!")
            return 1

        with open(concat_list_file, 'w') as f:
            f.write('\n'.join(concat_list))

        # Verify files
        missing_files = [
            line[6:-1] for line in concat_list
            if line.startswith("file '") and not Path(line[6:-1]).exists()
        ]
        if missing_files:
            logger.warning(f"⚠️  {len(missing_files)} audio files missing, removing from list")
            valid_list = [line for line in concat_list
                         if not any(m in line for m in missing_files)]
            with open(concat_list_file, 'w') as f:
                f.write('\n'.join(valid_list))

        logger.info("🔗 Concatenating audio segments...")
        subprocess.run([
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", str(concat_list_file), "-c", "copy", str(voiceover_wav)
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

        logger.info("📊 Normalizing audio levels...")
        normalize_audio(str(voiceover_wav), str(voiceover_norm), target_level=-16.0)
        state.mark_completed('synthesis')

    # Step 7: Final video assembly
    logger.info("[7/7] Assembling final video...")
    run_ffmpeg([
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-i", str(voiceover_norm),
        "-filter_complex",
        f"[0:a]volume={args.background_volume}[bg];[1:a]volume={args.voice_volume}[fg];"
        f"[bg][fg]amix=inputs=2:duration=first:dropout_transition=2",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-map", "0:v:0",
        str(output_file)
    ], "Final video assembly")

    if not args.keep_temp:
        logger.info("🧹 Cleaning up temporary files...")
        for pattern in ['*_raw.*', 'silence_*.wav', 'xtts_sil_*.wav', 'speech_*_processed.*']:
            for f in work_dir.glob(pattern):
                f.unlink(missing_ok=True)

    elapsed_time = time.time() - start_time
    logger.info(f"✅ Completed in {elapsed_time/60:.1f} minutes!")
    logger.info(f"📹 Output: {output_file}")
    logger.info(f"📁 Working files: {work_dir}")
    return 0


async def batch_process(video_files: List[str], args, logger: Logger):
    logger.info(f"🎬 Batch processing {len(video_files)} videos")
    results = []
    for i, video in enumerate(video_files, 1):
        logger.info(f"\n{'='*60}\nProcessing video {i}/{len(video_files)}: {video}\n{'='*60}\n")
        try:
            result = await process_video(video, args, logger)
            results.append((video, result == 0))
        except Exception as e:
            logger.error(f"Failed to process {video}: {e}")
            results.append((video, False))

    success_count = sum(1 for _, s in results if s)
    logger.info(f"\n{'='*60}\nBATCH SUMMARY\n{'='*60}")
    logger.info(f"✅ Successful: {success_count}/{len(results)}")
    if success_count < len(results):
        for video, success in results:
            if not success:
                logger.info(f"  ❌ {video}")


async def main():
    parser = argparse.ArgumentParser(
        description="Voxa v1.0 — Professional Video Dubbing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage
  python voxa.py video.mp4 --target_lang ru

  # High quality with all enhancements
  python voxa.py video.mp4 --target_lang es --whisper_model large --detect-emotion --auto-rate

  # XTTS voice cloning (clone voice from source video automatically)
  python voxa.py video.mp4 --target_lang ru --tts xtts

  # XTTS with custom voice reference
  python voxa.py video.mp4 --target_lang ru --tts xtts --voice-sample my_voice.wav

  # Batch processing
  python voxa.py video1.mp4 video2.mp4 --target_lang fr --parallel

  # Subtitles only
  python voxa.py video.mp4 --target_lang de --subtitles-only
        """
    )

    parser.add_argument("videos", nargs="+", help="Input video file(s)")
    parser.add_argument("--target_lang", default="ru", help="Target language code (default: ru)")
    parser.add_argument("--output-dir", help="Output directory (default: current directory)")

    parser.add_argument("--whisper_model", default="turbo",
                        choices=["tiny", "base", "small", "medium", "large", "turbo"],
                        help="Whisper model size (default: turbo)")
    parser.add_argument("--whisper-backend", choices=["openai", "faster"], default="openai",
                        help="Transcription engine: openai (openai-whisper, default) or "
                             "faster (faster-whisper — 2-4x faster; pip install 'voxa[faster]')")
    parser.add_argument("--no-speech-threshold", type=float, default=0.6,
                        help="Drop transcription segments whose no_speech_prob exceeds this "
                             "(0-1) — removes music/intro that Whisper transcribed as phantom "
                             "text. Set 1.0 to disable.")
    parser.add_argument("--quality-gate", action="store_true",
                        help="Score each synthesized segment (ASR round-trip via faster-whisper "
                             "+ artifact/pacing checks) and log a per-job quality report")
    parser.add_argument("--gate-model", default="tiny",
                        help="faster-whisper model for the quality gate's ASR round-trip "
                             "(default: tiny; use base/small/medium for low-resource languages)")

    parser.add_argument("--translator", choices=["google", "ollama"] + sorted(LLM_PROVIDERS),
                        default="google", help="Translation service (default: google)")
    parser.add_argument("--ollama_model", default="llama3",
                        help="Ollama model for translation (default: llama3)")
    # Per-provider LLM flags (--openai_model/--openai_api_key, --anthropic_model/...).
    for _pname, _pinfo in LLM_PROVIDERS.items():
        parser.add_argument(f"--{_pname}_model", default=_pinfo["default_model"],
                            help=f"{_pname} model (default: {_pinfo['default_model']})")
        parser.add_argument(f"--{_pname}_api_key", default=None,
                            help=f"{_pname} API key (falls back to {_pinfo['env_key']} env var)")
    parser.add_argument("--llm_batch_size", type=int, default=DEFAULT_LLM_BATCH_SIZE,
                        help=f"Subtitle lines translated together per LLM call for context "
                             f"(default: {DEFAULT_LLM_BATCH_SIZE})")
    parser.add_argument("--speech-rate", type=float, default=DEFAULT_SPEECH_RATE_CPS,
                        help=f"Assumed speaking rate in characters/second used to length-budget "
                             f"LLM translations for dub timing (default: {DEFAULT_SPEECH_RATE_CPS}). "
                             f"Higher = allow longer translations (faster delivery).")
    parser.add_argument("--parallel", action="store_true",
                        help="Translate segments in parallel threads (google/ollama only — "
                             "LLM translators already batch whole blocks in one call)")
    parser.add_argument("--workers", type=int, default=4,
                        help="Number of parallel workers (default: 4)")

    parser.add_argument("--tts", choices=sorted(TTS_PROVIDERS), default="edge",
                        help="TTS engine: edge (online), piper (offline), xtts (cloning), "
                             "openai (multilingual, instructable — best for languages XTTS "
                             "can't do, e.g. az)")
    parser.add_argument("--openai-voice", default="alloy",
                        help="OpenAI TTS voice (alloy, echo, fable, onyx, nova, shimmer, "
                             "ash, ballad, coral, sage, verse)")
    parser.add_argument("--openai-tts-model", default="gpt-4o-mini-tts",
                        help="OpenAI TTS model (default: gpt-4o-mini-tts)")
    parser.add_argument("--openai-tts-base-url", default=os.environ.get("OPENAI_TTS_BASE_URL"),
                        help="Send speech requests to an OpenAI-compatible server instead of "
                             "OpenAI (e.g. http://localhost:8004/v1 for Chatterbox-TTS-Server "
                             "or LocalAI). No API key is required. Translation still uses "
                             "OpenAI unless you change --translator")
    parser.add_argument("--openai-tts-instructions",
                        default="Speak naturally and clearly at a steady, even pace that "
                                "matches the natural rhythm of speech. Do not slow down or "
                                "add pauses.",
                        help="Delivery instructions for gpt-4o-mini-tts")
    parser.add_argument("--voice-sample", type=str, default=None,
                        help="Path to reference WAV for XTTS voice cloning (optional, "
                             "auto-extracted from source video if not provided)")

    parser.add_argument("--no-stretch", action="store_true",
                        help="Disable audio time-stretching")
    parser.add_argument("--detect-emotion", action="store_true",
                        help="Expressive delivery: edge TTS voice styles, and for OpenAI TTS "
                             "an LLM tags each line with a delivery direction (A2 T1)")
    parser.add_argument("--auto-rate", action="store_true",
                        help="Auto adjust TTS rate")
    parser.add_argument("--background-volume", type=float, default=0.05,
                        help="Original audio volume (0.0-1.0, default: 0.05 — keeps the "
                             "source as a faint ambience bed ~35 dB under the dub, so the "
                             "original speech is not intelligible; raise toward 0.15 to "
                             "hear more of the original, 0.0 to mute it entirely)")
    parser.add_argument("--voice-volume", type=float, default=1.5,
                        help="Dubbed voice volume (0.0-2.0, default: 1.5)")

    parser.add_argument("--max_sentence_duration", type=float, default=10.0,
                        help="Max sentence duration in seconds (default: 10.0)")
    parser.add_argument("--keep-temp", action="store_true",
                        help="Keep temporary files")
    parser.add_argument("--subtitles-only", action="store_true",
                        help="Generate only subtitles")
    parser.add_argument("--verbose", action="store_true",
                        help="Enable verbose (DEBUG-level) logging")
    parser.add_argument("--log-format", choices=["plain", "json"], default="plain",
                        help="Log output format (default: plain)")
    parser.add_argument("--config", default=None,
                        help="JSON config file providing default option values "
                             "(argparse dest names, e.g. {\"translator\": \"openai\"})")
    parser.add_argument("--env-file", default=".env",
                        help="Path to a .env file with API keys (default: .env)")
    parser.add_argument("--resume", action=argparse.BooleanOptionalAction, default=True,
                        help="Resume from checkpoint (use --no-resume to force a fresh run)")

    # First pass: peek at --config so its values become argparse defaults
    # (explicit CLI flags still override them on the final parse).
    pre_args, _ = parser.parse_known_args()
    if pre_args.config:
        cfg = load_config_defaults(pre_args.config)
        known = {a.dest for a in parser._actions}
        parser.set_defaults(**{k: v for k, v in cfg.items() if k in known})
    args = parser.parse_args()

    # Load API keys / settings from a .env file (existing env vars take precedence).
    load_dotenv(args.env_file)

    # Ensure runtime dependencies are present, then apply library patches.
    if not _check_runtime_deps():
        return 1
    _apply_runtime_patches()

    # Fail fast if an LLM translator is selected but no API key is available.
    if args.translator in LLM_PROVIDERS:
        _pinfo = LLM_PROVIDERS[args.translator]
        _key = getattr(args, f"{args.translator}_api_key") or os.environ.get(_pinfo["env_key"])
        if not _key:
            print(f"❌ {args.translator} translator selected but no API key found.\n"
                  f"   Set {_pinfo['env_key']} or pass --{args.translator}_api_key.")
            return 1

    # --parallel is only wired into the google/ollama path; say so instead of silently
    # ignoring it (LLM translators take the batch branch before --parallel is consulted).
    if args.parallel and args.translator in LLM_PROVIDERS:
        print(f"ℹ️  --parallel is ignored with the {args.translator} translator: "
              f"lines are already translated in context-aware batches.")

    # Fail fast if OpenAI TTS is selected with neither a key nor a self-hosted endpoint.
    if (args.tts == "openai"
            and not (args.openai_api_key or os.environ.get("OPENAI_API_KEY"))
            and not args.openai_tts_base_url):
        print("❌ OpenAI TTS selected but no API key found.\n"
              "   Set OPENAI_API_KEY or pass --openai_api_key,\n"
              "   or point --openai-tts-base-url at a compatible server (no key needed).")
        return 1

    # Preflight: fail before creating a workspace or loading a model, so a typo in a
    # filename or a missing FFmpeg produces a readable error and leaves no stray folder.
    if not _check_external_tools():
        return 1
    if not _check_input_videos(args.videos):
        return 1

    first_video = Path(args.videos[0])
    work_dir = Path.cwd() / f"{first_video.stem}_work"
    work_dir.mkdir(exist_ok=True)
    logger = Logger(work_dir,
                    level=logging.DEBUG if args.verbose else logging.INFO,
                    json_format=(args.log_format == "json"))

    logger.info("╔════════════════════════════════════════════════════════╗")
    logger.info("║" + " " * 15 + "Voxa v1.0 - Configuration" + " " * 16 + "║")
    logger.info("╚════════════════════════════════════════════════════════╝")
    logger.info(f"📹 Videos: {len(args.videos)}")
    logger.info(f"🌍 Target Language: {args.target_lang}")
    logger.info(f"🎙️  TTS Engine: {args.tts}")
    if args.tts == "xtts":
        logger.info(f"🎤 Voice Sample: {args.voice_sample or 'auto-extract from video'}")
    logger.info(f"🔤 Translator: {args.translator}")
    if args.translator in LLM_PROVIDERS:
        logger.info(f"🤖 {args.translator} Model: {getattr(args, f'{args.translator}_model')}")
    logger.info(f"🧠 Whisper Model: {args.whisper_model}")
    if args.translator in LLM_PROVIDERS:
        # --parallel never reaches an LLM translator: context-aware batch translation
        # handles the whole block in one call and takes that branch first.
        logger.info("⚡ Parallel Processing: n/a (context-aware batch translation)")
    else:
        logger.info(f"⚡ Parallel Processing: {'Yes' if args.parallel else 'No'}")
    logger.info(f"🎭 Emotion Detection: {'Yes' if args.detect_emotion else 'No'}")
    logger.info(f"📈 Auto Rate Adjust: {'Yes' if args.auto_rate else 'No'}")
    logger.info(f"🎵 Audio Stretching: {'Yes' if not args.no_stretch else 'No'}")
    logger.info("")

    try:
        if len(args.videos) > 1:
            await batch_process(args.videos, args, logger)
        else:
            await process_video(args.videos[0], args, logger)
        return 0
    except KeyboardInterrupt:
        logger.info("\n⚠️  Process interrupted by user")
        return 130
    except FFmpegError as e:
        # ffmpeg already explained itself; don't bury that behind a stack trace.
        logger.error(f"❌ {e}")
        return 1
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        if args.verbose:
            import traceback
            logger.error(traceback.format_exc())
        return 1


def cli():
    """Synchronous console-script entry point (see pyproject [project.scripts])."""
    sys.exit(asyncio.run(main()))


if __name__ == "__main__":
    cli()
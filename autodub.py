#!/usr/bin/env python3
"""
AutoDub Pro v4.0 - Professional Video Translation and Dubbing Tool
FIXED: Audio distortion and Piper silence issues (Linux/Fedora compatible)
Added: XTTS v2 voice cloning support
"""
import sys, os, asyncio, subprocess, argparse, json, re, time, logging, shutil, functools, random, contextlib
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Optional, Tuple
from datetime import timedelta, datetime

# Heavy / third-party dependencies are guarded so the module can still be imported
# (e.g. for unit tests) when they are not installed. They are required to actually
# run the pipeline — this is enforced in main() via _check_runtime_deps().
_MISSING_DEPS: List[str] = []


def _try_import(name, attr=None):
    """Import a module (or attribute) and record it if missing. Returns the object or None."""
    try:
        mod = __import__(name)
        return getattr(mod, attr) if attr else mod
    except ImportError:
        _MISSING_DEPS.append(name)
        return None


np = _try_import("numpy")
requests = _try_import("requests")
whisper = _try_import("whisper")
pysrt = _try_import("pysrt")
edge_tts = _try_import("edge_tts")
torch = _try_import("torch")
torchaudio = _try_import("torchaudio")
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


def _check_runtime_deps() -> bool:
    """Return True if all runtime dependencies are importable, else print guidance."""
    if _MISSING_DEPS:
        print("❌ Missing required packages: " + ", ".join(_MISSING_DEPS) +
              "\n   Install them first:  pip install -r install.txt")
        return False
    return True


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
        logging.warning(f"Failed to read {path}: {e}")
    return loaded


def load_config_defaults(path: str) -> Dict:
    """Load a JSON config file of default option values (argparse dest names, e.g.
    {"translator": "openai", "target_lang": "ru"}). Returns {} on missing/invalid."""
    p = Path(path)
    if not p.exists():
        logging.warning(f"Config file not found: {path}")
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception as e:
        logging.warning(f"Failed to parse config {path}: {e}")
        return {}


def _has_content(path: Path, min_bytes: int = 1) -> bool:
    """True if the file exists and is at least min_bytes. Treats a stale 0-byte
    artifact (e.g. left by a failed run) as absent so it gets regenerated."""
    try:
        return path.exists() and path.stat().st_size >= min_bytes
    except OSError:
        return False


# ─────────────────────────────────────────────
#  XTTS v2 — voice cloning
# ─────────────────────────────────────────────

def load_xtts_model():
    """Load XTTS v2 model (downloaded automatically on first run)"""
    try:
        from TTS.api import TTS
        logging.info("🔄 Loading XTTS v2 model (first run may take a while)...")
        device = "cuda" if torch.cuda.is_available() else "cpu"
        # XTTS checkpoints store config objects, so they need weights_only=False —
        # scoped to this trusted local load only (see _allow_unsafe_torch_load).
        with _allow_unsafe_torch_load():
            tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)
        logging.info(f"✓ XTTS v2 loaded on {device.upper()}")
        return tts
    except ImportError:
        logging.error("❌ TTS package not found. Install with: pip install TTS")
        return None
    except Exception as e:
        logging.error(f"❌ Failed to load XTTS model: {e}")
        return None


def extract_voice_sample(video_path: str, output_wav: str, duration: float = 30.0) -> bool:
    """Extract a clean voice sample from the source video for cloning"""
    try:
        subprocess.run([
            "ffmpeg", "-y", "-i", video_path,
            "-vn", "-acodec", "pcm_s16le",
            "-ar", "22050", "-ac", "1",
            "-t", str(duration),
            output_wav
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        logging.info(f"✓ Extracted voice sample: {output_wav} ({duration}s)")
        return True
    except Exception as e:
        logging.error(f"❌ Failed to extract voice sample: {e}")
        return False


def generate_xtts(subs, tts_model, speaker_wav: str, lang_code: str,
                  concat_list: list, temp_files: list,
                  work_dir: Path, enable_stretch: bool):
    """
    Generate speech using XTTS v2 with voice cloning.

    Args:
        subs: pysrt subtitles list
        tts_model: loaded TTS model instance
        speaker_wav: path to reference audio for voice cloning
        lang_code: target language code (must be in XTTS_SUPPORTED_LANGS)
        concat_list: ffmpeg concat file list (modified in-place)
        temp_files: list of temp files to clean up (modified in-place)
        work_dir: working directory for temp files
        enable_stretch: whether to time-stretch to match subtitle timing
    """
    # XTTS outputs 24000 Hz
    sample_rate = 24000

    # Normalize lang code — XTTS uses 2-letter codes
    xtts_lang = lang_code[:2].lower()
    if xtts_lang not in XTTS_SUPPORTED_LANGS:
        logging.warning(f"⚠️  XTTS may not support '{xtts_lang}', attempting anyway")

    if not Path(speaker_wav).exists():
        logging.error(f"❌ Speaker WAV not found: {speaker_wav}")
        return

    logging.info(f"🎙️  XTTS voice cloning from: {speaker_wav}")
    logging.info(f"🌍 Target language: {xtts_lang}")

    generated_count = 0
    current_time_ms = 0

    for i, sub in enumerate(tqdm(subs, desc="XTTS Synthesis", unit="phrase")):
        start_ms = (sub.start.hours * 3600 + sub.start.minutes * 60 +
                    sub.start.seconds) * 1000 + sub.start.milliseconds
        end_ms = (sub.end.hours * 3600 + sub.end.minutes * 60 +
                  sub.end.seconds) * 1000 + sub.end.milliseconds

        text = sub.text.replace("\n", " ").strip()
        if not text:
            continue

        target_duration = (end_ms - start_ms) / 1000.0

        # ── Silence before segment ──────────────────────────
        sil_dur_ms = start_ms - current_time_ms
        if sil_dur_ms > 100:
            sil_file = work_dir / f"xtts_sil_{i}.wav"
            try:
                num_samples = int((sil_dur_ms / 1000.0) * sample_rate)
                sf.write(str(sil_file), np.zeros(num_samples, dtype=np.float32),
                         sample_rate, subtype='PCM_16')
                concat_list.append(f"file '{sil_file}'")
                temp_files.append(str(sil_file))
                current_time_ms += sil_dur_ms
            except Exception as e:
                logging.warning(f"Silence generation failed for segment {i}: {e}")

        # ── Speech generation ────────────────────────────────
        raw_file = work_dir / f"xtts_raw_{i}.wav"
        final_file = work_dir / f"xtts_fin_{i}.wav"

        if not final_file.exists():
            try:
                tts_model.tts_to_file(
                    text=text,
                    speaker_wav=speaker_wav,
                    language=xtts_lang,
                    file_path=str(raw_file)
                )

                if raw_file.exists() and raw_file.stat().st_size > 1000:
                    if enable_stretch:
                        if not stretch_audio_smart(str(raw_file), str(final_file),
                                                   target_duration, work_dir, sample_rate):
                            data, sr = sf.read(str(raw_file))
                            sf.write(str(final_file), data, sr, subtype='PCM_16')
                    else:
                        data, sr = sf.read(str(raw_file))
                        sf.write(str(final_file), data, sr, subtype='PCM_16')

                    concat_list.append(f"file '{final_file}'")
                    temp_files.append(str(final_file))
                    generated_count += 1
                else:
                    logging.warning(f"XTTS produced empty output for segment {i}: {text[:40]}")

            except Exception as e:
                logging.error(f"XTTS segment {i} error: {e}")
                continue

        current_time_ms = end_ms

    logging.info(f"✓ XTTS generated {generated_count}/{len(subs)} segments")


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
    """Enhanced logging with both file and console output."""
    def __init__(self, work_dir: Path, level: int = logging.INFO, json_format: bool = False):
        self.log_file = work_dir / "autodub.log"
        formatter = _JsonFormatter() if json_format else \
            logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handlers = [
            logging.FileHandler(self.log_file, encoding='utf-8'),
            logging.StreamHandler(),
        ]
        for h in handlers:
            h.setFormatter(formatter)
        logging.basicConfig(level=level, handlers=handlers, force=True)
        self.logger = logging.getLogger(__name__)

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
        logging.error(f"Failed to create silence: {e}")
        return False


def download_piper_model(lang_code: str, models_dir: Path) -> Optional[Path]:
    if 'ru' in lang_code:
        model_name = "ru_RU-ruslan-medium.onnx"
    else:
        model_name = "en_US-lessac-medium.onnx"
    manual_path = Path.home() / ".piper_models" / model_name
    if manual_path.exists():
        logging.info(f"✓ Found manual model: {manual_path}")
        return manual_path
    else:
        logging.error(f"❌ Model file missing: {manual_path}")
        logging.error("👉 Please run the wget commands from the instructions to download the model manually!")
        return None


def generate_piper(subs, model_path: Path, concat_list: list, temp_files: list,
                   work_dir: Path, enable_stretch: bool):
    piper_cmd = shutil.which("piper")
    if not piper_cmd:
        possible_path = Path(sys.executable).parent / "piper"
        if possible_path.exists():
            piper_cmd = str(possible_path)
    if not piper_cmd:
        logging.error("❌ Piper command not found!")
        return

    logging.info(f"🎙️ Using Piper binary: {piper_cmd}")
    logging.info(f"📂 Model path: {model_path}")

    sample_rate = 22050
    generated_count = 0
    current_time_ms = 0

    for i, sub in enumerate(tqdm(subs, desc="Piper Synthesis", unit="phrase")):
        start_ms = (sub.start.hours * 3600 + sub.start.minutes * 60 + sub.start.seconds) * 1000 + sub.start.milliseconds
        end_ms = (sub.end.hours * 3600 + sub.end.minutes * 60 + sub.end.seconds) * 1000 + sub.end.milliseconds

        text = sub.text.replace("\n", " ").replace('"', '').replace("'", "").strip()
        if not text:
            continue

        target_duration = (end_ms - start_ms) / 1000.0

        sil_dur_ms = start_ms - current_time_ms
        if sil_dur_ms > 100:
            sil_file = work_dir / f"sil_{i}.wav"
            try:
                num_samples = int((sil_dur_ms / 1000.0) * sample_rate)
                silence_data = np.zeros(num_samples, dtype=np.float32)
                sf.write(str(sil_file), silence_data, sample_rate)
                concat_list.append(f"file '{sil_file}'")
                temp_files.append(str(sil_file))
                current_time_ms += sil_dur_ms
            except Exception as e:
                logging.debug(f"Piper silence generation failed for segment {i}: {e}")

        f_temp = work_dir / f"p_raw_{i}.wav"
        f_final = work_dir / f"p_fin_{i}.wav"

        if not f_final.exists():
            try:
                cmd = [piper_cmd, "--model", str(model_path), "--output_file", str(f_temp)]
                process = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                                           stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                stdout, stderr = process.communicate(input=text.encode('utf-8'))

                if f_temp.exists() and f_temp.stat().st_size > 1000:
                    if enable_stretch:
                        if not stretch_audio_smart(str(f_temp), str(f_final), target_duration, work_dir, sample_rate):
                            data, sr = sf.read(str(f_temp))
                            sf.write(str(f_final), data, sr)
                    else:
                        data, sr = sf.read(str(f_temp))
                        sf.write(str(f_final), data, sr)
                    concat_list.append(f"file '{f_final}'")
                    temp_files.append(str(f_final))
                    generated_count += 1
                else:
                    logging.warning(f"Piper fail/empty: {text[:20]}... Error: {stderr.decode()[:100]}")
            except Exception as e:
                logging.error(f"Segment {i} error: {e}")
                continue

        current_time_ms = end_ms

    logging.info(f"✓ Generated {generated_count}/{len(subs)} segments")


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
                logging.warning(f"Translation failed after {max_retries} attempts: {e}")
    try:
        if translator_type == "google":
            logging.info("Falling back to Ollama translator")
            return translate_ollama(text, target_lang, ollama_model)
        else:
            logging.info("Falling back to Google translator")
            return GoogleTranslator(source='auto', target=target_lang).translate(text)
    except Exception as e:
        logging.error(f"All translation methods failed for '{text[:50]}...': {e}")
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
        logging.warning(f"Ollama error: {e}")
        return text


# ─────────────────────────────────────────────
#  LLM translation providers (OpenAI, Anthropic, …)
# ─────────────────────────────────────────────

_openai_client = None
_anthropic_client = None


def get_openai_client(api_key: Optional[str] = None):
    """Lazily create and cache a single OpenAI client instance."""
    global _openai_client
    if _openai_client is not None:
        return _openai_client
    try:
        from openai import OpenAI
    except ImportError:
        logging.error("❌ 'openai' package not installed. Run: pip install openai")
        return None
    key = api_key or os.environ.get("OPENAI_API_KEY")
    if not key:
        logging.error("❌ OpenAI API key not found. "
                      "Set the OPENAI_API_KEY environment variable or pass --openai_api_key")
        return None
    try:
        _openai_client = OpenAI(api_key=key)
    except Exception as e:
        logging.error(f"❌ Failed to initialize OpenAI client: {e}")
        return None
    return _openai_client


def get_anthropic_client(api_key: Optional[str] = None):
    """Lazily create and cache a single Anthropic client instance."""
    global _anthropic_client
    if _anthropic_client is not None:
        return _anthropic_client
    try:
        import anthropic
    except ImportError:
        logging.error("❌ 'anthropic' package not installed. Run: pip install anthropic")
        return None
    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        logging.error("❌ Anthropic API key not found. "
                      "Set the ANTHROPIC_API_KEY environment variable or pass --anthropic_api_key")
        return None
    try:
        _anthropic_client = anthropic.Anthropic(api_key=key, max_retries=5)
    except Exception as e:
        logging.error(f"❌ Failed to initialize Anthropic client: {e}")
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
    logging.info(f"💰 {provider} usage: {u['calls']} calls, {total} tokens "
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
                    logging.warning(f"OpenAI transient error (try {attempt + 1}/{max_backoff_retries}): "
                                    f"{e}; retrying in {wait:.1f}s")
                    time.sleep(wait)
                    backoff = min(backoff * 2, 60)
                    continue
                break   # non-transient or parameter error → move to next param combo
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
        logging.warning(f"LLM translate error: {e}")
        return text
    result = _clean_line(result)
    return result if result else text


def translate_openai(text: str, target_lang: str, model: str,
                     api_key: Optional[str] = None) -> str:
    """Backward-compatible single-line OpenAI translation (delegates to the registry)."""
    return _llm_translate_single(text, target_lang, model, _openai_chat_text, api_key)


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
                         context_pairs: List[Tuple[str, str]]) -> List[str]:
    """Translate one contiguous chunk of subtitle lines in a single API call, with mutual
    context. Falls back to per-line translation if the batch response is invalid."""
    system_prompt = (
        f"You are a professional subtitle translator and native-level localization expert "
        f"for {full_lang}. You receive a contiguous block of subtitle lines from a single video "
        f"and translate ALL of them into {full_lang}. Use the surrounding lines (and any provided "
        f"'context' lines) to keep pronouns, gender, names, terminology, tone and style perfectly "
        f"consistent and natural across the whole block. Each translation must sound like a native "
        f"speaker wrote it and fit roughly the same speaking duration as the source (for dubbing). "
        f"Never merge, split, reorder, add or drop lines, and never translate the 'context' lines. "
        f"Respond ONLY with a JSON object of the form {{\"translations\": [\"...\", \"...\"]}} "
        f"containing EXACTLY {len(chunk)} items, in the same order as the input 'lines'."
    )
    user_obj: Dict = {"lines": chunk}
    if context_pairs:
        user_obj["context"] = [{"source": s, "translation": t} for s, t in context_pairs]
    user = json.dumps(user_obj, ensure_ascii=False)

    try:
        raw = chat_fn(system_prompt, user, model, True, api_key)
    except Exception as e:
        logging.warning(f"LLM batch error: {e} — falling back to per-line for this chunk")
        return [_llm_translate_single(t, target_lang, model, chat_fn, api_key) for t in chunk]

    parsed = _parse_batch_translations(raw, len(chunk))
    if parsed is not None:
        return parsed
    logging.warning("LLM batch: response count/parse mismatch — falling back to per-line for this chunk")
    return [_llm_translate_single(t, target_lang, model, chat_fn, api_key) for t in chunk]


def _llm_translate_batch(texts: List[str], target_lang: str, model: str, chat_fn,
                         api_key: Optional[str] = None,
                         batch_size: int = DEFAULT_LLM_BATCH_SIZE) -> List[str]:
    """Translate a full list of subtitle lines using context-aware chunked LLM calls.
    Output length and order always match the input; falls back to the source on failure."""
    full_lang = LANG_MAP.get(target_lang.lower(), target_lang)
    if batch_size < 1:
        batch_size = DEFAULT_LLM_BATCH_SIZE

    results: List[str] = []
    for start in tqdm(range(0, len(texts), batch_size),
                      desc="LLM batch translate", unit="chunk"):
        chunk = texts[start:start + batch_size]

        # Carry a short tail of the previous chunk as cross-boundary context.
        context_pairs: List[Tuple[str, str]] = []
        if start > 0 and _LLM_CONTEXT_OVERLAP > 0:
            ctx_src = texts[max(0, start - _LLM_CONTEXT_OVERLAP):start]
            ctx_tr = results[max(0, start - _LLM_CONTEXT_OVERLAP):start]
            context_pairs = list(zip(ctx_src, ctx_tr))

        translated = _llm_translate_chunk(chunk, full_lang, target_lang, model,
                                          chat_fn, api_key, context_pairs)
        if len(translated) != len(chunk):   # final alignment safety net
            translated = [_llm_translate_single(t, target_lang, model, chat_fn, api_key)
                          for t in chunk]
        results.extend(translated)

    return results


def translate_llm(text: str, target_lang: str, provider: str, model: Optional[str] = None,
                  api_key: Optional[str] = None) -> str:
    """Single-line translation via the named LLM provider from LLM_PROVIDERS."""
    p = LLM_PROVIDERS[provider]
    return _llm_translate_single(text, target_lang, model or p["default_model"],
                                 p["chat"], api_key)


def translate_llm_batch(texts: List[str], target_lang: str, provider: str,
                        model: Optional[str] = None, api_key: Optional[str] = None,
                        batch_size: int = DEFAULT_LLM_BATCH_SIZE) -> List[str]:
    """Context-aware batch translation via the named LLM provider from LLM_PROVIDERS."""
    p = LLM_PROVIDERS[provider]
    return _llm_translate_batch(texts, target_lang, model or p["default_model"],
                                p["chat"], api_key, batch_size)


def translate_openai_batch(texts: List[str], target_lang: str, model: str,
                           api_key: Optional[str] = None,
                           batch_size: int = DEFAULT_LLM_BATCH_SIZE) -> List[str]:
    """Backward-compatible OpenAI batch translation (delegates to the registry)."""
    return translate_llm_batch(texts, target_lang, "openai", model, api_key, batch_size)


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


def get_audio_duration(audio_file: str) -> Optional[float]:
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", audio_file],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True
        )
        return float(result.stdout.strip())
    except Exception as e:
        logging.debug(f"ffprobe duration failed for {audio_file}: {e}")
        return None


def calculate_speed_factor(original_duration: float, target_duration: float) -> float:
    if target_duration == 0:
        return 1.0
    ratio = original_duration / target_duration
    if 0.95 <= ratio <= 1.05:
        return 1.0
    return max(0.5, min(2.5, ratio))


def stretch_audio_smart(input_file: str, output_file: str, target_duration: float,
                        work_dir: Path, target_sr: int = 22050) -> bool:
    try:
        data, sr = sf.read(input_file, dtype='float32')
        current_duration = len(data) / sr
        if current_duration == 0:
            return False
        ratio = calculate_speed_factor(current_duration, target_duration)
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
        logging.warning(f"Audio stretching failed: {e}, using original")
        try:
            subprocess.run([
                "ffmpeg", "-y", "-i", input_file,
                "-ar", str(target_sr), "-ac", "1", output_file
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            return True
        except Exception as e:
            logging.warning(f"Audio stretch fallback failed: {e}")
            return False


def reduce_noise(input_file: str, output_file: str) -> bool:
    try:
        data, rate = sf.read(input_file, dtype='float32')
        reduced_noise = nr.reduce_noise(y=data, sr=rate, stationary=True, prop_decrease=0.8)
        sf.write(output_file, reduced_noise, rate, subtype='PCM_16')
        return True
    except Exception as e:
        logging.warning(f"Noise reduction failed: {e}")
        try:
            sf.write(output_file, *sf.read(input_file))
        except Exception:
            shutil.copy(input_file, output_file)
        return False


def normalize_audio(input_file: str, output_file: str, target_level: float = -20.0) -> bool:
    try:
        subprocess.run([
            "ffmpeg", "-y", "-i", input_file,
            "-filter:a", f"loudnorm=I={target_level}:TP=-1.5:LRA=11",
            "-ar", "44100", "-ac", "1", output_file
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return True
    except Exception as e:
        logging.warning(f"Audio normalization failed: {e}")
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
        logging.warning("Edge TTS produced an empty file; retrying")
    except Exception as e:
        logging.error(f"Edge TTS failed: {e}")
    # Retry once without the emotion style (also covers the empty-output case).
    try:
        communicate = edge_tts.Communicate(text, voice, rate=rate)
        await communicate.save(output_file)
        if _has_content(Path(output_file)):
            return True
    except Exception as e:
        logging.debug(f"Edge TTS retry failed: {e}")
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
                logging.error(f"Translation failed: {e}")
    return [r for r in results if r is not None]


async def synthesize_speech_batch(subs, voice: str, work_dir: Path,
                                  enable_stretch: bool, emotion_detection: bool,
                                  rate_adjust: bool, has_emotion_support: bool = False) -> Tuple[List[str], List[str]]:
    concat_list, temp_files = [], []
    current_time_ms = 0
    target_sr = 44100
    emotion_stats = {}

    for i, s in enumerate(tqdm(subs, desc="Edge TTS", unit="sentence")):
        start_ms = (s.start.hours*3600 + s.start.minutes*60 + s.start.seconds)*1000 + s.start.milliseconds
        end_ms = (s.end.hours*3600 + s.end.minutes*60 + s.end.seconds)*1000 + s.end.milliseconds
        txt = s.text.strip()
        if not txt:
            continue
        target_duration = (end_ms - start_ms) / 1000.0

        silence_dur_ms = start_ms - current_time_ms
        if silence_dur_ms > 100:
            silence_file = work_dir / f"silence_{i}.wav"
            if not silence_file.exists():
                create_silence_wav(silence_dur_ms / 1000.0, str(silence_file), target_sr)
            if silence_file.exists():
                concat_list.append(f"file '{silence_file}'")
                temp_files.append(str(silence_file))
                current_time_ms += silence_dur_ms

        raw_file = work_dir / f"speech_{i}_raw.mp3"
        wav_file = work_dir / f"speech_{i}_converted.wav"
        processed_file = work_dir / f"speech_{i}_processed.wav"
        final_file = work_dir / f"speech_{i}_final.wav"

        if not _has_content(final_file, 100):
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
                    rate = f"{rate_factor*100:+.0f}%"

            if not _has_content(raw_file):
                success = await generate_tts_edge(txt, voice, str(raw_file), emotion, rate, has_emotion_support)
                if not success:
                    continue

            if not _has_content(wav_file):
                try:
                    subprocess.run([
                        "ffmpeg", "-y", "-i", str(raw_file),
                        "-ar", str(target_sr), "-ac", "1", str(wav_file)
                    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                except Exception as e:
                    logging.error(f"Failed to convert MP3 to WAV for segment {i}: {e}")
                    continue

            if not _has_content(processed_file):
                try:
                    reduce_noise(str(wav_file), str(processed_file))
                except Exception as e:
                    logging.debug(f"Noise reduction failed for segment {i}, using raw audio: {e}")
                    sf.write(str(processed_file), *sf.read(str(wav_file)))

            if enable_stretch:
                success = stretch_audio_smart(str(processed_file), str(final_file),
                                              target_duration, work_dir, target_sr)
                if not success:
                    sf.write(str(final_file), *sf.read(str(processed_file)))
            else:
                sf.write(str(final_file), *sf.read(str(processed_file)))

        if final_file.exists() and final_file.stat().st_size > 100:
            concat_list.append(f"file '{final_file}'")
            temp_files.append(str(final_file))
        current_time_ms = end_ms

    if emotion_stats:
        logging.info(f"🎭 Emotion usage: {emotion_stats}")
    return concat_list, temp_files


def transcribe_audio(audio_path: str, model_name: str, backend: str, device: str) -> Tuple[List[Dict], str]:
    """Transcribe audio and return (segments, detected_language). `segments` is a list
    of dicts each having at least 'start', 'end', 'text' — normalized across backends.
    backend: 'openai' (openai-whisper, default) or 'faster' (faster-whisper)."""
    if backend == "faster":
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            raise RuntimeError("faster-whisper not installed. Run: pip install faster-whisper")
        compute_type = "float16" if device == "cuda" else "int8"
        # faster-whisper names the turbo model 'large-v3-turbo'.
        fw_model = "large-v3-turbo" if model_name == "turbo" else model_name
        model = WhisperModel(fw_model, device=device, compute_type=compute_type)
        seg_iter, info = model.transcribe(audio_path)
        segments = [{"start": s.start, "end": s.end, "text": s.text} for s in seg_iter]
        return segments, getattr(info, "language", "unknown")

    # Default: openai-whisper. Loads a trusted local checkpoint (weights_only scoped).
    with _allow_unsafe_torch_load():
        model = whisper.load_model(model_name, device=device)
    result = model.transcribe(audio_path, fp16=(device == "cuda"), verbose=False)
    return result["segments"], result.get("language", "unknown")


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
        subprocess.run([
            "ffmpeg", "-y", "-i", str(video_path),
            "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", str(audio_wav)
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
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
            translated_texts = translate_llm_batch(
                texts, args.target_lang, args.translator, model=llm_model,
                api_key=llm_api_key, batch_size=args.llm_batch_size
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
        subs = pysrt.open(str(srt_file))
        concat_list, temp_files = [], []

        if args.tts == "edge":
            logger.info(f"🔎 Finding voice for: {args.target_lang}")
            voice, has_emotions = await get_edge_voice(args.target_lang)
            logger.info(f"🎙️  Selected: {voice} (Emotions: {'Yes' if has_emotions else 'No'})")
            concat_list, temp_files = await synthesize_speech_batch(
                subs, voice, work_dir,
                enable_stretch=not args.no_stretch,
                emotion_detection=args.detect_emotion,
                rate_adjust=args.auto_rate,
                has_emotion_support=has_emotions
            )

        elif args.tts == "piper":
            logger.info(f"🔎 Loading Piper model for: {args.target_lang}")
            model_path = download_piper_model(args.target_lang, Path.home() / ".piper_models")
            if not model_path:
                logger.error("Failed to download Piper model")
                return 1
            logger.info("🎙️  Using Piper (offline mode)")
            generate_piper(subs, model_path, concat_list, temp_files, work_dir,
                           enable_stretch=not args.no_stretch)

        elif args.tts == "xtts":
            # ── XTTS voice cloning ───────────────────────────
            lang_code = args.target_lang[:2].lower()
            if lang_code not in XTTS_SUPPORTED_LANGS:
                logger.error(f"❌ XTTS does not support language '{lang_code}'. "
                             f"Supported: {sorted(XTTS_SUPPORTED_LANGS)}")
                return 1

            # Determine speaker reference wav
            speaker_wav = args.voice_sample
            if not speaker_wav:
                # Auto-extract from source video
                auto_sample = work_dir / "auto_voice_sample.wav"
                if not auto_sample.exists():
                    logger.info("🎤 No --voice-sample provided, extracting from source video...")
                    if not extract_voice_sample(str(video_path), str(auto_sample)):
                        logger.error("Failed to extract voice sample")
                        return 1
                speaker_wav = str(auto_sample)
            else:
                if not Path(speaker_wav).exists():
                    logger.error(f"❌ Voice sample not found: {speaker_wav}")
                    return 1
                logger.info(f"🎤 Using provided voice sample: {speaker_wav}")

            # Load model
            tts_model = load_xtts_model()
            if tts_model is None:
                return 1

            generate_xtts(
                subs, tts_model, speaker_wav, lang_code,
                concat_list, temp_files, work_dir,
                enable_stretch=not args.no_stretch
            )

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
    subprocess.run([
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-i", str(voiceover_norm),
        "-filter_complex",
        f"[0:a]volume={args.background_volume}[bg];[1:a]volume={args.voice_volume}[fg];"
        f"[bg][fg]amix=inputs=2:duration=first:dropout_transition=2",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-map", "0:v:0",
        str(output_file)
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

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
        description="AutoDub Pro v4.0 - Professional Video Dubbing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage
  python autodub.py video.mp4 --target_lang ru

  # High quality with all enhancements
  python autodub.py video.mp4 --target_lang es --whisper_model large --detect-emotion --auto-rate

  # XTTS voice cloning (clone voice from source video automatically)
  python autodub.py video.mp4 --target_lang ru --tts xtts

  # XTTS with custom voice reference
  python autodub.py video.mp4 --target_lang ru --tts xtts --voice-sample my_voice.wav

  # Batch processing
  python autodub.py video1.mp4 video2.mp4 --target_lang fr --parallel

  # Subtitles only
  python autodub.py video.mp4 --target_lang de --subtitles-only
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
                             "faster (faster-whisper — 2-4x faster; pip install faster-whisper)")

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
    parser.add_argument("--parallel", action="store_true",
                        help="Enable parallel translation (faster)")
    parser.add_argument("--workers", type=int, default=4,
                        help="Number of parallel workers (default: 4)")

    parser.add_argument("--tts", choices=["edge", "piper", "xtts"], default="edge",
                        help="TTS engine: edge (online), piper (offline), xtts (voice cloning)")
    parser.add_argument("--voice-sample", type=str, default=None,
                        help="Path to reference WAV for XTTS voice cloning (optional, "
                             "auto-extracted from source video if not provided)")

    parser.add_argument("--no-stretch", action="store_true",
                        help="Disable audio time-stretching")
    parser.add_argument("--detect-emotion", action="store_true",
                        help="Enable emotion detection (edge TTS only)")
    parser.add_argument("--auto-rate", action="store_true",
                        help="Auto adjust TTS rate")
    parser.add_argument("--background-volume", type=float, default=0.15,
                        help="Original audio volume (0.0-1.0, default: 0.15)")
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

    first_video = Path(args.videos[0])
    work_dir = Path.cwd() / f"{first_video.stem}_work"
    work_dir.mkdir(exist_ok=True)
    logger = Logger(work_dir,
                    level=logging.DEBUG if args.verbose else logging.INFO,
                    json_format=(args.log_format == "json"))

    logger.info("╔════════════════════════════════════════════════════════╗")
    logger.info("║           AutoDub Pro v4.0 - Configuration           ║")
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

# AutoDub - Automatic Video Translation & Dubbing

Automatically transcribe, translate, and dub videos into different languages using AI-powered text-to-speech.

## Features

- 🎙️ **Speech Recognition**: Whisper transcription (openai-whisper or faster-whisper)
- 🌍 **Translation**: Google, Ollama (local LLM), or context-aware LLM (OpenAI / Anthropic)
- 🗣️ **Three TTS Engines**:
    - **Edge TTS**: High-quality Microsoft voices (recommended)
    - **Piper**: Fast offline TTS (no internet after model download)
    - **XTTS**: Voice cloning from a short reference sample
- 🎬 **Video Preservation**: Keeps original video, mixes the original audio in as a quiet ambience bed (8%) under the dubbed voice (150%)
- 📝 **Subtitle Generation**: Creates SRT files for translated text

## Requirements

### System Dependencies
```bash
# Fedora/RHEL
sudo dnf install ffmpeg python3.10 python3.10-devel

# Ubuntu/Debian
sudo apt install ffmpeg python3.10 python3.10-devel

# macOS
brew install ffmpeg
```

### Python Dependencies
```bash
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
pip install -r install.txt
pip install TTS  # Only needed for XTTS voice cloning
```

##  Local Translation with Ollama (Optional)

AutoDub now supports fully offline translation using **Ollama**. This is ideal for privacy, avoiding API limits, and achieving more context-aware translations.

### 1. Install Ollama
**For Linux (Fedora/Ubuntu/etc.):**
```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3
```

## Quick Start

```bash
# 1. Install dependencies (see Requirements above for the full setup)
pip install -r install.txt

# 2. (Optional) add API keys for LLM translation
cp .env.example .env    # then edit

# 3. Dub a video
python autodub.py video.mp4 --target_lang ru
```

On Linux you can instead run `chmod +x setup.sh && ./setup.sh`, which creates a
`venv` and a `run.sh` wrapper.

### Basic Usage (Edge TTS - Recommended)
```bash
# Dub to Russian (default)
python autodub.py video.mp4

# Dub to English
python autodub.py video.mp4 --target_lang en

# Dub to German
python autodub.py video.mp4 --target_lang de
```

### Piper TTS (Faster, offline)
```bash
# Offline synthesis (model downloaded to ~/.piper_models on first use)
python autodub.py video.mp4 --tts piper --target_lang ru
```
### XTTS Voice Cloning (Most Natural)
```bash
# Auto-extracts a reference sample from the source video
python autodub.py video.mp4 --tts xtts --target_lang en

# Or provide your own clean voice sample
python autodub.py video.mp4 --tts xtts --voice-sample my_voice.wav --target_lang en
```

### Ollama translator

```bash
# Use Ollama with default llama3 model
./run.sh video.mp4 --translator ollama

# Use a specific model (e.g., Mistral)
./run.sh video.mp4 --translator ollama --ollama_model mistral 
```

### OpenAI TTS (multilingual, instructable)

A cloud speech engine for languages XTTS can't clone. Needs `OPENAI_API_KEY`.

```bash
python autodub.py video.mp4 --tts openai --target_lang en --openai-voice nova
python autodub.py video.mp4 --tts openai --openai-tts-instructions "Warm, upbeat narrator."
```

Voices: alloy, echo, fable, onyx, nova, shimmer, ash, ballad, coral, sage, verse.
Note: OpenAI voices are strongest for major languages; for languages with a dedicated
Microsoft neural voice (e.g. `az-AZ`), Edge/Azure often sounds more native — compare with
`--quality-gate --gate-model base`.

Add `--detect-emotion` to have an LLM tag each line with a short delivery direction
(emotion / energy / pace) that is passed to OpenAI TTS as a per-line instruction, for more
expressive, content-aware prosody (one cheap API call per job, cached; falls back to a
punctuation heuristic if unavailable):

```bash
python autodub.py video.mp4 --tts openai --target_lang az --detect-emotion
```

### LLM translators — OpenAI & Anthropic (most natural)

Professional, native-sounding translations via an LLM. Two providers are built in
(`--translator openai` and `--translator anthropic`), and adding another is a small
change in the `LLM_PROVIDERS` registry in `autodub.py`. The model is fully configurable.

```bash
# OpenAI (key via env var — recommended)
export OPENAI_API_KEY="sk-..."          # PowerShell: $env:OPENAI_API_KEY="sk-..."
python autodub.py video.mp4 --translator openai --target_lang ru
python autodub.py video.mp4 --translator openai --openai_model gpt-5-mini

# Anthropic (Claude)
export ANTHROPIC_API_KEY="sk-ant-..."   # PowerShell: $env:ANTHROPIC_API_KEY="sk-ant-..."
python autodub.py video.mp4 --translator anthropic --target_lang ru
python autodub.py video.mp4 --translator anthropic --anthropic_model claude-sonnet-5
```

LLM translation is **context-aware**: subtitle lines are translated in blocks
(not one-by-one), so the model keeps pronouns, gender, names, terminology and tone
consistent across the whole scene, and carries a short overlap of the previous block
as context. This produces more natural, professional dubbing and lowers cost/latency.
If a block response is invalid, it automatically falls back to per-line translation.

Robustness: transient (rate-limit / 5xx) errors are retried with backoff, and token
usage is logged after translation. To also print an estimated cost, add your model's
prices to the `LLM_PRICING` table in `autodub.py`.

```bash
# Larger blocks = more context (and fewer API calls); smaller = safer for long lines
python autodub.py video.mp4 --translator openai --llm_batch_size 25
```

| Option | Description | Default |
|--------|-------------|---------|
| `--openai_model` | OpenAI model id (e.g. `gpt-5`, `gpt-5-mini`) | `gpt-5` |
| `--anthropic_model` | Claude model id (e.g. `claude-opus-4-8`, `claude-sonnet-5`) | `claude-opus-4-8` |
| `--openai_api_key` / `--anthropic_api_key` | API key (falls back to the provider's env var) | env var |
| `--llm_batch_size` | Subtitle lines translated together per call | `25` |
| `--speech-rate` | Chars/sec used to length-budget translations for dub timing (lower = shorter/slower) | `15` |

## Command-Line Options
```
positional arguments:
  videos                Input video file(s)

options:
  -h, --help            Show help message
  --tts {edge,piper,xtts}
                        TTS engine (default: edge)
  --target_lang LANG    Target language code (default: ru)
                        Supports: ru, en, de, fr, es, it, pt, ja, zh, etc.
  --translator {google,ollama,openai,anthropic}
                        Translation backend (default: google)
  --voice-sample FILE   Reference WAV for XTTS voice cloning (optional)
  --output-dir DIR      Directory for the final video / subtitles
  --subtitles-only      Generate only the translated .srt (no TTS/video)
  --no-resume           Ignore previous checkpoint and start fresh
  --keep-temp           Keep temporary files after processing
  --whisper-backend {openai,faster}
                        Transcription engine (default: openai). "faster" uses
                        faster-whisper — 2-4x quicker on long videos / large models
                        (pip install faster-whisper)
  --no-speech-threshold F
                        Drop transcription segments with no_speech_prob > F (music /
                        intro that Whisper hallucinated as text). Default 0.6; 1.0 off
  --quality-gate        Score each synthesized segment (ASR round-trip + artifact /
                        pacing checks) and log a per-job quality report. For XTTS
                        (stochastic), a flagged segment is automatically re-synthesized
                        up to twice and the best-scoring take is kept.
  --gate-model MODEL    faster-whisper model for the gate (default: tiny; use
                        base/small for low-resource languages like az to avoid
                        false-positive WER)
  --config FILE         JSON file of default option values
  --env-file FILE       Path to a .env file with API keys (default: .env)
  --log-format {plain,json}
                        Log output format (default: plain)
  --verbose             DEBUG-level logging
```

## Configuration

**API keys via `.env`** — copy `.env.example` to `.env` (gitignored) and fill in your
keys; AutoDub loads it automatically on startup. Real environment variables always win.

```bash
cp .env.example .env      # then edit; no need to `export` on every run
```

**Defaults via a JSON config** — put commonly-used options in a file and pass `--config`.
Keys are the long option names with dashes as underscores. Explicit CLI flags override it.

```json
{ "translator": "openai", "target_lang": "ru", "tts": "edge", "llm_batch_size": 30 }
```
```bash
python autodub.py video.mp4 --config my_defaults.json
```

**Structured logging** — `--log-format json` emits one JSON object per log line (for log
pipelines); `--verbose` raises the level to DEBUG.

## Supported Languages

Edge TTS supports 100+ languages. Common codes:
- `ru` - Russian
- `en` - English
- `de` - German
- `fr` - French
- `es` - Spanish
- `it` - Italian
- `pt` - Portuguese
- `ja` - Japanese
- `zh` - Chinese

Full list: https://speech.microsoft.com/portal/voicegallery

## Output

The script generates:
- `{video}_dubbed.mp4` - Video with dubbed audio
- `{video}_{lang}.srt` - Subtitle file with translations

## Performance

| Engine | Speed | Quality | Languages | Notes |
|--------|-------|---------|-----------|-------|
| Edge TTS | Fast | ⭐⭐⭐⭐⭐ | 100+ | Best quality, requires internet |
| Piper | Very Fast | ⭐⭐⭐ | ~15 | Offline, robotic |
| XTTS | Slow | ⭐⭐⭐⭐⭐ | 16 | Voice cloning, GPU recommended |

## Troubleshooting

### "No module named 'soundfile'"
```bash
pip install soundfile
```

### Dub speaks during a music/intro (no original speech there)
Whisper transcribes non-speech audio (intros, music) as phantom text, which then
gets dubbed. AutoDub drops segments with `no_speech_prob > 0.6` by default; lower
`--no-speech-threshold` (e.g. 0.4) to be more aggressive, or use
`--whisper-backend faster` (built-in VAD removes non-speech at the source).

### Edge TTS fails with `403 Invalid response status`
Microsoft tightened its speech endpoint; older `edge-tts` versions are rejected.
Upgrade: `pip install -U "edge-tts>=7.0"`.

### "TorchCodec is required"
This is already patched in the code. If you still see it, update PyTorch:
```bash
pip install --upgrade torch torchaudio
```

### Piper model missing
Piper models are looked up in `~/.piper_models`. Download the model for your
language before using `--tts piper` (see the Piper releases page).

### XTTS out of memory
Use CPU mode or reduce video length. For long videos, split into segments.

### Poor voice quality with Piper
Use Edge TTS or XTTS instead. Piper is designed for speed, not quality.

### Ollama Integration Features

1. **Privacy**: Your transcripts and translations never leave your local machine.
2. **Custom Context**: LLMs can handle nuances, slang, and technical terms better than basic translators.
3. **Cost**: 100% free with no character limits or subscription fees.
4. **Offline Workflow**: Combined with Piper or XTTS, you can dub videos without an active internet connection.

| Feature   | Google Translate       | Ollama (Local LLM)        |
|-----------|------------------------|---------------------------|
| Speed     | Instant                | Depends on your GPU/RAM   |
| Setup     | Zero setup             | Requires model download  |
| Internet | Required               | Not required              |
| Quality   | Literal / Standard     | Contextual / Natural      |


## Technical Details

### Processing Pipeline
1. **Extract Audio**: FFmpeg extracts mono 16kHz WAV
2. **Transcribe**: Whisper (default `turbo`) transcribes with timestamps
3. **Translate**: Google / Ollama / OpenAI translates the merged sentences
4. **Synthesize**: TTS engine generates speech for each subtitle
5. **Merge**: FFmpeg mixes original + dubbed audio with the original video

### Audio Mixing
- Original audio: 8% volume — a quiet ambience bed, ~31 dB under the dub, so the
  original speech doesn't compete with it (`--background-volume`, 0.0 mutes it)
- Dubbed audio: 150% volume (foreground) (`--voice-volume`)
- The two are combined with `amix`, which halves each input, so the mix does not clip
- Output: AAC 192kbps, video copied without re-encoding

## License

MIT License - see LICENSE file

## Credits

- [OpenAI Whisper](https://github.com/openai/whisper) - Speech recognition
- [Edge-TTS](https://github.com/rany2/edge-tts) - Microsoft TTS
- [Piper](https://github.com/rhasspy/piper) - Offline neural TTS
- [Coqui TTS](https://github.com/coqui-ai/TTS) - XTTS voice cloning

## Contributing

Issues and pull requests welcome!

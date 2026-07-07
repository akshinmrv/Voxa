
# AutoDub - Automatic Video Translation & Dubbing

Automatically transcribe, translate, and dub videos into different languages using AI-powered text-to-speech.

## Features

- 🎙️ **Speech Recognition**: Transcribe audio using OpenAI Whisper
- 🌍 **Translation**: Google Translate, Ollama (local LLM), or OpenAI (context-aware)
- 🗣️ **Three TTS Engines**:
    - **Edge TTS**: High-quality Microsoft voices (recommended)
    - **Piper**: Fast offline TTS (no internet after model download)
    - **XTTS**: Voice cloning from a short reference sample
- 🎬 **Video Preservation**: Keeps original video, mixes original audio (20%) with dubbed audio (150%)
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
curl -fsSL [https://ollama.com/install.sh](https://ollama.com/install.sh) | sh
ollama pull llama3
````

## Quick Start

Here is the concise guide on how to get started using your setup.sh script, formatted in Markdown:
🚀 Quick Start Guide

Follow these three steps to set up and start dubbing your videos:
1. Prepare Files

Ensure you have the following files in your project directory:

    setup.sh (The installer)

    autodub.py (The main engine)

    install.txt (List of dependencies)

2. Run Installation

Open your terminal in the project folder and execute:
```Bash

chmod +x setup.sh && ./setup.sh
````

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

### OpenAI translator (most natural)

Professional, native-sounding translations via the OpenAI API. The model is
fully configurable and can be swapped for any current or future model.

```bash
# Provide the API key via environment variable (recommended)
export OPENAI_API_KEY="sk-..."          # Windows PowerShell: $env:OPENAI_API_KEY="sk-..."
python autodub.py video.mp4 --translator openai --target_lang ru

# Choose a specific model
python autodub.py video.mp4 --translator openai --openai_model gpt-5-mini

# Or pass the key directly instead of the env var
python autodub.py video.mp4 --translator openai --openai_api_key sk-...
```

OpenAI translation is **context-aware**: subtitle lines are translated in blocks
(not one-by-one), so the model keeps pronouns, gender, names, terminology and tone
consistent across the whole scene, and carries a short overlap of the previous block
as context. This produces more natural, professional dubbing and lowers cost/latency.
If a block response is invalid, it automatically falls back to per-line translation.

Robustness: rate-limit / 5xx errors are retried with exponential backoff, and token
usage is logged after translation. To also print an estimated cost, add your model's
prices to the `OPENAI_PRICING` table in `autodub.py`.

```bash
# Larger blocks = more context (and fewer API calls); smaller = safer for long lines
python autodub.py video.mp4 --translator openai --openai_batch_size 25
```

| Option | Description | Default |
|--------|-------------|---------|
| `--openai_model` | OpenAI model id (e.g. `gpt-5`, `gpt-5-mini`) | `gpt-5` |
| `--openai_api_key` | API key (falls back to `OPENAI_API_KEY`) | env var |
| `--openai_batch_size` | Subtitle lines translated together per call | `25` |

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
  --translator {google,ollama,openai}
                        Translation backend (default: google)
  --voice-sample FILE   Reference WAV for XTTS voice cloning (optional)
  --output-dir DIR      Directory for the final video / subtitles
  --subtitles-only      Generate only the translated .srt (no TTS/video)
  --no-resume           Ignore previous checkpoint and start fresh
  --keep-temp           Keep temporary files after processing
```

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
- Original audio: 20% volume (background)
- Dubbed audio: 150% volume (foreground)
- Output: AAC 128kbps, video copied without re-encoding

## License

MIT License - see LICENSE file

## Credits

- [OpenAI Whisper](https://github.com/openai/whisper) - Speech recognition
- [Edge-TTS](https://github.com/rany2/edge-tts) - Microsoft TTS
- [Piper](https://github.com/rhasspy/piper) - Offline neural TTS
- [Coqui TTS](https://github.com/coqui-ai/TTS) - XTTS voice cloning

## Contributing

Issues and pull requests welcome!

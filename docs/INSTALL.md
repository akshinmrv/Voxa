# Installing Voxa

There are four ways in. Pick the first one that fits:

1. [VoxaSetup.exe](#windows-voxasetupexe) if you are on Windows and want an app.
2. [The one-line installer](#one-line-installer) on Windows, macOS or Linux.
3. [pipx](#by-hand) if you already manage Python tools yourself.
4. [Docker](#docker) if you'd rather keep Python, PyTorch and FFmpeg off the host.

Whichever you choose, `voxa doctor` tells you afterwards what works and what is missing.

## Windows: VoxaSetup.exe

Download it from [voxa.servoogle.com/download](https://voxa.servoogle.com/download). The link
always points at the newest release on GitHub.

The installer is 11 MB. It installs for your user only and doesn't ask for administrator
rights. It puts Voxa, the Python it runs on and Voxa Studio in
`%LOCALAPPDATA%\Programs\Voxa`, adds Voxa Studio to the Start menu, and installs FFmpeg with
winget if you don't have it. While it runs it downloads the rest, about 1 GB, most of which is
PyTorch. It shows up in *Apps & features*, where you uninstall it.

It isn't code-signed yet. Windows may stop it with *Windows protected your PC*; choose *More
info*, then *Run anyway*. Your browser may also ask whether to keep the file.

Your dubs, settings and API keys live in `%USERPROFILE%\Voxa`, and engines you add later in
`%USERPROFILE%\.voxa`. Uninstalling leaves both alone. To upgrade, run the newer
VoxaSetup.exe over the old one.

## One-line installer

No Python needed beforehand.

```powershell
irm https://voxa.servoogle.com/install.ps1 | iex          # Windows (PowerShell)
```

```bash
curl -fsSL https://voxa.servoogle.com/install.sh | sh     # macOS, Linux
```

The script uses [uv](https://docs.astral.sh/uv/) to put Voxa, its console and the Python they
need in an environment of their own. That takes 0.85 GB on Windows and 1.4 GB on Linux, mostly
PyTorch: the CUDA build if uv finds an NVIDIA GPU, the CPU build otherwise. It installs FFmpeg
with winget on Windows and Homebrew on macOS. On Linux it prints the command instead, since
that one needs `sudo`. It adds a Voxa Studio shortcut and finishes by running `voxa doctor`.

Run it again to upgrade. `uv tool uninstall voxa-dub` removes it. The settings it reads, such
as `VOXA_EXTRAS=serve,piper`, are listed at the top of each script.

## By hand

**FFmpeg.** Voxa checks for it when it starts and tells you if it's missing.

```bash
sudo apt install ffmpeg      # Debian, Ubuntu
sudo dnf install ffmpeg      # Fedora, RHEL
brew install ffmpeg          # macOS
winget install Gyan.FFmpeg   # Windows
```

**Voxa.** Python 3.10 to 3.14. On an Intel Mac it's 3.10 to 3.12, because PyTorch has no build
for anything newer there.

```bash
pipx install voxa-dub                  # the command line
pipx install "voxa-dub[studio]"        # the command line, the console and Voxa Studio
```

The package on PyPI is `voxa-dub`; the command it installs is `voxa`. (There is no `voxa`
package to install.) To try it once without installing anything:

```bash
uvx voxa-dub talk.mp4 --target_lang ru
```

<details>
<summary>From source</summary>

```bash
git clone https://github.com/akshinmrv/Voxa
cd Voxa
python3 -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate

# The CPU build of PyTorch is much smaller. For an NVIDIA GPU, see "GPU" below.
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -e ".[dev,studio]"
```

The console ships inside the package. Working from source, build it once with
`npm ci && npm run build:console` in `web/`.

</details>

## Docker

```bash
docker run --rm -v "$PWD:/data" ghcr.io/akshinmrv/voxa talk.mp4 --target_lang ru
```

The dub is written next to the input on your machine. The defaults need no API key; pass one
with `-e OPENAI_API_KEY=...` if you switch engines. Mount a cache so the Whisper models aren't
downloaded on every run:

```bash
docker run --rm -v "$PWD:/data" -v voxa-cache:/cache \
    ghcr.io/akshinmrv/voxa talk.mp4 --target_lang ru
```

The image is about 3 GB, mostly PyTorch's CPU build, FFmpeg and Whisper. It includes the
console:

```bash
docker run --rm -p 127.0.0.1:8000:8000 -v "$PWD:/data" -v voxa-cache:/cache \
    -v voxa-engines:/engines ghcr.io/akshinmrv/voxa serve --host 0.0.0.0
```

Open the link it prints (`http://127.0.0.1:8000/?token=...`). Because the server listens beyond
the container's loopback, the console asks for an access token: a new one on each start, or
your own with `-e VOXA_TOKEN=...`. Publishing the port on `127.0.0.1` keeps it off your network.

Uploads, dubs and the keys you add in Settings stay in the mounted folder. Engines go into the
`voxa-engines` volume, from the console's Engines page or the command line:

```bash
docker run --rm -v voxa-cache:/cache -v voxa-engines:/engines \
    ghcr.io/akshinmrv/voxa engines install chatterbox
```

To translate with Ollama running on the host, add
`-e OLLAMA_HOST=http://host.docker.internal:11434` (and on Linux,
`--add-host=host.docker.internal:host-gateway`).

## Check the install

```bash
voxa doctor            # FFmpeg, packages, GPU, engines, keys
voxa doctor --online   # also tries Google, Microsoft Edge and Hugging Face
voxa doctor --deep     # also loads XTTS and pyannote, which tend to break on updates
```

Each line says what it found and, when something is missing, the command that fixes it for
this particular install (`pipx inject` if Voxa lives in pipx, a new VoxaSetup.exe if that's how
you installed it). It reports whether an API key is set, never the key. The console's System
page runs the same checks.

## Optional engines

The default install translates with Google and speaks with Microsoft Edge's voices. Everything
else is opt in.

| Install | Gives you |
|---|---|
| `pipx install "voxa-dub[faster]"` | `--whisper-backend faster`: transcription 2 to 4 times quicker, no PyTorch needed |
| `pipx install "voxa-dub[piper]"` | `--tts piper`: offline speech. The engine is GPL-3.0 and each voice has its own licence ([NOTICE](../NOTICE.md#41-piper-voices)) |
| `pipx install "voxa-dub[anthropic]"` | `--translator anthropic` |
| `pipx install "voxa-dub[xtts]"` | `--tts xtts`: voice cloning, non-commercial weights (see below) |
| `pipx install "voxa-dub[url]"` | `voxa <video-url>`: downloads the input with yt-dlp first |
| `pipx install "voxa-dub[diarize]"` | `--diarize`: a separate voice for each speaker (pyannote) |
| `voxa engines install chatterbox` | `--tts chatterbox`: clones each speaker in 23 languages, MIT. About 4.5 GB; slow without a GPU |
| `voxa engines install voxcpm` | `--tts voxcpm`: VoxCPM2 clones each speaker in 30 languages, Apache-2.0. About 6.4 GB; made for an NVIDIA GPU |
| `voxa engines install demucs` | `--separate`: keeps the original's music and effects, with its speech taken out. About 0.7 GB |

If you installed with VoxaSetup.exe or the one-line installer, the console's Engines page and
`voxa doctor` give you the right command for your install.

### Engines in environments of their own

Chatterbox, VoxCPM2 and Demucs pin their own versions of PyTorch and transformers. Installing
them next to Voxa would break one or the other, so `voxa engines install` puts each in its own
environment under `~/.voxa/engines`, and Voxa talks to it through a small worker process.
`voxa engines remove <name>` deletes that folder and nothing else.

On a laptop CPU, Chatterbox took 40 to 60 seconds per sentence, so a GPU matters here. Every
clip it makes carries Resemble AI's inaudible PerTh watermark. Chatterbox sometimes keeps
going after a line, with extra words or a murmur; Voxa listens for the line's last word with
Whisper and cuts what follows. VoxCPM2 and XTTS get the same check.

VoxCPM2 speaks seven languages Chatterbox doesn't, Vietnamese, Thai and Indonesian among them.
It needs a GPU even more: on a laptop CPU one sentence took 2 to 3 minutes, and loading the
model peaked at 9.5 GB of memory. In our test in five languages Whisper understood every word
it said. Its clones of an English speaker scored 0.74 for speaker similarity (0.50 when
speaking German), against 0.02 to 0.17 for its built-in voices.

Demucs separates speech from everything else. By default Voxa lays the dub over the whole
original turned down low, so the music is barely there and the old speech is only quieter.
With `--separate`, the speech is removed first and the music and effects stay at full volume.
In a test mix of speech over music, the music came out 26 dB louder than in the default mix.
Whisper also gets the separated speech: over music 12 dB louder than the voice, its word error
rate fell from 32% to 12%. Where the dub speaks, the background drops just enough to sit 10 dB
under it (`--no-duck` turns that off). Separation took about 0.6 times the video's length on a
laptop CPU and 1.7 GB of memory, and the result is kept for the next language. Demucs' code is
MIT, but its author says the licence of the weights is unclear; check
[NOTICE](../NOTICE.md#47-engines-in-environments-of-their-own-voxa-engines) before commercial use.

### XTTS

`voxa-dub[xtts]` installs [coqui-tts](https://github.com/idiap/coqui-ai-TTS), the maintained
fork. The XTTS-v2 weights are licensed for non-commercial use only (CPML), and Coqui, the
company that could have sold you a commercial licence, closed in 2024. For commercial cloning
use Chatterbox or VoxCPM2. If `import TTS` fails after installing, pip probably picked a
transformers version coqui-tts can't use; `pip install "transformers==4.53.0"` fixes it.

### Several speakers

`--diarize` works out who speaks when and gives each speaker their own voice, so an interview
isn't dubbed in one voice. It needs a Hugging Face token (`--hf-token`, `HF_TOKEN`, or Settings ›
Speakers in the console) and a one-time acceptance of the model terms at
[hf.co/pyannote/speaker-diarization-3.1](https://huggingface.co/pyannote/speaker-diarization-3.1).
The pipeline is MIT and only gated; the speaker-embedding model it loads is CC BY 4.0, so credit
it. Pass `--num-speakers N` if you know the count.

Edge and OpenAI give each speaker a different voice on their own. XTTS, Chatterbox and
VoxCPM2 clone each speaker from the stretch of the original where that person talks longest.
Piper has one voice per language, so for Piper you name the voices yourself with
`--speaker-voices`. Diarization needs the original audio, so it doesn't combine with
`--subtitles`.

### Dubbing from a link

`voxa "https://..." --target_lang de` downloads the video with yt-dlp, then dubs it as usual.
Downloading may break the platform's terms of service, and it is up to you to have the right to
the content. Voxa says so before it fetches anything.

## GPU

Voxa finds an NVIDIA GPU on its own; `--device cpu` keeps everything on the CPU.

| Stage | On the GPU |
|---|---|
| Whisper, both backends | yes (CUDA, fp16) |
| Voice cloning: XTTS, Chatterbox, VoxCPM2 | yes |
| Demucs separation | yes |
| Quality gate | yes |
| Translation | no: it waits on the network, and Ollama uses the GPU by itself |
| Edge and OpenAI speech | no: they run in the cloud |
| Piper | no: CPU (ONNX) |

The one-line installer picks the CUDA build of PyTorch when it sees an NVIDIA GPU. By hand,
install that build instead of the CPU one:

```bash
# Match the CUDA version your driver supports: https://pytorch.org/get-started/locally/
pip install torch --index-url https://download.pytorch.org/whl/cu124
python -c "import torch; print(torch.cuda.is_available())"   # True
```

The run log says `Using device: CUDA` at the transcription step. Rough memory per Whisper
model: `tiny` and `base` about 1 GB, `small` 2 GB, `medium` 5 GB, `turbo` 6 GB, `large` 10 GB.
XTTS wants about 4 GB on top.

A GPU newer than your PyTorch build can report `torch.cuda.is_available()` as `True` and then
fail with *no kernel image is available for execution on the device*. Install a newer CUDA
build, or switch to `--whisper-backend faster` (`voxa-dub[faster]`), which doesn't depend on
PyTorch's CUDA kernels. On the GPU it needs NVIDIA's libraries:
`pip install nvidia-cublas-cu12 nvidia-cudnn-cu12`. AMD GPUs fall back to the CPU.

**Apple Silicon** is experimental. `--device mps` (or Settings › Performance in the console)
tries the Mac's GPU for Whisper, diarization, Chatterbox and Demucs. Each of them falls back to
the CPU if it fails, so a dub never stops over it. XTTS, VoxCPM2 and the faster backend stay on
the CPU. It is off by default because nobody has measured it on a Mac yet, and Whisper on MPS
may well be slower than on the CPU. If you try it, an issue with your timings would help decide
whether it should become the default.

## Updates

Once a day the console, `voxa serve` and `voxa doctor` ask PyPI for the newest version. If
yours is older, they say so and show how your install gets the new one: the new VoxaSetup.exe,
or the one command that matches how you installed Voxa. PyPI sees that request like any
download (your IP address and Voxa's version); nothing else is sent. Turn it off in Settings ›
General, or everywhere with `VOXA_NO_UPDATE_CHECK=1`.

# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Python 3.13 and 3.14.** CI and the release now test them alongside 3.10–3.12. On both, Voxa
  and its `[serve]` and `[piper]` extras install from ready-made wheels, `voxa serve` runs, and
  a 29-second clip dubbed into German came out whole: Whisper missed at most one word of Edge's,
  and 3–4 of Piper's, a voice that misses 5 of the same clip on 3.11. On an Intel Mac stay on
  3.10–3.12, since PyTorch has no build for 3.13 or later there, and on any Mac, Piper on 3.14
  needs macOS 14 or newer, as far back as onnxruntime builds for it.

### Removed

- **Python 3.9.** It reached its end of life in October 2025, so Voxa now needs 3.10 or newer.
  On 3.9, pip keeps installing 1.13.0, the last release that runs there. The one-line installer
  and the Docker image bring their own Python 3.12, so they aren't affected.

## [1.13.0] - 2026-11-06

### Added

- **VoxCPM2 (`--tts voxcpm`), cloning in 30 languages.** `voxa engines install voxcpm` puts
  OpenBMB's VoxCPM2 (Apache-2.0, code and weights) in an environment of its own, and `--tts
  voxcpm` clones each speaker from the original video, as Chatterbox does, in 30 languages:
  seven of them (Vietnamese, Thai, Indonesian, Tagalog, Khmer, Lao, Burmese) no other cloning
  engine in Voxa speaks. It is made for an NVIDIA GPU. On a laptop CPU (Ryzen 5 5600H) a
  sentence took 2–3 minutes, 18–22× its length in its own voices and 26–31× cloning, and
  loading it peaked at 9.5 GB of memory (in float32 it doesn't fit 14 GB at all), so the dry
  run says so, and on a CPU the run says how long its speech may take: a 29-second clip dubbed
  into German took 12.5 minutes, 11 of them speaking, where the run had said 8 to 14. In a
  test in five languages (en, de, tr, vi, id) Whisper heard every word it said; its clones of
  an English speaker scored 0.74 for speaker similarity (ECAPA), 0.50 speaking German, against
  0.02–0.17 for its own voices.

### Changed

- **Ollama lets go of its model before Chatterbox or VoxCPM2 loads**, as it already did before
  Demucs: translation is over by then, and llama3's 5 GB plus the 9.5 GB VoxCPM2 peaks at
  while loading come to more than a 14 GB laptop has.

### Fixed

- **The console's voice sample reaches Chatterbox.** The console sent its **Voice sample** to
  XTTS only, so a Chatterbox dub cloned from a sample cut from the video instead of the one
  given. Every cloning engine gets it now.

## [1.12.0] - 2026-11-05

### Added

- **Keep the music and effects (`--separate`).** The original stays under the dub as a faint
  bed, at 5%, which leaves its music barely audible and its speech only quieter. With `voxa
  engines install demucs` and `--separate`, Demucs takes the speech out first, in an
  environment of its own, and the music and effects go under the dub at full volume. In a test
  mix of speech over music, dubbed into German, the music came out 26 dB louder than in the
  faint bed and the original speech 5 dB quieter. The separation runs before transcription, so
  Whisper and a cloned voice get the speech alone: over music 12 dB louder than the speech,
  Whisper's word error rate fell from 32% (it made up the last sentence) to 12%, and in a
  cloning reference cut from it the gaps between words are 30 dB under the voice instead of 3.
  A transcript already made is kept, so adding `--separate` to a finished dub only remixes it.
  Where the dub speaks, the background is lowered just enough to stay 10 dB under it, and
  between lines it plays at its own level (`--no-duck` keeps it at one level): over music 12
  dB louder than the speech, which came out 7 dB over the dub, German Whisper misheard 34% of
  the dub without that and 6.5% with it, the same as under the faint bed (5.2% alone). On a
  laptop CPU it took 0.6× the video's length and 1.7 GB of memory, however long the video,
  since it works two minutes at a time; the result is kept for a dub of the same video into
  another language. Ollama keeps the model it translated with in memory for five minutes,
  which in a batch left Demucs short on a 14 GB laptop, so Voxa asks Ollama to free that model
  first (5.0 GB for llama3). The console offers it as **Background → Keep the music and
  effects**. Demucs' code is MIT, but the licence of its weights is unclear, which `voxa
  engines`, the console and the dry run say.
- **The container image has the console, and engines install into a volume.** `docker run -p
  127.0.0.1:8000:8000 … ghcr.io/akshinmrv/voxa serve --host 0.0.0.0` opens the console on
  http://127.0.0.1:8000; it is built from `web/` in a stage of its own, so the image needs no
  Node. `voxa engines install` works in the container too, into `/engines` (a volume, so an
  engine outlives the container), and the console uses what is there. A port-mapped request
  isn't loopback, so the console can't change settings, keys or engines from inside a
  container; its refusal now says to pass keys with `-e` and install an engine with the CLI.
  CI builds and starts the image on every push, where before only a release built it.
- **Ollama wherever `OLLAMA_HOST` says.** Voxa called Ollama on localhost:11434 only, which
  inside a container is the container itself. It now reads `OLLAMA_HOST` as Ollama's own tools
  do (`host`, `host:port` or a URL), so `-e OLLAMA_HOST=http://host.docker.internal:11434`
  reaches Ollama on the host; `voxa doctor` says where it looked.

### Changed

- **The container image is 1.3 GB smaller.** openai-whisper pulls in triton on Linux for its
  CUDA kernels, which it imports only for a tensor on a GPU; the CPU-only image no longer
  carries it. The same build measured locally with and without it: 4.31 GB → 2.98 GB; a dub
  inside it (Whisper, Ollama on the host, Edge) came out in German, as Whisper heard it back
  (p=1.0).

## [1.11.1] - 2026-11-04

### Security

- **Your OpenAI key is no longer sent to a self-hosted speech server.** With
  `--openai-tts-base-url` set, speech requests carried `OPENAI_API_KEY` to that address — to
  the server you meant, or to whatever else answers there. Such a server now gets no key, or
  `OPENAI_TTS_API_KEY` (`--openai-tts-api-key`) if it wants one of its own; one that refuses a
  request for want of a key is told once which variable to set, and `voxa doctor` says which
  key the server gets. Checked with a local server that records each request's header: 1.11.0
  sent it the OpenAI key; now it receives none, or the server key when one is set.

### Fixed

- **The console's connection test for OpenRouter asked OpenAI.** It sent the OpenRouter key to
  api.openai.com, which refused it, so the test failed whatever the key. It now asks OpenRouter
  — on its key endpoint, since OpenRouter's model list answers any key.
- **Edge speaks again on installs with an older edge-tts.** Microsoft's service now refuses
  (403) every request from edge-tts before 7.3.0, which added the token it asks for, so the
  default engine made no speech at all. Voxa needs edge-tts 7.3.1 or newer — upgrading Voxa
  brings it — and when Microsoft refuses one anyway, the log names the installed version and
  the command that upgrades it. Checked on one machine, minutes apart: 7.2.8 got a 403 every
  time, 7.3.0 and 7.3.1 spoke.
- **A video with no audio track is explained, and can be voiced.** It used to stop at step 1
  on ffmpeg's "Output file does not contain any stream". Now the run, and `--dry-run`, say
  before anything is made that there is no speech to transcribe, and point to `--subtitles`:
  with a script, a silent screen recording is voiced and the dub becomes its only track. A
  cloning engine asks for `--voice-sample` there, since there is no voice to copy.

## [1.11.0] - 2026-11-03

### Added

- **Chatterbox, and engines that install themselves.** `voxa engines install chatterbox` — or
  Install on the console's Models page — puts Chatterbox Multilingual (MIT) in an environment of
  its own under `~/.voxa/engines`, made with uv, which also picks the CPU or CUDA build of
  PyTorch for the machine. Its pinned PyTorch and transformers can't clash with Voxa's or
  XTTS's, and `voxa engines remove` deletes it. `--tts chatterbox` then clones each speaker
  from the original video in 23 languages, through a worker that loads the model once per run.
  As Chatterbox's README advises for cloning across languages, `cfg_weight` is 0 so the dub
  doesn't keep the source language's accent. Measured on a laptop CPU: German, Russian and
  Turkish sentences cloned from an English speaker came back word for word (CER 0), at 40–60
  seconds a sentence; a 45-second clip took 11 minutes to dub, so a GPU matters. Every clip
  carries Resemble AI's inaudible PerTh watermark. `voxa doctor`, `--dry-run` and the job form
  say when it isn't installed or doesn't speak the language, before a run starts.
- **Speech a voice model adds after a line is cut.** Chatterbox sometimes keeps talking once
  a line is over — a few made-up words, or part of the line again. Each clip is transcribed
  with word timings (by the quality gate's ASR, or a small faster-whisper model of its own) to
  find where the line ends, and what follows is cut with a short fade. On the clip where it
  happened, the line's character error went from 19% to 0 with every word kept; the four
  clean clips were left as they were.
- **A one-line installer.** `irm https://voxa.servoogle.com/install.ps1 | iex` on Windows,
  `curl -fsSL https://voxa.servoogle.com/install.sh | sh` on macOS and Linux. It needs no
  Python beforehand: uv installs Voxa and its console into an environment of their own, with
  the Python they run on. It installs FFmpeg through winget or Homebrew (on Linux it prints the
  command, since that needs sudo), adds a Voxa Studio shortcut, and ends with `voxa doctor`.
  The site's install section, which still showed a clone-and-`pip install .` route, now shows
  these instead.
- **`voxa doctor` checks the install.** It lists what works (FFmpeg, packages, GPU, each
  translator and voice engine, the extras, disk space), what is optional and not set up,
  and the command that fixes each item for this install: `pipx inject` when Voxa lives in
  pipx, the running Python's pip otherwise. It says whether an API key is set, never its
  value. `--online` also tries Google, Microsoft Edge and Hugging Face, which is how a
  rate-limited Google endpoint shows up before a dub fails on it; `--deep` loads XTTS and
  pyannote, which break on dependency updates; `--json` is for scripts. When Voxa can't
  start for a missing package or FFmpeg, it now points at `voxa doctor` (the missing-package
  message used to suggest `pip install -r requirements.txt`, which a pip install doesn't have).
- **`voxa studio`: the console now comes with the package.** Installing `voxa-dub[serve]`
  used to bring only the server; the console had to be run from a clone of the repository
  with Node. The package now carries it as a static build, `voxa serve` serves it on the same
  address as its API, and `voxa studio` starts the server and opens the console in the
  browser, in the browser's language. The Docker image doesn't include it yet.
- **Self-hosted speech servers get the target language.** With `--openai-tts-base-url`, each
  request now carries the target language — a field Chatterbox-TTS-Server and VoiceStudio accept
  for choosing it — while OpenAI's own API gets nothing extra. A server that rejects the field
  gets the line again without it and isn't sent it again. `--dry-run` names the server and the
  language instead of reading as if the speech went to OpenAI. Tested end to end with
  VoiceStudio 0.5.7 and its OmniVoice model on a CPU: a 45-second clip dubbed into Azerbaijani,
  each line transcribed back within 7% character error of the text Voxa sent (2.9% on average).
- **NOTICE.md covers self-hosted speech servers** (§4.6): the dub's licence follows the model
  the server runs, not the server. VoiceStudio's default model, OmniVoice, is non-commercial;
  Chatterbox is MIT. The README shows how to point Voxa at VoiceStudio.

### Fixed

- **A translation with letters of another script is caught.** An LLM can slip a word in
  another script into a line — Ollama's llama3 put Chinese characters into a Turkish one —
  and the voice then stumbles over it. Such a line is now translated again, then with
  `--fallback-translator`, and if it's still mixed the foreign letters are dropped; the log
  says which line and what happened. Latin letters always pass, since brand names and
  acronyms keep them in any language. On that Turkish dub, one retry gave a clean line.
- **Piper wasn't found in a pipx install on Windows.** Its binary isn't on PATH there, and
  Voxa looked next to Python for `piper` while the file is `piper.exe`.
- **The install hint for `voxa serve` named the wrong package.** Without the `[serve]` extra
  it told you to install `voxa[serve]`; `voxa` on PyPI is an unrelated project, and the
  package is `voxa-dub`.

## [1.10.0] - 2026-10-27

### Added

- **Piper says what each voice's licence allows.** Every voice in the table now carries the
  licence from its model card, and Voxa reports it when it picks the voice — as a warning when
  the voice isn't cleared for commercial use — and in `--dry-run`. Until now the README called
  `--tts piper` "fully permissive", but several of its voices are licensed for non-commercial
  or research use only, and nothing at run time said so. A network test
  (`VOXA_NETWORK_TESTS=1`) checks each label against the voice's model card.

### Changed

- **Piper's English, Russian and Vietnamese voices are now cleared for commercial use.** English
  moves from `en_US-lessac` (research licence) to `en_US-kristin` (public domain), Russian from
  `ru_RU-ruslan` to `ru_RU-denis` (CC BY-NC-SA 4.0 → CC0), and Vietnamese from
  `vi_VN-vivos-x_low` to `vi_VN-vais1000-medium` (CC BY-NC-SA 4.0 → CC BY 4.0), so 11 of the 15
  voices now allow commercial use, up from 8. Measured by transcribing the same three sentences
  per voice with Whisper large-v3 and no language hint: the Vietnamese character error rate drops
  from 11.2% to 1.3%, Russian is unchanged at 0.9%, and English goes from 0.4% to 0.9%, with
  every English error, old voice and new, on the word "Voxa". The new English voice speaks a
  little slower (17.5 characters a second, against 20.3). It downloads on the first run after the
  update. NOTICE.md now also lists the voice each one was fine-tuned from.

## [1.9.1] - 2026-10-22

### Fixed

- **`voxa serve` on Python 3.9: a queued dub no longer crashes.** A job that had to wait for a
  free slot — a second video while the first was still running — failed with "attached to a
  different loop" instead of starting once the first one finished. Python 3.10 and later, and the
  Docker image, were not affected.

## [1.9.0] - 2026-10-21

### Fixed

- **Piper now speaks the target language — and fetches its own voice.** Every language except
  Russian was being spoken with the English voice (`en_US-lessac`), and the model was never
  downloaded: `--tts piper` only worked if the right file was already in `~/.piper_models`. The
  per-language voice table existed but wasn't used. Voxa now picks the voice from that table and
  downloads it, with its config, from rhasspy/piper-voices on first use; after that the run is
  fully offline. A language with no voice mapped fails with a clear message — and `--dry-run`
  reports it up front — instead of falling back to another language's voice. Two entries pointed
  at voices that don't exist (Japanese, Dutch) and were corrected. Measured on the same German
  sentence: Whisper hears the new voice as German (p=1.00) and transcribes it almost verbatim;
  the old one came out as unintelligible English. Reported by @deelipsolanki-DSML in #6.
- **A translation that didn't happen no longer finishes as a dub.** When the translator failed —
  Google rate-limiting the machine, an unreachable Ollama, a bad key — each engine handed the
  source text back, and that flowed on into synthesis: the run reported success with a "German"
  dub spoken in English, and cached it, so running again changed nothing. Voxa now checks the
  translation before using it. If nothing came back translated, or at least two lines and half of
  them didn't, it stops with a clear error, saves nothing, and the next run retries. A few lines
  left as they were — names, numbers, a lone "OK." — only produce a warning. Found while testing
  the Piper fix above.

### Added

- **Queue several videos in one go.** The job form takes more than one video now: drop or pick
  a handful and each gets its own job, uploaded in order. A single video still opens on its own
  page; a batch goes to the jobs list, where they can be watched together. How many of them
  actually run at the same time is the concurrency setting below.
- **Save each dub automatically (Settings → Advanced).** With it on, a finished job's video is
  downloaded as soon as it completes, instead of waiting for a click. Only dubs that finish
  while the console is open are saved — opening the jobs list doesn't re-download the history —
  and a browser may ask permission before saving several files from one page. Off by default.
- **Dub several videos at once in the operator console.** `voxa serve` ran one job at a time, so
  a second upload just queued. Settings → Advanced now has "Videos dubbed at once" (1–4,
  default 1, so nothing changes unless you ask for it). Raising it pays off when the engines
  spend their time waiting on the network — cloud translation and speech — and costs memory
  when they don't, since each job is a separate process loading its own Whisper model. Two dubs
  of the *same* video still run one after the other: they share a content-keyed work dir and its
  resume state, so overlapping them would race. The limit is read when a job starts, so changing
  it applies to the next job without restarting the server.

## [1.8.0] - 2026-07-30

### Added

- **Dub from a URL in the operator console.** The `voxa serve` job form now has an "Upload
  file / From URL" switch: paste a video link and the backend runs the CLI's URL pipeline
  (yt-dlp download, then the normal dub) instead of an upload. It appears only when the `url`
  extra is installed, and carries the same Terms-of-Service notice as the CLI — you are
  responsible for having the right to the content. This closes the gap where the URL input
  shipped in 1.4.0 for the CLI only.

## [1.7.0] - 2026-07-30

### Added

- **Translation and speech cost estimates.** The per-job summary now reports an estimated cost, not
  just token counts. For translation, a couple of low-cost defaults are built in and `--llm-prices`
  (a JSON object of `model → [input, output]` USD per 1M tokens, usually set once in a `--config`
  file) covers any model on your plan. For OpenAI TTS, the characters spoken are always reported and
  `--tts-price` (USD per 1M characters) turns that into a cost. Free engines and unpriced models
  still just report usage.

### Changed

- **A running clock on a single-video run.** The source media length is logged up front and each
  long step prints the elapsed time — `[6/7] (2m10s) Synthesizing speech...` — so a long dub isn't
  a silent wait. The fine-grained "time remaining" stays on the per-segment progress bars, since
  step cost depends on the engine and hardware.

## [1.6.4] - 2026-07-29

### Fixed

- **A closing line that breathes past the source audio is no longer cut off.** The last-line pacing
  (1.6.1) can extend the final line to the end of the *video*, but the mix ended it at the source
  *audio* stream — which can be shorter than the video — truncating the sentence. The mix now runs
  to the longer of the two, so the closing line always finishes.

### Added

- **Per-speaker voices for XTTS and Piper, plus a `--speaker-voices` override.** Under `--diarize`,
  XTTS now clones each speaker from where they talk in the source, so every dubbed speaker keeps the
  original speaker's voice. `--speaker-voices "SPEAKER_00=voice,SPEAKER_01=voice"` pins a voice per
  speaker for any engine — Edge/OpenAI voice names, Piper model files (the only way to get
  per-speaker Piper, whose pool is one voice per language), or XTTS reference wavs. Unlisted
  speakers keep the automatic voice.

## [1.6.3] - 2026-07-28

### Added

- **The operator console runs diarization.** The `voxa serve` job form now has a "Speakers" toggle
  that gives each speaker their own voice, with an optional speaker count — mirroring the CLI's
  `--diarize`. It appears only when the `diarize` extra is installed, and the Hugging Face token is
  read from the server's environment, just like the OpenAI key.

### Changed

- **Diarization folds a voice it accidentally split.** In auto mode (no `--num-speakers` or
  `--max-speakers`), pyannote can split one clean voice into two speakers; Voxa now merges speakers
  whose voice embeddings are near-identical back into one, so a two-person clip isn't dubbed in
  three voices. It merges by voice, not by timing, so it never mislabels the way a positional guess
  would, and setting a count or bound keeps pyannote's own clustering untouched.

## [1.6.2] - 2026-07-28

### Added

- **`--min-speakers` / `--max-speakers` for `--diarize`.** Bound the speaker count when you don't
  know it exactly — pyannote clusters within the bounds, which curbs the over-splitting a clean or
  short recording can produce. `--num-speakers` still wins when you do know the exact count.

### Changed

- **Diarization is steadier.** Sub-quarter-second diarization turns (a clipped word, a brief
  misattribution to a new speaker) are dropped before speakers are assigned, and a segment that
  overlaps no turn now takes the nearest turn's speaker instead of an arbitrary one.

## [1.6.1] - 2026-07-28

### Changed

- **The final line now finishes at a natural pace.** The last line has nothing after it to overlap,
  so it is no longer compressed to its own spoken window — it plays out to the end of the media
  (its start still anchored to the source), which keeps a wordier final line from sounding rushed.
  Earlier lines already breathe into the pause that follows them, added in 1.6.0.

### Documentation

- The README (all three languages) now documents speaker diarization (`--diarize`) and its
  per-speaker voices, and notes that the most natural pacing comes from an LLM translator.
  `NOTICE.md` records the pyannote diarization model: MIT, gated on Hugging Face, no commercial
  restriction.

## [1.6.0] - 2026-07-28

### Added

- **Speaker diarization with per-speaker voices (`--diarize`).** Detects who speaks when
  (pyannote.audio), keeps every sentence within one speaker, and gives each speaker a **distinct
  voice** — Edge picks different voices from the language's pool, OpenAI cycles its voice set.
  Optional extra (`pip install 'voxa-dub[diarize]'`) with a Hugging-Face-gated model: MIT-licensed
  and free to ship, but you accept its terms and pass a token (`--hf-token` / `HF_TOKEN`). Optional
  `--num-speakers` hint. Default off, so runs without `--diarize` are byte-for-byte unchanged.
  Piper/XTTS stay single-voice for now, and it isn't yet combinable with `--subtitles`
  (diarization needs the source audio).

### Changed

- **Dubbed lines now breathe into the pause before the next line.** When the target language is
  wordier than the source (Turkish or Russian for English, say), a line no longer has to be sped
  up to fit only its original spoken window — it may extend into the following silence, up to a
  short gap before the next line's onset, so the pace stays natural instead of sounding rushed.
  The start of every line is still anchored to the source timeline, so nothing drifts and lines
  never overlap. This pairs with an LLM translator's per-line length budget for the most natural
  result; with the plain `google` translator a very verbose line can still be compressed to fit.

## [1.5.0] - 2026-07-27

### Added

- **Import subtitles with `--subtitles file.srt`.** Skip Whisper and dub from a source-language
  SRT you already have — hand-corrected captions, or accurate subtitles that shipped with the
  source. The lines are still translated and spoken; audio extraction and transcription are
  skipped, and editing the SRT re-runs the stages that depend on it. Local files and the normal
  transcribe-first flow are unchanged.

## [1.4.0] - 2026-07-27

### Added

- **Dub straight from a URL.** `voxa <video-url> --target_lang de` downloads the video with
  yt-dlp and then runs the normal pipeline on it. It is an optional extra —
  `pip install 'voxa-dub[url]'` — because downloading may breach the source platform's Terms
  of Service: the CLI prints a notice and **you are responsible for having the right to the
  content**. Local files behave exactly as before, and `--dry-run` reports the pending
  download without fetching anything.

## [1.3.1] - 2026-07-27

### Added

- **`voxa --version`.** Prints the version and exits.

### Fixed

- The version now comes from the package metadata (a single source of truth built from
  `pyproject.toml`) instead of a hard-coded "v1.0" string, so the `--help` banner, the startup
  configuration box and `--version` all report the real release (e.g. 1.3.0) instead of a stale
  number.

## [1.3.0] - 2026-07-26

### Changed

- **Network TTS now synthesises in parallel.** OpenAI and Edge speech ran one HTTP request
  per segment, sequentially — the single biggest bottleneck on a long dub, and one a GPU
  cannot help because the work is remote. Synthesis and placement are now separated: segments
  are synthesised concurrently (bounded by `--tts-workers`, default 4) while the
  order-dependent anchored placement pass stays sequential, so timing and drift are unchanged.
  On a measured run (2.4-min clip, 37 segments, RTX-class VPS) the speech step dropped from
  57.5s to 18.5s for OpenAI TTS at the default 4 workers (3.1×), and to 12.7s at 8 workers
  (4.5×); Edge TTS went 44.0s → 17.1s (2.6×) → 13.6s (3.2×). Longer, more network-bound clips
  gain more. Offline engines (Piper, XTTS) stay sequential since they are CPU/GPU-bound. Use
  `--tts-workers 1` for the old one-at-a-time behaviour, or raise it if your API tier allows.

### Added

- OpenAI TTS requests now retry with exponential backoff on rate-limit / 5xx errors, so the
  added concurrency rides out a 429 instead of dropping that segment's audio.
- **The operator console exposes the parallel-synthesis worker count.** Settings → Advanced has
  a "Parallel speech requests" field (1–16) that drives `--tts-workers` for console jobs, so the
  concurrency can be raised or lowered without touching the CLI.

## [1.2.0] - 2026-07-26

### Added

- **OpenRouter translator.** `--translator openrouter` reaches OpenRouter's OpenAI-compatible
  gateway, so a single `OPENROUTER_API_KEY` unlocks models from many vendors (DeepSeek,
  Gemini, Llama, and OpenAI/Anthropic too) with no extra to install — the `openai` client is
  already a core dependency. Model names are vendor-prefixed, e.g. `--openrouter_model
  deepseek/deepseek-chat`. It works everywhere the other LLM translators do: as a
  `--fallback-translator`, in the operator console's provider settings and connection test,
  and in `--dry-run` plans. Adding it was one chat adapter and one registry line — the
  extensibility the provider registries were built for.
- **Batch progress with ETA.** In multi-video runs, each finished video now prints an overall
  progress line — `📊 Batch progress: 7/20 videos · elapsed 21m00s · ~39m00s left` — with the
  ETA estimated from the average wall-time per completed video, and the summary reports the
  total. It's a plain line, not a rewriting progress bar, so it stays readable in the log file
  and when the output is piped; the per-video banner is unchanged.

## [1.1.0] - 2026-07-18

### Added

- **`--dry-run`.** Prints what a run would do — transcription model, translator and target,
  speech engine and voice, output path — and, most usefully, which cached steps it would
  reuse, so dubbing the same video into a second language shows up front that only
  translation and speech will rerun. It reports every blocker at once (a missing API key, a
  missing voice sample) instead of failing on the first, returns non-zero when it finds any,
  and writes nothing at all: no workspace, no log file.
- **Container image.** `docker run --rm -v "$PWD:/data" ghcr.io/akshinmrv/voxa clip.mp4
  --target_lang ru` — no Python, torch or ffmpeg on the host. Published to GHCR on each
  tagged release.
- **Speech-quality benchmark.** `scripts/benchmark.py` dubs one clip into several languages
  under `--quality-gate` and collects the round-trip word error rate per language;
  `docs/BENCHMARK.md` records a run across six languages together with its limitations.

## [1.0.1] - 2026-07-18

### Changed

- **The distribution is now published as `voxa-dub`.** The `voxa` name on PyPI belongs to an
  unrelated, abandoned package, so `pip install voxa` installed the wrong project entirely.
  Install with `pipx install voxa-dub` (or run it without installing: `uvx voxa-dub …`). The
  command it puts on your PATH is still **`voxa`**, and the import module is still `voxa`, so
  nothing changes once it is installed. Tagged releases now publish to PyPI automatically via
  Trusted Publishing.

### Added

- **Web frontend (`web/`).** A trilingual (EN/AZ/TR) public landing plus a local operator
  app, built with Next.js, Tailwind and next-intl. The landing is tuned for search and AI
  answer engines (hreflang, OpenGraph, JSON-LD, sitemap, robots, `llms.txt`); the operator
  app runs against `voxa serve`. A `public` build target swaps the app for a "run locally"
  notice so the landing can be deployed on its own.
- **`voxa serve`.** An optional FastAPI operator backend (behind the `[serve]` extra) that
  drives the pipeline per job and streams the seven-step progress over Server-Sent Events:
  `GET /api/options`, `POST /api/upload`, `POST /api/jobs`, `GET /api/jobs/{id}/events`, and
  result downloads. The core dubbing pipeline is unchanged — `serve` is a thin dispatch in
  the CLI.
- **CI** now also lints and builds the web frontend.

## [1.0.0] — 2026-07-10

First public release. Voxa was developed privately for some time before being opened; the
version number restarts at 1.0.0 rather than continuing a history nobody can see.

### Added

- **One-command dubbing.** `voxa video.mp4 --target_lang ru` transcribes, translates,
  synthesizes and mixes, with no API key required by default.
- **Four TTS engines** behind a `TTS_PROVIDERS` registry: `edge` (Microsoft neural voices),
  `openai` (instructable delivery), `piper` (fully offline), `xtts` (voice cloning).
- **Four translation backends** behind an `LLM_PROVIDERS` registry: `google`, `ollama`
  (local, private), `openai` and `anthropic`. LLM translation is context-aware — lines are
  translated in blocks so pronouns, gender, names and tone stay consistent — with automatic
  per-line fallback when a block response is malformed.
- **Anchored placement.** Each clip occupies the slot between its own source onset and the
  next line's onset. Over-runs are trimmed, short clips are padded, and the cursor is
  assigned rather than accumulated — so the dub cannot drift out of sync with the speaker.
- **Duration-matched translation.** The translator receives a character budget per line
  (`--speech-rate`), so a line fits its slot at a natural pace instead of being sped up.
- **No-slowdown fitting.** Clips are only ever sped up to fit; a short clip is padded with
  silence rather than stretched, which sounds dragged.
- **Word-onset refinement.** Segment starts are tightened to the first word's timestamp, so
  the dub doesn't begin before the speaker does.
- **Non-speech filtering.** Segments Whisper flags as likely non-speech (music intros it
  transcribed as phantom text) are dropped before synthesis.
- **Quality gate** (`--quality-gate`): each synthesized segment is transcribed back and
  scored for word error rate, clipping, near-silence and pacing, with a per-job report.
- **XTTS auto-regeneration**: XTTS sampling is stochastic, so a flagged segment is
  re-synthesized up to twice and the best-scoring take is kept.
- **LLM delivery direction** (`--detect-emotion`): an LLM tags each line with a short
  emotion/energy/pace instruction for OpenAI TTS, cached per job.
- **Self-hosted speech** (`--openai-tts-base-url`): route synthesis to any server exposing
  OpenAI's `/v1/audio/speech` — Chatterbox, LocalAI, Kokoro-FastAPI — with no API key and no
  extra Python dependency. This is the license-clean route to voice cloning.
- **`faster-whisper` backend** (`--whisper-backend faster`): 2-4× quicker, no torch, with
  built-in VAD.
- **Resumable runs.** Every step is checkpointed in `<video>_work/`; an interrupted job
  resumes. `--no-resume` forces a fresh start.
- **Preflight validation.** Missing input files and a missing ffmpeg are reported before any
  work begins, and ffmpeg's own error output is surfaced when it fails.
- **Structured logging** (`--log-format json`), `.env` loading, and JSON config defaults
  (`--config`).
- **Golden regression harness** covering the deterministic pipeline end to end, with no
  engine, network or API key required.
- Community health files, CI (lint + tests on Python 3.9–3.12), and Dependabot.

### Licensing

- Voxa is MIT and requires **no copyleft dependency**. The GPL-3.0 `pysrt` requirement was
  removed in favour of a built-in SubRip parser.
- Third-party engine licenses, the non-commercial status of the XTTS-v2 weights, and the
  unofficial nature of the `edge-tts` and `deep-translator` endpoints are documented in
  [NOTICE.md](NOTICE.md).

### Known limitations

- `--tts xtts` requires `coqui-tts`, whose model weights are **non-commercial** (CPML), and
  Coqui Inc. no longer exists to sell a commercial licence. Use `--openai-tts-base-url` with
  an MIT engine for commercial cloning.
- `--parallel` applies to the `google` and `ollama` translators only; LLM translators already
  batch whole blocks in one call.
- Synthesis requests are issued sequentially. For network-bound engines this is the main
  remaining performance headroom.

[Unreleased]: https://github.com/akshinmrv/Voxa/compare/v1.13.0...HEAD
[1.13.0]: https://github.com/akshinmrv/Voxa/compare/v1.12.0...v1.13.0
[1.12.0]: https://github.com/akshinmrv/Voxa/compare/v1.11.1...v1.12.0
[1.11.1]: https://github.com/akshinmrv/Voxa/compare/v1.11.0...v1.11.1
[1.11.0]: https://github.com/akshinmrv/Voxa/compare/v1.10.0...v1.11.0
[1.10.0]: https://github.com/akshinmrv/Voxa/compare/v1.9.1...v1.10.0
[1.9.1]: https://github.com/akshinmrv/Voxa/compare/v1.9.0...v1.9.1
[1.9.0]: https://github.com/akshinmrv/Voxa/compare/v1.8.0...v1.9.0
[1.8.0]: https://github.com/akshinmrv/Voxa/compare/v1.7.0...v1.8.0
[1.7.0]: https://github.com/akshinmrv/Voxa/compare/v1.6.4...v1.7.0
[1.6.4]: https://github.com/akshinmrv/Voxa/compare/v1.6.3...v1.6.4
[1.6.3]: https://github.com/akshinmrv/Voxa/compare/v1.6.2...v1.6.3
[1.6.2]: https://github.com/akshinmrv/Voxa/compare/v1.6.1...v1.6.2
[1.6.1]: https://github.com/akshinmrv/Voxa/compare/v1.6.0...v1.6.1
[1.6.0]: https://github.com/akshinmrv/Voxa/compare/v1.5.0...v1.6.0
[1.5.0]: https://github.com/akshinmrv/Voxa/compare/v1.4.0...v1.5.0
[1.4.0]: https://github.com/akshinmrv/Voxa/compare/v1.3.1...v1.4.0
[1.3.1]: https://github.com/akshinmrv/Voxa/compare/v1.3.0...v1.3.1
[1.3.0]: https://github.com/akshinmrv/Voxa/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/akshinmrv/Voxa/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/akshinmrv/Voxa/compare/v1.0.1...v1.1.0
[1.0.1]: https://github.com/akshinmrv/Voxa/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/akshinmrv/Voxa/releases/tag/v1.0.0

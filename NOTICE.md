# Third-Party Notices

**Voxa** is released under the [MIT License](LICENSE).

The Python package (`pip install voxa-dub`) contains only Voxa's own two modules — **no model
weights and no third-party source code**. Voxa orchestrates tools and models that you install and
run yourself. Their licences are their own, and some are **more restrictive than Voxa's MIT
licence** — including several of the speech voices Voxa downloads for you. The container image is
a different case: it bundles system packages (see §6).

Read this file before using Voxa commercially.

---

## 1. Quick answer: what is safe for commercial use?

| Configuration | Commercially usable? | Why |
|---|:---:|---|
| `--tts openai` + `--translator openai` / `anthropic` | ✅ Yes | Paid APIs under the provider's commercial terms |
| `--tts piper` | ⚠️ **Depends on the voice** | 11 of the 15 default voices allow it; the Japanese, Korean and Turkish voices do not, and the Chinese one is unknown. Most were fine-tuned from a voice licensed for research only (see §4.1) |
| `--translator ollama` | ⚠️ **Depends on the model** | The default, `llama3`, allows it under conditions (see §4.3) |
| `--tts edge` (default) | ⚠️ Grey area | Uses an **unofficial** Microsoft endpoint (see §3) |
| `--translator google` (default) | ⚠️ Grey area | Uses an **unofficial** Google endpoint (see §3) |
| `--tts xtts` | ❌ **No** | XTTS-v2 model weights are **non-commercial only** (see §4.4) |

> **Offline is not the same as commercially clean.** `--translator ollama --tts piper` sends
> nothing over the network, but whether you may use the result commercially depends on the voice
> for your target language and the LLM you run.

> **The default configuration (`--tts edge --translator google`) is convenient for personal use
> but is NOT recommended for a commercial product.** Prefer `openai`/`anthropic` translation and
> `openai` synthesis, or a self-hosted OpenAI-compatible endpoint whose model licence you have
> checked.

---

## 2. Runtime dependencies

Licences below were read from each package's PyPI metadata and, where the two disagree, the
licence file the package ships (October 2026).

### Required — installed by `pip install voxa-dub`

| Package | Role | License |
|---|---|---|
| [openai-whisper](https://github.com/openai/whisper) | Speech recognition | MIT |
| [edge-tts](https://github.com/rany2/edge-tts) | Default TTS engine | **LGPL-3.0** |
| [deep-translator](https://github.com/nidhaloff/deep-translator) | Google translation backend | Apache-2.0 (the licence file it ships; its metadata says MIT) |
| [openai](https://github.com/openai/openai-python) | OpenAI API client | Apache-2.0 |
| [torch](https://github.com/pytorch/pytorch) | Inference runtime | BSD-3-Clause (bundled components under other permissive licences) |
| [soundfile](https://github.com/bastibe/python-soundfile) | Audio I/O | BSD-3-Clause (libsndfile: LGPL) |
| [noisereduce](https://github.com/timsainb/noisereduce) | Source-audio denoising | MIT |
| [numpy](https://numpy.org/) | Numerics | BSD-3-Clause |
| [tqdm](https://github.com/tqdm/tqdm) | Progress bars | MPL-2.0 AND MIT |
| [requests](https://requests.readthedocs.io/) | Ollama HTTP calls | Apache-2.0 |

### Optional — installed only with an extra

| Package | Extra | Enables | License |
|---|---|---|---|
| [piper-tts](https://github.com/OHF-Voice/piper1-gpl) | `[piper]` | `--tts piper` | **GPL-3.0-or-later** |
| [coqui-tts](https://github.com/idiap/coqui-ai-TTS) | `[xtts]` | `--tts xtts` | MPL-2.0 (toolkit only — see §4.4 for the weights) |
| [torchaudio](https://github.com/pytorch/audio) | `[xtts]` | `--tts xtts` | BSD-2-Clause |
| [faster-whisper](https://github.com/SYSTRAN/faster-whisper) | `[faster]` | `--whisper-backend faster` | MIT |
| [anthropic](https://github.com/anthropics/anthropic-sdk-python) | `[anthropic]` | `--translator anthropic` | Apache-2.0 |
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) | `[url]` | Dubbing from a URL | Unlicense |
| [pyannote.audio](https://github.com/pyannote/pyannote-audio) | `[diarize]` | `--diarize` | MIT (see §4.5 for the models) |
| [fastapi](https://github.com/fastapi/fastapi) · [uvicorn](https://github.com/Kludex/uvicorn) · [python-multipart](https://github.com/Kludex/python-multipart) | `[serve]` | `voxa serve` | MIT · BSD-3-Clause · Apache-2.0 |

### ⚠️ Copyleft dependencies you should know about

- **`edge-tts` is LGPL-3.0** and is a required dependency. Importing it without modification is
  generally compatible with an MIT application, provided users remain able to replace the library.
  Do not vendor a modified copy without complying with the LGPL.
- **`piper-tts` is GPL-3.0-or-later** (since 1.3.0, when development moved to
  [OHF-Voice/piper1-gpl](https://github.com/OHF-Voice/piper1-gpl); versions up to 1.2.0 were MIT).
  Voxa runs the `piper` program as a separate process and neither imports nor links it, so Voxa's
  own code stays MIT. The GPL governs `piper-tts` itself: if you redistribute an environment that
  includes it, that copy comes with the GPL's obligations. The older MIT releases are not a
  practical alternative — they depend on `piper-phonemize`, which has no Windows wheels and no Linux
  wheels for Python 3.12 or later.

> **Removed:** Voxa used to require `pysrt` (GPL-3.0) for a single call — reading back the
> subtitle file it had just written itself. That call was replaced with a small built-in SubRip
> parser, so **no GPL-licensed package is required to run Voxa.**

---

## 3. Unofficial service endpoints

Two default backends talk to endpoints that are **not officially published APIs**:

- **`edge-tts`** speaks to Microsoft's internal Edge "Read Aloud" speech service. It is not a
  supported public API, has no SLA, and can break without notice — versions below `7.0` are
  already rejected with HTTP 403. For a supported, commercially licensed equivalent, use
  Azure Cognitive Services Speech.
- **`deep-translator`'s Google backend** scrapes the public Google Translate web endpoint. It is
  not the paid Google Cloud Translation API, and it rate-limits heavy use.

Using them is your decision and your risk. For production or commercial work, prefer an official,
paid API (OpenAI / Anthropic for translation; OpenAI TTS or Azure Speech for synthesis).

---

## 4. Models and voices

Voxa downloads models at runtime; it never ships weights.

### 4.1 Piper voices

`--tts piper` picks one voice per target language and downloads it from
[rhasspy/piper-voices](https://huggingface.co/rhasspy/piper-voices) on first use. Each voice's
model card gives its licence as that of the recordings it was trained on. Whether a dataset's
licence carries over to a model trained on it — and to audio that model produces — is not settled
law; the table takes the cautious reading and treats the voice as bound by it. Voxa names the
licence when it picks the voice, and warns when the voice isn't cleared for commercial use.

| Language | Voice | Licence | Commercial use | Fine-tuned from |
|---|---|---|:---:|---|
| English | `en_US-kristin-medium` | Public domain (LibriVox) | ✅ | — trained from scratch |
| German | `de_DE-thorsten-medium` | CC0 | ✅ | `en_US-lessac` |
| Spanish | `es_ES-davefx-medium` | CC0 | ✅ | `en_US-lessac` |
| Dutch | `nl_NL-pim-medium` | CC0 | ✅ | `en_US-lessac` |
| Polish | `pl_PL-darkman-medium` | CC0 | ✅ | `en_US-lessac` |
| Russian | `ru_RU-denis-medium` | CC0 | ✅ | `en_US-lessac` |
| Ukrainian | `uk_UA-ukrainian_tts-medium` | CC0 | ✅ | — trained from scratch |
| French | `fr_FR-siwis-medium` | CC BY 4.0 | ✅ with attribution | `en_US-lessac` |
| Portuguese | `pt_BR-edresson-low` | CC BY 4.0 | ✅ with attribution | `en_US-ryan` |
| Vietnamese | `vi_VN-vais1000-medium` | CC BY 4.0 | ✅ with attribution | `en_US-lessac` |
| Italian | `it_IT-riccardo-x_low` | M-AILABS (BSD-style, commercial use permitted) | ✅ keep the notice | — trained from scratch |
| Japanese | `ja_JP-hi_fi_captain-medium` | CC BY-NC-SA 4.0 | ❌ non-commercial | LibriTTS-R base model |
| Korean | `ko_KR-kss-medium` | CC BY-NC-SA 4.0 | ❌ non-commercial | LibriTTS-R base model |
| Turkish | `tr_TR-dfki-medium` | CC BY-NC-SA 4.0 | ❌ non-commercial | `en_US-lessac` |
| Chinese | `zh_CN-huayan-x_low` | Unknown | ❓ not cleared | — trained from scratch |

**Fine-tuned voices.** Most of these voices were not trained from scratch: they started from an
English Piper voice and were then trained further on recordings in their own language. The
Licence column, like the model card, gives the licence of those recordings. The voices they
started from are licensed more narrowly: `en_US-lessac` was trained on the Blizzard 2013 Lessac
data, which is licensed for research only, and `en_US-ryan` on RyanSpeech, CC BY-NC-SA 4.0.
Whether that licence also binds a voice fine-tuned from them is an open question, and the table
does not apply it. If you need to rule that risk out, the voices trained from scratch on
permissively licensed recordings are the English, Ukrainian and Italian ones.

There is currently no permissively licensed Piper voice for Japanese, Korean or Turkish. Chinese
has one, `zh_CN-chaowen-medium` (CC0), but it needs piper-tts's optional Chinese dependencies
(`piper-tts[zh]`), which Voxa does not install, so Voxa keeps `huayan`. For commercial work in
those languages — or wherever the fine-tuning question matters to you — use `--tts openai` or a
self-hosted engine whose licence fits.

Before Voxa 1.10, the English, Russian and Vietnamese voices were `en_US-lessac-medium` (research
licence), `ru_RU-ruslan-medium` and `vi_VN-vivos-x_low` (both CC BY-NC-SA 4.0).

For a CC BY voice, credit it where you publish the audio, e.g. *"Voice: Piper fr_FR-siwis (SIWIS
dataset, CC BY 4.0)"*.

### 4.2 Speech recognition

| Model | Licence | Commercial use |
|---|---|:---:|
| Whisper weights (OpenAI) | MIT | ✅ |
| faster-whisper conversions (`Systran/faster-whisper-*`) | MIT | ✅ |

### 4.3 Translation with Ollama

Ollama itself is MIT, but each model has its own licence. The default, `--ollama_model llama3`, is
under the **Meta Llama 3 Community License**: commercial use is allowed (unless your products
exceed 700 million monthly active users), on condition that you follow Meta's Acceptable Use
Policy and display "Built with Meta Llama 3" in a product built with it. That is a licence with
conditions, not a permissive one. To use a different model, pass `--ollama_model` and check its
licence on its Ollama or Hugging Face page.

### 4.4 XTTS

| Model | Licence | Commercial use |
|---|---|:---:|
| **XTTS-v2 weights (Coqui)** | **Coqui Public Model License (CPML) 1.0** | ❌ **Non-commercial only** |

Coqui Inc. **ceased operations in January 2024**. Consequences:

1. The original `TTS` PyPI package is **unmaintained**. Voxa's optional extra installs the
   community-maintained fork [`coqui-tts`](https://github.com/idiap/coqui-ai-TTS) instead.
2. The XTTS-v2 **model weights remain under CPML, which permits non-commercial use only**, and
   because the company no longer exists, **there is no party from whom a commercial license can
   be obtained.**
3. Its declared dependency bounds are loose, so `pip` can pick a `transformers` that `coqui-tts`
   does not work with — the tell is an `ImportError` on `import TTS` (e.g. `isin_mps_friendly` or
   `is_torchcodec_available`). Pin a compatible one; `pip install "transformers==4.53.0"` worked at
   the time of writing, and it coexists with the `[diarize]` extra's `pyannote`.

If you need voice cloning for a commercial product, XTTS is not a viable path. Consider an
MIT-licensed alternative such as [Chatterbox](https://github.com/resemble-ai/chatterbox), served
behind an OpenAI-compatible endpoint.

### 4.5 Speaker diarization

| Model | Licence | Commercial use |
|---|---|:---:|
| `pyannote/speaker-diarization-3.1` (pipeline) | MIT, access-gated on Hugging Face | ✅ |
| `pyannote/segmentation-3.0` | MIT, access-gated on Hugging Face | ✅ |
| `pyannote/wespeaker-voxceleb-resnet34-LM` (speaker embeddings, loaded by the pipeline) | CC BY 4.0 | ✅ with attribution |

You accept the gated models' terms once and pass a token (`--hf-token` / `HF_TOKEN`). The gate is
access control, not a commercial restriction — unlike the XTTS weights, none of these has a
non-commercial clause; the embedding model asks for credit. `--diarize` is an optional extra
(`voxa-dub[diarize]`) and is off by default.

---

## 5. External APIs

`--translator openai`, `--translator anthropic` and `--tts openai` send your transcript and/or
text to third-party services under their own terms of service and pricing. Voxa never transmits
your API keys anywhere except to the corresponding provider.

For a pipeline that sends nothing over the network, use:

```bash
voxa video.mp4 --translator ollama --tts piper
```

— and check §4.1 and §4.3 before using its output commercially.

---

## 6. Container image

The image published at `ghcr.io/akshinmrv/voxa` is a redistribution of third-party software, not
just of Voxa. It is built from `python:3.12-slim` (Debian) and contains, among other packages:

- **FFmpeg from Debian**, which Debian builds with GPL components enabled (`--enable-gpl`), so the
  copy in the image is under the GPL;
- the required Python dependencies listed in §2 (including LGPL-3.0 `edge-tts`), a CPU build of
  `torch`, and the `[serve]` extra.

It does not include `piper-tts`, `coqui-tts` or any model weights; Whisper models are downloaded
at runtime into `/cache`. The image's `org.opencontainers.image.licenses="MIT"` label describes
Voxa's own code. Each Debian package's licence is in `/usr/share/doc/<package>/copyright`, and its
source is available from Debian.

---

*If you believe any license above is stated incorrectly, please open an issue — accuracy here
matters more than convenience.*

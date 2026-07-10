# Third-Party Notices

**Voxa** is released under the [MIT License](LICENSE).

Voxa **does not bundle or redistribute any model weights or third-party source code**.
It orchestrates tools and models that you install and run yourself. The licenses of those
components are their own, and some of them are **more restrictive than Voxa's MIT license**.

Read this file before using Voxa commercially.

---

## 1. Quick answer: what is safe for commercial use?

| Configuration | Commercially usable? | Why |
|---|:---:|---|
| `--tts piper` + `--translator ollama` | ✅ Yes | Fully offline, permissive licenses |
| `--tts openai` + `--translator openai` | ✅ Yes | Paid API under OpenAI's commercial terms |
| `--tts edge` (default) | ⚠️ Grey area | Uses an **unofficial** Microsoft endpoint (see §3) |
| `--translator google` (default) | ⚠️ Grey area | Uses an **unofficial** Google endpoint (see §3) |
| `--tts xtts` | ❌ **No** | XTTS-v2 model weights are **non-commercial only** (see §4) |

> **The default configuration (`--tts edge --translator google`) is convenient for personal use
> but is NOT recommended for a commercial product.** Prefer `openai`/`anthropic` translation and
> `openai` or `piper` synthesis, or a self-hosted OpenAI-compatible endpoint.

---

## 2. Runtime dependencies

Licenses below were read from the installed package metadata.

### Required

| Package | Role | License |
|---|---|---|
| [openai-whisper](https://github.com/openai/whisper) | Speech recognition | MIT |
| [edge-tts](https://github.com/rany2/edge-tts) | Default TTS engine | **LGPL-3.0** |
| [pysrt](https://github.com/byroot/pysrt) | Subtitle parsing | **GPL-3.0** |
| [deep-translator](https://github.com/nidhaloff/deep-translator) | Google translation backend | MIT |
| [openai](https://github.com/openai/openai-python) | OpenAI API client | Apache-2.0 |
| [anthropic](https://github.com/anthropics/anthropic-sdk-python) | Anthropic API client | MIT |
| [torch](https://github.com/pytorch/pytorch) / torchaudio | Inference runtime | BSD-3-Clause |
| [soundfile](https://github.com/bastibe/python-soundfile) | Audio I/O | BSD-3-Clause (libsndfile: LGPL) |
| [noisereduce](https://github.com/timsainb/noisereduce) | Source-audio denoising | MIT |
| [numpy](https://numpy.org/) | Numerics | BSD-3-Clause |
| [tqdm](https://github.com/tqdm/tqdm) | Progress bars | MPL-2.0 AND MIT |
| [requests](https://requests.readthedocs.io/) | Ollama HTTP calls | Apache-2.0 |

### Optional

| Package | Enables | License |
|---|---|---|
| [piper-tts](https://github.com/rhasspy/piper) | `--tts piper` | MIT |
| [coqui-tts](https://github.com/idiap/coqui-ai-TTS) | `--tts xtts` | MPL-2.0 (toolkit only) |
| [faster-whisper](https://github.com/SYSTRAN/faster-whisper) | `--whisper-backend faster` | MIT |

### ⚠️ Copyleft dependencies you should know about

- **`pysrt` is GPL-3.0** and is currently a required dependency. Voxa's own source is MIT and
  does not include any pysrt code, but if you redistribute a bundled artifact (for example a
  frozen binary or a container image that vendors pysrt), the combined work may fall under the
  GPL. *Voxa uses pysrt for exactly one call — reading back a subtitle file Voxa itself wrote —
  and replacing it with a permissive implementation is tracked as a planned change.*
- **`edge-tts` is LGPL-3.0.** Importing it without modification is generally compatible with an
  MIT application, provided users remain able to replace the library. Do not vendor a modified
  copy without complying with the LGPL.

---

## 3. Unofficial service endpoints

Two default backends talk to endpoints that are **not officially published APIs**:

- **`edge-tts`** speaks to Microsoft's internal Edge "Read Aloud" speech service. It is not a
  supported public API, has no SLA, and can break without notice — versions below `7.0` are
  already rejected with HTTP 403. For a supported, commercially licensed equivalent, use
  Azure Cognitive Services Speech.
- **`deep-translator`'s Google backend** scrapes the public Google Translate web endpoint. It is
  not the paid Google Cloud Translation API.

Using them is your decision and your risk. For production or commercial work, prefer an official,
paid API (OpenAI / Anthropic for translation; OpenAI TTS or Azure Speech for synthesis).

---

## 4. Models

Voxa downloads models at runtime; it never ships weights.

| Model | License | Commercial use |
|---|---|---|
| Whisper weights (OpenAI) | MIT | ✅ Allowed |
| Piper voices | Per-voice (commonly MIT / CC-BY) | ✅ Check the individual voice |
| **XTTS-v2 weights (Coqui)** | **Coqui Public Model License (CPML) 1.0** | ❌ **Non-commercial only** |

### About XTTS

Coqui Inc. **ceased operations in January 2024**. Consequences:

1. The original `TTS` PyPI package is **unmaintained**. Voxa's optional extra installs the
   community-maintained fork [`coqui-tts`](https://github.com/idiap/coqui-ai-TTS) instead.
2. The XTTS-v2 **model weights remain under CPML, which permits non-commercial use only**, and
   because the company no longer exists, **there is no party from whom a commercial license can
   be obtained.**

If you need voice cloning for a commercial product, XTTS is not a viable path. Consider an
MIT-licensed alternative such as [Chatterbox](https://github.com/resemble-ai/chatterbox), served
behind an OpenAI-compatible endpoint.

---

## 5. External APIs

`--translator openai`, `--translator anthropic` and `--tts openai` send your transcript and/or
text to third-party services under their own terms of service and pricing. Voxa never transmits
your API keys anywhere except to the corresponding provider.

For a fully offline pipeline that sends nothing over the network, use:

```bash
voxa video.mp4 --translator ollama --tts piper
```

---

*If you believe any license above is stated incorrectly, please open an issue — accuracy here
matters more than convenience.*

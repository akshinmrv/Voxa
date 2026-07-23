<div align="center">

# Voxa

**İstənilən videonu başqa dilə dublyaj et — və sinxronu qoru.**

Voxa videonu transkripsiya edir, kontekstlə tərcümə edir, hədəf dildə səsləndirir və nəticəni
orijinalın üzərinə miksləyir. Mühərrik tək Python faylıdır — dörd nitq mühərriki, beş tərcümə
backend-i və bir güzəştsiz xüsusiyyət: dublyaj danışandan sürüşmür.

[![CI](https://github.com/akshinmrv/Voxa/actions/workflows/ci.yml/badge.svg)](https://github.com/akshinmrv/Voxa/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/akshinmrv/Voxa?display_name=tag&sort=semver)](https://github.com/akshinmrv/Voxa/releases)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.9%20%7C%203.10%20%7C%203.11%20%7C%203.12-blue.svg)](https://www.python.org/downloads/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

</div>

```bash
pipx install voxa-dub
voxa talk.mp4 --target_lang ru        # → talk_dubbed_ru.mp4
```

<div align="center">

🎧 **[Demo dublyajları dinlə](https://voxa.servoogle.com)** — İngiliscədən türk, Azərbaycan
və fransız dillərinə, API açarı olmadan

</div>

---

## Ümumi baxış

Əksər dublyaj alətləri sintez edilmiş kliplər ard-arda birləşdirir. Bir az uzun çıxan klip
növbətisini gecikdirir, xəta toplanır, və üç dəqiqədən sonra dublyaj danışandan bir cümlə
geridə qalır.

Voxa hər klipi **mənbə zaman oxuna bağlayaraq** yerləşdirir. Bir sətrin yeri onun öz
başlanğıcından **növbəti sətrin** başlanğıcına qədərdir. Yerinə sığmayan klip kəsilir, qısa
klip sükutla doldurulur. Kursor toplanmır — **təyin edilir**, ona görə sürüşmə struktur olaraq
mümkün deyil.

Qalan hər şey bu qərardan doğur: tərcüməçiyə simvol büdcəsi verilir ki, sətir öz yerinə təbii
sürətdə sığsın; nitq yalnız sürətləndirilir (heç vaxt yavaşladılmır — yavaşladılmış nitq
"sürünən" səslənir); və seqment başlanğıcları ilk sözün vaxt damğasına sıxlaşdırılır ki,
dublyaj danışandan əvvəl başlamasın.

```bash
voxa talk.mp4 --target_lang az
# → talk_dubbed_az.mp4 + subtitles_az.srt
```

API açarı tələb olunmur. Default parametrlər olduğu kimi işləyir.

## İmkanlar

| İmkan | Təfərrüat |
|---|---|
| **Video dublyaj** | Dublyaj səsi orijinalın üzərinə miksləndir; video axını yenidən kodlaşdırılmır |
| **Nitqin tanınması** | `openai-whisper` (tiny → turbo) və ya `faster-whisper` (2–4× sürətli, daxili VAD, torch-suz) |
| **Avtomatik tərcümə** | Google, Ollama (lokal), OpenAI, Anthropic, OpenRouter |
| **Kontekst-məlumatlı tərcümə** | Sətirlər bloklarla tərcümə olunur, ona görə əvəzliklər, cins, adlar və ton səhnə boyu ardıcıl qalır |
| **Uzunluğa uyğun tərcümə** | Hər sətrə simvol büdcəsi verilir ki, dublyaj sıxılmadan öz yerinə sığsın |
| **İşi əvvəlcədən gör** | `--dry-run` mühərrikləri, modelləri, çıxış yolunu və hansı keşlənmiş addımların təkrar işlədiləcəyini çap edir — sonra heç nə yazmadan çıxır |
| **Altyazı emalı** | SRT çıxışı, `--subtitles-only` rejimi, daxili SubRip parseri (GPL asılılığı yoxdur) |
| **Səs klonlama** | XTTS v2, qısa referans nümunəsindən — verməsəniz, mənbədən avtomatik çıxarılır |
| **OpenAI TTS** | `gpt-4o-mini-tts`, təlimatla idarə olunan ifa |
| **Ekspressiv ifa** | `--detect-emotion` Edge-də doğma səs stillərini seçir; OpenAI TTS-də LLM hər sətrə emosiya/enerji/temp göstərişi verir |
| **Öz serverində nitq** | `--openai-tts-base-url` istənilən OpenAI-uyğun `/v1/audio/speech` serverini işlədir — açar da, əlavə asılılıq da lazım deyil |
| **Offline nitq** | Piper, model yükləndikdən sonra tam offline |
| **Bağlanmış yerləşdirmə** | Aşan kliplər fade ilə kəsilir, qısaları doldurulur, sürüşmə toplanmır |
| **Keyfiyyət nəzarəti** | Hər klip geri transkripsiya olunur və ballanır (WER, clipping, sükut, temp) |
| **Avtomatik yenidən sintez** | XTTS stoxastikdir, ona görə zəif seqment 2 dəfəyə qədər yenidən sintez olunur və ən yaxşısı saxlanılır |
| **Toplu emal** | Bir əmrdə bir neçə video |
| **Bərpa olunan işlər** | Hər addım checkpoint-lənir; yarımçıq iş bərpa olunur |
| **Preflight yoxlaması** | Olmayan giriş faylı və olmayan FFmpeg iş başlamazdan əvvəl bildirilir |
| **Konfiqurasiya** | `.env`, JSON config, struktur JSON logging |
| **Genişlənə bilən** | Yeni nitq və ya tərcümə provayderi = 1 adapter + 1 registry sətri |

> [!NOTE]
> Voxa heç bir model çəkisi daşımır və üçüncü tərəf kodu daxil etmir. O, sizin quraşdırdığınız
> alətləri idarə edir. Kommersiya istifadəsindən əvvəl [NOTICE.md](NOTICE.md) oxuyun.

## Dəstəklənən dillər

| Qat | Əhatə |
|---|---|
| **Transkripsiya** | Whisper-in tam dil dəsti, avtomatik təyin |
| **Tərcümə** | 74 hədəf dil üçün tam dil adı LLM prompt-una ötürülür; Google daha çoxunu qəbul edir |
| **Edge TTS** | 100+ lokal, o cümlədən doğma `az-AZ` səsləri |
| **OpenAI TTS** | Çoxdilli; böyük dillərdə ən güclü |
| **Piper** | 15 səs, tam offline |
| **XTTS** | 17 — `ar` `cs` `de` `en` `es` `fr` `hi` `hu` `it` `ja` `ko` `nl` `pl` `pt` `ru` `tr` `zh` |

### Hansı dil üçün hansı mühərrik?

Universal cavab yoxdur, və bulud mühərriki həmişə qalib gəlmir — dili həqiqətən əhatə edən səs,
onu yalnız təxmin edən daha böyük modeli adətən üstələyir. Məhz buna görə Voxa hökm yox,
**ölçmə** təqdim edir.

`--quality-gate` hər sintez olunmuş klipi ikinci ASR modeli ilə geri transkripsiya edir və söz
xəta nisbəti ilə ballandırır — beləliklə mühərrikləri **öz** materialında yoxlaya bilərsən:

```bash
voxa clip.mp4 --target_lang az --tts edge --quality-gate --gate-model base
```

[`docs/BENCHMARK.md`](docs/BENCHMARK.md) təkrarlana bilən skript, altı dil üzrə nümunə ölçmə və
— eyni dərəcədə vacib — belə bir rəqəmin nə deyə bilmədiyinin hüdudlarını verir.

> [!TIP]
> Dilin Edge-də doğma neyron səsi varsa, əvvəlcə onu sına. Az-resurslu dil üçün `--gate-model
> base` və ya daha böyüyünü işlət: `tiny` modeli tamamilə yaxşı səsi səhv oxuyur və layiq
> olduğundan pis bal verir.

> [!IMPORTANT]
> **WER rəqəmi yalnız hansı klipdən gəldiyi ilə birlikdə məna daşıyır.** Eyni mühərrik və dil
> fərqli mənbə materialında çox fərqli bal alır — qısa klipdə bir xüsusi isim ortalamanı
> kəskin dəyişə bilər. İstənilən dərc olunmuş rəqəmi, bizimki də daxil, sıralama kimi yox, öz
> ölçmən üçün başlanğıc nöqtəsi kimi qəbul et.

## Dəstəklənən modellər

| Mərhələ | Modellər |
|---|---|
| Transkripsiya | `tiny` · `base` · `small` · `medium` · `large` · `turbo` |
| Tərcümə (OpenAI) | `gpt-5` (default), `gpt-5-mini`, istənilən chat model |
| Tərcümə (Anthropic) | `claude-opus-4-8` (default), `claude-sonnet-5` |
| Tərcümə (Ollama) | `llama3` (default), istənilən lokal model |
| Nitq (OpenAI) | `gpt-4o-mini-tts` |
| İfa direktivi | `gpt-4o-mini` — iş başına bir ucuz çağırış, keşlənir |
| Səs klonlama | XTTS v2 |
| Offline nitq | Piper səsləri |
| Keyfiyyət nəzarəti | `faster-whisper` (`tiny` default, az-resurslu dillərdə `base`) |

## Arxitektura

```
                         Video
                           │
                           ▼
              ┌─────────────────────────┐
              │    Nitqin tanınması     │  Whisper / faster-whisper
              │                         │  + söz-onset dəqiqləşdirmə
              │                         │  + qeyri-nitq filtri
              └────────────┬────────────┘
                           ▼
              ┌─────────────────────────┐
              │        Tərcümə          │  Google · Ollama · OpenAI · Anthropic · OpenRouter
              │                         │  kontekstli, uzunluq büdcəli
              └────────────┬────────────┘
                           ▼
              ┌─────────────────────────┐
              │      Nitq sintezi       │  Edge · OpenAI · Piper · XTTS
              │                         │  vahid timeline sürücüsü
              └────────────┬────────────┘
                           ▼
              ┌─────────────────────────┐
              │      Audio emalı        │  yerləşdirmə (yalnız sürətləndirmə)
              │                         │  bağlanmış anchor
              │                         │  2-keçidli loudnorm
              └────────────┬────────────┘
                           ▼
                    Dublyaj edilmiş video
```

Hər mərhələ `<video>_work/` qovluğunda checkpoint-lənir. Kursorun niyə toplanmadığını və
registry-lərin necə işlədiyini [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) izah edir.

## Demo

15 saniyəlik bir ingilis klipi, **tək transkripsiyadan** üç dilə dublyaj edilib. Aşağıdakı
bütün dublyajlar **defolt mühərriklərlə və API açarı olmadan** hazırlanıb:

```bash
voxa clip.mp4 --target_lang tr        # sonra --target_lang az, --target_lang fr
```

| Hədəf | Mühərriklər | Dinlə |
|---|---|---|
| 🎬 Orijinal (İngilis) | — | [oynat ▶](https://voxa.servoogle.com) · [`original.mp4`](web/public/demo/original.mp4) |
| 🇹🇷 Türkçe | `google` + `edge` | [oynat ▶](https://voxa.servoogle.com) · [`dub_tr.mp4`](web/public/demo/dub_tr.mp4) |
| 🇦🇿 Azərbaycan | `google` + `edge` | [oynat ▶](https://voxa.servoogle.com) · [`dub_az.mp4`](web/public/demo/dub_az.mp4) |
| 🇫🇷 Fransız | `google` + `edge` | [oynat ▶](https://voxa.servoogle.com) · [`dub_fr.mp4`](web/public/demo/dub_fr.mp4) |

İkinci və üçüncü dillər keşlənmiş transkripsiyanı təkrar işlətdi — yalnız tərcümə və nitq
yenidən yaradıldı, ona görə timeline hər üçündə eynidir.

<!-- DEMO_TR --> <!-- DEMO_AZ --> <!-- DEMO_FR -->

## Quraşdırma

**1. FFmpeg** — Voxa onu başlanğıcda yoxlayır və yoxdursa bildirir.

```bash
sudo apt install ffmpeg      # Debian / Ubuntu
sudo dnf install ffmpeg      # Fedora / RHEL
brew install ffmpeg          # macOS
winget install Gyan.FFmpeg   # Windows
```

**2. Voxa** — Python 3.9 və ya daha yeni.

```bash
pipx install voxa-dub          # tövsiyə olunan: izolyasiya, PATH-ə `voxa` əlavə edir
```

Və ya heç nə quraşdırmadan bir dəfə işlət:

```bash
uvx voxa-dub talk.mp4 --target_lang ru
```

<details>
<summary>Mənbədən (development üçün)</summary>

```bash
git clone https://github.com/akshinmrv/Voxa
cd Voxa
python3 -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate

# Yalnız-CPU torch quraşdırmanı xeyli kiçildir.
# NVIDIA GPU-nuz var? Əvəzinə CUDA wheel quraşdırın — aşağıda "4. GPU sürətləndirmə".
pip install torch --index-url https://download.pytorch.org/whl/cpu

pip install .
```

</details>

> [!NOTE]
> Paketin adı **`voxa-dub`**-dır (PyPI-dakı `voxa` adı əlaqəsiz, tərk edilmiş paketə
> məxsusdur). Quraşdırdığı əmr isə **`voxa`**-dır — aşağıdakı bütün nümunələr onu işlədir.
> Skripti birbaşa işlətmək, `python voxa.py …`, eyni işi görür.

<details>
<summary>Docker — host-da Python, torch və ffmpeg olmadan</summary>

```bash
docker run --rm -v "$PWD:/data" ghcr.io/akshinmrv/voxa talk.mp4 --target_lang ru
```

Dublyaj host-da girişin yanında yaranır. Defolt parametrlər API açarı tələb etmir; başqa
mühərrikə keçsəniz `-e OPENAI_API_KEY=...` ilə ötürün. Yüklənmiş Whisper modellərini
saxlamaq üçün keşi mount edin:

```bash
docker run --rm -v "$PWD:/data" -v voxa-cache:/cache     ghcr.io/akshinmrv/voxa talk.mp4 --target_lang ru
```

Image ~3.7 GB-dır, demək olar hamısı torch-un CPU buildidir. `voxa serve` də konteynerdə
işləyir (`serve --host 0.0.0.0`), amma onun settings endpoint-ləri yalnız loopback
çağırışlarına açıqdır — port-mapped sorğu buna uyğun gəlmir, ona görə konsolu nativ işlədin.

</details>

**3. Opsional mühərriklər** — yalnız istifadə etdiyinizi quraşdırın.

| Əmr | Nəyi açır |
|---|---|
| `pipx install "voxa-dub[faster]"` | `--whisper-backend faster` — 2–4× sürətli, torch-suz |
| `pipx install "voxa-dub[piper]"` | `--tts piper` — tam offline |
| `pipx install "voxa-dub[anthropic]"` | `--translator anthropic` |
| `pipx install "voxa-dub[xtts]"` | `--tts xtts` səs klonlama |

> [!WARNING]
> `voxa-dub[xtts]` [`coqui-tts`](https://github.com/idiap/coqui-ai-TTS) forkunu quraşdırır.
> **XTTS-v2 model çəkiləri qeyri-kommersiyadır** (CPML) və Coqui Inc. artıq mövcud deyil ki,
> kommersiya lisenziyası satsın. Kommersiya klonlama üçün `--openai-tts-base-url` ilə
> MIT lisenziyalı mühərrik işlədin.

**4. GPU sürətləndirmə** — opsional, yalnız NVIDIA.

Voxa CUDA-nı özü aşkarlayır; açmaq üçün heç bir flag yoxdur. Nəyi sürətləndirir:

| Mərhələ | GPU-da |
|---|---|
| Whisper transkripsiya (hər iki backend) | ✅ CUDA, fp16 |
| XTTS səs klonlama | ✅ CUDA |
| Keyfiyyət qapısı (WER ballama) | ✅ CUDA |
| Tərcümə — Google / OpenAI / Anthropic | ➖ şəbəkə-asılı |
| Tərcümə — Ollama | ➖ Ollama GPU-nu özü işlədir |
| Nitq — Edge / OpenAI | ➖ bulud |
| Nitq — Piper | ➖ CPU (ONNX) |

Step 2-dəki CPU wheel əvəzinə PyTorch-un **CUDA** buildini quraşdırın:

```bash
# Sürücünüzün dəstəklədiyi CUDA versiyasını seçin — https://pytorch.org/get-started/locally/
pip install torch --index-url https://download.pytorch.org/whl/cu124
```

Yoxlayın:

```bash
python -c "import torch; print(torch.cuda.is_available())"   # → True
```

GPU işləyəndə iş loqu transkripsiya addımında `⚙️  Using device: CUDA` çap edir (əks halda `CPU`).
Təxmini VRAM (Whisper modelinə görə): `tiny`/`base` ≈ 1 GB, `small` ≈ 2 GB, `medium` ≈ 5 GB,
`turbo` ≈ 6 GB, `large` ≈ 10 GB; XTTS üstünə təxminən 4 GB istəyir.

> [!NOTE]
> `--whisper-backend faster` (CTranslate2) da GPU-da işləyir, amma NVIDIA cuBLAS və cuDNN
> kitabxanalarını tələb edir: `pip install nvidia-cublas-cu12 nvidia-cudnn-cu12`.
> Voxa **yalnız CUDA**-nı yoxlayır — Apple Silicon (MPS) və AMD GPU-lar CPU-ya düşür.

## Konfiqurasiya

**API açarları.** `.env.example`-i `.env` (gitignore olunur) kimi kopyalayın və doldurun. Voxa
onu başlanğıcda yükləyir; real mühit dəyişənləri həmişə üstündür. `--openai_api_key`
əvəzinə bunu seçin — flaq shell tarixçəsinə və proses siyahısına düşür.

**Default-lar.** Tez-tez işlədilən parametrləri JSON faylına yazın. Açarlar uzun flaq
adlarıdır (tirelər alt-xətt). Tam nümunə: [`examples/config.json`](examples/config.json).

**Loglama.** `--log-format json` hər sətrə bir JSON obyekti verir. `--verbose` səviyyəni DEBUG
edir.

**Bütün parametrlər:** `voxa --help` — koddan generasiya olunur, ona görə heç vaxt köhnəlmir.

## Sürətli başlanğıc

```bash
# Ən sadə: açar yox, konfiqurasiya yox
voxa video.mp4 --target_lang az

# LLM ilə təbii, kontekstli tərcümə
export OPENAI_API_KEY="sk-..."
voxa video.mp4 --target_lang de --translator openai

# Bir OpenRouter açarı ilə yüzlərlə model (DeepSeek, Gemini, Llama…) — əlavə quraşdırma yox
export OPENROUTER_API_KEY="sk-or-..."
voxa video.mp4 --target_lang az --translator openrouter --openrouter_model deepseek/deepseek-chat

# Danışanın səsini klonla
voxa video.mp4 --target_lang tr --tts xtts

# Tam offline: lokal LLM tərcümə + offline nitq
voxa video.mp4 --target_lang fr --translator ollama --tts piper

# Yalnız altyazı
voxa video.mp4 --target_lang es --subtitles-only

# Bir əmrdə bir neçə video
voxa a.mp4 b.mp4 c.mp4 --target_lang az

# Təxmin etmək əvəzinə nəticəni ölç
voxa video.mp4 --target_lang az --quality-gate --gate-model base

# Öz serverində nitq: OpenAI-uyğun endpoint, açarsız
voxa video.mp4 --target_lang tr --tts openai \
     --openai-tts-base-url http://localhost:8004/v1
```

## Veb interfeys (`voxa serve`)

Voxa [`web/`](web/) qovluğunda opsional veb frontend və `voxa serve` arxasında lokal operator
backend təqdim edir — bir dizayn sistemi, iki səth:

- **Landing** — publik, üçdilli (EN/AZ/TR) təqdimat saytı, statik olaraq deploy oluna bilər.
- **Operator app** — lokal konsol: video yüklə, mühərrik seç, yeddi-addımlı pipeline-ı canlı
  izlə (SSE) və nəticəni yüklə. Heç nə serverə yüklənmir — öz maşınında işləyir.

```bash
# Backend: REST + SSE
pipx install "voxa-dub[serve]"
voxa serve                              # http://127.0.0.1:8000

# Frontend (ayrı terminal)
cd web && npm install && npm run dev    # http://localhost:3000  →  /en/app
```

Development, mühit dəyişənləri və deploy üçün: [`web/README.md`](web/README.md).

## Layihə strukturu

```
Voxa/
├── voxa.py                     # Bütün alət: pipeline, mühərriklər, registry-lər, CLI
├── pyproject.toml              # Paketləşmə, extras, ruff və pytest konfiqurasiyası
├── requirements.txt            # Əsas asılılıqlar (opsional mühərriklər extras-dadır)
│
├── tests/
│   ├── test_voxa.py            # Unit testlər
│   ├── test_golden.py          # Golden harness: funksiyalar kompozisiyada
│   └── golden/                 # Qeydə alınmış giriş və gözlənilən çıxışlar
│
├── docs/
│   ├── ARCHITECTURE.md         # Dizayn qərarları
│   ├── RELEASING.md            # Buraxılış siyahısı
│   └── assets/                 # Demo videoları və şəkillər
│
├── examples/
│   └── config.json             # Tam, yoxlanılmış konfiqurasiya
│
├── .github/                    # CI, release, issue/PR şablonları, dependabot
│
├── README.md
├── CHANGELOG.md
├── CONTRIBUTING.md
├── SECURITY.md
├── CODE_OF_CONDUCT.md
├── NOTICE.md                   # Üçüncü tərəf lisenziyaları
└── LICENSE                     # MIT
```

## Yol xəritəsi

Bu, vəd deyil, istiqamətdir. Avadanlıq və ya ödənişli açar tələb edən hər şey dürüst test
edilə bilənə qədər gözləyir.

| İş | Status | Qeyd |
|---|---|---|
| Şəbəkə mühərrikləri üçün paralel sintez | Planlaşdırılır | Sorğular hazırda ardıcıl gedir; əsas performans ehtiyatı budur |
| Azure Neural TTS adapteri | Bloklu | Test üçün API açarı lazımdır. Rəsmi `az-AZ` səsləri və SSML |
| Danışan oxşarlığı və MOS ballama | Nəzərdən keçirilir | Keyfiyyət nəzarətini WER-dən kənara genişləndirər |
| Daha geniş golden dəst | Nəzərdən keçirilir | Reqressiya harness-ində daha çox dil |
| Demo materialları | Açıq | `docs/assets/` üçün əvvəl/sonra klipləri |

## FAQ

<details>
<summary><strong>API açarı lazımdırmı?</strong></summary>

Xeyr. Default-lar — Whisper, Google Translate və Edge TTS — açar tələb etmir. Açar yalnız
OpenAI/Anthropic tərcüməsi və ya OpenAI nitqi üçün lazımdır.
</details>

<details>
<summary><strong>Dublyaj niyə sürüşmür?</strong></summary>

Hər klip öz başlanğıcı ilə növbəti sətrin başlanğıcı arasındakı yerə qoyulur və kursor klip
müddətlərindən toplanmır — həmin növbəti başlanğıca **təyin edilir**. Aşan klip sonrakıların
hamısını itələmək əvəzinə kəsilir. Vaxt riyaziyyatı safdır, unit test və golden harness ilə
kilidlənib.
</details>

<details>
<summary><strong>Kommersiya məqsədilə istifadə edə bilərəmmi?</strong></summary>

Voxa özü MIT-dir və copyleft asılılığı yoxdur. İdarə etdiyi mühərriklərin öz lisenziyaları
var. `--tts piper` + `--translator ollama` tam sərbəstdir. `--tts xtts` kommersiya üçün
**yararsızdır**. Bax: [NOTICE.md](NOTICE.md).
</details>

<details>
<summary><strong>Kommersiya məhsulu üçün səsi necə klonlayım?</strong></summary>

MIT lisenziyalı, OpenAI-uyğun nitq serverini lokal işlədin və Voxa-nı ona yönləndirin:

```bash
voxa video.mp4 --tts openai --openai-tts-base-url http://localhost:8004/v1
```

Açar yoxdur, əlavə asılılıq yoxdur, qeyri-kommersiya model çəkisi yoxdur.
</details>

<details>
<summary><strong>Tam offline işləyə bilərmi?</strong></summary>

Bəli: `--translator ollama --tts piper`. Modellər yükləndikdən sonra heç nə cihazınızdan
çıxmır.
</details>

<details>
<summary><strong>Video yenidən kodlaşdırılırmı?</strong></summary>

Xeyr. Video axını kopyalanır. Yalnız audio yenidən qurulur: orijinal 5%-lə sakit ambiyans
yatağı kimi, dublyaj 150%-lə qarışdırılır; `amix` hər ikisini yarıya bölür, ona görə miks
kəsilmir. Hər iki səviyyə konfiqurasiya olunur.
</details>

<details>
<summary><strong>Uzun iş yarımçıq qaldı. Yenidən başlamalıyam?</strong></summary>

Xeyr. Hər addım `<video>_work/` qovluğunda checkpoint-lənir; eyni əmri təkrarlayın, Voxa davam
edəcək. Təmiz başlanğıc üçün `--no-resume`.
</details>

<details>
<summary><strong>Bir işin maliyyəti nə qədərdir?</strong></summary>

Default-larla heç nə. LLM tərcüməçisi ilə hər işdən sonra token istifadəsi loglanır; təxmini
qiymət də görmək üçün modelinizin qiymətlərini `voxa.py` içindəki `LLM_PRICING` cədvəlinə
əlavə edin.
</details>

<details>
<summary><strong>Windows-da işləyirmi?</strong></summary>

Bəli, FFmpeg PATH-də olduqda. CI Linux-da qaçır, alət isə Windows-da inkişaf etdirilir.
</details>

## Töhfə vermək

Issue və pull request-lər qəbul olunur. [CONTRIBUTING.md](CONTRIBUTING.md) test paketini,
golden faylların yenilənməsini və iki vacib asılılıq qaydasını izah edir: **GPL lisenziyalı
məcburi asılılıq olmamalıdır**, mühərriyə xas paketlər **extras**-a getməlidir.

Nitq mühərriki əlavə etmək = 1 adapter + 1 registry sətri.

```bash
pip install -e ".[dev]"
ruff check .
pytest
```

---

## Lisenziya

Voxa [MIT lisenziyası](LICENSE) altında yayımlanır.

Voxa heç bir model çəkisi daşımır və üçüncü tərəf kodu daxil etmir, lakin idarə etdiyi
mühərriklərin öz lisenziyaları var — bəziləri Voxa-nınkından sərtdir. Kommersiya
istifadəsindən əvvəl [NOTICE.md](NOTICE.md) oxuyun.

| Konfiqurasiya | Kommersiya istifadəsi |
|---|:---:|
| `--tts piper` + `--translator ollama` (tam offline) | ✅ |
| `--tts openai` + `--translator openai` (ödənişli API) | ✅ |
| `--tts edge` / `--translator google` (default, qeyri-rəsmi endpoint) | ⚠️ boz zona |
| `--tts xtts` (XTTS-v2 çəkiləri CPML-dir) | ❌ yalnız qeyri-kommersiya |

## Təşəkkürlər

Voxa başqalarının gördüyü işin üzərində dayanır.

| Layihə | Rolu |
|---|---|
| [OpenAI Whisper](https://github.com/openai/whisper) | Nitqin tanınması |
| [faster-whisper](https://github.com/SYSTRAN/faster-whisper) | Sürətli transkripsiya backend-i |
| [edge-tts](https://github.com/rany2/edge-tts) | Microsoft neyron səsləri |
| [Piper](https://github.com/rhasspy/piper) | Offline neyron nitq |
| [coqui-tts](https://github.com/idiap/coqui-ai-TTS) | XTTS səs klonlamasını işlədən fork |
| [OpenAI](https://platform.openai.com/) · [Anthropic](https://www.anthropic.com/) | LLM tərcümə və nitq |
| [Ollama](https://ollama.com/) | Lokal, məxfi LLM tərcümə |
| [FFmpeg](https://ffmpeg.org/) | Bütün audio və video işləri |

## Müəllif

**Voxa** **[Akshin Miranov](https://github.com/akshinmrv)** tərəfindən **Servoogle** adı
altında qurulur və dəstəklənir.

Servoogle praktiki AI alətləri qurmaq üçün mövcuddur — modeli nümayiş etdirən deyil, real
problemi başdan-sona həll edən proqram təminatı — və başqalarının üzərində qura biləcəyi
hissələri açıq buraxmaq üçün. Voxa həmin hissələrdən biridir. Videonu dublyaj etmək üçün
studiya, lisenziya danışığı və ya qapalı pipeline lazım olmamalıdır; bir əmr və artıq
sahib olduğunuz kompüter kifayətdir.

Voxa məhz buna görə MIT-dir, məhz buna görə copyleft asılılığı daşımır, lisenziya
öhdəlikləri məhz buna görə gizlədilmir, sənədləşdirilir, və hər mühərrik məhz buna görə
istənilən adamın genişləndirə biləcəyi registry-nin arxasındadır. Bu sahədəki maraqlı
problemlər — dublyajı sinxron saxlamaq, süni səsi tələsməyən göstərmək, çıxışın həqiqətən
yaxşı olub-olmadığını bilmək — açıq şəkildə həll edilməyə dəyər.

Voxa sizə faydalıdırsa, göndərə biləcəyiniz ən dəyərli şey logu əlavə edilmiş bir baq
hesabatıdır.

<div align="center">

---

**Başqa dildə oxu:** 🇬🇧 [English](README.md) · 🇹🇷 [Türkçe](README.tr.md)

**Voxa** · MIT · [Baq bildir](https://github.com/akshinmrv/Voxa/issues) ·
[Töhfə ver](CONTRIBUTING.md) · [Arxitektura](docs/ARCHITECTURE.md)

</div>

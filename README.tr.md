<div align="center">

# Voxa

**Herhangi bir videoyu başka bir dile dublajlayın — ve senkronu koruyun.**

Voxa bir videoyu yazıya çevirir, bağlamıyla birlikte çevirir, hedef dilde seslendirir ve
sonucu orijinalin üzerine karıştırır. Dört konuşma motoru ve dört çeviri arka ucu olan tek
dosyalık bir CLI aracıdır — ve tavizsiz bir özelliği vardır: dublaj konuşmacıdan kaymaz.

[![CI](https://github.com/akshinmrv/Voxa/actions/workflows/ci.yml/badge.svg)](https://github.com/akshinmrv/Voxa/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/akshinmrv/Voxa?display_name=tag&sort=semver)](https://github.com/akshinmrv/Voxa/releases)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.9%20%7C%203.10%20%7C%203.11%20%7C%203.12-blue.svg)](https://www.python.org/downloads/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Stars](https://img.shields.io/github/stars/akshinmrv/Voxa?style=flat)](https://github.com/akshinmrv/Voxa/stargazers)

</div>

---

## 🌍 Dokümantasyon

Dilinizi seçin:

- 🇬🇧 **English** → [README.md](README.md)
- 🇦🇿 **Azərbaycan** → [README.az.md](README.az.md)
- 🇹🇷 **Türkçe** — şu anda okuduğunuz belge

---

## Genel bakış

Çoğu dublaj aracı sentezlenen klipleri arka arkaya birleştirir. Biraz uzun süren bir klip bir
sonrakini geciktirir, hata birikir ve üç dakika sonra dublaj konuşmacının bir cümle gerisinde
kalır.

Voxa her klibi **kaynak zaman çizelgesine sabitleyerek** yerleştirir. Bir satırın yuvası kendi
başlangıcından **bir sonraki satırın** başlangıcına kadardır. Yuvaya sığmayan klip kırpılır,
kısa olan sessizlikle doldurulur. İmleç biriktirilmez — **atanır**, dolayısıyla kayma yapısal
olarak imkânsızdır.

Geri kalan her şey bu karardan doğar: çevirmene karakter bütçesi verilir ki satır yuvasına
doğal bir hızda sığsın; konuşma yalnızca hızlandırılır (asla yavaşlatılmaz, çünkü yavaşlatılmış
konuşma sürüklenmiş gibi duyulur); ve segment başlangıçları ilk kelimenin zaman damgasına
sıkıştırılır ki dublaj konuşmacıdan önce başlamasın.

```bash
voxa talk.mp4 --target_lang tr
# → talk_dubbed_tr.mp4 + subtitles_tr.srt
```

API anahtarı gerekmez. Varsayılanlar kutudan çıktığı gibi çalışır.

## Özellikler

| Yetenek | Ayrıntı |
|---|---|
| **Video dublaj** | Dublaj sesi orijinalin üzerine karıştırılır; video akışı yeniden kodlanmaz |
| **Konuşma tanıma** | `openai-whisper` (tiny → turbo) veya `faster-whisper` (2–4× hızlı, dahili VAD, torch'suz) |
| **Otomatik çeviri** | Google, Ollama (yerel), OpenAI, Anthropic |
| **Bağlam duyarlı çeviri** | Satırlar bloklar hâlinde çevrilir; zamirler, cinsiyet, isimler ve ton sahne boyunca tutarlı kalır |
| **Süreye uyumlu çeviri** | Her satıra karakter bütçesi verilir; dublaj sıkıştırılmadan yuvasına sığar |
| **Altyazı işleme** | SRT çıktısı, `--subtitles-only` modu, dahili SubRip ayrıştırıcı (GPL bağımlılığı yok) |
| **Ses klonlama** | Kısa bir referans örneğinden XTTS v2; vermezseniz kaynaktan otomatik çıkarılır |
| **OpenAI TTS** | `gpt-4o-mini-tts`, talimatla yönlendirilen sunum |
| **Anlatımlı sunum** | `--detect-emotion` Edge'de yerel ses stillerini seçer; OpenAI TTS'te bir LLM her satıra duygu/enerji/tempo yönergesi verir |
| **Kendi sunucunuzda konuşma** | `--openai-tts-base-url` OpenAI uyumlu her `/v1/audio/speech` sunucusunu sürer — anahtar da ek bağımlılık da gerekmez |
| **Çevrimdışı konuşma** | Piper, model indirildikten sonra tamamen çevrimdışı |
| **Sabitlenmiş yerleştirme** | Taşan klipler fade ile kırpılır, kısalar doldurulur, kayma birikmez |
| **Kalite kapısı** | Her klip geri yazıya çevrilir ve puanlanır (WER, kırpılma, sessizlik, tempo) |
| **Otomatik yeniden sentez** | XTTS stokastiktir; işaretlenen segment iki kez yeniden sentezlenir, en iyisi saklanır |
| **Toplu işleme** | Tek komutta birden çok video |
| **Sürdürülebilir çalışmalar** | Her adım kayıt altına alınır; yarıda kalan iş kaldığı yerden devam eder |
| **Ön kontrol** | Eksik girdi dosyası ve eksik FFmpeg iş başlamadan bildirilir |
| **Yapılandırma** | `.env`, JSON yapılandırma, yapılandırılmış JSON günlükleme |
| **Genişletilebilir** | Yeni konuşma veya çeviri sağlayıcısı = 1 adaptör + 1 registry satırı |

> [!NOTE]
> Voxa hiçbir model ağırlığı taşımaz ve üçüncü taraf kodu içermez. Kendi kurduğunuz araçları
> yönetir. Ticari kullanımdan önce [NOTICE.md](NOTICE.md) dosyasını okuyun.

## Desteklenen diller

| Katman | Kapsam |
|---|---|
| **Yazıya çevirme** | Whisper'ın tüm dil kümesi, otomatik algılama |
| **Çeviri** | 74 hedef dil için tam dil adı LLM istemine aktarılır; Google daha fazlasını kabul eder |
| **Edge TTS** | 100+ yerel ayar |
| **OpenAI TTS** | Çok dilli; büyük dillerde en güçlü |
| **Piper** | 15 ses, tamamen çevrimdışı |
| **XTTS** | 17 — `ar` `cs` `de` `en` `es` `fr` `hi` `hu` `it` `ja` `ko` `nl` `pl` `pt` `ru` `tr` `zh` |

### Hangi dil için hangi motor?

`--quality-gate --gate-model base` ile ölçüldü (ASR turu kelime hata oranı; düşük olan
iyidir). Bulut motoru her zaman kazanmaz:

| Dil | Motor | WER | Sonuç |
|---|---|---|---|
| İngilizce | OpenAI TTS | **0.02** | Mükemmel |
| Azerice (`az`) | Edge, yerel `az-AZ` sesi | **0.41** | Bunu kullanın |
| Azerice (`az`) | OpenAI TTS | 0.81 | Yabancı aksan |

> [!TIP]
> Bir dilin Edge'de özel yerel nöral sesi varsa onu tercih edin. Düşük kaynaklı bir dil için
> `--gate-model base` kullanın — `tiny` modeli aynı sesi 0.41 yerine 0.74 puanladı.

## Desteklenen modeller

| Aşama | Modeller |
|---|---|
| Yazıya çevirme | `tiny` · `base` · `small` · `medium` · `large` · `turbo` |
| Çeviri (OpenAI) | `gpt-5` (varsayılan), `gpt-5-mini` |
| Çeviri (Anthropic) | `claude-opus-4-8` (varsayılan), `claude-sonnet-5` |
| Çeviri (Ollama) | `llama3` (varsayılan), herhangi bir yerel model |
| Konuşma (OpenAI) | `gpt-4o-mini-tts` |
| Sunum yönergesi | `gpt-4o-mini` — iş başına tek ucuz çağrı, önbelleklenir |
| Ses klonlama | XTTS v2 |
| Çevrimdışı konuşma | Piper sesleri |
| Kalite kapısı | `faster-whisper` (`tiny` varsayılan, düşük kaynaklı dillerde `base`) |

## Mimari

```
                         Video
                           │
                           ▼
              ┌─────────────────────────┐
              │     Konuşma Tanıma      │  Whisper / faster-whisper
              │                         │  + kelime başlangıcı hassaslaştırma
              │                         │  + konuşma dışı filtreleme
              └────────────┬────────────┘
                           ▼
              ┌─────────────────────────┐
              │         Çeviri          │  Google · Ollama · OpenAI · Anthropic
              │                         │  bağlam duyarlı, süre bütçeli
              └────────────┬────────────┘
                           ▼
              ┌─────────────────────────┐
              │      Metinden Sese      │  Edge · OpenAI · Piper · XTTS
              │                         │  tek ortak zaman çizelgesi sürücüsü
              └────────────┬────────────┘
                           ▼
              ┌─────────────────────────┐
              │      Ses İşleme         │  yerleştirme (yalnızca hızlandırma)
              │                         │  sabitlenmiş anchor
              │                         │  2 geçişli loudnorm
              └────────────┬────────────┘
                           ▼
                    Dublajlı Video
```

Her aşama `<video>_work/` içinde kayıt altına alınır. Ayrıntılar için
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Demo

| Hedef | Kaynak | Motor | Dosya |
|---|---|---|---|
| 🇹🇷 Türkçe | İngilizce | *TBD* | `docs/assets/dubbed_tr.mp4` |
| 🇦🇿 Azerice | İngilizce | *TBD* | `docs/assets/dubbed_az.mp4` |
| 🇫🇷 Fransızca | İngilizce | *TBD* | `docs/assets/dubbed_fr.mp4` |

> [!IMPORTANT]
> Demo dosyaları `docs/assets/` içinde bulunmalıdır. Kök dizindeki `*.mp4` gitignore'ludur.

<!-- DEMO_TR --> <!-- paste the user-attachments URL for the Turkish demo here -->
<!-- DEMO_AZ --> <!-- paste the user-attachments URL for the Azerbaijani demo here -->
<!-- DEMO_FR --> <!-- paste the user-attachments URL for the French demo here -->

## Kurulum

**1. FFmpeg** — Voxa başlangıçta kontrol eder ve eksikse bildirir.

```bash
sudo apt install ffmpeg      # Debian / Ubuntu
sudo dnf install ffmpeg      # Fedora / RHEL
brew install ffmpeg          # macOS
winget install Gyan.FFmpeg   # Windows
```

**2. Voxa** — Python 3.9 veya üzeri.

```bash
git clone https://github.com/akshinmrv/Voxa
cd Voxa
python3 -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate

# Yalnızca CPU torch tekerleği kurulumu belirgin şekilde küçültür
pip install torch --index-url https://download.pytorch.org/whl/cpu

pip install .
```

> [!NOTE]
> `pip install .` PATH'inize bir **`voxa`** komutu ekler — aşağıdaki tüm örnekler bunu
> kullanır. Kurmak istemiyorsanız (ya da yalnızca `pip install -r requirements.txt`
> yaptıysanız), betiği doğrudan çalıştırın: `python voxa.py …`. İkisi birbirinin yerine geçer.

**3. İsteğe bağlı motorlar** — yalnızca kullandığınızı kurun.

| Komut | Neyi etkinleştirir |
|---|---|
| `pip install "voxa[faster]"` | `--whisper-backend faster` — 2–4× hızlı, torch'suz |
| `pip install "voxa[piper]"` | `--tts piper` — tamamen çevrimdışı |
| `pip install "voxa[anthropic]"` | `--translator anthropic` |
| `pip install "voxa[xtts]"` | `--tts xtts` ses klonlama |

> [!WARNING]
> `voxa[xtts]` bakımı sürdürülen [`coqui-tts`](https://github.com/idiap/coqui-ai-TTS) çatalını
> kurar. **XTTS-v2 model ağırlıkları ticari değildir** (CPML) ve Coqui Inc. artık ticari lisans
> satacak durumda değil. Ticari ses klonlama için `--openai-tts-base-url` ile MIT lisanslı bir
> motor kullanın.

## Yapılandırma

**API anahtarları.** `.env.example` dosyasını `.env` olarak kopyalayın (gitignore'lu) ve
doldurun. Voxa başlangıçta yükler; gerçek ortam değişkenleri her zaman önceliklidir.

**Varsayılanlar.** Sık kullanılan seçenekleri bir JSON dosyasına koyun. Tam örnek:
[`examples/config.json`](examples/config.json).

**Günlükleme.** `--log-format json` her satır için bir JSON nesnesi üretir. `--verbose`
seviyeyi DEBUG'a çıkarır.

**Tüm seçenekler:** `voxa --help` — koddan üretilir, dolayısıyla asla eskimez.

## Hızlı başlangıç

```bash
# En basiti: anahtar yok, yapılandırma yok
voxa video.mp4 --target_lang tr

# LLM ile doğal, bağlam duyarlı çeviri
export OPENAI_API_KEY="sk-..."
voxa video.mp4 --target_lang de --translator openai

# Konuşmacının sesini klonla
voxa video.mp4 --target_lang tr --tts xtts

# Tamamen çevrimdışı
voxa video.mp4 --target_lang fr --translator ollama --tts piper

# Yalnızca altyazı
voxa video.mp4 --target_lang es --subtitles-only

# Tek komutta birden çok video
voxa a.mp4 b.mp4 c.mp4 --target_lang tr

# Tahmin etmek yerine ölç
voxa video.mp4 --target_lang az --quality-gate --gate-model base

# Kendi sunucunuzda konuşma
voxa video.mp4 --target_lang tr --tts openai \
     --openai-tts-base-url http://localhost:8004/v1
```

## Web arayüzü (`voxa serve`)

Voxa, [`web/`](web/) klasöründe isteğe bağlı bir web önyüzü ve `voxa serve` arkasında yerel bir
operatör arka ucu sunar — tek tasarım sistemi, iki yüzey:

- **Landing** — herkese açık, üç dilli (EN/AZ/TR) tanıtım sitesi, statik olarak dağıtılabilir.
- **Operatör uygulaması** — yerel konsol: video yükle, motor seç, yedi adımlı hattı canlı izle
  (SSE) ve sonucu indir. Hiçbir şey sunucuya yüklenmez — kendi makinende çalışır.

```bash
# Arka uç: REST + SSE
pip install ".[serve]"
voxa serve                              # http://127.0.0.1:8000

# Önyüz (ayrı terminal)
cd web && npm install && npm run dev    # http://localhost:3000  →  /en/app
```

Geliştirme, ortam değişkenleri ve dağıtım için: [`web/README.md`](web/README.md).

## Proje yapısı

```
Voxa/
├── voxa.py                     # Tüm araç: pipeline, motorlar, registry'ler, CLI
├── pyproject.toml              # Paketleme, extras, ruff ve pytest yapılandırması
├── requirements.txt            # Temel bağımlılıklar (isteğe bağlı motorlar extras'ta)
│
├── tests/
│   ├── test_voxa.py            # Birim testleri
│   ├── test_golden.py          # Golden koşum: fonksiyonlar bir arada
│   └── golden/                 # Kaydedilmiş girdiler ve beklenen çıktılar
│
├── docs/
│   ├── ARCHITECTURE.md         # Tasarım kararları
│   ├── RELEASING.md            # Sürüm kontrol listesi
│   └── assets/                 # Demo videoları ve görseller
│
├── examples/
│   └── config.json             # Eksiksiz, doğrulanmış bir yapılandırma
│
├── .github/                    # CI, release, issue/PR şablonları, dependabot
│
├── README.md
├── CHANGELOG.md
├── CONTRIBUTING.md
├── SECURITY.md
├── CODE_OF_CONDUCT.md
├── NOTICE.md                   # Üçüncü taraf lisansları
└── LICENSE                     # MIT
```

## Yol haritası

Bu bir söz değil, bir yön. Donanım veya ücretli anahtar gerektiren her şey dürüstçe test
edilebilene kadar bekler.

| Madde | Durum | Not |
|---|---|---|
| Ağ motorları için paralel sentez | Planlandı | İstekler şu anda sırayla gidiyor; asıl performans payı burada |
| Azure Neural TTS adaptörü | Engellendi | Test için API anahtarı gerekiyor |
| Konuşmacı benzerliği ve MOS puanlama | Değerlendiriliyor | Kalite kapısını WER'in ötesine taşır |
| Daha geniş golden küme | Değerlendiriliyor | Regresyon koşumunda daha fazla dil |
| Demo materyalleri | Açık | `docs/assets/` için önce/sonra klipleri |

## SSS

<details>
<summary><strong>API anahtarı gerekli mi?</strong></summary>

Hayır. Varsayılanlar — Whisper, Google Translate ve Edge TTS — anahtar gerektirmez.
</details>

<details>
<summary><strong>Dublaj neden senkronu kaybetmiyor?</strong></summary>

Her klip kendi başlangıcı ile bir sonraki satırın başlangıcı arasındaki yuvaya yerleştirilir ve
imleç klip sürelerinden biriktirilmez, doğrudan o başlangıca atanır. Taşan bir klip sonrakileri
itmek yerine kırpılır. Zamanlama matematiği saftır ve golden regresyon koşumuyla kilitlenmiştir.
</details>

<details>
<summary><strong>Ticari olarak kullanabilir miyim?</strong></summary>

Voxa'nın kendisi MIT'tir ve copyleft bağımlılığı yoktur. Sürdüğü motorların kendi lisansları
vardır. `--tts xtts` ticari kullanıma **uygun değildir**. Bkz. [NOTICE.md](NOTICE.md).
</details>

<details>
<summary><strong>Ticari bir ürün için sesi nasıl klonlarım?</strong></summary>

MIT lisanslı, OpenAI uyumlu bir konuşma sunucusunu yerel çalıştırın ve Voxa'yı ona yönlendirin:

```bash
voxa video.mp4 --tts openai --openai-tts-base-url http://localhost:8004/v1
```
</details>

<details>
<summary><strong>Tamamen çevrimdışı çalışır mı?</strong></summary>

Evet: `--translator ollama --tts piper`.
</details>

<details>
<summary><strong>Videom yeniden kodlanıyor mu?</strong></summary>

Hayır. Video akışı kopyalanır; yalnızca ses yeniden oluşturulur.
</details>

<details>
<summary><strong>Bir çalıştırmanın maliyeti nedir?</strong></summary>

Varsayılanlarla hiçbir şey. LLM çevirmeniyle her işten sonra token kullanımı günlüğe yazılır;
tahminî bir maliyet de görmek için modelinizin fiyatlarını `voxa.py` içindeki `LLM_PRICING`
tablosuna ekleyin.
</details>

<details>
<summary><strong>Uzun bir iş yarıda kesildi. Baştan mı başlamalıyım?</strong></summary>

Hayır. Her adım `<video>_work/` içinde kayıt altına alınır; aynı komutu tekrar çalıştırın,
Voxa kaldığı yerden devam eder. Temiz bir başlangıç için `--no-resume`.
</details>

<details>
<summary><strong>Windows'ta çalışır mı?</strong></summary>

Evet, FFmpeg PATH'inizde olduğu sürece. CI Linux üzerinde koşar, araç ise Windows'ta
geliştirilir.
</details>

## Katkıda bulunma

Issue ve pull request'ler memnuniyetle karşılanır. [CONTRIBUTING.md](CONTRIBUTING.md) test
paketini, golden dosyaların yeniden kaydını ve iki önemli bağımlılık kuralını açıklar: **GPL
lisanslı zorunlu bağımlılık olmamalı**, motora özgü paketler **extras**'a girmeli.

Bir konuşma motoru eklemek = 1 adaptör + 1 registry satırı.

```bash
pip install -e ".[dev]"
ruff check .
pytest
```

---

## Lisans

Voxa [MIT Lisansı](LICENSE) ile yayımlanır.

Voxa hiçbir model ağırlığı taşımaz ve üçüncü taraf kodu içermez; ancak sürdüğü motorların
kendi lisansları vardır — bazıları Voxa'nınkinden katıdır. Ticari kullanımdan önce
[NOTICE.md](NOTICE.md) dosyasını okuyun.

| Yapılandırma | Ticari kullanım |
|---|:---:|
| `--tts piper` + `--translator ollama` (tamamen çevrimdışı) | ✅ |
| `--tts openai` + `--translator openai` (ücretli API'ler) | ✅ |
| `--tts edge` / `--translator google` (varsayılan, resmî olmayan uç noktalar) | ⚠️ gri alan |
| `--tts xtts` (XTTS-v2 ağırlıkları CPML) | ❌ yalnızca ticari olmayan |

## Teşekkürler

Voxa başkalarının yaptığı işin üzerinde yükselir.

| Proje | Rolü |
|---|---|
| [OpenAI Whisper](https://github.com/openai/whisper) | Konuşma tanıma |
| [faster-whisper](https://github.com/SYSTRAN/faster-whisper) | Hızlı yazıya çevirme arka ucu |
| [edge-tts](https://github.com/rany2/edge-tts) | Microsoft nöral sesleri |
| [Piper](https://github.com/rhasspy/piper) | Çevrimdışı nöral konuşma |
| [coqui-tts](https://github.com/idiap/coqui-ai-TTS) | XTTS ses klonlamasını çalıştıran çatal |
| [OpenAI](https://platform.openai.com/) · [Anthropic](https://www.anthropic.com/) | LLM çeviri ve konuşma |
| [Ollama](https://ollama.com/) | Yerel, gizli LLM çeviri |
| [FFmpeg](https://ffmpeg.org/) | Tüm ses ve video işleri |

## Yazar

**Voxa**, **[Akshin Miranov](https://github.com/akshinmrv)** tarafından **Servoogle** adı
altında geliştirilir ve sürdürülür.

Servoogle, pratik yapay zekâ araçları geliştirmek için var — bir modeli sergileyen değil,
gerçek bir problemi baştan sona çözen yazılım — ve başkalarının üzerine inşa edebileceği
parçaları açık bırakmak için. Voxa bu parçalardan biri. Bir videoyu dublajlamak için stüdyo,
lisans pazarlığı ya da kapalı bir pipeline gerekmemeli; bir komut ve zaten sahip olduğunuz
bir bilgisayar yetmeli.

Voxa tam da bu yüzden MIT'tir, tam da bu yüzden copyleft bağımlılığı taşımaz, lisans
yükümlülükleri tam da bu yüzden gizlenmez, belgelenir; ve her motor tam da bu yüzden
herkesin genişletebileceği bir registry'nin arkasındadır. Bu alandaki ilginç problemler —
dublajı senkronda tutmak, sentetik bir sesi aceleci göstermemek, çıktının gerçekten iyi olup
olmadığını bilmek — açıkta çözülmeye değer.

Voxa size yararlı olduysa, geri gönderebileceğiniz en değerli şey, günlüğü eklenmiş bir hata
raporudur.

<div align="center">

---

**Voxa** · MIT · [Hata bildir](https://github.com/akshinmrv/Voxa/issues) ·
[Katkıda bulun](CONTRIBUTING.md) · [Mimari](docs/ARCHITECTURE.md)

</div>

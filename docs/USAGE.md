# Using Voxa

This page covers the command line in detail. Voxa Studio does the same things with buttons, and
every option here has a place in its Studio form or Settings; see the
[README](../README.md#voxa-studio) for a tour.

## A first dub

```bash
voxa talk.mp4 --target_lang ru
```

That transcribes `talk.mp4` with Whisper, translates it with Google, speaks it with a Microsoft
Edge voice and writes `talk_dubbed_ru.mp4` next to the original. The picture is copied as it
is; only the sound is rebuilt. No API key is involved.

Everything Voxa works out along the way goes into `talk_work/`: the audio, the transcription,
the translated lines (`translated.json`), the subtitles (`captions_ru.srt`), every synthesized
clip and `voxa.log`. If a run stops halfway, the same command picks up where it left off.
`--no-resume` starts clean. A second language reuses the transcription, so it's quicker.

`--output-dir` puts the result somewhere else. Several videos go in one command:
`voxa a.mp4 b.mp4 c.mp4 --target_lang ru`.

## Look before you dub

```bash
# What would happen: engines, models, output path, which steps are already cached
voxa talk.mp4 --target_lang ru --dry-run

# The first 20 seconds only (or --preview 45), as talk.preview20s_dubbed_ru.mp4
voxa talk.mp4 --target_lang ru --preview

# Stop once the lines are translated, so you can read them first
voxa talk.mp4 --target_lang de --review
```

After `--review`, open `talk_work/translated.json`, change whatever reads wrong, and run the
same command without `--review`. If you change a line after the dub is done and run again, only
that line is voiced again.

You can also bring the translation yourself, as an `.srt` or as JSON in the shape
`translated.json` uses:

```bash
voxa talk.mp4 --target_lang de --translation lines.de.srt
```

## Translation

| Translator | Key | Notes |
|---|---|---|
| `google` (default) | none | Literal, quick, free. Uses an unofficial endpoint |
| `openai` | `OPENAI_API_KEY` | `gpt-5` by default, `--openai_model` for another |
| `anthropic` | `ANTHROPIC_API_KEY` | `claude-opus-4-8` by default; needs `voxa-dub[anthropic]` |
| `openrouter` | `OPENROUTER_API_KEY` | Hundreds of models behind one key, e.g. `--openrouter_model deepseek/deepseek-chat` |
| `ollama` | none | Runs on your machine. `llama3` by default, `--ollama_model` for another |

The LLM translators get lines in blocks, so names, pronouns and tone stay consistent across a
scene, and each line comes with a character budget so the translation fits the time the
speaker took. That matters most when the target language is wordier than the source (English
into Turkish or Russian, say). When a line still comes out too long once it is voiced, an LLM
translator says it again in fewer words, keeping its meaning, and the shorter line goes into
the subtitles too. Google translates line by line and knows nothing about time, so with it a
long line is played up to 1.25 times faster, and past that it runs into the time of the lines
after it; the log says which lines.

`--fallback-translator google` takes over the lines an LLM translator leaves untranslated,
after an outage or with a bad key. `--translation-prompt` adds your own guidance on tone,
register or terms.

## Speech

| Engine | Key | Notes |
|---|---|---|
| `edge` (default) | none | Microsoft's neural voices, 100+ locales including Azerbaijani. Unofficial endpoint |
| `openai` | `OPENAI_API_KEY` | `gpt-4o-mini-tts`, which takes delivery instructions |
| `piper` | none | Offline. Needs `voxa-dub[piper]` |
| `xtts` | none | Clones the speaker, 17 languages. Non-commercial weights |
| `chatterbox` | none | Clones the speaker, 23 languages, MIT. `voxa engines install chatterbox` |
| `voxcpm` | none | Clones the speaker, 30 languages, Apache-2.0. `voxa engines install voxcpm` |

```bash
voxa voices --lang az                                         # the voices for a language
voxa talk.mp4 --target_lang az --edge-voice az-AZ-BanuNeural  # pick one
voxa talk.mp4 --target_lang tr --tts chatterbox               # clone the speaker
voxa talk.mp4 --target_lang tr --tts xtts --voice-sample me.wav
```

A cloning engine copies the original speaker unless you give it `--voice-sample`. Voxa only
ever speeds speech up to fit; it never slows it down, because slowed speech sounds dragged. A
line that is still too long runs into the pause after it rather than being rushed, and the
next line still starts on time.

`--detect-emotion` picks Edge's speaking styles per line where a voice has them; with OpenAI it
asks an LLM for a short delivery note per line.

### A speech server of your own

Any server that speaks OpenAI's `/v1/audio/speech` works, with no key and no extra package:

```bash
voxa talk.mp4 --target_lang tr --tts openai --openai-tts-base-url http://localhost:8004/v1
```

Your `OPENAI_API_KEY` is never sent to it; if the server wants its own key, set
`OPENAI_TTS_API_KEY`. Each request carries the target language, so a multilingual model knows
what to speak. The model the server runs decides what you may do with the result. VoiceStudio's
local server (port 3900) defaults to OmniVoice, which speaks Azerbaijani but is non-commercial;
see [NOTICE](../NOTICE.md#46-self-hosted-speech-servers). On a laptop CPU, a 45-second clip
through VoiceStudio and OmniVoice took about four minutes to synthesize.

## Which engine for which language

There isn't one answer, and the cloud doesn't always win. A voice made for a language usually
beats a bigger model that only approximates it. In our runs, Edge's native Azerbaijani voice
scored a word error rate of 0.41 where OpenAI's TTS scored 0.81.

So measure it on your own material. `--quality-gate` transcribes every synthesized clip back
with a second Whisper and scores it:

```bash
voxa clip.mp4 --target_lang az --tts edge --quality-gate --gate-model base
```

For a language with little training data, use `--gate-model base` or larger. `tiny` misreads a
perfectly good voice and reports it worse than it is. One proper noun in a short clip can also
move the average a lot, so read any number, ours included, next to the clip it came from.
[BENCHMARK.md](BENCHMARK.md) has a script to reproduce this and a run across six languages.

With the gate on, XTTS synthesizes a clip that scores badly again, up to twice, because its
output varies from take to take, and keeps the best take. OpenAI TTS renders such a line once
more without its style instructions, if it had any. The log ends with a report per line.

## Subtitles

```bash
voxa talk.mp4 --target_lang es --subtitles-only                            # subtitles, no voice
voxa talk.mp4 --target_lang es --subtitles-only --subtitles-in-video hard  # drawn onto the picture
voxa talk.mp4 --target_lang es --subtitles-in-video soft                   # a dub with a subtitle track
```

Subtitles are cut to read comfortably: at most two lines of about 42 characters (21 for
Chinese, Japanese and Korean). `soft` adds a track players can switch on and keeps the picture
as it is. `hard` draws them onto the picture for players and sites that show no tracks, which
means encoding the video again.

If you already have subtitles, Voxa can start from them and skip Whisper. That also voices a
video with no sound at all, a screen recording for instance:

```bash
voxa screencast.mp4 --target_lang de --subtitles script.srt
```

## Several speakers

```bash
voxa interview.mp4 --target_lang de --diarize --num-speakers 2
```

Each speaker gets their own voice. It needs a Hugging Face token and `voxa-dub[diarize]`; see
[INSTALL](INSTALL.md#several-speakers). To choose the voices yourself:
`--speaker-voices "SPEAKER_00=de-DE-ConradNeural,SPEAKER_01=de-DE-KatjaNeural"`.

## The original's music

By default the dub replaces the original's sound entirely. That sound carries the speech the
dub replaces, and Voxa doesn't let any of it be heard under the dub. With Demucs installed
(`voxa engines install demucs`), `--separate` takes the original speech out and keeps the music
and effects. Demucs can leave some of the voice behind: where the background rises and falls
with the original voice, it is muted while the original speaks. `--background-volume` sets the
background's level and `--voice-volume` the dub's.
Measurements are in [INSTALL](INSTALL.md#engines-in-environments-of-their-own).

## Configuration

**API keys** go in a `.env` file next to where you run Voxa (copy `.env.example`). Real
environment variables win over it. Avoid `--openai_api_key` on the command line: it ends up in
your shell history and the process list. Voxa Studio and `voxa serve` save the keys you
enter in Settings to the `.env` in the folder they run in (`%USERPROFILE%\Voxa` for a
VoxaSetup install) and never show them back.

```dotenv
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
OPENROUTER_API_KEY=sk-or-...
HF_TOKEN=hf_...
```

**Defaults** you use every time go in a JSON file, keyed by the long option names with
underscores. Flags on the command line override it.
[`examples/config.json`](../examples/config.json) is a complete example.

```bash
voxa talk.mp4 --config examples/config.json
```

**Costs.** After each job Voxa logs what it used. For LLM translators it prints an estimate
when it knows the price; list prices change, so set yours with `--llm-prices`, best kept in the
config file. For OpenAI TTS, `--tts-price` (USD per million characters) turns the character
count into a cost.

```json
{ "llm_prices": { "gpt-5": [1.25, 10], "claude-opus-4-8": [15, 75] }, "tts_price": 12.0 }
```

**Logs.** `--log-format json` writes one JSON object per line. `--verbose` adds debug output,
including third-party libraries.

`voxa --help` lists every option. It's generated from the code, so it's always current.

## Languages and models

| Stage | Coverage |
|---|---|
| Transcription | Whisper's full set, detected automatically |
| Translation | 74 languages get their full name in the LLM prompt; Google accepts more |
| Edge | 100+ locales |
| OpenAI TTS | Multilingual, strongest in widely spoken languages |
| Piper | 15 languages mapped to a voice |
| XTTS | 17: `ar` `cs` `de` `en` `es` `fr` `hi` `hu` `it` `ja` `ko` `nl` `pl` `pt` `ru` `tr` `zh` |
| Chatterbox | 23 |
| VoxCPM2 | 30 |

Whisper models: `tiny`, `base`, `small`, `medium`, `large`, `turbo` (`--whisper_model`).
`--whisper-backend faster` runs the same models through CTranslate2, 2 to 4 times quicker.

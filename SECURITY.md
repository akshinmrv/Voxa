# Security Policy

## Supported versions

Voxa is developed on `main`. Security fixes land there and in the next release; there is no
long-term support branch.

| Version | Supported |
|---------|:---------:|
| 1.x     | ✅ |
| < 1.0   | ❌ (pre-release, never published) |

## Reporting a vulnerability

**Please do not open a public issue for a security problem.**

Use GitHub's [private vulnerability reporting](https://github.com/akshinmrv/Voxa/security/advisories/new),
or email **akshinmiranov@gmail.com** with `[voxa security]` in the subject.

Include what you can: the version or commit, the command you ran, what you expected, what
happened, and a minimal reproduction. You'll get an acknowledgement within a few days, and
credit in the release notes unless you'd rather not be named.

## What is in scope

Voxa is a local command-line tool, not a service. The realistic risks are:

- **Model deserialization.** Loading an XTTS checkpoint executes `torch.load` with
  `weights_only=False`. Voxa scopes that to the model load and nowhere else, but a malicious
  checkpoint can still run code. **Only load model files you trust.**
- **Configuration files.** `--config` reads a JSON file whose keys become option defaults.
  Treat it like a script: don't run Voxa with a config you didn't write.
- **Subprocess arguments.** Voxa shells out to `ffmpeg` and `piper`. Every call passes an
  argument list — never `shell=True` — so a crafted filename cannot inject a command. If you
  find a path where that isn't true, that is a vulnerability; please report it.
- **API keys.** Keys are read from the environment or a gitignored `.env` and are only ever
  sent to the provider they belong to. Voxa does not log them. Passing a key with
  `--openai_api_key` puts it in your shell history and the process list — prefer the
  environment variable.

## Out of scope

- Vulnerabilities in third-party engines and models (Whisper, edge-tts, Coqui/XTTS, Piper) —
  report those upstream. [NOTICE.md](NOTICE.md) lists what Voxa drives.
- The fact that `edge-tts` talks to an undocumented Microsoft endpoint, and
  `deep-translator` to an undocumented Google one. This is disclosed in NOTICE.md; if it
  matters to you, use `--tts openai`/`--tts piper` and an official translation API.

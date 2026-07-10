# Releasing Voxa

Voxa follows [Semantic Versioning](https://semver.org/). Releases are cut from `main`.

## Checklist

1. **Everything green locally**

   ```bash
   ruff check .
   pytest
   ```

   Then run a real dub — the test suite cannot hear:

   ```bash
   voxa some_video.mp4 --target_lang ru --whisper_model tiny
   ```

2. **Bump the version** in `pyproject.toml`.

3. **Update `CHANGELOG.md`.** Move everything under `## [Unreleased]` into a new version
   section with today's date, and add the comparison links at the bottom.

4. **Commit and tag.**

   ```bash
   git commit -am "Release vX.Y.Z"
   git tag -a vX.Y.Z -m "Voxa vX.Y.Z"
   git push origin main --follow-tags
   ```

5. **The tag does the rest.** `.github/workflows/release.yml` re-runs lint and tests against
   the tagged commit and, only if they pass, opens the GitHub release.

## Repository settings (once)

Set on GitHub, not in the repo:

- **Description:** *Automatic video translation and dubbing — Whisper transcription, LLM
  translation, four TTS engines, and a dub that stays in sync.*
- **Topics:** `dubbing`, `video-dubbing`, `text-to-speech`, `speech-to-text`, `whisper`,
  `translation`, `voice-cloning`, `subtitles`, `ffmpeg`, `openai`, `python`, `cli`
- Enable **private vulnerability reporting** (Settings → Security), which `SECURITY.md`
  points contributors at.
- Enable **Dependabot alerts**; `.github/dependabot.yml` handles the update PRs.

## PyPI (optional)

Voxa is installable from source (`pip install .`) and does not currently publish to PyPI.
If that changes, prefer [trusted publishing](https://docs.pypi.org/trusted-publishers/) over
storing an API token in repository secrets.

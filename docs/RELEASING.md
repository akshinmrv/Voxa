# Releasing Voxa

Voxa follows [Semantic Versioning](https://semver.org/). A release is a tag on `main`; the
workflow in `.github/workflows/release.yml` builds and publishes everything from it.

## Before the tag

1. **The code is ready.** `ruff check .` and `pytest` pass locally, and anything that touches
   synthesis, timing or mixing has been tried on a real video. Tests can't hear.

2. **The release commit.** In one commit:
   - set `version` in `pyproject.toml`;
   - in `CHANGELOG.md`, rename `## [Unreleased]` to `## [X.Y.Z] - YYYY-MM-DD`, start a new
     empty `## [Unreleased]` above it, and add the compare link at the bottom.

   `python scripts/check_release_tag.py vX.Y.Z` checks the two agree.

3. **Push it and wait for CI to pass on that commit.** Only then tag it.

## The tag

Tag the release commit itself, after pulling it:

```bash
git pull --ff-only
git log -1 --format='%h %s'      # the release commit
git tag vX.Y.Z
git push origin vX.Y.Z
```

A tag on the wrong commit is the mistake this process has made most. The workflow's first job
compares the tag with `pyproject.toml` and stops everything if they differ, so nothing is
published. Move the tag to the right commit and push it again:

```bash
git tag -f vX.Y.Z <release-commit> && git push --force origin vX.Y.Z
```

## What the workflow does

| Job | What it does |
|---|---|
| Check the tag | The tag must match `pyproject.toml` and have a CHANGELOG section |
| Verify | Lint and tests on Python 3.10 to 3.14 |
| Publish GitHub release | Creates the release with generated notes |
| Publish to PyPI | Builds the console and the wheel, checks the wheel carries the console, publishes `voxa-dub` through trusted publishing (no token in the repository) |
| Publish the container image | Builds `ghcr.io/akshinmrv/voxa` and tags it `X.Y.Z`, `X.Y` and `latest` |
| Publish the Windows installer | Waits until PyPI's index serves the new version, builds VoxaSetup.exe, installs it on a Windows runner from PyPI, checks it, uninstalls it, then attaches `VoxaSetup.exe` and `VoxaSetup-X.Y.Z.exe` to the release |

If the installer job fails on a PyPI that hasn't caught up yet, re-run the failed job
(`gh run rerun <id> --failed`). Until it succeeds,
`releases/latest/download/VoxaSetup.exe` and voxa.servoogle.com/download return 404, so check
them when the run is green.

## After it

- PyPI shows the new version, and `pipx install voxa-dub` gets it.
- `docker pull ghcr.io/akshinmrv/voxa:X.Y.Z` works, and the image's labels name the version
  and the commit.
- voxa.servoogle.com/download downloads the new VoxaSetup.exe.
- Existing installs see the update within a day (they check PyPI once a day).

## Repository settings

Set on GitHub, not in the repository:

- Description: *Video dubbing that stays in sync with the speaker. Whisper, LLM translation,
  six speech engines, voice cloning. Runs locally, MIT.*
- Topics: `dubbing`, `video-dubbing`, `text-to-speech`, `speech-to-text`, `whisper`,
  `translation`, `voice-cloning`, `subtitles`, `ffmpeg`, `python`, `cli`
- Private vulnerability reporting (Settings, Security), which `SECURITY.md` points to.
- Dependabot alerts; `.github/dependabot.yml` opens the update PRs. It ignores numpy and numba
  on purpose: newer ones break Intel Macs.
- A `pypi` environment trusted by PyPI for this repository and workflow.

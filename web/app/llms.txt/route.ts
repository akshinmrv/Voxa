import { DOWNLOAD_PATH, SITE } from "@/lib/site";

// llms.txt — a concise, factual brief for AI answer engines (GEO §27).
// Extensionless-safe: `.txt` is excluded from the i18n proxy matcher.
export const dynamic = "force-static";

export function GET() {
  const body = `# Voxa

> Voxa is an open-source, MIT-licensed AI video dubbing tool. It transcribes a
> video with Whisper, translates the text with an LLM, synthesizes speech with
> one of four TTS engines, and keeps the dub locked in sync with the speaker
> (anchored placement — zero drift). It runs locally on your own machine.

## Key facts
- License: MIT (open source)
- Author: ${SITE.author.name}; Publisher: ${SITE.org.name}
- Runs locally — no SaaS, no account, no telemetry
- Transcription: Whisper (tiny → large, multiple sizes)
- Translation: Google, Ollama (offline), OpenAI, Anthropic
- Text-to-speech: Edge, OpenAI, Piper (offline), XTTS (voice cloning)
- Self-hostable TTS via any OpenAI-compatible endpoint (--openai-tts-base-url)
- Differentiator: anchored placement pins every clip to the source timeline, so
  the dub never falls behind the speaker (unlike naive tools that concatenate
  clips and drift)
- Local operator UI: run \`voxa serve\` for a browser console (upload, configure,
  watch progress, download)

## Install
- Windows: VoxaSetup.exe, ${SITE.url}${DOWNLOAD_PATH} (for one user, no administrator
  rights; brings the Python it runs on, installs FFmpeg with winget if it's missing, adds
  Voxa Studio to the Start menu)
- Windows, one line: irm ${SITE.url}/install.ps1 | iex
- macOS / Linux, one line: curl -fsSL ${SITE.url}/install.sh | sh
- With Python already: pipx install "voxa-dub[serve]" (the PyPI package is voxa-dub,
  not voxa; the command it installs is voxa)
- Then: voxa studio (the desktop app), or voxa talk.mp4 --target_lang ru

## Languages
Whisper covers ~100 source languages; target languages depend on the chosen TTS
engine. UI and docs are available in English, Azerbaijani, and Turkish.

## Links
- Repository: ${SITE.repo}
- Website: ${SITE.url}
- Documentation: ${SITE.repo}#readme
`;

  return new Response(body, {
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  });
}

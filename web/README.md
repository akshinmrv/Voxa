# Voxa web

The frontend for [Voxa](https://github.com/akshinmrv/Voxa). One Next.js app, built three ways:

- **The console** (`/[locale]/app`): what Voxa Studio shows. It talks to `voxa serve`, and a
  static build of it ships inside the Python package (`voxa_ui/static`).
- **The website** (`/[locale]`): [voxa.servoogle.com](https://voxa.servoogle.com) in English,
  Azerbaijani and Turkish, deployed on Vercel. Its download button goes to `/download`, which
  `next.config.ts` redirects to the newest VoxaSetup.exe.
- **The style guide** (`/[locale]/style-guide`): every building block in both themes and all
  three languages. It's left out of the package.

Next.js (App Router), React, Tailwind CSS, Radix primitives, next-intl, next-themes and React
Query. Texts live in `messages/en.json`, `az.json` and `tr.json`.

## Develop

```bash
cd web
npm ci
npm run dev          # http://localhost:3000
```

The console needs the server next to it:

```bash
pip install -e ".[serve]"      # in the repository's root; or: pipx install "voxa-dub[serve]"
voxa serve                     # http://127.0.0.1:8000
```

In development the bare `/` goes straight to the console; a production build keeps the
website there.

## Environment

Copy `.env.example` to `.env.local` if you need to change anything. All of these are optional.

| Variable | Default | Purpose |
| --- | --- | --- |
| `NEXT_PUBLIC_TARGET` | `local` | `local` is the full app. `public` is the website: `/app` becomes a "run it locally" notice. `console` is set by `build:console` |
| `NEXT_PUBLIC_SITE_URL` | Vercel's domain, else voxa.servoogle.com | Canonical URL for SEO: hreflang, OpenGraph, sitemap, JSON-LD, llms.txt |
| `NEXT_PUBLIC_VOXA_API` | `http://localhost:8000` | Where the console finds `voxa serve`. Empty in the packaged console, which uses its own origin |

## Build

```bash
npm run build:console                      # the console, copied into ../voxa_ui/static
NEXT_PUBLIC_TARGET=public npm run build    # the website, as Vercel builds it
```

## Checks

CI runs all of these:

```bash
npm run lint
npx tsc --noEmit
npm run check:messages     # the three languages have the same keys and arguments, none empty,
                           # none given twice, and no console text left in English
npm run check:contrast     # every text colour against every surface, both themes, WCAG AA
```

The browser tests in `../tests/test_e2e.py` run against a `build:console` build; see
[CONTRIBUTING.md](../CONTRIBUTING.md#before-you-open-a-pull-request).

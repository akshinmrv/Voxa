# Voxa Web

The frontend for [Voxa](https://github.com/akshinmrv/Voxa) — one design system, two surfaces:

- **Landing** (`/[locale]`) — a public, static, trilingual (EN/AZ/TR) showcase, tuned for SEO and AI answer engines.
- **Operator app** (`/[locale]/app`) — a local console for the `voxa serve` backend: upload a video, pick engines, watch the seven-step pipeline live (SSE), and download the result.

Built with Next.js (App Router), React, Tailwind CSS, shadcn-style primitives, next-intl, next-themes, and React Query.

## Develop

```bash
cd web
npm install
npm run dev          # http://localhost:3000
```

For the operator app to work, run the backend alongside it:

```bash
pip install "voxa[serve]"
voxa serve           # http://localhost:8000
```

## Environment

Copy `.env.example` to `.env.local` and adjust. Key variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `NEXT_PUBLIC_TARGET` | `local` | `local` ships the full app; `public` replaces `/app` with a "run locally" notice |
| `NEXT_PUBLIC_SITE_URL` | placeholder | Canonical URL for SEO (canonical, hreflang, OpenGraph, sitemap, JSON-LD) |
| `NEXT_PUBLIC_VOXA_API` | `http://localhost:8000` | Base URL of the `voxa serve` backend |
| `NEXT_PUBLIC_DEMO_VIDEO` / `_POSTER` | empty | Optional demo clip for the landing |

## Build & deploy

```bash
npm run build        # local build (full app)

# Public landing for a domain:
NEXT_PUBLIC_TARGET=public NEXT_PUBLIC_SITE_URL=https://your-domain npm run build
```

Deploy the public build to any Next-compatible host (Vercel, Cloudflare Pages, Netlify). The landing pages are statically prerendered; the operator app is intended to run locally only.

## Scripts

- `npm run dev` — dev server
- `npm run build` — production build
- `npm run start` — serve the production build
- `npm run lint` — ESLint

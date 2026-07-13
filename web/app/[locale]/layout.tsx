import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import { notFound } from "next/navigation";
import { hasLocale, NextIntlClientProvider } from "next-intl";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { routing } from "@/i18n/routing";
import { SITE, localeUrl } from "@/lib/site";
import { ThemeProvider } from "@/components/theme-provider";
import { SkipLink } from "@/components/skip-link";
import "../globals.css";

// latin-ext covers Azerbaijani (ə) and Turkish (ş ğ ı) glyphs.
const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin", "latin-ext"],
});

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-jetbrains-mono",
  subsets: ["latin", "latin-ext"],
});

export function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "Meta" });
  const title = t("title");
  const description = t("description");

  // hreflang: every locale points at its counterpart, plus x-default → default locale.
  const languages: Record<string, string> = Object.fromEntries([
    ...routing.locales.map((l) => [l, localeUrl(l)]),
    ["x-default", localeUrl(routing.defaultLocale)],
  ]);

  return {
    metadataBase: new URL(SITE.url),
    title,
    description,
    applicationName: SITE.name,
    authors: [{ name: SITE.author.name, url: SITE.author.github }],
    creator: SITE.author.name,
    publisher: SITE.org.name,
    keywords: [
      "video dubbing",
      "AI dubbing",
      "open source dubbing",
      "Whisper transcription",
      "text to speech",
      "TTS",
      "voice cloning",
      "self-hosted dubbing",
      "subtitles",
      "video localization",
      "Voxa",
    ],
    alternates: { canonical: localeUrl(locale), languages },
    icons: { icon: "/icon" },
    openGraph: {
      type: "website",
      siteName: SITE.name,
      title,
      description,
      url: localeUrl(locale),
      locale,
      alternateLocale: routing.locales.filter((l) => l !== locale),
      images: [{ url: "/opengraph-image", width: 1200, height: 630, alt: title }],
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
      images: ["/opengraph-image"],
    },
    robots: { index: true, follow: true },
  };
}

export default async function LocaleLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  if (!hasLocale(routing.locales, locale)) {
    notFound();
  }
  setRequestLocale(locale);

  return (
    <html
      lang={locale}
      suppressHydrationWarning
      className={`${inter.variable} ${jetbrainsMono.variable} h-full`}
    >
      <body className="min-h-dvh flex flex-col antialiased">
        <NextIntlClientProvider>
          <ThemeProvider
            attribute="class"
            defaultTheme="dark"
            enableSystem={false}
            disableTransitionOnChange
          >
            <SkipLink />
            {children}
          </ThemeProvider>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}

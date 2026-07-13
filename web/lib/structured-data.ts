import { SITE, localeUrl } from "./site";

/**
 * schema.org @graph for the landing page: the Voxa software, its author
 * (Akshin Miranov) and publisher (Servoogle), the website, and the FAQ.
 * Powers rich results and gives answer engines clean, linked facts (GEO §27).
 */
export function landingJsonLd({
  locale,
  description,
  faq,
  demo,
}: {
  locale: string;
  description: string;
  faq: { q: string; a: string }[];
  demo?: { url: string; poster: string; name: string; description: string } | null;
}) {
  const authorId = `${SITE.url}/#author`;
  const orgId = `${SITE.url}/#servoogle`;

  const videoNode = demo?.url
    ? [
        {
          "@type": "VideoObject",
          "@id": `${SITE.url}/#demo`,
          name: demo.name,
          description: demo.description,
          contentUrl: demo.url,
          thumbnailUrl: demo.poster || `${SITE.url}/opengraph-image`,
          uploadDate: new Date().toISOString(),
          publisher: { "@id": orgId },
        },
      ]
    : [];

  return {
    "@context": "https://schema.org",
    "@graph": [
      ...videoNode,
      {
        "@type": "Organization",
        "@id": orgId,
        name: SITE.org.name,
        url: SITE.org.url,
        sameAs: SITE.sameAs,
      },
      {
        "@type": "Person",
        "@id": authorId,
        name: SITE.author.name,
        url: SITE.author.github,
        sameAs: [SITE.author.github],
      },
      {
        "@type": "WebSite",
        "@id": `${SITE.url}/#website`,
        url: SITE.url,
        name: SITE.name,
        description,
        inLanguage: locale,
        publisher: { "@id": orgId },
      },
      {
        "@type": "SoftwareApplication",
        "@id": `${SITE.url}/#software`,
        name: SITE.name,
        url: localeUrl(locale),
        description,
        applicationCategory: "MultimediaApplication",
        operatingSystem: "Windows, macOS, Linux",
        softwareVersion: "1.0.0",
        license: "https://opensource.org/licenses/MIT",
        codeRepository: SITE.repo,
        sameAs: [SITE.repo],
        offers: { "@type": "Offer", price: "0", priceCurrency: "USD" },
        author: { "@id": authorId },
        creator: { "@id": authorId },
        publisher: { "@id": orgId },
      },
      {
        "@type": "FAQPage",
        "@id": `${SITE.url}/#faq`,
        mainEntity: faq.map((item) => ({
          "@type": "Question",
          name: item.q,
          acceptedAnswer: { "@type": "Answer", text: item.a },
        })),
      },
    ],
  };
}

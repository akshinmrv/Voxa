import { defineRouting } from "next-intl/routing";

// EN default/fallback, plus AZ and TR — mirrors the trilingual READMEs.
export const routing = defineRouting({
  locales: ["en", "az", "tr"],
  defaultLocale: "en",
});

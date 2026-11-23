import { defineRouting } from "next-intl/routing";

// EN default/fallback, plus AZ and TR — mirrors the trilingual READMEs.
export const routing = defineRouting({
  locales: ["en", "az", "tr"],
  defaultLocale: "en",
  // next-intl 4 keeps the language you pick in a session cookie, which Voxa Studio's window
  // (and a browser) drops when it closes, so the console came back in the system's language.
  // A year keeps the choice; the cookie holds only "en", "az" or "tr".
  localeCookie: { maxAge: 60 * 60 * 24 * 365 },
});

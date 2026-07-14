import createMiddleware from "next-intl/middleware";
import { NextResponse, type NextRequest } from "next/server";
import { routing } from "./i18n/routing";

// Next.js 16 renamed "middleware" to "proxy"; next-intl's handler is unchanged.
const intlMiddleware = createMiddleware(routing);

// Local dev is used to operate the app, so the bare root goes straight to it.
// Public deploys keep the marketing landing at the root.
const IS_PUBLIC = process.env.NEXT_PUBLIC_TARGET === "public";

function pickLocale(request: NextRequest): string {
  const locales = routing.locales as readonly string[];
  const cookie = request.cookies.get("NEXT_LOCALE")?.value;
  if (cookie && locales.includes(cookie)) return cookie;
  const accept = (request.headers.get("accept-language") ?? "").toLowerCase();
  return locales.find((l) => accept.startsWith(l)) ?? routing.defaultLocale;
}

export default function proxy(request: NextRequest) {
  // Only the bare "/" is redirected, so "/<locale>" still reaches the landing
  // (e.g. the app's "Back to site" link keeps working).
  if (!IS_PUBLIC && request.nextUrl.pathname === "/") {
    return NextResponse.redirect(
      new URL(`/${pickLocale(request)}/app`, request.url),
    );
  }
  return intlMiddleware(request);
}

export const config = {
  // Match all paths except API, Next internals, the extensionless metadata image
  // routes (opengraph-image / icon / apple-icon), and files with an extension.
  matcher: "/((?!api|_next|_vercel|opengraph-image|icon|apple-icon|.*\\..*).*)",
};

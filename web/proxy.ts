import createMiddleware from "next-intl/middleware";
import { routing } from "./i18n/routing";

// Next.js 16 renamed "middleware" to "proxy"; next-intl's handler is unchanged.
export default createMiddleware(routing);

export const config = {
  // Match all paths except API, Next internals, and files with an extension.
  matcher: "/((?!api|_next|_vercel|.*\\..*).*)",
};

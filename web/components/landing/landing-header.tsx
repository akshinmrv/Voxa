import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import { Waveform } from "@/components/waveform";
import { ThemeToggle } from "@/components/theme-toggle";
import { LanguageSwitcher } from "@/components/language-switcher";
import { Button } from "@/components/ui/button";
import { GithubIcon } from "@/components/icons/github";

const GITHUB_URL = "https://github.com/akshinmrv/Voxa";

export function LandingHeader() {
  const t = useTranslations("Nav");

  const navItems = [
    { href: "#features", label: t("features") },
    { href: "#how-it-works", label: t("howItWorks") },
    { href: "#models", label: t("models") },
    { href: "#install", label: t("install") },
    { href: "#faq", label: t("faq") },
  ];

  return (
    <header className="sticky top-0 z-50 border-b border-border bg-background/80 backdrop-blur">
      <div className="mx-auto flex h-16 w-full max-w-6xl items-center justify-between px-6">
        <Link href="/" className="flex items-center gap-2.5" aria-label="Voxa">
          <Waveform bars={5} className="h-5" />
          <span className="text-lg font-semibold tracking-tight">Voxa</span>
        </Link>

        <nav className="hidden items-center gap-6 md:flex">
          {navItems.map((item) => (
            <a
              key={item.href}
              href={item.href}
              className="text-sm text-muted-foreground transition-colors hover:text-foreground"
            >
              {item.label}
            </a>
          ))}
        </nav>

        <div className="flex items-center gap-2">
          <LanguageSwitcher />
          <ThemeToggle />
          <Button asChild variant="secondary" size="sm" className="hidden sm:inline-flex">
            <a href={GITHUB_URL} target="_blank" rel="noopener noreferrer">
              <GithubIcon />
              {t("github")}
            </a>
          </Button>
        </div>
      </div>
    </header>
  );
}

import { useTranslations } from "next-intl";
import { Building2, User } from "lucide-react";
import { SITE } from "@/lib/site";
import { GithubIcon } from "@/components/icons/github";
import { SectionHeader } from "./section-header";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";

export function Author() {
  const t = useTranslations("Author");

  return (
    <section id="author" className="scroll-mt-20 border-t border-border bg-surface-1">
      <div className="mx-auto w-full max-w-4xl px-6 py-24">
        <SectionHeader label={t("label")} title={t("title")} subtitle={t("body")} />

        <div className="mt-12 grid gap-4 sm:grid-cols-2">
          <Card>
            <CardHeader>
              <div className="mb-2 flex size-10 items-center justify-center rounded-md border border-border bg-surface-2 text-primary">
                <Building2 className="size-5" />
              </div>
              <CardTitle>{t("org")}</CardTitle>
              <CardDescription>{t("orgTagline")}</CardDescription>
            </CardHeader>
            <CardContent>
              <Button asChild variant="secondary" size="sm">
                <a href={SITE.repo} target="_blank" rel="noopener noreferrer">
                  <GithubIcon /> {t("viewRepo")}
                </a>
              </Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <div className="mb-2 flex size-10 items-center justify-center rounded-md border border-border bg-surface-2 text-primary">
                <User className="size-5" />
              </div>
              <CardTitle>{t("authorName")}</CardTitle>
              <CardDescription>{t("authorRole")}</CardDescription>
            </CardHeader>
            <CardContent>
              <Button asChild variant="secondary" size="sm">
                <a href={SITE.author.github} target="_blank" rel="noopener noreferrer">
                  <GithubIcon /> {t("viewProfile")}
                </a>
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    </section>
  );
}

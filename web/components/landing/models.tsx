import { useTranslations } from "next-intl";
import { SectionHeader } from "./section-header";

type Row = { stage: string; options: string; notes: string };

export function Models() {
  const t = useTranslations("Models");
  const rows = t.raw("rows") as Row[];

  return (
    <section id="models" className="scroll-mt-20">
      <div className="mx-auto w-full max-w-6xl px-6 py-24">
        <SectionHeader
          label={t("label")}
          title={t("title")}
          subtitle={t("subtitle")}
        />
        <div className="mt-14 overflow-x-auto rounded-md border border-border">
          <table className="w-full min-w-[40rem] border-collapse text-left text-sm">
            <thead>
              <tr className="border-b border-border bg-surface-1">
                <th className="type-label px-5 py-3 text-muted-foreground">
                  {t("colStage")}
                </th>
                <th className="type-label px-5 py-3 text-muted-foreground">
                  {t("colOptions")}
                </th>
                <th className="type-label px-5 py-3 text-muted-foreground">
                  {t("colNotes")}
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, i) => (
                <tr
                  key={row.stage}
                  className={i > 0 ? "border-t border-border" : undefined}
                >
                  <td className="px-5 py-4 font-medium text-foreground">
                    {row.stage}
                  </td>
                  <td className="type-code px-5 py-4 text-muted-foreground">
                    {row.options}
                  </td>
                  <td className="px-5 py-4 text-muted-foreground">{row.notes}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}

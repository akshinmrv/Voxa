import { cn } from "@/lib/utils";

/** Consistent section heading: tracked label + H2 title + optional subtitle. */
export function SectionHeader({
  label,
  title,
  subtitle,
  align = "center",
  className,
}: {
  label: string;
  title: string;
  subtitle?: string;
  align?: "center" | "left";
  className?: string;
}) {
  return (
    <div
      className={cn(
        "max-w-2xl",
        align === "center" && "mx-auto text-center",
        className,
      )}
    >
      <p className="type-label text-primary">{label}</p>
      <h2 className="type-h1 mt-3 text-balance">{title}</h2>
      {subtitle && (
        <p className="type-body mt-3 text-pretty text-muted-foreground">
          {subtitle}
        </p>
      )}
    </div>
  );
}

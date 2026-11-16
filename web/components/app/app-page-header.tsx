/**
 * What a page is for, in a line under the header. The page's name is the header's title
 * (components/shell/header.tsx), so it isn't repeated here.
 */
export function AppPageHeader({ subtitle }: { subtitle?: string }) {
  if (!subtitle) return null;
  return <p className="mb-6 text-ui-body text-muted-foreground">{subtitle}</p>;
}

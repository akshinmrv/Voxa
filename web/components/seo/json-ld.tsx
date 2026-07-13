/**
 * Renders a JSON-LD structured-data script. Content is our own (not user input),
 * so serializing it into the tag is safe.
 */
export function JsonLd({ data }: { data: object }) {
  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(data) }}
    />
  );
}

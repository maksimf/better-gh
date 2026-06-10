export function PreviewLink({ url }: { url: string | null }) {
  if (!url) {
    return <span className="preview preview--pending">preview is pending</span>;
  }

  return (
    <a
      className="preview preview--live"
      href={url}
      target="_blank"
      rel="noopener"
    >
      preview &uarr;
    </a>
  );
}

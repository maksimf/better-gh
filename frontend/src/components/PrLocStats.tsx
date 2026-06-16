export function PrLocStats({
  additions,
  deletions,
}: {
  additions: number;
  deletions: number;
}) {
  if (additions === 0 && deletions === 0) {
    return null;
  }

  return (
    <span className="pr-loc" aria-label={`${additions} additions, ${deletions} deletions`}>
      <span className="pr-loc-add">+{additions}</span>
      {" "}
      <span className="pr-loc-del">-{deletions}</span>
    </span>
  );
}

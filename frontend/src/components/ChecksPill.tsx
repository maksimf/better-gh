import type { Checks } from "../api/types";

function ChecksCell({
  value,
  modifier,
  names,
}: {
  value: number;
  modifier: "pass" | "pending" | "fail";
  names?: { name: string }[];
}) {
  const cls = value === 0 ? "checks-cell--zero" : `checks-cell--${modifier}`;
  if (modifier === "fail" && value > 0 && names && names.length > 0) {
    const title = `Failed checks: ${names.map((n) => n.name).join(", ")}`;
    return (
      <span className={`checks-cell ${cls}`} title={title}>
        {value}
      </span>
    );
  }
  return <span className={`checks-cell ${cls}`}>{value}</span>;
}

export function ChecksPill({ checks }: { checks: Checks }) {
  return (
    <span className="checks" title="Checks: passed / pending / failed">
      <span className="checks-label">Checks</span>
      <ChecksCell value={checks.passed} modifier="pass" />
      <ChecksCell value={checks.pending} modifier="pending" />
      <ChecksCell value={checks.failed} modifier="fail" names={checks.failed_names} />
    </span>
  );
}

export function Conflicts({ conflicts }: { conflicts: number }) {
  if (conflicts <= 0) return null;
  return (
    <span className="conflicts" title="Merge conflicts with target branch">
      <span className="conflicts-bang">!</span>
      <span>
        {conflicts} {conflicts === 1 ? "conflict" : "conflicts"}
      </span>
    </span>
  );
}

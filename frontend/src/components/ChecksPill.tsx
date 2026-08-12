import type { Checks } from "../api/types";
import { MetricCell, MetricPill } from "../ui/MetricPill";

export function ChecksPill({ checks }: { checks: Checks }) {
  return (
    <MetricPill label="Checks" title="Checks: passed / pending / failed">
      <MetricCell
        family="checks"
        tone={checks.passed === 0 ? "zero" : "pass"}
        value={checks.passed}
      />
      <MetricCell
        family="checks"
        tone={checks.pending === 0 ? "zero" : "pending"}
        value={checks.pending}
      />
      <MetricCell
        family="checks"
        tone={checks.failed === 0 ? "zero" : "fail"}
        value={checks.failed}
        title={
          checks.failed > 0 && checks.failed_names.length > 0
            ? `Failed checks: ${checks.failed_names.map((n) => n.name).join(", ")}`
            : undefined
        }
      />
    </MetricPill>
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

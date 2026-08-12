import type { Meta, StoryObj } from "@storybook/react-vite";

import { Tag } from "./Tag";
import { Chip } from "./Chip";
import { MetricCell, MetricPill } from "./MetricPill";
import { CheckIcon } from "../components/icons";

const meta = {
  title: "UI/Badges",
  parameters: { layout: "centered" },
} satisfies Meta;

export default meta;
type Story = StoryObj<typeof meta>;

export const DraftTag: Story = {
  render: () => <Tag variant="draft">Draft</Tag>,
};

export const Chips: Story = {
  render: () => (
    <div className="reviewer-chips" style={{ display: "flex", gap: 8 }}>
      <Chip
        variant="approved"
        initial="A"
        title="@alice approved"
        checks={<CheckIcon />}
      />
      <Chip variant="review" initial="B" title="@bob review requested" />
      <Chip
        variant="pending"
        initial="C"
        title="Request review from @carol"
        onClick={() => undefined}
      />
      <Chip
        variant="pending"
        initial="D"
        error
        title="Failed to request"
        onClick={() => undefined}
      />
    </div>
  ),
};

export const ChecksMetrics: Story = {
  render: () => (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <MetricPill label="Checks" title="Checks: passed / pending / failed">
        <MetricCell family="checks" tone="pass" value={12} />
        <MetricCell family="checks" tone="zero" value={0} />
        <MetricCell family="checks" tone="zero" value={0} />
      </MetricPill>
      <MetricPill label="Checks">
        <MetricCell family="checks" tone="pass" value={8} />
        <MetricCell family="checks" tone="pending" value={3} />
        <MetricCell family="checks" tone="zero" value={0} />
      </MetricPill>
      <MetricPill label="Checks">
        <MetricCell family="checks" tone="pass" value={9} />
        <MetricCell family="checks" tone="zero" value={0} />
        <MetricCell
          family="checks"
          tone="fail"
          value={2}
          title="Failed checks: ci / test, lint"
        />
      </MetricPill>
      <MetricPill label="Comments" className="comments" title="Comments">
        <MetricCell family="comments" tone="human" as="button" onClick={() => undefined}>
          H 3
        </MetricCell>
        <MetricCell family="comments" tone="bot">
          B 2
        </MetricCell>
      </MetricPill>
    </div>
  ),
};

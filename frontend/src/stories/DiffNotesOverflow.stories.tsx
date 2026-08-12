import type { Meta, StoryObj } from "@storybook/react-vite";

import { DiffPanel } from "../components/DiffPanel";
import { ReviewRow } from "../components/ReviewRow";
import { HumanCommentsPopover } from "../components/HumanCommentsPopover";
import { NotesDrawer } from "../components/NotesDrawer";
import { OverflowMenu } from "../components/OverflowMenu";
import { CloudAgentLink } from "../components/CloudAgentLink";
import { reviewPr } from "./fixtures";
import { useState } from "react";

const meta = {
  title: "Components/DiffNotesOverflow",
} satisfies Meta;

export default meta;
type Story = StoryObj<typeof meta>;

export const Diff: Story = {
  render: () => (
    <div style={{ height: 560 }}>
      <DiffPanel
        owner="acme"
        repo="app"
        number={128}
        title="Add Storybook catalog for dashboard UI"
        url="https://github.com/acme/app/pull/128"
        author="maxfilippov"
        onClose={() => undefined}
      />
    </div>
  ),
};

export const ReviewRowDefault: Story = {
  render: () => (
    <ReviewRow
      pr={reviewPr}
      now={Date.now()}
      reviewedHas={() => false}
      onToggleReviewed={() => undefined}
      deferredHas={() => false}
      onToggleDeferred={() => undefined}
      selected={false}
      onSelect={() => undefined}
    />
  ),
};

export const CommentsPopover: Story = {
  render: () => (
    <div style={{ position: "relative", minHeight: 240 }}>
      <HumanCommentsPopover owner="acme" repo="app" number={128} />
    </div>
  ),
  parameters: { layout: "centered" },
};

export const Notes: Story = {
  render: () => {
    const [open, setOpen] = useState(true);
    return (
      <div style={{ minHeight: 320 }}>
        <NotesDrawer
          open={open}
          onOpen={() => setOpen(true)}
          onClose={() => setOpen(false)}
        />
      </div>
    );
  },
};

export const Overflow: Story = {
  render: () => (
    <OverflowMenu>
      <CloudAgentLink prKey="acme/app#128" repo="acme/app" number={128} />
    </OverflowMenu>
  ),
  parameters: { layout: "centered" },
};

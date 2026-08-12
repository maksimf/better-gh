import type { Meta, StoryObj } from "@storybook/react-vite";

import { ActionButton } from "./ActionButton";
import { CheckIcon } from "../components/icons";

const meta = {
  title: "UI/ActionButton",
  component: ActionButton,
  parameters: { layout: "centered" },
} satisfies Meta<typeof ActionButton>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Approve: Story = {
  args: {
    kind: "approve",
    children: (
      <>
        APPROVE{" "}
        <span aria-hidden="true">
          <CheckIcon />
        </span>
      </>
    ),
    onClick: () => undefined,
  },
};

export const Approved: Story = {
  args: {
    kind: "approve",
    done: true,
    children: (
      <>
        APPROVED{" "}
        <span aria-hidden="true">
          <CheckIcon />
        </span>
      </>
    ),
  },
};

export const Merge: Story = {
  args: {
    kind: "merge",
    children: "MERGE →",
    onClick: () => undefined,
  },
};

export const Merged: Story = {
  args: {
    kind: "merge",
    done: true,
    children: (
      <>
        MERGED{" "}
        <span aria-hidden="true">
          <CheckIcon />
        </span>
      </>
    ),
  },
};

export const Ready: Story = {
  args: {
    kind: "ready",
    children: "Mark ready →",
    onClick: () => undefined,
  },
};

export const BulkMerge: Story = {
  args: {
    kind: "bulk-merge",
    children: (
      <>
        MERGE ALL <span className="bulk-merge-count">3</span>
      </>
    ),
    onClick: () => undefined,
  },
};

export const ReviewRequest: Story = {
  args: {
    kind: "review-request",
    children: "REQUEST REVIEW",
    onClick: () => undefined,
  },
};

export const ErrorState: Story = {
  args: {
    kind: "approve",
    error: true,
    title: "Already reviewed",
    children: "APPROVE",
    onClick: () => undefined,
  },
};

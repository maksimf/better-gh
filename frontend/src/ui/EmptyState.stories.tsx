import type { Meta, StoryObj } from "@storybook/react-vite";

import { EmptyState } from "./EmptyState";

const meta = {
  title: "UI/EmptyState",
  component: EmptyState,
} satisfies Meta<typeof EmptyState>;

export default meta;
type Story = StoryObj<typeof meta>;

export const InboxZero: Story = {
  args: {
    title: "INBOX ZERO",
    subtitle: "No open pull requests. Go touch grass.",
  },
};

export const AllClear: Story = {
  args: {
    variant: "reviews",
    title: "ALL CLEAR",
    subtitle: "No PRs are waiting for your review.",
  },
};

export const Picker: Story = {
  args: {
    variant: "picker",
    title: "PICK YOUR REPOS",
    subtitle:
      "Select the repositories you want this board to track. Your choice stays in this browser.",
  },
  render: (args) => (
    <EmptyState {...args}>
      <div className="empty-state-picker-card">
        <p style={{ margin: 0 }}>Repo picker slot</p>
      </div>
    </EmptyState>
  ),
};

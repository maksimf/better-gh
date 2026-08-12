import type { Meta, StoryObj } from "@storybook/react-vite";

import { CardToggle } from "./CardToggle";
import { CheckIcon, EyeIcon, NoteIcon, PauseIcon } from "../components/icons";

const meta = {
  title: "UI/CardToggle",
  component: CardToggle,
  parameters: { layout: "centered" },
  decorators: [
    (Story) => (
      <div className="pr-toggles" style={{ display: "flex", gap: 8 }}>
        <Story />
      </div>
    ),
  ],
} satisfies Meta<typeof CardToggle>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Reviewed: Story = {
  args: {
    variant: "reviewed",
    pressed: false,
    title: "Mark as reviewed by you",
    onClick: () => undefined,
    icon: <CheckIcon />,
  },
};

export const ReviewedPressed: Story = {
  args: {
    ...Reviewed.args,
    pressed: true,
    title: "Reviewed by you -- click to unmark",
  },
};

export const Watch: Story = {
  args: {
    variant: "watch",
    pressed: false,
    title: "Watch — notify me when checks pass",
    onClick: () => undefined,
    icon: <EyeIcon />,
  },
};

export const WatchDisabled: Story = {
  args: {
    ...Watch.args,
    disabled: true,
    title: "set ntfy channel in settings",
  },
};

export const Note: Story = {
  args: {
    variant: "note",
    pressed: true,
    title: "Edit your personal note for this PR",
    onClick: () => undefined,
    icon: <NoteIcon />,
  },
};

export const Deferred: Story = {
  args: {
    variant: "deferred",
    pressed: false,
    title: "Defer — hide from the board for now",
    onClick: () => undefined,
    icon: <PauseIcon />,
  },
};

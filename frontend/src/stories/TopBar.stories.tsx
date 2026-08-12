import type { Meta, StoryObj } from "@storybook/react-vite";

import { TopBar } from "../components/TopBar";
import { ThemeToggle } from "../components/ThemeToggle";
import { meFixture } from "./fixtures";
import { storyQueryClient } from "../../.storybook/query-client";

const meta = {
  title: "Components/TopBar",
  component: TopBar,
  decorators: [
    (Story) => {
      storyQueryClient.setQueryData(["me"], meFixture);
      return <Story />;
    },
  ],
} satisfies Meta<typeof TopBar>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
  args: {
    onOpenSettings: () => undefined,
  },
};

export const ThemeToggleAlone: Story = {
  args: {
    onOpenSettings: () => undefined,
  },
  render: () => <ThemeToggle />,
  parameters: { layout: "centered" },
};

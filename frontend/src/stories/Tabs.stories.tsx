import type { Meta, StoryObj } from "@storybook/react-vite";
import { useState } from "react";

import { Tabs } from "../components/Tabs";
import type { TabName } from "../hooks/useActiveTab";

const meta = {
  title: "Components/Tabs",
  component: Tabs,
} satisfies Meta<typeof Tabs>;

export default meta;
type Story = StoryObj<typeof meta>;

export const MineActive: Story = {
  args: {
    active: "mine",
    mineCount: 5,
    reviewsCount: 2,
    onSelect: () => undefined,
  },
};

export const ReviewsActive: Story = {
  args: {
    active: "reviews",
    mineCount: 5,
    reviewsCount: 2,
    onSelect: () => undefined,
  },
};

export const Interactive: Story = {
  args: {
    active: "mine",
    mineCount: 5,
    reviewsCount: 2,
    onSelect: () => undefined,
  },
  render: () => {
    const [active, setActive] = useState<TabName>("mine");
    return (
      <Tabs
        active={active}
        mineCount={5}
        reviewsCount={2}
        onSelect={setActive}
      />
    );
  },
};

import type { Meta, StoryObj } from "@storybook/react-vite";
import { useState } from "react";

import { PrCard } from "../components/PrCard";
import {
  meFixture,
  prApproved,
  prDraft,
  prExternal,
  prFailing,
  prReady,
  prStacked,
} from "./fixtures";
import { storyQueryClient } from "../../.storybook/query-client";

function noop() {
  /* story noop */
}

const meta = {
  title: "Components/PrCard",
  component: PrCard,
  decorators: [
    (Story) => {
      storyQueryClient.setQueryData(["me"], meFixture);
      return (
        <div style={{ maxWidth: 720 }}>
          <Story />
        </div>
      );
    },
  ],
} satisfies Meta<typeof PrCard>;

export default meta;
type Story = StoryObj<typeof meta>;

const baseHandlers = {
  reviewedHas: () => false,
  onToggleReviewed: noop,
  deferredHas: () => false,
  onToggleDeferred: noop,
  watchedHas: () => false,
  onToggleWatch: noop,
  watchDisabled: false,
  selected: false,
  onSelect: noop,
};

export const Ready: Story = {
  args: { pr: prReady, ...baseHandlers },
};

export const Draft: Story = {
  args: { pr: prDraft, ...baseHandlers },
};

export const Approved: Story = {
  args: { pr: prApproved, ...baseHandlers },
};

export const FailingChecks: Story = {
  args: { pr: prFailing, ...baseHandlers },
};

export const Stacked: Story = {
  args: { pr: prStacked, ...baseHandlers },
};

export const ExternalAuthor: Story = {
  args: {
    pr: prExternal,
    ...baseHandlers,
  },
};

export const ReviewedWatchedDeferred: Story = {
  args: {
    pr: prReady,
    ...baseHandlers,
    reviewedHas: () => true,
    watchedHas: () => true,
    deferredHas: () => true,
  },
};

export const BulkSelected: Story = {
  args: {
    pr: prApproved,
    ...baseHandlers,
    bulkSelected: true,
    onToggleBulkSelected: noop,
  },
};

export const Selected: Story = {
  args: {
    pr: prReady,
    ...baseHandlers,
    selected: true,
  },
};

export const Interactive: Story = {
  args: {
    pr: prReady,
    ...baseHandlers,
  },
  render: () => {
    const [reviewed, setReviewed] = useState(false);
    const [watched, setWatched] = useState(false);
    const [deferred, setDeferred] = useState(false);
    const [selected, setSelected] = useState(false);
    return (
      <PrCard
        pr={prReady}
        reviewedHas={() => reviewed}
        onToggleReviewed={() => setReviewed((v) => !v)}
        deferredHas={() => deferred}
        onToggleDeferred={() => setDeferred((v) => !v)}
        watchedHas={() => watched}
        onToggleWatch={() => setWatched((v) => !v)}
        watchDisabled={false}
        selected={selected}
        onSelect={() => setSelected((v) => !v)}
      />
    );
  },
};

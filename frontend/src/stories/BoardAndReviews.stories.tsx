import type { Meta, StoryObj } from "@storybook/react-vite";
import { useState } from "react";

import { Board } from "../components/Board";
import { ReviewsList } from "../components/ReviewsList";
import { PickerEmptyState } from "../components/PickerEmptyState";
import {
  dashboardFixture,
  meFixture,
  prApproved,
  prDraft,
  prReady,
  prStackLeaf,
  prStackRoot,
  prStacked,
  repoSummaries,
  reviewPr,
  reviewPrDraft,
} from "./fixtures";
import { storyQueryClient } from "../../.storybook/query-client";

function alwaysFalse() {
  return false;
}

const meta = {
  title: "Components/BoardAndReviews",
  decorators: [
    (Story) => {
      storyQueryClient.setQueryData(["me"], meFixture);
      storyQueryClient.setQueryData(["dashboard", null], dashboardFixture);
      return <Story />;
    },
  ],
} satisfies Meta;

export default meta;
type Story = StoryObj<typeof meta>;

export const BoardPopulated: Story = {
  render: () => (
    <Board
      prs={[prDraft, prReady, prApproved]}
      deferredPrs={[]}
      reviewedHas={alwaysFalse}
      onToggleReviewed={() => undefined}
      deferredHas={alwaysFalse}
      onToggleDeferred={() => undefined}
      watchedHas={alwaysFalse}
      onToggleWatch={() => undefined}
      watchDisabled={false}
    />
  ),
};

export const BoardWithStacks: Story = {
  render: () => (
    <Board
      prs={[
        prDraft,
        prReady,
        prApproved,
        prStackRoot,
        prStacked,
        prStackLeaf,
      ]}
      deferredPrs={[]}
      reviewedHas={alwaysFalse}
      onToggleReviewed={() => undefined}
      deferredHas={alwaysFalse}
      onToggleDeferred={() => undefined}
      watchedHas={alwaysFalse}
      onToggleWatch={() => undefined}
      watchDisabled={false}
    />
  ),
};

export const BoardEmpty: Story = {
  render: () => (
    <Board
      prs={[]}
      deferredPrs={[]}
      reviewedHas={alwaysFalse}
      onToggleReviewed={() => undefined}
      deferredHas={alwaysFalse}
      onToggleDeferred={() => undefined}
      watchedHas={alwaysFalse}
      onToggleWatch={() => undefined}
      watchDisabled={false}
    />
  ),
};

export const ReviewsPopulated: Story = {
  render: () => (
    <ReviewsList
      reviews={[reviewPr, reviewPrDraft]}
      deferredReviews={[]}
      reviewedHas={alwaysFalse}
      onToggleReviewed={() => undefined}
      deferredHas={alwaysFalse}
      onToggleDeferred={() => undefined}
    />
  ),
};

export const ReviewsEmpty: Story = {
  render: () => (
    <ReviewsList
      reviews={[]}
      deferredReviews={[]}
      reviewedHas={alwaysFalse}
      onToggleReviewed={() => undefined}
      deferredHas={alwaysFalse}
      onToggleDeferred={() => undefined}
    />
  ),
};

export const PickerEmpty: Story = {
  render: () => {
    const [selected, setSelected] = useState<Set<string>>(new Set());
    return (
      <PickerEmptyState
        repos={repoSummaries}
        has={(repo) => selected.has(repo)}
        onToggle={(repo, checked) => {
          setSelected((prev) => {
            const next = new Set(prev);
            if (checked) next.add(repo);
            else next.delete(repo);
            return next;
          });
        }}
      />
    );
  },
};

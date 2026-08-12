import type { Meta, StoryObj } from "@storybook/react-vite";

import { ChecksPill, Conflicts } from "../components/ChecksPill";
import { CommentsPill } from "../components/CommentsPill";
import {
  NotifyReviewerAction,
  RequestReviewAction,
  ReviewerChips,
} from "../components/ReviewerChip";
import {
  checksFail,
  checksPass,
  checksPending,
  checksZero,
  reviewersApproved,
  reviewersMixed,
  reviewersPending,
} from "./fixtures";

const meta = {
  title: "Components/PillsAndChips",
  parameters: { layout: "centered" },
} satisfies Meta;

export default meta;
type Story = StoryObj<typeof meta>;

export const ChecksPass: Story = {
  render: () => <ChecksPill checks={checksPass} />,
};

export const ChecksPending: Story = {
  render: () => <ChecksPill checks={checksPending} />,
};

export const ChecksFail: Story = {
  render: () => <ChecksPill checks={checksFail} />,
};

export const ChecksEmpty: Story = {
  render: () => <ChecksPill checks={checksZero} />,
};

export const ConflictsBadge: Story = {
  render: () => <Conflicts conflicts={2} />,
};

export const Comments: Story = {
  render: () => (
    <CommentsPill
      human={3}
      bot={2}
      prRef={{ owner: "acme", repo: "app", number: 128 }}
    />
  ),
};

export const ReviewerStrip: Story = {
  render: () => (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <ReviewerChips
        reviewers={reviewersApproved}
        owner="acme"
        repo="app"
        number={128}
      />
      <ReviewerChips
        reviewers={reviewersMixed}
        owner="acme"
        repo="app"
        number={128}
      />
      <ReviewerChips
        reviewers={reviewersPending}
        owner="acme"
        repo="app"
        number={128}
      />
    </div>
  ),
};

export const RequestReview: Story = {
  render: () => (
    <RequestReviewAction
      reviewers={reviewersPending}
      owner="acme"
      repo="app"
      number={128}
    />
  ),
};

export const NotifyReviewer: Story = {
  render: () => (
    <NotifyReviewerAction
      reviewers={reviewersPending}
      owner="acme"
      repo="app"
      number={128}
    />
  ),
};

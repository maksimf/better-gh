import type { Meta, StoryObj } from "@storybook/react-vite";
import { useState } from "react";

import { ApproveButton } from "../components/ApproveButton";
import { MergeButton } from "../components/MergeButton";
import { DraftButton } from "../components/DraftButton";
import { BulkMergeButton } from "../components/BulkMergeButton";
import { MergeModal } from "../components/MergeModal";
import { NoteModal } from "../components/NoteModal";
import { SettingsModal } from "../components/SettingsModal";
import { CloudAgentModal } from "../components/CloudAgentModal";
import { ReviewActions } from "../components/ReviewActions";
import { prApproved, repoSummaries } from "./fixtures";
import { failingMutationHandlers } from "./mocks/handlers";

const meta = {
  title: "Components/ActionsAndModals",
  parameters: { layout: "centered" },
} satisfies Meta;

export default meta;
type Story = StoryObj<typeof meta>;

export const Approve: Story = {
  render: () => <ApproveButton owner="acme" repo="app" number={55} />,
};

export const Merge: Story = {
  render: () => (
    <MergeButton
      owner="acme"
      repo="app"
      number={142}
      title="Ship merge modal Linear shortcut"
      linearUrl="https://linear.app/acme/issue/ENG-142"
    />
  ),
};

export const MarkReady: Story = {
  render: () => <DraftButton owner="acme" repo="app" number={101} />,
};

export const BulkMerge: Story = {
  render: () => (
    <BulkMergeButton prs={[prApproved]} onMerged={() => undefined} />
  ),
};

export const MergeModalOpen: Story = {
  render: () => {
    const [open, setOpen] = useState(true);
    return (
      <MergeModal
        open={open}
        title="Ship merge modal Linear shortcut"
        number={142}
        linearTicket="ENG-142"
        pending={false}
        onJustMerge={() => setOpen(false)}
        onMergeAndLinear={() => setOpen(false)}
        onClose={() => setOpen(false)}
      />
    );
  },
};

export const NoteModalOpen: Story = {
  render: () => {
    const [open, setOpen] = useState(true);
    return (
      <NoteModal
        open={open}
        number={128}
        initialNote="Check dark theme coverage"
        onSave={() => setOpen(false)}
        onClose={() => setOpen(false)}
      />
    );
  },
};

export const SettingsOpen: Story = {
  render: () => {
    const [open, setOpen] = useState(true);
    const [reviewers, setReviewers] = useState(["alice", "bob"]);
    return (
      <SettingsModal
        open={open}
        onClose={() => setOpen(false)}
        repos={repoSummaries}
        has={() => true}
        onToggleRepo={() => undefined}
        reviewers={reviewers}
        onReviewersChange={setReviewers}
        ntfyChannel="better-gh-demo"
        onNtfyChannelChange={() => undefined}
      />
    );
  },
  parameters: { layout: "padded" },
};

export const QaAgentModal: Story = {
  render: () => {
    const [open, setOpen] = useState(true);
    return (
      <CloudAgentModal
        open={open}
        number={128}
        pending={false}
        error={null}
        onLaunch={() => setOpen(false)}
        onClose={() => setOpen(false)}
      />
    );
  },
};

export const ReviewActionBar: Story = {
  render: () => (
    <div style={{ width: 420 }}>
      <ReviewActions owner="acme" repo="app" number={55} isOwnPr={false} />
    </div>
  ),
};

export const ApproveError: Story = {
  render: () => <ApproveButton owner="acme" repo="app" number={55} />,
  beforeEach: ({ msw }) => {
    msw.use(...failingMutationHandlers);
  },
};

import type { Meta, StoryObj } from "@storybook/react-vite";

import { Button } from "./Button";

const meta = {
  title: "UI/Button",
  parameters: { layout: "centered" },
} satisfies Meta;

export default meta;
type Story = StoryObj<typeof meta>;

export const ChromeSettings: Story = {
  render: () => (
    <Button surface="chrome" variant="settings" onClick={() => undefined}>
      SETTINGS
    </Button>
  ),
};

export const ChromeRefresh: Story = {
  render: () => (
    <Button surface="chrome" variant="refresh" onClick={() => undefined}>
      REFRESH
    </Button>
  ),
};

export const ChromeSignout: Story = {
  render: () => (
    <Button surface="chrome" variant="signout" onClick={() => undefined}>
      SIGN OUT
    </Button>
  ),
};

export const ModalMerge: Story = {
  render: () => (
    <div style={{ display: "flex", gap: 8 }}>
      <Button surface="modal" modal="merge" variant="ghost" onClick={() => undefined}>
        Cancel
      </Button>
      <Button surface="modal" modal="merge" variant="merge" onClick={() => undefined}>
        Just merge
      </Button>
      <Button surface="modal" modal="merge" variant="linear" onClick={() => undefined}>
        Merge &amp; mark ENG-1 done
      </Button>
    </div>
  ),
};

export const ReviewActions: Story = {
  render: () => (
    <div style={{ display: "flex", gap: 8 }}>
      <Button surface="review" variant="changes" onClick={() => undefined}>
        REQUEST CHANGES
      </Button>
      <Button surface="review" variant="comment" onClick={() => undefined}>
        COMMENT
      </Button>
    </div>
  ),
};

export const HcpActions: Story = {
  render: () => (
    <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
      <Button surface="hcp" variant="ack" onClick={() => undefined}>
        ACK
      </Button>
      <Button surface="hcp" variant="reply" onClick={() => undefined}>
        REPLY
      </Button>
      <Button surface="hcp" variant="submit" onClick={() => undefined}>
        SEND
      </Button>
      <Button surface="hcp" variant="cancel" onClick={() => undefined}>
        CANCEL
      </Button>
    </div>
  ),
};

export const DiffToggle: Story = {
  render: () => (
    <Button
      surface="toggle"
      variant="diff"
      active
      onClick={() => undefined}
    >
      DIFF
    </Button>
  ),
};

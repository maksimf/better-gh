import type { Meta, StoryObj } from "@storybook/react-vite";

import { Loader } from "../components/Loader";
import { ErrorBanner } from "../components/ErrorBanner";
import { FooterMeta } from "../components/FooterMeta";
import { PageTitleRow } from "../components/PageTitleRow";
import { Column } from "../components/Column";
import { DeferredSection } from "../components/DeferredSection";
import { BrandMark, CheckIcon, EyeIcon, NoteIcon, PauseIcon, EllipsisIcon } from "../components/icons";

const meta = {
  title: "Components/Chrome",
} satisfies Meta;

export default meta;
type Story = StoryObj<typeof meta>;

export const PageLoader: Story = {
  render: () => <Loader />,
};

export const ErrorWithReset: Story = {
  render: () => (
    <ErrorBanner
      error={{
        message: "GitHub rate limit exceeded",
        reset_at: new Date(Date.now() + 15 * 60_000).toISOString(),
      }}
    />
  ),
};

export const ErrorPlain: Story = {
  render: () => (
    <ErrorBanner error={{ message: "Failed to poll dashboard", reset_at: null }} />
  ),
};

export const Footer: Story = {
  render: () => <FooterMeta lastPolledAt="2026-08-12T12:05:00Z" />,
};

export const PageTitle: Story = {
  render: () => <PageTitleRow title="MY PULL REQUESTS" />,
};

export const BoardColumn: Story = {
  render: () => (
    <Column column="ready" count={2} hidden={false}>
      <div className="pr-card">
        <div className="pr-card-body">
          <p style={{ margin: 12 }}>Sample card slot</p>
        </div>
      </div>
    </Column>
  ),
};

export const Deferred: Story = {
  render: () => (
    <DeferredSection count={1}>
      <div className="pr-card">
        <div className="pr-card-body">
          <p style={{ margin: 12 }}>Deferred PR slot</p>
        </div>
      </div>
    </DeferredSection>
  ),
};

export const Icons: Story = {
  render: () => (
    <div style={{ display: "flex", gap: 16, alignItems: "center" }}>
      <BrandMark />
      <BrandMark large />
      <CheckIcon />
      <EyeIcon />
      <NoteIcon />
      <PauseIcon />
      <EllipsisIcon />
    </div>
  ),
  parameters: { layout: "centered" },
};

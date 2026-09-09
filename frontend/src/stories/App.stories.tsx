import type { Decorator, Meta, StoryObj } from "@storybook/react-vite";
import { delay, http, HttpResponse } from "msw";

import { App } from "../App";
import type { Dashboard } from "../api/types";
import { storyQueryClient } from "../../.storybook/query-client";
import {
  dashboardEmptyFixture,
  dashboardFixture,
  dashboardRateLimitedFixture,
  meFixture,
} from "./fixtures";
import { seedAppStoryState } from "./seedPrefs";

function withAppState(options?: {
  dashboard?: Dashboard | null;
  prefs?: Record<string, unknown>;
  tab?: "mine" | "reviews";
}): Decorator {
  return (Story) => {
    const prefs = seedAppStoryState(options);
    storyQueryClient.setQueryData(["me"], meFixture);
    storyQueryClient.setQueryData(["prefs"], prefs);
    if (options?.dashboard !== null) {
      storyQueryClient.setQueryData(
        ["dashboard", null],
        options?.dashboard ?? dashboardFixture,
      );
    }
    return (
      <div style={{ minHeight: "100vh" }}>
        <Story />
      </div>
    );
  };
}

const meta = {
  title: "App",
  component: App,
  parameters: { layout: "fullscreen" },
} satisfies Meta<typeof App>;

export default meta;
type Story = StoryObj<typeof meta>;

export const PopulatedBoard: Story = {
  name: "My PRs — all states",
  decorators: [withAppState()],
};

export const Reviewing: Story = {
  name: "Reviewing — all states",
  decorators: [withAppState({ tab: "reviews" })],
};

export const Loading: Story = {
  decorators: [withAppState({ dashboard: null })],
  parameters: {
    msw: [
      http.get("/api/dashboard", async () => {
        await delay("infinite");
        return HttpResponse.json(dashboardFixture);
      }),
    ],
  },
};

export const PickRepos: Story = {
  decorators: [
    withAppState({
      prefs: { "better-gh.selected-repos": [] },
    }),
  ],
};

export const InboxZero: Story = {
  decorators: [withAppState({ dashboard: dashboardEmptyFixture })],
};

export const RateLimited: Story = {
  name: "Rate-limited banner",
  decorators: [withAppState({ dashboard: dashboardRateLimitedFixture })],
};

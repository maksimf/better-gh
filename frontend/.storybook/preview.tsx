import type { Preview } from "@storybook/react-vite";
import { QueryClientProvider } from "@tanstack/react-query";
import { withThemeByDataAttribute } from "@storybook/addon-themes";
import { setupWorker } from "msw/browser";
import { mswLoader } from "msw-storybook-addon/csf3";

import "../styles.css";
import { handlers } from "../src/stories/mocks/handlers";
import { storyQueryClient } from "./query-client";

const preview: Preview = {
  loaders: [
    mswLoader(async () => {
      const worker = setupWorker(...handlers);
      await worker.start({ onUnhandledRequest: "bypass" });
      return worker;
    }),
  ],
  beforeEach: () => {
    storyQueryClient.clear();
  },
  decorators: [
    (Story) => (
      <QueryClientProvider client={storyQueryClient}>
        <Story />
      </QueryClientProvider>
    ),
    withThemeByDataAttribute({
      themes: {
        light: "light",
        dark: "dark",
      },
      defaultTheme: "light",
      attributeName: "data-theme",
    }),
  ],
  parameters: {
    controls: {
      matchers: {
        color: /(background|color)$/i,
        date: /Date$/i,
      },
    },
    layout: "padded",
  },
};

export default preview;

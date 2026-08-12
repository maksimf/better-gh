import type { StorybookConfig } from "@storybook/react-vite";

const config = {
  framework: "@storybook/react-vite",
  stories: ["../src/**/*.stories.@(ts|tsx)", "../src/**/*.mdx"],
  addons: [
    "@storybook/addon-docs",
    "@storybook/addon-a11y",
    "@storybook/addon-themes",
    "msw-storybook-addon",
  ],
  staticDirs: ["../public"],
} satisfies StorybookConfig;

export default config;

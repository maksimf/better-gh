import type { Meta, StoryObj } from "@storybook/react-vite";

/**
 * Full-page mirror of frontend/login.html so the static auth screen can be
 * reviewed in Storybook light/dark themes without changing the production
 * FastAPI-served HTML.
 */
function LoginPage() {
  return (
    <div className="auth-page" style={{ minHeight: "100vh" }}>
      <main className="auth-card">
        <span className="brand-mark brand-mark--large" aria-hidden="true">
          <span className="shape shape--circle" />
          <span className="shape shape--square" />
          <span className="shape shape--triangle" />
        </span>
        <h1 className="brand-title auth-title">
          BETTER<span className="slash">//</span>GH
        </h1>
        <p className="auth-tagline">
          A clearer, calmer view of your open pull requests.
        </p>

        <a className="btn btn--signin" href="/auth/start">
          <svg
            className="signin-icon"
            viewBox="0 0 24 24"
            aria-hidden="true"
            focusable="false"
          >
            <path
              fill="currentColor"
              d="M12 .5C5.65.5.5 5.65.5 12c0 5.08 3.29 9.39 7.86 10.91.58.11.79-.25.79-.55 0-.27-.01-1.17-.02-2.12-3.2.69-3.88-1.36-3.88-1.36-.52-1.32-1.27-1.68-1.27-1.68-1.04-.71.08-.7.08-.7 1.15.08 1.76 1.18 1.76 1.18 1.02 1.75 2.69 1.25 3.35.95.1-.74.4-1.25.73-1.54-2.55-.29-5.24-1.28-5.24-5.69 0-1.26.45-2.29 1.18-3.1-.12-.29-.51-1.46.11-3.04 0 0 .97-.31 3.18 1.18.92-.26 1.92-.39 2.9-.4.98.01 1.98.14 2.91.4 2.2-1.49 3.17-1.18 3.17-1.18.63 1.58.23 2.75.11 3.04.74.81 1.18 1.84 1.18 3.1 0 4.42-2.69 5.39-5.26 5.68.41.36.77 1.05.77 2.12 0 1.53-.01 2.76-.01 3.13 0 .3.21.66.8.55C20.21 21.39 23.5 17.08 23.5 12 23.5 5.65 18.35.5 12 .5Z"
            />
          </svg>
          SIGN IN WITH GITHUB
        </a>

        <p className="auth-scopes">
          Requests <code>repo</code> + <code>read:org</code>. Your token is
          signed into an HttpOnly cookie; nothing is stored server-side.
        </p>
      </main>

      <footer className="auth-footer">
        <a
          href="https://github.com/settings/applications"
          target="_blank"
          rel="noopener"
        >
          Manage app permissions on GitHub &rsaquo;
        </a>
      </footer>
    </div>
  );
}

const meta = {
  title: "Pages/Login",
  component: LoginPage,
  parameters: {
    layout: "fullscreen",
  },
} satisfies Meta<typeof LoginPage>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {};

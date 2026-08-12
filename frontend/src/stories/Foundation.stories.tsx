import type { Meta, StoryObj } from "@storybook/react-vite";

const TOKENS = [
  ["--black", "Ink"],
  ["--yellow", "Accent yellow"],
  ["--red", "Accent red"],
  ["--blue", "Accent blue"],
  ["--bg", "Background"],
  ["--fg", "Foreground"],
  ["--muted", "Muted"],
  ["--border", "Border"],
  ["--card", "Card"],
  ["--surface", "Surface"],
] as const;

function Foundation() {
  return (
    <div style={{ display: "grid", gap: 24 }}>
      <section>
        <h2 className="page-title">Theme tokens</h2>
        <p className="empty-state-sub">
          Toggle light/dark in the Storybook toolbar. Tokens come from{" "}
          <code>styles.css</code> via <code>data-theme</code>.
        </p>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))",
            gap: 12,
            marginTop: 16,
          }}
        >
          {TOKENS.map(([token, label]) => (
            <div
              key={token}
              style={{
                border: "1px solid var(--border, #ccc)",
                borderRadius: 8,
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  height: 64,
                  background: `var(${token})`,
                }}
              />
              <div style={{ padding: 8, fontSize: 12 }}>
                <div>{label}</div>
                <code>{token}</code>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section>
        <h2 className="page-title">Typography</h2>
        <h1 className="brand-title">
          BETTER<span className="slash">//</span>GH
        </h1>
        <h2 className="empty-state-title">INBOX ZERO</h2>
        <p className="empty-state-sub">Body / muted supporting copy.</p>
        <button type="button" className="btn btn--settings">
          SETTINGS
        </button>
      </section>
    </div>
  );
}

const meta = {
  title: "Foundation/Theme",
  component: Foundation,
} satisfies Meta<typeof Foundation>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Tokens: Story = {};

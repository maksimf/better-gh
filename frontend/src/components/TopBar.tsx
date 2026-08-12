import { useMe } from "../api/queries";
import { Button } from "../ui/Button";
import { BrandMark } from "./icons";
import { ThemeToggle } from "./ThemeToggle";

export function TopBar({ onOpenSettings }: { onOpenSettings: () => void }) {
  const me = useMe();
  const login = me.data?.login;

  return (
    <header className="topbar">
      <div className="brand">
        <BrandMark />
        <h1 className="brand-title">
          BETTER<span className="slash">//</span>GH
        </h1>
      </div>
      <div className="topbar-actions">
        <span className="me" aria-live="polite">
          {me.data?.avatar_url && (
            <img
              className="me-avatar"
              src={me.data.avatar_url}
              alt={`@${login} avatar`}
              width={22}
              height={22}
            />
          )}
          <span>{login ? `@${login}` : "@\u2026"}</span>
        </span>
        <ThemeToggle />
        <Button
          surface="chrome"
          variant="settings"
          ariaLabel="Open settings"
          onClick={onOpenSettings}
        >
          SETTINGS
        </Button>
        <form method="post" action="/logout" className="signout-form">
          <Button surface="chrome" variant="signout" type="submit" title="Sign out">
            SIGN OUT
          </Button>
        </form>
      </div>
    </header>
  );
}

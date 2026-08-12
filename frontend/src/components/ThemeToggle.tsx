import { useTheme } from "../hooks/useTheme";
import { Button } from "../ui/Button";

export function ThemeToggle() {
  const { toggle } = useTheme();
  return (
    <Button
      surface="chrome"
      variant="theme"
      ariaLabel="Toggle dark mode (follows system by default)"
      title="Toggle dark mode (follows system by default)"
      onClick={toggle}
    >
      <svg
        className="theme-icon theme-icon--moon"
        viewBox="0 0 24 24"
        aria-hidden="true"
        focusable="false"
      >
        <path
          d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"
          fill="currentColor"
        />
      </svg>
      <svg
        className="theme-icon theme-icon--sun"
        viewBox="0 0 24 24"
        aria-hidden="true"
        focusable="false"
      >
        <circle cx="12" cy="12" r="4" fill="currentColor" />
        <g
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          fill="none"
        >
          <line x1="12" y1="2.5" x2="12" y2="5" />
          <line x1="12" y1="19" x2="12" y2="21.5" />
          <line x1="2.5" y1="12" x2="5" y2="12" />
          <line x1="19" y1="12" x2="21.5" y2="12" />
          <line x1="4.9" y1="4.9" x2="6.7" y2="6.7" />
          <line x1="17.3" y1="17.3" x2="19.1" y2="19.1" />
          <line x1="4.9" y1="19.1" x2="6.7" y2="17.3" />
          <line x1="17.3" y1="6.7" x2="19.1" y2="4.9" />
        </g>
      </svg>
    </Button>
  );
}

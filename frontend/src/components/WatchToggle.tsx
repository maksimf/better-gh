import { CardToggle } from "../ui/CardToggle";
import { EyeIcon } from "./icons";

export function WatchToggle({
  pressed,
  onToggle,
  disabled = false,
}: {
  pressed: boolean;
  onToggle: () => void;
  disabled?: boolean;
}) {
  const title = disabled
    ? "set ntfy channel in settings"
    : pressed
      ? "Watching — the server will ntfy you when checks pass and the preview is ready"
      : "Watch — notify me when checks pass and the preview is ready";
  return (
    <CardToggle
      variant="watch"
      pressed={pressed}
      disabled={disabled}
      title={title}
      onClick={onToggle}
      icon={<EyeIcon />}
    />
  );
}

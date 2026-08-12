import { CardToggle } from "../ui/CardToggle";
import { PauseIcon } from "./icons";

export function DeferredToggle({
  pressed,
  onToggle,
}: {
  pressed: boolean;
  onToggle: () => void;
}) {
  const title = pressed
    ? "Deferred — click to restore to the board"
    : "Defer — hide from the board for now";
  return (
    <CardToggle
      variant="deferred"
      pressed={pressed}
      title={title}
      onClick={onToggle}
      icon={<PauseIcon />}
    />
  );
}

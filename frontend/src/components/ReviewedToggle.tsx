import { CardToggle } from "../ui/CardToggle";
import { CheckIcon } from "./icons";

export function ReviewedToggle({
  pressed,
  onToggle,
}: {
  pressed: boolean;
  onToggle: () => void;
}) {
  const title = pressed
    ? "Reviewed by you -- click to unmark"
    : "Mark as reviewed by you";
  return (
    <CardToggle
      variant="reviewed"
      pressed={pressed}
      title={title}
      onClick={onToggle}
      icon={<CheckIcon />}
    />
  );
}

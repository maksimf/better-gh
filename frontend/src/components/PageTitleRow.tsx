import { useRefresh } from "../api/queries";
import { Button } from "../ui/Button";

export function PageTitleRow({ title }: { title: string }) {
  const refresh = useRefresh();
  return (
    <div className="page-title-row">
      <h2 className="page-title">{title}</h2>
      <Button
        surface="chrome"
        variant="refresh"
        disabled={refresh.isPending}
        onClick={() => refresh.mutate()}
      >
        REFRESH
      </Button>
    </div>
  );
}

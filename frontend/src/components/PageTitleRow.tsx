import { useRefresh } from "../api/queries";

export function PageTitleRow({ title }: { title: string }) {
  const refresh = useRefresh();
  return (
    <div className="page-title-row">
      <h2 className="page-title">{title}</h2>
      <button
        type="button"
        className="btn btn--refresh"
        disabled={refresh.isPending}
        onClick={() => refresh.mutate()}
      >
        REFRESH
      </button>
    </div>
  );
}

import { useState } from "react";

import { useCloudAgentStatus } from "../api/queries";
import type { CloudAgentStatus } from "../api/types";
import {
  cursorAgentUrl,
  parseCursorAgentId,
  useCloudAgents,
} from "../hooks/useCloudAgents";
import { CheckIcon } from "./icons";

/**
 * Per-PR "QA agent" control. With no agent linked it offers a button that
 * reveals a paste field; once a Cursor cloud-agent link is stored it shows
 * a live running/done badge (polled via /api/cloud-agent) plus a link to
 * the run. The link is kept in localStorage, keyed by the PR.
 */
export function CloudAgentLink({ prKey }: { prKey: string }) {
  const { get, set, remove } = useCloudAgents();
  const agentId = get(prKey);

  if (agentId) {
    return (
      <CloudAgentBadge agentId={agentId} onRemove={() => remove(prKey)} />
    );
  }

  return <CloudAgentAdder onAdd={(id) => set(prKey, id)} />;
}

function CloudAgentAdder({ onAdd }: { onAdd: (agentId: string) => void }) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState("");
  const [error, setError] = useState(false);

  function commit() {
    const id = parseCursorAgentId(value);
    if (!id) {
      setError(true);
      return;
    }
    onAdd(id);
    setValue("");
    setError(false);
    setEditing(false);
  }

  if (!editing) {
    return (
      <button
        type="button"
        className="cloud-agent-add"
        title="Link a Cursor cloud agent QAing this PR"
        onClick={() => setEditing(true)}
      >
        + QA agent
      </button>
    );
  }

  return (
    <span className={`cloud-agent-edit${error ? " is-error" : ""}`}>
      <input
        type="text"
        className="cloud-agent-input"
        // eslint-disable-next-line jsx-a11y/no-autofocus -- intentional: the
        // field only mounts on an explicit click, so focusing it is expected.
        autoFocus
        placeholder="Paste cursor.com/agents/ link"
        value={value}
        onChange={(e) => {
          setValue(e.target.value);
          if (error) setError(false);
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter") commit();
          else if (e.key === "Escape") setEditing(false);
        }}
      />
      <button
        type="button"
        className="cloud-agent-save"
        title="Save QA agent link"
        onClick={commit}
      >
        OK
      </button>
    </span>
  );
}

function CloudAgentBadge({
  agentId,
  onRemove,
}: {
  agentId: string;
  onRemove: () => void;
}) {
  const { data, isLoading } = useCloudAgentStatus(agentId);
  const href = data?.url ?? cursorAgentUrl(agentId);
  const view = describe(data, isLoading);

  return (
    <span className="cloud-agent-group">
      <a
        className={`cloud-agent-link cloud-agent-link--${view.tone}`}
        href={href}
        target="_blank"
        rel="noopener"
        title={view.title}
      >
        <span className="cloud-agent-dot" aria-hidden="true">
          {view.tone === "done" ? <CheckIcon /> : null}
        </span>
        {view.label}
      </a>
      <button
        type="button"
        className="cloud-agent-remove"
        title="Unlink QA agent"
        aria-label="Unlink QA agent"
        onClick={onRemove}
      >
        &times;
      </button>
    </span>
  );
}

type Tone = "running" | "done" | "error" | "muted";

function describe(
  data: CloudAgentStatus | undefined,
  isLoading: boolean,
): { tone: Tone; label: string; title: string } {
  if (!data && isLoading) {
    return { tone: "muted", label: "QA \u2026", title: "Checking QA agent\u2026" };
  }
  if (!data) {
    return { tone: "muted", label: "QA", title: "Open the QA agent run" };
  }
  if (data.configured === false) {
    return {
      tone: "muted",
      label: "QA",
      title:
        data.error ??
        "Server can't poll agent state (CURSOR_API_KEY unset) -- link still opens the run.",
    };
  }

  switch (data.state) {
    case "running":
      return {
        tone: "running",
        label: "QA running",
        title: `QA agent is running${data.status ? ` (${data.status})` : ""}`,
      };
    case "done": {
      const raw = (data.status ?? "").toUpperCase();
      if (raw === "ERROR" || raw === "FAILED") {
        return { tone: "error", label: "QA errored", title: "QA agent run errored" };
      }
      if (raw === "CANCELLED" || raw === "CANCELED") {
        return { tone: "muted", label: "QA cancelled", title: "QA agent run was cancelled" };
      }
      if (raw === "EXPIRED") {
        return { tone: "muted", label: "QA expired", title: "QA agent run expired" };
      }
      return { tone: "done", label: "QA done", title: "QA agent run finished" };
    }
    case "error":
      return {
        tone: "error",
        label: "QA ?",
        title: data.error ?? "Couldn't read QA agent state",
      };
    default:
      return { tone: "muted", label: "QA", title: "QA agent" };
  }
}

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { App } from "./App";

// Global react-query defaults. The key behaviours the rework asks for:
//   - refetchIntervalInBackground: false  -> most queries go quiet while
//     the tab is hidden. useDashboard opts back in on a 10-minute beat
//     so the browser-tab W/R/A counts stay current (Gmail-style).
//   - refetchOnWindowFocus: true          -> the moment the user returns
//     to the tab, the dashboard refetches so they never stare at stale data.
// The per-query refetchInterval (see useDashboard) drives the steady-state
// cadence while the tab is focused.
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchIntervalInBackground: false,
      refetchOnWindowFocus: true,
      retry: 1,
      staleTime: 30_000,
    },
  },
});

const rootEl = document.getElementById("root");
if (!rootEl) throw new Error("missing #root element");

createRoot(rootEl).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>,
);

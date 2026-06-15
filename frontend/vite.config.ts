import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The backend (FastAPI) owns auth, the JSON API, and mutation endpoints.
// In dev we run Vite on :5173 and proxy those paths through to uvicorn.
// Static assets (styles.css, favicons) are served from this directory so
// dev works even when :8000 is occupied. Override the backend URL when
// needed, e.g. BETTER_GH_BACKEND=http://localhost:8001 npm run dev
const BACKEND = process.env.BETTER_GH_BACKEND ?? "http://localhost:8000";
const PROXY_PATHS = [
  "/api",
  "/me",
  "/pulls",
  "/refresh",
  "/logout",
  "/auth",
  "/login",
];

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: Object.fromEntries(
      PROXY_PATHS.map((path) => [path, { target: BACKEND, changeOrigin: true }]),
    ),
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
});

import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The backend (FastAPI) owns auth, the JSON API, the mutation endpoints,
// and the shared static assets (styles.css / favicons / login.html). In
// dev we run Vite on :5173 and proxy those paths through to uvicorn on
// :8000 so the SPA behaves exactly like the built+served version.
const BACKEND = "http://localhost:8000";
const PROXY_PATHS = [
  "/api",
  "/me",
  "/pulls",
  "/refresh",
  "/logout",
  "/auth",
  "/login",
  "/styles.css",
  "/favicon.svg",
  "/favicon.ico",
  "/apple-touch-icon.png",
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

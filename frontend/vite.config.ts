import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In dev and in docker the API runs on :8000; Vite proxies /api so the browser sees one origin.
const apiTarget = process.env.MIRA_API_URL ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/api": { target: apiTarget, changeOrigin: true } } },
  preview: { proxy: { "/api": { target: apiTarget, changeOrigin: true } } },
});

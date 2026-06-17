import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  // Fail loudly if the configured port is taken rather than silently shifting to a
  // port the API's CORS allowlist does not include.
  server: { strictPort: true },
  preview: { strictPort: true },
});

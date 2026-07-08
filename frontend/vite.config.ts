import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        // 8000 is held by an unrelated process on this machine; QVault's backend
        // runs on 8004 until 8000 is freed (see CLAUDE.md for the documented default).
        target: "http://127.0.0.1:8004",
        changeOrigin: true,
      },
    },
  },
});

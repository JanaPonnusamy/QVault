import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5174,
    proxy: {
      "/api": {
        // 8000/8004 are already used by other local apps on this machine;
        // QVault's backend runs on 8005 to avoid port conflicts.
        target: "http://127.0.0.1:8005",
        changeOrigin: true,
      },
    },
  },
});

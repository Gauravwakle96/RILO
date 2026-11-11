import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5187,
    strictPort: true,
    proxy: {
      "/api": { target: "http://127.0.0.1:8018", changeOrigin: false },
      "/docs": { target: "http://127.0.0.1:8018", changeOrigin: false },
      "/redoc": { target: "http://127.0.0.1:8018", changeOrigin: false },
      "/openapi.json": { target: "http://127.0.0.1:8018", changeOrigin: false },
    },
  },
  build: { sourcemap: false },
});

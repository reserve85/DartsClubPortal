import react from "@vitejs/plugin-react";
import { resolve } from "node:path";
import { defineConfig } from "vite";

// Built files go to app/static/dist and are served by Django/WhiteNoise.
export default defineConfig({
  plugins: [react()],
  base: "/static/dist/",
  resolve: { alias: { "@": resolve(import.meta.dirname, "src") } },
  build: {
    outDir: resolve(import.meta.dirname, "../app/static/dist"),
    emptyOutDir: true,
    manifest: true,
    rollupOptions: { input: resolve(import.meta.dirname, "src/main.tsx") },
  },
  server: { port: 5173, strictPort: true, origin: "http://localhost:5173" },
});

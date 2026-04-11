import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import tailwindcss from "@tailwindcss/vite";
import { configDefaults } from "vitest/config";

export default defineConfig({
  plugins: [vue(), tailwindcss()],
  server: {
    port: 5173,
    host: "0.0.0.0",
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true
      }
    }
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./tests/setup.ts",
    include: ["tests/unit/**/*.test.ts"],
    exclude: [...configDefaults.exclude, "tests/e2e/**"],
    coverage: {
      provider: "v8"
    }
  }
});

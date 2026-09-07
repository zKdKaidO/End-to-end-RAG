import { defineConfig } from "../frontend/node_modules/vitest/dist/config.js";

export default defineConfig({
  test: {
    environment: "node",
    include: ["cloud/worker/src/**/*.test.ts"],
  },
});

import { defineConfig } from "vitest/config"
import path from "node:path"

// Unit tests cover the pure-TS layer only (src/lib, later the M4 sync engine)
// and run in Node — no React Native runtime. Component testing on the RN side
// arrives with jest-expo if/when it earns its keep.
export default defineConfig({
  resolve: {
    alias: { "@": path.resolve(__dirname, "src") },
  },
  test: {
    include: ["src/**/*.test.ts"],
    environment: "node",
  },
})

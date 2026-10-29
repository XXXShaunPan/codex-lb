import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: ".",
  testMatch: "spend-control.spec.ts",
  timeout: 60_000,
  workers: 1,
  use: {
    channel: process.env.SCREENSHOT_BROWSER_CHANNEL,
    viewport: { width: 1440, height: 1100 },
  },
  webServer: process.env.SPEND_CONTROL_LIVE_BASE_URL ? undefined : {
    command: process.env.SPEND_CONTROL_PREVIEW_COMMAND ?? "bun run preview --outDir ../.local/spend-control-build --port 4177",
    port: 4177,
    reuseExistingServer: false,
  },
});

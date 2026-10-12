import { defineConfig, devices } from "@playwright/test"

const PORT = Number(process.env.UI_PORT ?? 8790)
// Locally the project venv; in CI, setup-python puts `python` on PATH.
const PYTHON = process.env.PYTHON ?? ".venv/bin/python"

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: [
    ["list"],
    ["html", { open: "never" }],
    // Per-section tables and totals at the end of the run.
    ["./reporters/table-summary-reporter.ts"],
  ],
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  // Starts the Python chat server (web/server.py) before the tests run.
  webServer: {
    command: `${PYTHON} -m web.server`,
    url: `http://127.0.0.1:${PORT}`,
    env: { PORT: String(PORT) },
    // Never reuse: a different app on the same port would be tested silently.
    // A busy port fails fast instead; pick another with UI_PORT=....
    reuseExistingServer: false,
    timeout: 30_000,
  },
})

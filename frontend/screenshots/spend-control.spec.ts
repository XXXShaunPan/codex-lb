import { test, expect, type Page } from "@playwright/test";
import { createAccountSummary, createAccountTrends, createDashboardAuthSession, createDashboardSettings,
  createUpstreamProxyAdmin, createDashboardOverview } from "../src/test/mocks/factories";

const account = createAccountSummary({
  accountId: "budget-ui-fixture", displayName: "Enterprise budget fixture", email: "budget@example.test", planType: "ent26",
  usage: { primaryRemainingPercent: null, secondaryRemainingPercent: null, monthlyRemainingPercent: null },
  windowMinutesPrimary: null, windowMinutesSecondary: null, windowMinutesMonthly: null,
  resetAtPrimary: null, resetAtSecondary: null,
  spendControl: { unit: "usd", limit: "200.00", used: "83.33", remaining: "116.67", remainingPercent: 58,
    reached: false, budgetOnly: true, observedAt: "2026-10-28T10:00:00Z", resetAt: "2026-11-01T00:00:00Z" },
});

async function mockApi(page: Page) {
  await page.addInitScript(() => localStorage.setItem("codex-lb-language", "zh-CN"));
  await page.route("**/health/**", r => r.fulfill({ json: { status: "ok" } }));
  await page.route("**/api/**", async route => {
    const p = new URL(route.request().url()).pathname.replace(/\/$/, "");
    let data: unknown = {};
    if (p === "/api/dashboard-auth/session") data = createDashboardAuthSession({ role: "admin", permissions: ["read", "write"], totpConfigured: false });
    else if (p === "/api/accounts") data = { accounts: [account] };
    else if (p === "/api/model-sources") data = { sources: [] };
    else if (p === "/api/settings") data = createDashboardSettings();
    else if (p === "/api/settings/upstream-proxy") data = createUpstreamProxyAdmin();
    else if (p === "/api/dashboard/overview") data = createDashboardOverview({ accounts: [account] });
    else if (p.endsWith("/trends")) data = createAccountTrends(account.accountId, { primary: [], secondary: [], secondaryScheduled: [] });
    else if (p.endsWith("/usage-reset-credits")) data = { accountId: account.accountId, rateLimitResetCredits: { availableCount: 0 } };
    else if (p === "/api/models") data = { models: [] };
    return route.fulfill({ json: data });
  });
}

test("enterprise spending budget on account page", async ({ page }, info) => {
  await mockApi(page);
  if (process.env.SPEND_CONTROL_BEFORE_URL) {
    await page.goto(process.env.SPEND_CONTROL_BEFORE_URL + "/accounts");
    await expect(page.getByText("Enterprise budget fixture", { exact: true }).first()).toBeVisible();
    await page.screenshot({ path: info.outputPath("budget-before.png"), fullPage: true });
  }
  await page.goto("http://localhost:4177/accounts");
  await expect(page.getByTestId("spend-control-quota").first()).toBeVisible();
  await expect(page.getByTestId("spend-control-quota").first()).toContainText("116.67");
  await page.getByText("Enterprise budget fixture", { exact: true }).first().click();
  await expect(page.getByTestId("spend-control-quota")).toHaveCount(2);
  await page.screenshot({ path: info.outputPath("budget-after.png"), fullPage: true });
});

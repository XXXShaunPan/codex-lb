import { test, expect, type Page } from "@playwright/test";
import { createAccountSummary, createAccountTrends, createDashboardAuthSession, createDashboardSettings,
  createUpstreamProxyAdmin, createDashboardOverview } from "../src/test/mocks/factories";

const baseUrl = process.env.SPEND_CONTROL_LIVE_BASE_URL ?? "http://localhost:4177";

const account = createAccountSummary({
  accountId: "budget-ui-fixture", displayName: "Enterprise budget fixture", email: "budget@example.test", planType: "ent26",
  usage: { primaryRemainingPercent: null, secondaryRemainingPercent: null, monthlyRemainingPercent: 58 },
  windowMinutesPrimary: null, windowMinutesSecondary: null, windowMinutesMonthly: null,
  remainingCreditsPrimary:null, remainingCreditsSecondary:null, remainingCreditsMonthly:null,
  capacityCreditsPrimary:null, capacityCreditsSecondary:null, capacityCreditsMonthly:null,
  resetAtPrimary: null, resetAtSecondary: null, resetAtMonthly: "2026-11-01T00:00:00Z",
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
    else if (p === "/api/image-routing/settings") data = {hostModel:null,resolvedHostModel:null,availableHostModels:[]};
    else if (p === "/api/settings") data = createDashboardSettings({routingStrategy:"custom_weighted_quota"});
    else if (p === "/api/relay-routing/weights") data = {accounts:[
      {accountId:account.accountId,name:"Enterprise budget fixture",kind:"account",weight:1},
      {accountId:"model-source:compass",name:"Compass",kind:"model_source",weight:1},
    ]};
    else if (p === "/api/settings/upstream-proxy") data = createUpstreamProxyAdmin();
    else if (p === "/api/dashboard/overview") data = createDashboardOverview({ accounts: [account] });
    else if (p.endsWith("/trends")) data = createAccountTrends(account.accountId, { primary: [], secondary: [], secondaryScheduled: [] });
    else if (p.endsWith("/usage-reset-credits")) data = { accountId: account.accountId, rateLimitResetCredits: { availableCount: 0 } };
    else if (p === "/api/models") data = { models: [] };
    return route.fulfill({ json: data });
  });
}

test("enterprise monthly quota, USD balance and quadratic routing controls", async ({ page }, info) => {
  const priorityRequests: string[] = [];
  page.on("request", request => {
    if (request.url().startsWith(baseUrl + "/api/relay-routing/rules")) priorityRequests.push(request.url());
  });
  await mockApi(page);
  if (process.env.SPEND_CONTROL_BEFORE_URL) {
    await page.goto(process.env.SPEND_CONTROL_BEFORE_URL + "/accounts");
    await expect(page.getByText("Enterprise budget fixture", { exact: true }).first()).toBeVisible();
    await page.screenshot({ path: info.outputPath("budget-before.png"), fullPage: true });
    await page.goto(process.env.SPEND_CONTROL_BEFORE_URL + "/dashboard");
    await expect(page.getByText("Enterprise budget fixture", {exact:true}).first()).toBeVisible();
    await page.screenshot({path:info.outputPath("balance-before.png"),fullPage:true});
  }
  priorityRequests.length = 0;
  await page.goto(baseUrl + "/accounts");
  await expect(page.getByTestId("mini-quota-track-月度")).toHaveAttribute("value", "58");
  await expect(page.getByText(/支出额度/)).toHaveCount(0);
  await page.getByText("Enterprise budget fixture", { exact: true }).first().click();
  await expect(page.getByText(/月度.*剩余/)).toBeVisible();
  await expect(page.getByText("58%", {exact:true})).toHaveCount(2);
  await expect(page.getByText(/支出额度|116\.67|套餐与账号优先级规则/)).toHaveCount(0);
  await expect(page.getByText(/^(5h|每周)\s*剩余$/)).toHaveCount(0);
  await page.screenshot({ path: info.outputPath("monthly-after.png"), fullPage: true });
  await page.goto(baseUrl + "/dashboard");
  await expect(page.getByText("$116.67", {exact:true}).first()).toBeVisible();
  await page.screenshot({path:info.outputPath("balance-after.png"),fullPage:true});
  await page.goto(baseUrl + "/settings?advanced=1");
  await expect(page.getByText(/分数决定随机抽取的概率/)).toBeVisible();
  await expect(page.getByText(/相同权重、剩余 80% 与 20%/)).toBeVisible();
  await expect(page.getByText(/100%.*占位/)).toBeVisible();
  await expect(page.getByText("套餐与账号优先级规则", {exact:true})).toHaveCount(0);
  expect(priorityRequests).toEqual([]);
  await page.screenshot({ path: info.outputPath("routing-after.png"), fullPage: true });
});

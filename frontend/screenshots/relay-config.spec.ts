import path from "node:path";
import { expect, test, type Page } from "@playwright/test";
import {
  createApiKey, createApiKeyTrends, createApiKeyUsage7Day, createDashboardAuthSession,
  createDashboardSettings, createUpstreamProxyAdmin,
} from "../src/test/mocks/factories";

const base = process.env.SCREENSHOT_BASE_URL ?? "http://localhost:4173";
const insecureOrigin = "http://relay-copy.test";

async function verifyRealClipboard(page: Page) {
  const expected=await page.getByRole("textbox",{name:"Configuration command"}).inputValue();
  await page.getByRole("button",{name:"Copy command",exact:true}).click();
  await expect(page.getByRole("button",{name:"Copy command Copied",exact:true})).toBeVisible();
  // Read only a boolean comparison in a disposable secure-origin reader. Never
  // emit clipboard contents (including an unrelated concurrent user's copy).
  const reader=await page.context().newPage();
  try {
    await page.context().grantPermissions(["clipboard-read"],{origin:new URL(base).origin});
    await reader.route("**/*",route=>route.fulfill({contentType:"text/html",body:"<!doctype html><title>Clipboard verification</title>"}));
    await reader.goto(base+"/clipboard-verification");
    await reader.bringToFront();
    const matches=await reader.evaluate(async value => (await navigator.clipboard.readText()).replace(/\r\n/g,"\n")===value.replace(/\r\n/g,"\n"),expected);
    expect(matches,"Clipboard should contain the complete selected command").toBe(true);
  } finally {
    await reader.close();
    await page.bringToFront();
  }
}

for (const guest of [false, true]) {
  test(`relay configuration ${guest ? "visitor" : "administrator"}`, async ({page}, testInfo) => {
    let available = false;
    const exports: unknown[] = [];
    const key = createApiKey({name:"Example assigned key"});
    await page.route(insecureOrigin+"/**",async route=>{
      const url=new URL(route.request().url());
      const response=await route.fetch({url:new URL(url.pathname+url.search,base).href});
      await route.fulfill({response});
    });
    await page.route("**/health/**", route => route.fulfill({contentType:"application/json",body:'{"status":"ok"}'}));
    await page.addInitScript(() => localStorage.setItem("i18nextLng","en"));
    await page.route("**/api/**", async route => {
      const p = new URL(route.request().url()).pathname.replace(/\/$/,"");
      let data: unknown = {};
      if (p === "/api/dashboard-auth/session") data = createDashboardAuthSession({role:guest ? "guest":"admin",permissions:guest ? ["read"]:["read","write"],totpConfigured:false});
      else if (p === "/api/api-keys") data = [key];
      else if (p.endsWith("/usage-7d")) data = createApiKeyUsage7Day();
      else if (p.endsWith("/trends")) data = createApiKeyTrends();
      else if (p === "/api/accounts") data = {accounts:[]};
      else if (p === "/api/model-sources") data = {sources:[]};
      else if (p === "/api/settings") data = createDashboardSettings();
      else if (p === "/api/settings/upstream-proxy") data = createUpstreamProxyAdmin();
      else if (p === "/api/models") data = {models:[]};
      else if (p === "/api/image-routing/settings") data = {hostModel:null,resolvedHostModel:"catalog-host",availableHostModels:["catalog-host"]};
      else if (p === "/api/codex-config/status") data = {tokenAvailable:available,resetRequired:!available};
      else if (p === "/api/codex-config/generate") {
        exports.push(route.request().postDataJSON());
        data = {apiKey:{key:"sk-example-not-a-real-key"},reset:!available};
        available = true;
      }
      return route.fulfill({contentType:"application/json",body:JSON.stringify(data)});
    });
    await page.goto(insecureOrigin + "/settings");
    expect(await page.evaluate(()=>window.isSecureContext)).toBe(false);
    await page.getByRole("link",{name:/^APIs/}).click();
    if (guest) {
      await expect(page.getByRole("link",{name:/^Accounts/})).toHaveCount(0);
      await expect(page.getByRole("button",{name:/Create.*key/i})).toHaveCount(0);
    }
    await page.getByRole("button",{name:"Configure Codex",exact:true}).click();
    const button = page.getByRole("button",{name:"Reset and generate commands"});
    await expect(button).toBeDisabled();
    await page.screenshot({path:testInfo.outputPath("missing-token.png"),fullPage:true});
    await page.getByRole("checkbox",{name:/I confirm resetting/}).check();
    await button.click();
    await expect(page.getByRole("textbox",{name:"Configuration command"})).toContainText("FromBase64String");
    expect(exports).toEqual([{apiKeyId:key.id,resetKey:false,confirmReset:true}]);
    await verifyRealClipboard(page);
    await page.keyboard.press("Escape");
    await page.getByRole("button",{name:"Configure Codex",exact:true}).click();
    await expect(page.getByRole("button",{name:"Generate configuration",exact:true})).toBeEnabled();
    await page.screenshot({path:testInfo.outputPath("saved-token.png"),fullPage:true});
    await page.keyboard.press("Escape");
    await page.getByRole("button",{name:"Restore Codex config",exact:true}).click();
    await expect(page.getByRole("heading",{name:"Remove Codex-LB settings"})).toBeVisible();
    await expect(page.getByRole("textbox",{name:"Configuration command"})).toContainText("Remove-RelayConfiguration");
    await verifyRealClipboard(page);
    await page.getByRole("combobox").selectOption("linux");
    await expect(page.getByRole("textbox",{name:"Configuration command"})).toContainText("/bin/bash <<'CODEX_LB_BASH'");
    await verifyRealClipboard(page);
    expect(exports).toHaveLength(1);
    await page.screenshot({path:testInfo.outputPath("targeted-cleanup.png"),fullPage:true});
    if (!guest) {
      await page.keyboard.press("Escape");
      await page.goto(insecureOrigin + "/settings");
      await expect(page.getByText("Image model routing",{exact:true})).toBeVisible();
      await page.getByText("Image model routing",{exact:true}).scrollIntoViewIfNeeded();
      await page.screenshot({path:testInfo.outputPath("image-routing.png"),fullPage:false});
    }
    await testInfo.attach("UI screenshot directory",{body:path.dirname(testInfo.outputPath("saved-token.png")),contentType:"text/plain"});
  });
}

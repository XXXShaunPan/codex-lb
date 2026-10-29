import { describe, expect, it } from "vitest";

import {
  accountSubscriptionCredits,
  accountSubscriptionQuota,
  formatSubscriptionQuota,
  formatPurchasedCredits,
} from "@/features/dashboard/account-credit-display";
import { createAccountSummary } from "@/test/mocks/factories";

function enterprise(remaining: string | null, unit: string | null = "usd") {
  return createAccountSummary({planType:"ent26",
    remainingCreditsPrimary:null, remainingCreditsSecondary:null, remainingCreditsMonthly:null,
    spendControl:{unit,remaining,limit:"200",used:null,remainingPercent:58,reached:false,
      resetAt:null,observedAt:"2026-10-29T00:00:00Z",budgetOnly:true}});
}

describe("account credit display", () => {
  it.each([
    ["116.6687", "$116.67"], ["0", "$0.00"], ["-1.23", "-$1.23"], ["1234.50", "$1,234.50"],
  ])("formats ent26's actual USD remaining balance %s", (remaining, formatted) => {
    const account = enterprise(remaining);
    expect(formatSubscriptionQuota(account)).toBe(formatted);
    expect(accountSubscriptionQuota(account)).toEqual({unit:"usd",value:Number(remaining)});
    expect(accountSubscriptionCredits(account)).toBeNull();
  });
  it.each([null, "", "  ", "NaN", "Infinity", "not-an-amount"])("does not invent a balance from %s", remaining => {
    expect(formatSubscriptionQuota(enterprise(remaining))).toBe("-");
  });
  it.each([null, "", "eur"])("does not mislabel a %s allowance as USD", unit => {
    expect(formatSubscriptionQuota(enterprise("100", unit))).toBe("-");
  });
  it("retains the existing credit unit and format for other plans", () => {
    const account = createAccountSummary({remainingCreditsSecondary:5065.2});
    expect(accountSubscriptionQuota(account)).toEqual({unit:"credits",value:5065.2});
    expect(formatSubscriptionQuota(account)).toBe("5065.20");
  });
  it("uses monthly credits for monthly-only accounts", () => {
    const account = createAccountSummary({
      windowMinutesPrimary: null,
      windowMinutesSecondary: null,
      windowMinutesMonthly: 43_200,
      remainingCreditsPrimary: null,
      remainingCreditsSecondary: null,
      remainingCreditsMonthly: 900,
    });

    expect(accountSubscriptionCredits(account)).toBe(900);
  });

  it("uses secondary credits for weekly-only accounts", () => {
    const account = createAccountSummary({
      windowMinutesPrimary: null,
      windowMinutesSecondary: 10_080,
      windowMinutesMonthly: null,
      remainingCreditsPrimary: null,
      remainingCreditsSecondary: 700,
    });

    expect(accountSubscriptionCredits(account)).toBe(700);
  });

  it("prefers secondary credits when both subscription windows exist", () => {
    const account = createAccountSummary({
      windowMinutesPrimary: 300,
      windowMinutesSecondary: 10_080,
      remainingCreditsPrimary: 100,
      remainingCreditsSecondary: 600,
    });

    expect(accountSubscriptionCredits(account)).toBe(600);
  });

  it("falls back to primary credits when secondary credits are unavailable", () => {
    const account = createAccountSummary({
      windowMinutesPrimary: 300,
      windowMinutesSecondary: 10_080,
      remainingCreditsPrimary: 100,
      remainingCreditsSecondary: null,
    });

    expect(accountSubscriptionCredits(account)).toBe(100);
  });

  it("falls back to primary credits for legacy accounts without window metadata", () => {
    const account = createAccountSummary({
      windowMinutesPrimary: null,
      windowMinutesSecondary: null,
      windowMinutesMonthly: null,
      remainingCreditsPrimary: 100,
      remainingCreditsSecondary: null,
      remainingCreditsMonthly: null,
    });

    expect(accountSubscriptionCredits(account)).toBe(100);
  });

  it("formats unlimited only for purchased credits", () => {
    const account = createAccountSummary({ creditsUnlimited: true, creditsBalance: null });

    expect(formatPurchasedCredits(account, "Unlimited")).toBe("Unlimited");
    expect(accountSubscriptionCredits(account)).toBe(5_065.2);
  });
});

import { describe, expect, it, vi } from "vitest";

import { DEFAULT_ACCOUNT_SORT_MODE, sortAccountsForDisplay } from "@/features/accounts/sorting";
import type { AccountSummary } from "@/features/accounts/schemas";
import { createAccountSummary } from "@/test/mocks/factories";

const BOTH = "both";

it("sorts ent26 by its monthly reset even without a synthetic duration", () => {
  const clock = vi.spyOn(Date, "now").mockReturnValue(Date.parse("2026-10-29T00:00:00Z"));
  try {
    const monthly = createAccountSummary({accountId:"monthly", planType:"ent26",
      usage:{primaryRemainingPercent:null,secondaryRemainingPercent:null,monthlyRemainingPercent:58},
      windowMinutesPrimary:null,windowMinutesSecondary:null,windowMinutesMonthly:null,
      resetAtPrimary:null,resetAtSecondary:null,resetAtMonthly:"2026-11-01T00:00:00Z"});
    const weekly = createAccountSummary({accountId:"weekly",resetAtPrimary:null,resetAtSecondary:"2026-11-04T00:00:00Z"});
    expect(sortAccountsForDisplay([weekly,monthly], "both", "reset_soonest").map(a=>a.accountId)).toEqual(["monthly","weekly"]);
    expect(sortAccountsForDisplay([monthly,weekly], "both", "reset_latest").map(a=>a.accountId)).toEqual(["weekly","monthly"]);
  } finally { clock.mockRestore(); }
});

describe("sortAccountsForDisplay — most_reset_credits", () => {
  it("uses most reset credits as the default sort mode", () => {
    expect(DEFAULT_ACCOUNT_SORT_MODE).toBe("most_reset_credits");
  });

  it("orders accounts by available reset credits descending", () => {
    const fewer = createAccountSummary({
      accountId: "acc-fewer",
      displayName: "Fewer",
      availableResetCredits: 1,
    });
    const more = createAccountSummary({
      accountId: "acc-more",
      displayName: "More",
      availableResetCredits: 4,
    });

    const sorted = sortAccountsForDisplay([fewer, more], BOTH, "most_reset_credits");

    expect(sorted.map((account) => account.accountId)).toEqual([
      "acc-more",
      "acc-fewer",
    ]);
  });

  it("breaks ties by soonest expiry ascending", () => {
    const later = createAccountSummary({
      accountId: "acc-later",
      displayName: "Later",
      availableResetCredits: 2,
      resetCreditNearestExpiresAt: "2026-02-01T00:00:00.000Z",
    });
    const sooner = createAccountSummary({
      accountId: "acc-sooner",
      displayName: "Sooner",
      availableResetCredits: 2,
      resetCreditNearestExpiresAt: "2026-01-10T00:00:00.000Z",
    });

    const sorted = sortAccountsForDisplay([later, sooner], BOTH, "most_reset_credits");

    expect(sorted.map((account) => account.accountId)).toEqual([
      "acc-sooner",
      "acc-later",
    ]);
  });

  it("sorts accounts with null expiry after accounts that have one", () => {
    const noExpiry = createAccountSummary({
      accountId: "acc-no-expiry",
      displayName: "No Expiry",
      availableResetCredits: 3,
      resetCreditNearestExpiresAt: null,
    });
    const withExpiry = createAccountSummary({
      accountId: "acc-with-expiry",
      displayName: "With Expiry",
      availableResetCredits: 3,
      resetCreditNearestExpiresAt: "2026-01-10T00:00:00.000Z",
    });

    const sorted = sortAccountsForDisplay(
      [noExpiry, withExpiry],
      BOTH,
      "most_reset_credits",
    ) as AccountSummary[];

    expect(sorted.map((account) => account.accountId)).toEqual([
      "acc-with-expiry",
      "acc-no-expiry",
    ]);
  });

  it("still sorts credits descending when both accounts have null expiry", () => {
    const low = createAccountSummary({
      accountId: "acc-low",
      displayName: "Low",
      availableResetCredits: 1,
      resetCreditNearestExpiresAt: null,
    });
    const high = createAccountSummary({
      accountId: "acc-high",
      displayName: "High",
      availableResetCredits: 5,
      resetCreditNearestExpiresAt: null,
    });

    const sorted = sortAccountsForDisplay([low, high], BOTH, "most_reset_credits");

    expect(sorted.map((account) => account.accountId)).toEqual([
      "acc-high",
      "acc-low",
    ]);
  });
});

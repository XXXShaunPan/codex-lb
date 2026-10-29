import type { AccountSummary } from "./schemas";

// A percentage/reset-only monthly allowance has no fabricated window duration.
export function hasMonthlyQuota(account: AccountSummary): boolean {
  return account.planType === "ent26" || account.windowMinutesMonthly != null ||
    account.usage?.monthlyRemainingPercent != null || account.resetAtMonthly != null;
}

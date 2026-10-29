import type { AccountSummary } from "@/features/dashboard/schemas";
import { formatCurrency } from "@/utils/formatters";

type SubscriptionQuota = { unit: "usd" | "credits"; value: number | null };

export function accountSubscriptionQuota(account: AccountSummary): SubscriptionQuota {
  if (account.planType !== "ent26") {
    return { unit: "credits", value: accountSubscriptionCredits(account) };
  }
  const remaining = account.spendControl?.remaining;
  const amount = remaining == null || remaining.trim() === "" ? null : Number(remaining);
  return {
    unit: "usd",
    value: account.spendControl?.unit?.trim().toLowerCase() === "usd" && amount !== null && Number.isFinite(amount)
      ? amount : null,
  };
}

export function formatSubscriptionQuota(account: AccountSummary): string {
  const quota = accountSubscriptionQuota(account);
  if (quota.value === null) return "-";
  return quota.unit === "usd" ? formatCurrency(quota.value) : formatCreditValue(quota.value);
}

export function accountSubscriptionCredits(account: AccountSummary): number | null {
  const monthlyOnly =
    account.windowMinutesMonthly != null &&
    account.windowMinutesPrimary == null &&
    account.windowMinutesSecondary == null;
  const weeklyOnly = account.windowMinutesPrimary == null && account.windowMinutesSecondary != null;

  const value = monthlyOnly
    ? account.remainingCreditsMonthly
    : weeklyOnly
      ? account.remainingCreditsSecondary
      : (account.remainingCreditsSecondary ?? account.remainingCreditsPrimary);

  return value ?? null;
}

export function formatCreditValue(value: number | null | undefined): string {
  return value == null ? "-" : value.toFixed(2);
}

export function formatPurchasedCredits(account: AccountSummary, unlimitedLabel: string): string {
  if (account.creditsUnlimited) {
    return unlimitedLabel;
  }
  return formatCreditValue(account.creditsBalance);
}

import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AccountListItem } from "./account-list-item";
import { AccountUsagePanel } from "./account-usage-panel";
import { AccountCard } from "@/features/dashboard/components/account-card";
import { AccountList } from "@/features/dashboard/components/account-list";
import { createAccountSummary } from "@/test/mocks/factories";
import { formatQuotaResetLabel } from "@/utils/formatters";
import type { AccountSummary } from "@/features/accounts/schemas";

const budget: NonNullable<AccountSummary["spendControl"]> = {
  unit: "usd", limit: "200.00", used: "83.33", remaining: "116.67",
  remainingPercent: 58, reached: false, resetAt: "2026-11-01T00:00:00Z",
  observedAt: "2026-10-28T10:00:00Z", budgetOnly: true,
};

function surface(name: string, account: AccountSummary) {
  return name === "list"
    ? <AccountListItem account={account} selected={false} onSelect={vi.fn()} />
    : name === "card" ? <AccountCard account={account} />
    : name === "table" ? <AccountList accounts={[account]} /> : <AccountUsagePanel account={account} />;
}

describe.each(["list", "card", "table", "details"])("enterprise monthly quota: %s", name => {
  it("keeps monthly percentage/reset and shows dollars only in the existing subscription field", () => {
    const account = createAccountSummary({
      planType: "ent26", spendControl: budget,
      // Retained short/weekly values model a live transition from cached data.
      usage: {primaryRemainingPercent: 90, secondaryRemainingPercent: 80, monthlyRemainingPercent: 58},
      resetAtMonthly: budget.resetAt, windowMinutesMonthly: null,
    });
    const {container} = render(surface(name, account));
    expect(screen.getByText(/^Monthly( remaining)?$/)).toBeInTheDocument();
    expect(screen.getByText("58%")).toBeInTheDocument();
    expect(container.textContent).toContain(formatQuotaResetLabel(budget.resetAt));
    expect(screen.queryByText(/Spending budget|支出额度/)).not.toBeInTheDocument();
    if (name === "card" || name === "table") expect(screen.getByText("$116.67")).toBeInTheDocument();
    else expect(screen.queryByText(/116\.67/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Limit: 200|Used: 83\.33/)).not.toBeInTheDocument();
    expect(screen.queryByText(/^5h( remaining)?$/)).not.toBeInTheDocument();
    expect(screen.queryByText(/^Weekly( remaining)?$/)).not.toBeInTheDocument();
  });

  it("keeps missing percentage/reset unknown rather than assuming full or empty", () => {
    const account = createAccountSummary({
      planType: "ent26", spendControl: {...budget, remainingPercent: null, resetAt: null},
      usage: {primaryRemainingPercent: null, secondaryRemainingPercent: null, monthlyRemainingPercent: null},
      windowMinutesPrimary: null, windowMinutesSecondary: null, windowMinutesMonthly: null,
      resetAtPrimary: null, resetAtSecondary: null, resetAtMonthly: null,
    });
    render(surface(name, account));
    expect(screen.getByText(/^Monthly( remaining)?$/)).toBeInTheDocument();
    expect(screen.queryByText(/^(0|100)(\.0)?%$/)).not.toBeInTheDocument();
    expect(screen.getAllByText("--").length).toBeGreaterThan(0);
  });

  it("preserves real short and weekly windows alongside a monthly control", () => {
    const account = createAccountSummary({
      planType: "ent26", spendControl: {...budget, budgetOnly: false},
      usage: {primaryRemainingPercent: 90, secondaryRemainingPercent: 80, monthlyRemainingPercent: 58},
      resetAtMonthly: budget.resetAt,
    });
    render(surface(name, account));
    expect(screen.getByText(/^Monthly( remaining)?$/)).toBeInTheDocument();
    expect(screen.getByText(/^5h( remaining)?$/)).toBeInTheDocument();
    expect(screen.getByText(/^Weekly( remaining)?$/)).toBeInTheDocument();
    expect(screen.queryByText(/Spending budget/)).not.toBeInTheDocument();
  });
});

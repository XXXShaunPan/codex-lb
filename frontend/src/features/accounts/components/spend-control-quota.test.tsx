import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AccountListItem } from "./account-list-item";
import { AccountUsagePanel } from "./account-usage-panel";
import { AccountCard } from "@/features/dashboard/components/account-card";
import { SpendControlQuota } from "./spend-control-quota";
import { createAccountSummary } from "@/test/mocks/factories";
import type { AccountSummary } from "@/features/accounts/schemas";

const budget: NonNullable<AccountSummary["spendControl"]> = {
  unit: "usd",
  limit: "200.00",
  used: "83.33126151561737",
  remaining: "116.66873848438263",
  remainingPercent: 58,
  reached: false,
  resetAt: "2026-11-01T00:00:00Z",
  observedAt: "2026-10-28T10:00:00Z",
  budgetOnly: true,
};

describe("Spend-control quotas", () => {
  it.each(["list", "card", "details"])(
    "shows actual budget without fake windows in %s",
    (surface) => {
      // Keep old windows in the fixture to exercise a live transition from cached data.
      const account = createAccountSummary({
        planType: "ent26",
        spendControl: budget,
      });
      render(
        surface === "list" ? (
          <AccountListItem
            account={account}
            selected={false}
            onSelect={vi.fn()}
          />
        ) : surface === "card" ? (
          <AccountCard account={account} />
        ) : (
          <AccountUsagePanel account={account} />
        ),
      );
      const panel = within(screen.getByTestId("spend-control-quota"));
      expect(panel.getByText("Spending budget (USD)")).toBeInTheDocument();
      expect(panel.getByText("Remaining: 116.67")).toBeInTheDocument();
      expect(panel.getByText("Used: 83.33")).toBeInTheDocument();
      expect(panel.getByText("Limit: 200")).toBeInTheDocument();
      expect(panel.getByText(/58/)).toBeInTheDocument();
      expect(screen.queryByText(/^5h( remaining)?$/)).not.toBeInTheDocument();
      expect(
        screen.queryByText(/^Weekly( remaining)?$/),
      ).not.toBeInTheDocument();
    },
  );

  it("does not assume a fixed budget amount", () => {
    render(
      <SpendControlQuota
        budget={{
          ...budget,
          limit: "50.00",
          used: "21.69",
          remaining: "28.31",
          remainingPercent: 57,
        }}
      />,
    );
    expect(screen.getByText("Limit: 50")).toBeInTheDocument();
    expect(screen.getByText("Remaining: 28.31")).toBeInTheDocument();
  });

  it("keeps missing monetary values and percentages unknown", () => {
    render(
      <SpendControlQuota
        budget={{
          ...budget,
          limit: null,
          used: null,
          remaining: null,
          remainingPercent: null,
        }}
      />,
    );
    expect(screen.getByText("Remaining: —")).toBeInTheDocument();
    expect(screen.getByText("--")).toBeInTheDocument();
    expect(screen.queryByText(/Budget exhausted/)).not.toBeInTheDocument();
    expect(screen.queryByText(/^0/)).not.toBeInTheDocument();
  });

  it("shows exhausted control even with positive individual remaining amount", () => {
    render(<SpendControlQuota budget={{ ...budget, reached: true }} />);
    expect(screen.getByText(/Budget exhausted/)).toBeInTheDocument();
    expect(screen.getByText("Remaining: 116.67")).toBeInTheDocument();
  });

  it("retains real subscription windows when both quota kinds are reported", () => {
    const account = createAccountSummary({
      spendControl: { ...budget, budgetOnly: false },
    });
    render(<AccountUsagePanel account={account} />);
    expect(screen.getByTestId("spend-control-quota")).toBeInTheDocument();
    expect(screen.getByText("5h remaining")).toBeInTheDocument();
  });
});

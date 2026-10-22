import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it } from "vitest";

import { useAuthStore } from "@/features/auth/hooks/use-auth";
import { server } from "@/test/mocks/server";
import { renderWithProviders } from "@/test/utils";
import { PrioritySettings } from "./priority-settings";

const rule = { normalPriority: 10, lowPriority: 30, downgradePercent: 20, recoveryPercent: 25, quotaBasis: "minimum", allowLowQuota: true };
const account = { accountId: "plus-a", name: "Plus A", planType: "plus", override: null, effectiveRule: rule, quotaPlaceholder: false };

describe("priority routing settings", () => {
  beforeEach(() => {
    useAuthStore.setState({ role: "admin", canWrite: true, authenticated: true });
    server.use(http.get("/api/relay-routing/rules", () => HttpResponse.json({ plans: [{ planType: "plus", rule }], accounts: [account] })));
  });
  it("saves all plan controls including fallback and quota basis", async () => {
    let saved: unknown;
    server.use(http.put("/api/relay-routing/rules/plans/plus", async ({ request }) => {
      const body = await request.json(); saved = body; return HttpResponse.json(body);
    }));
    const user = userEvent.setup();
    renderWithProviders(<PrioritySettings />);
    const priority = await screen.findByRole("spinbutton", { name: "plus · Normal priority" });
    await user.clear(priority); await user.type(priority, "5");
    await user.selectOptions(screen.getByRole("combobox", { name: "plus · Threshold quota basis" }), "weekly");
    await user.click(screen.getByRole("checkbox", { name: "plus · Allow low-quota fallback" }));
    await user.click(screen.getByRole("button", { name: "Save plan rule" }));
    await waitFor(() => expect(saved).toEqual({ ...rule, normalPriority: 5, quotaBasis: "weekly", allowLowQuota: false }));
  });
  it("blocks recovery at or below the downgrade threshold", async () => {
    const user = userEvent.setup();
    renderWithProviders(<PrioritySettings />);
    const recovery = await screen.findByRole("spinbutton", { name: "plus · Recovery threshold (%)" });
    await user.clear(recovery); await user.type(recovery, "20");
    expect(screen.getByRole("button", { name: "Save plan rule" })).toBeDisabled();
    expect(screen.getByRole("alert")).toHaveTextContent("recovery must exceed downgrade");
  });
  it("supports an account override and restoring inheritance", async () => {
    const updates: unknown[] = [];
    server.use(http.put("/api/relay-routing/rules/accounts/plus-a", async ({ request }) => {
      const body = await request.json(); updates.push(body); return HttpResponse.json(body);
    }));
    const user = userEvent.setup();
    renderWithProviders(<PrioritySettings accountId="plus-a" />);
    await user.click(await screen.findByText(/Plus A · plus/));
    const toggle = screen.getByRole("checkbox", { name: /Plus A · Override plan rule/ });
    const low = screen.getByRole("spinbutton", { name: "Plus A · Low-quota priority" });
    expect(low).toBeDisabled();
    await user.click(toggle);
    await user.clear(low); await user.type(low, "40");
    await user.click(screen.getByRole("button", { name: "Save account rule" }));
    await waitFor(() => expect(updates).toContainEqual({ override: { ...rule, lowPriority: 40 } }));
    await user.click(toggle);
    await user.click(screen.getByRole("button", { name: "Save account rule" }));
    await waitFor(() => expect(updates).toContainEqual({ override: null }));
    expect(screen.queryByRole("combobox", { name: "Plan default rule" })).not.toBeInTheDocument();
  });
  it("labels source quota as a placeholder and hides everything from visitors", async () => {
    server.use(http.get("/api/relay-routing/rules", () => HttpResponse.json({ plans: [], accounts: [{
      ...account, accountId: "model-source:c", name: "Compass", planType: "other", quotaPlaceholder: true,
    }] })));
    const user = userEvent.setup();
    const view = renderWithProviders(<PrioritySettings />);
    await user.click(await screen.findByText(/Compass · other/));
    expect(screen.getByText(/not the actual Compass\/provider balance/)).toBeInTheDocument();
    view.unmount();
    useAuthStore.setState({ role: "guest", canWrite: false });
    const { container } = renderWithProviders(<PrioritySettings />);
    expect(container).toBeEmptyDOMElement();
  });
});

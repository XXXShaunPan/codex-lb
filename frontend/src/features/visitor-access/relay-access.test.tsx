import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithProviders } from "@/test/utils";
import { createApiKey } from "@/test/mocks/factories";
import { useAuthStore } from "@/features/auth/hooks/use-auth";
import { AppHeader } from "@/components/layout/app-header";
import { ApiList } from "@/features/apis/components/api-list";
import { CodexConfigButton } from "@/features/codex-config/codex-config-button";
import { AddAccountDialog } from "@/features/accounts/components/add-account-dialog";
import { http, HttpResponse } from "msw";
import { server } from "@/test/mocks/server";

describe("native relay role controls", () => {
  beforeEach(() =>
    useAuthStore.setState({
      role: "guest",
      canWrite: false,
      authenticated: true,
    }),
  );
  it("hides account/dashboard navigation and admin login for visitors", () => {
    renderWithProviders(
      <AppHeader onLogout={vi.fn()} showAdminLogin onAdminLogin={vi.fn()} />,
    );
    expect(
      screen.queryByRole("link", { name: /^Accounts/ }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: /^Dashboard/ }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /Admin sign/i }),
    ).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Reports/i })).toBeInTheDocument();
  });
  it("hides key creation while leaving Codex configuration available", async () => {
    server.use(
      http.get("/api/codex-config/status", () =>
        HttpResponse.json({ tokenAvailable: false, resetRequired: true }),
      ),
    );
    const keys = [createApiKey()];
    renderWithProviders(
      <>
        <ApiList
          apiKeys={keys}
          selectedKeyId={null}
          onSelect={vi.fn()}
          onOpenCreate={vi.fn()}
        />
        <CodexConfigButton apiKeys={keys} />
      </>,
    );
    expect(
      screen.queryByRole("button", { name: /Create.*key/i }),
    ).not.toBeInTheDocument();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Configure Codex" }));
    expect(
      await screen.findByRole("button", {
        name: "Reset and generate commands",
      }),
    ).toBeDisabled();
    await user.click(screen.getByRole("checkbox"));
    expect(
      screen.getByRole("button", { name: "Reset and generate commands" }),
    ).toBeEnabled();
  });
  it("exports a saved key without reset and requires confirmation for an optional reset", async () => {
    server.use(
      http.get("/api/codex-config/status", () =>
        HttpResponse.json({ tokenAvailable: true, resetRequired: false }),
      ),
    );
    renderWithProviders(<CodexConfigButton apiKeys={[createApiKey()]} />);
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Configure Codex" }));
    expect(
      await screen.findByText("Reset API key (optional)"),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("checkbox"));
    expect(
      screen.getByRole("button", { name: "Reset and generate commands" }),
    ).toBeDisabled();
    await user.click(
      screen.getByRole("checkbox", { name: /I confirm resetting/ }),
    );
    expect(
      screen.getByRole("button", { name: "Reset and generate commands" }),
    ).toBeEnabled();
  });
  it("offers model-source creation inside the add-account dialog", () => {
    renderWithProviders(
      <AddAccountDialog
        open
        onOpenChange={vi.fn()}
        onImport={vi.fn()}
        onAddAccount={vi.fn()}
        onAddSource={vi.fn()}
      />,
    );
    expect(
      screen.getByRole("button", { name: /Model Source/ }),
    ).toBeInTheDocument();
  });
  it("offers targeted cleanup without selecting or resetting a key", async () => {
    renderWithProviders(<CodexConfigButton apiKeys={[]} />);
    const user = userEvent.setup();
    await user.click(
      screen.getByRole("button", { name: "Restore Codex config" }),
    );
    expect(
      screen.getByRole("heading", { name: "Remove Codex-LB settings" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/does not restore an old backup or reset any API key/),
    ).toBeInTheDocument();
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
    expect(
      screen.getByRole("textbox", { name: "Configuration command" }),
    ).not.toHaveValue(expect.stringContaining("Python 3.11"));
  });
});

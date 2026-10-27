import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { server } from "@/test/mocks/server";
import { renderWithProviders } from "@/test/utils";
import { ImageRoutingSettings } from "./image-settings";

describe("image host configuration", () => {
  it("shows the resolved host and saves an independent host or automatic selection", async () => {
    let host: string | null = null;
    let saves = 0;
    const response = () => ({
      hostModel: host,
      resolvedHostModel: host ?? "catalog-host",
      availableHostModels: ["catalog-host"],
    });
    server.use(
      http.get("/api/image-routing/settings", () =>
        HttpResponse.json(response()),
      ),
      http.put("/api/image-routing/settings", async ({ request }) => {
        host = ((await request.json()) as { hostModel: string | null })
          .hostModel;
        saves++;
        return HttpResponse.json(response());
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<ImageRoutingSettings />);
    expect(
      await screen.findByText(/Current host: catalog-host/),
    ).toBeInTheDocument();
    const input = screen.getByRole("combobox");
    await user.type(input, "gpt-5.4");
    await user.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(saves).toBe(1));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Save" })).toBeDisabled(),
    );
    expect(host).toBe("gpt-5.4");
    await user.clear(input);
    await user.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(saves).toBe(2));
    expect(host).toBeNull();
  });
});

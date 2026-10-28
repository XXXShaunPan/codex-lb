import { afterEach, describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test/utils";
import { CodexConfigButton } from "./codex-config-button";

const clipboard = Object.getOwnPropertyDescriptor(navigator, "clipboard");
const secure = Object.getOwnPropertyDescriptor(window, "isSecureContext");
const exec = Object.getOwnPropertyDescriptor(document, "execCommand");

afterEach(() => {
  for (const [target, name, descriptor] of [
    [navigator, "clipboard", clipboard],
    [window, "isSecureContext", secure],
    [document, "execCommand", exec],
  ] as const) {
    if (descriptor) Object.defineProperty(target, name, descriptor);
    else Reflect.deleteProperty(target, name);
  }
  vi.restoreAllMocks();
});

describe("one-click Codex command copying", () => {
  it.each([false, true])(
    "copies the full command within the dialog (secure=%s)",
    async (isSecure) => {
      const user = userEvent.setup();
      const writeText = vi
        .fn()
        .mockRejectedValue(new Error("Clipboard API blocked"));
      Object.defineProperty(window, "isSecureContext", {
        configurable: true,
        value: isSecure,
      });
      Object.defineProperty(navigator, "clipboard", {
        configurable: true,
        value: isSecure ? { writeText } : undefined,
      });
      const values: string[] = [];
      const copy = vi.fn(() => {
        const active = document.activeElement as HTMLTextAreaElement;
        expect(active.tagName).toBe("TEXTAREA");
        expect(active.closest("[role=dialog]")).toBe(
          screen.getByRole("dialog"),
        );
        expect(active.selectionStart).toBe(0);
        expect(active.selectionEnd).toBe(active.value.length);
        values.push(active.value);
        return true;
      });
      Object.defineProperty(document, "execCommand", {
        configurable: true,
        value: copy,
      });
      renderWithProviders(<CodexConfigButton apiKeys={[]} />);
      await user.click(
        screen.getByRole("button", { name: "Restore Codex config" }),
      );
      const command = screen.getByRole("textbox", {
        name: "Configuration command",
      }) as HTMLTextAreaElement;
      await user.click(screen.getByRole("button", { name: "Copy command" }));
      expect(values).toEqual([command.value]);
      expect(command.value.length).toBeGreaterThan(1000);
      expect(
        screen.getByRole("button", { name: "Copy command Copied" }),
      ).toBeInTheDocument();
      if (isSecure) expect(writeText).toHaveBeenCalled();
      await user.selectOptions(screen.getByRole("combobox"), "linux");
      expect(
        screen.getByRole("button", { name: "Copy command" }),
      ).toBeInTheDocument();
      await user.click(screen.getByRole("button", { name: "Copy command" }));
      expect(values[1]).toBe(command.value);
      expect(values[1]).toMatch(/^\/bin\/bash/);
      expect(values[1]).not.toBe(values[0]);
      expect(
        screen.queryByText("Please copy the command manually."),
      ).not.toBeInTheDocument();
    },
  );
});

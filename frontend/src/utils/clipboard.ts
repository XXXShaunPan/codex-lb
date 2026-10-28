type CopyToClipboardOptions = {
  container?: HTMLElement | null;
};

function fallbackCopyToClipboard(
  text: string,
  options: CopyToClipboardOptions,
): boolean {
  if (typeof document.execCommand !== "function") {
    return false;
  }

  const container = options.container ?? document.body;
  if (!container) {
    return false;
  }

  const previousActiveElement =
    document.activeElement instanceof HTMLElement
      ? document.activeElement
      : null;
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "");
  textarea.setAttribute("aria-hidden", "true");
  textarea.style.position = "fixed";
  textarea.style.left = "-9999px";
  textarea.style.top = "-9999px";
  textarea.style.opacity = "0";

  container.appendChild(textarea);
  textarea.focus();
  textarea.select();
  textarea.setSelectionRange(0, text.length);

  try {
    return document.execCommand("copy");
  } catch {
    return false;
  } finally {
    if (textarea.parentNode === container) {
      container.removeChild(textarea);
    }
    if (previousActiveElement?.isConnected) {
      previousActiveElement.focus();
    }
  }
}

export async function copyToClipboard(
  text: string,
  options: CopyToClipboardOptions = {},
): Promise<boolean> {
  let clipboardWritePromise: Promise<boolean> | null = null;
  try {
    if (
      window.isSecureContext &&
      typeof navigator.clipboard?.writeText === "function"
    ) {
      clipboardWritePromise = navigator.clipboard
        .writeText(text)
        .then(() => true)
        .catch(() => false);
    }
  } catch {
    // Some browser/policy implementations throw before returning a promise.
    // Still try the synchronous click-gesture fallback below.
  }

  if (fallbackCopyToClipboard(text, options)) {
    if (clipboardWritePromise) {
      void clipboardWritePromise;
    }
    return true;
  }

  return clipboardWritePromise ?? false;
}

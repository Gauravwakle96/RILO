/** Keep keyboard focus inside an open native dialog, including at Tab boundaries. */
export function containDialogFocus(
  dialog: HTMLDialogElement | null,
): () => void {
  const handleKey = (event: KeyboardEvent) => {
    if (!dialog?.open || event.key !== "Tab") return;
    const controls = Array.from(
      dialog.querySelectorAll<HTMLElement>(
        'button:not(:disabled), a[href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), summary, [tabindex]:not([tabindex="-1"])',
      ),
    ).filter(
      (element) =>
        element.getClientRects().length > 0 && !element.closest("[inert]"),
    );
    const first = controls[0],
      last = controls.at(-1);
    if (!dialog.contains(document.activeElement)) {
      event.preventDefault();
      (event.shiftKey ? last : first)?.focus();
    } else if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last?.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first?.focus();
    }
  };
  document.addEventListener("keydown", handleKey, true);
  return () => document.removeEventListener("keydown", handleKey, true);
}

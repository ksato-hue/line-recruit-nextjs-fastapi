"use client";

import { useEffect, useId, useRef, type ReactNode } from "react";

export type ConfirmationDialogProps = {
  open: boolean;
  title: string;
  description: string;
  confirmLabel: string;
  cancelLabel: string;
  isSubmitting: boolean;
  onConfirm: () => void | Promise<void>;
  onCancel: () => void;
  children: ReactNode;
};

const FOCUSABLE_SELECTOR = [
  "button:not([disabled])",
  "[href]",
  "input:not([disabled])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  "[tabindex]:not([tabindex='-1'])"
].join(",");

export function ConfirmationDialog({
  open,
  title,
  description,
  confirmLabel,
  cancelLabel,
  isSubmitting,
  onConfirm,
  onCancel,
  children
}: ConfirmationDialogProps) {
  const titleId = useId();
  const descriptionId = useId();
  const dialogRef = useRef<HTMLDivElement>(null);
  const cancelButtonRef = useRef<HTMLButtonElement>(null);
  const onCancelRef = useRef(onCancel);
  const isSubmittingRef = useRef(isSubmitting);

  onCancelRef.current = onCancel;
  isSubmittingRef.current = isSubmitting;

  useEffect(() => {
    if (!open) return;

    const previouslyFocused = document.activeElement instanceof HTMLElement
      ? document.activeElement
      : null;
    const previousBodyOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    const focusFrame = window.requestAnimationFrame(() => {
      cancelButtonRef.current?.focus();
    });

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        if (isSubmittingRef.current) return;
        event.preventDefault();
        onCancelRef.current();
        return;
      }

      if (event.key !== "Tab" || !dialogRef.current) return;
      const focusableElements = Array.from(
        dialogRef.current.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)
      ).filter((element) => !element.hasAttribute("disabled") && element.getAttribute("aria-hidden") !== "true");

      if (focusableElements.length === 0) {
        event.preventDefault();
        dialogRef.current.focus();
        return;
      }

      const firstElement = focusableElements[0];
      const lastElement = focusableElements[focusableElements.length - 1];
      const activeElement = document.activeElement;

      if (event.shiftKey && (activeElement === firstElement || !dialogRef.current.contains(activeElement))) {
        event.preventDefault();
        lastElement.focus();
      } else if (!event.shiftKey && (activeElement === lastElement || !dialogRef.current.contains(activeElement))) {
        event.preventDefault();
        firstElement.focus();
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => {
      window.cancelAnimationFrame(focusFrame);
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = previousBodyOverflow;
      if (previouslyFocused?.isConnected) {
        window.requestAnimationFrame(() => previouslyFocused.focus());
      }
    };
  }, [open]);

  if (!open) return null;

  function requestCancel() {
    if (!isSubmitting) onCancel();
  }

  return (
    <div className="confirmationDialogBackdrop" role="presentation">
      <div
        ref={dialogRef}
        className="confirmationDialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={descriptionId}
        aria-busy={isSubmitting}
        tabIndex={-1}
      >
        <header className="confirmationDialogHeader">
          <div>
            <h2 id={titleId}>{title}</h2>
            <p id={descriptionId}>{description}</p>
          </div>
          <button
            type="button"
            className="confirmationDialogClose"
            aria-label="確認画面を閉じる"
            onClick={requestCancel}
            disabled={isSubmitting}
          >
            ×
          </button>
        </header>
        <div className="confirmationDialogContent">{children}</div>
        <footer className="confirmationDialogActions">
          <button
            ref={cancelButtonRef}
            type="button"
            className="secondaryButton"
            onClick={requestCancel}
            disabled={isSubmitting}
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            className="primaryButton"
            onClick={onConfirm}
            disabled={isSubmitting}
          >
            {isSubmitting ? "送信中…" : confirmLabel}
          </button>
        </footer>
      </div>
    </div>
  );
}

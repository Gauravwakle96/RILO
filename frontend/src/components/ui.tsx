import { useEffect, useId, useRef } from "react";
import type { ButtonHTMLAttributes, ReactNode } from "react";
import {
  AlertCircle,
  ArrowRight,
  Check,
  CheckCircle2,
  CircleDashed,
  Loader2,
  X,
} from "lucide-react";
import { human } from "../lib/format";
import { containDialogFocus } from "../lib/dialog";

export function Button({
  children,
  variant = "secondary",
  busy,
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  busy?: boolean;
}) {
  return (
    <button
      className={`button button-${variant} ${className}`}
      {...props}
      disabled={props.disabled || busy}
    >
      {busy && <Loader2 size={15} className="spin" aria-hidden="true" />}
      {children}
    </button>
  );
}

export function Badge({
  status,
  children,
}: {
  status?: string;
  children?: ReactNode;
}) {
  const tone = [
    "completed",
    "pass",
    "passed",
    "healthy",
    "available",
    "ready",
    "connected",
    "ok",
  ].includes(status ?? "")
    ? "good"
    : [
          "fail",
          "failed",
          "error",
          "unavailable",
          "offline",
          "infrastructure_error",
        ].includes(status ?? "")
      ? "bad"
      : ["running", "queued"].includes(status ?? "")
        ? "blue"
        : [
              "inconclusive",
              "partial",
              "cancelled",
              "missing",
              "not_configured",
              "unknown",
            ].includes(status ?? "")
          ? "warning"
          : "neutral";
  return (
    <span className={`badge badge-${tone}`}>
      <span className="status-dot" aria-hidden="true" />
      {children ?? human(status ?? "Unknown")}
    </span>
  );
}

export function PageHeader({
  title,
  description,
  actions,
}: {
  eyebrow?: string;
  title: string;
  description: string;
  actions?: ReactNode;
}) {
  return (
    <header className="page-header">
      <div>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {actions && <div className="header-actions">{actions}</div>}
    </header>
  );
}

export function EmptyState({
  title,
  description,
  action,
  icon,
}: {
  title: string;
  description: string;
  action?: ReactNode;
  icon?: ReactNode;
}) {
  return (
    <div className="empty-state">
      <div className="empty-icon">{icon ?? <CircleDashed size={26} />}</div>
      <h2>{title}</h2>
      <p>{description}</p>
      {action}
    </div>
  );
}

export function Notice({
  children,
  kind = "info",
  onDismiss,
}: {
  children: ReactNode;
  kind?: "info" | "error" | "warning" | "success";
  onDismiss?: () => void;
}) {
  return (
    <div
      className={`notice notice-${kind}`}
      role={kind === "error" ? "alert" : "status"}
    >
      {kind === "success" ? (
        <CheckCircle2 size={17} aria-hidden="true" />
      ) : (
        <AlertCircle size={17} aria-hidden="true" />
      )}
      <div>{children}</div>
      {onDismiss && (
        <button
          className="icon-button"
          aria-label="Dismiss notification"
          onClick={onDismiss}
        >
          <X size={15} />
        </button>
      )}
    </div>
  );
}

export function Skeleton({ rows = 4 }: { rows?: number }) {
  return (
    <div
      className="skeleton-stack"
      role="status"
      aria-label="Loading workspace"
    >
      <span className="sr-only">Loading workspace…</span>
      {Array.from({ length: rows }, (_, index) => (
        <div className="skeleton-row" key={index}>
          <span />
          <span />
          <span />
        </div>
      ))}
    </div>
  );
}

export function Modal({
  title,
  description,
  children,
  onClose,
  wide = false,
}: {
  title: string;
  description?: string;
  children: ReactNode;
  onClose: () => void;
  wide?: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const returnFocus = useRef(document.activeElement as HTMLElement | null);
  const titleId = useId();
  useEffect(() => {
    const dialog = ref.current;
    const opener = returnFocus.current;
    const old = document.body.style.overflow;
    dialog?.showModal();
    dialog?.querySelector<HTMLElement>("input, textarea, select")?.focus();
    const releaseFocus = containDialogFocus(dialog);
    document.body.style.overflow = "hidden";
    return () => {
      releaseFocus();
      dialog?.close();
      document.body.style.overflow = old;
      if (opener?.isConnected) opener.focus();
    };
  }, []);
  return (
    <dialog
      ref={ref}
      className={`modal ${wide ? "modal-wide" : ""}`}
      aria-labelledby={titleId}
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
      onClick={(event) => {
        if (event.target === ref.current) {
          const rect = ref.current.getBoundingClientRect();
          if (
            event.clientX < rect.left ||
            event.clientX > rect.right ||
            event.clientY < rect.top ||
            event.clientY > rect.bottom
          )
            onClose();
        }
      }}
    >
      <div className="modal-header">
        <div>
          <h2 id={titleId}>{title}</h2>
          {description && <p>{description}</p>}
        </div>
        <button
          className="icon-button"
          aria-label="Close dialog"
          onClick={onClose}
        >
          <X size={20} />
        </button>
      </div>
      {children}
    </dialog>
  );
}

export function Metric({
  label,
  value,
  detail,
  icon,
}: {
  label: string;
  value: ReactNode;
  detail: ReactNode;
  icon?: ReactNode;
}) {
  return (
    <div className="metric">
      <div className="metric-label">
        {label}
        {icon}
      </div>
      <strong className="metric-value">{value}</strong>
      <div className="metric-detail">{detail}</div>
    </div>
  );
}

export function SectionTitle({
  title,
  caption,
  actions,
}: {
  title: string;
  caption?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="section-title">
      <div>
        <h2>{title}</h2>
        {caption && <p>{caption}</p>}
      </div>
      {actions}
    </div>
  );
}

export function SelectCard({
  checked,
  onChange,
  title,
  description,
  icon,
  disabled = false,
}: {
  checked: boolean;
  onChange: () => void;
  title: string;
  description?: string;
  icon?: ReactNode;
  disabled?: boolean;
}) {
  return (
    <label
      className={`select-card ${checked ? "selected" : ""} ${disabled ? "disabled" : ""}`}
    >
      <input
        type="checkbox"
        checked={checked}
        onChange={onChange}
        disabled={disabled}
      />
      <span className="selection-mark" aria-hidden="true">
        {checked && <Check size={12} />}
      </span>
      {icon && <span className="selection-icon">{icon}</span>}
      <span>
        <strong>{title}</strong>
        {description && <small>{description}</small>}
      </span>
    </label>
  );
}

export function LinkAction({
  children,
  onClick,
}: {
  children: ReactNode;
  onClick: () => void;
}) {
  return (
    <button className="text-action" onClick={onClick}>
      {children}
      <ArrowRight size={14} />
    </button>
  );
}

export function JsonBlock({ value }: { value: unknown }) {
  return <pre className="json-block">{JSON.stringify(value, null, 2)}</pre>;
}

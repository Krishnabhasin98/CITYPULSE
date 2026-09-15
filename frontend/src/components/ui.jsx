/**
 * Shared UI primitives.
 *
 * One place defines buttons, cards, badges, skeletons and states so every page
 * looks and behaves the same — including the loading, empty and error paths,
 * which is what made the earlier UI feel half-finished.
 */
import { AlertTriangle, ChevronDown, Loader2, RefreshCw, Wifi, WifiOff } from "lucide-react";
import { useEffect } from "react";

export const cx = (...classes) => classes.filter(Boolean).join(" ");

// ---------------------------------------------------------------------------
// Tone system
// ---------------------------------------------------------------------------
const TONES = {
  critical: { chip: "bg-red-50 text-red-700 border-red-200", bar: "bg-red-500", text: "text-red-700", ring: "#C73E3E" },
  high: { chip: "bg-amber-50 text-amber-800 border-amber-200", bar: "bg-amber-500", text: "text-amber-700", ring: "#B7791F" },
  medium: { chip: "bg-sky-50 text-sky-800 border-sky-200", bar: "bg-sky-500", text: "text-sky-700", ring: "#0E7490" },
  low: { chip: "bg-emerald-50 text-emerald-800 border-emerald-200", bar: "bg-emerald-500", text: "text-emerald-700", ring: "#18864B" },
  neutral: { chip: "bg-slate-100 text-slate-700 border-slate-200", bar: "bg-slate-400", text: "text-slate-600", ring: "#5B6472" },
  info: { chip: "bg-indigo-50 text-indigo-700 border-indigo-200", bar: "bg-indigo-500", text: "text-indigo-700", ring: "#2457D6" },
};

export const tone = (name) => TONES[name] || TONES.neutral;

// ---------------------------------------------------------------------------
// Buttons
// ---------------------------------------------------------------------------
const BUTTON_VARIANTS = {
  primary: "bg-[var(--color-cobalt)] text-white shadow-sm hover:bg-blue-700 focus-visible:outline-blue-700",
  secondary: "border border-[var(--color-border)] bg-white text-[var(--color-text-primary)] hover:bg-slate-50",
  ghost: "text-[var(--color-text-secondary)] hover:bg-slate-100 hover:text-[var(--color-text-primary)]",
  danger: "bg-red-600 text-white shadow-sm hover:bg-red-700",
  teal: "bg-[var(--color-teal)] text-white shadow-sm hover:bg-teal-800",
};

const BUTTON_SIZES = {
  sm: "px-3 py-1.5 text-xs",
  md: "px-4 py-2 text-sm",
  lg: "px-5 py-3 text-sm",
};

export function Button({
  children,
  variant = "primary",
  size = "md",
  loading = false,
  disabled = false,
  className = "",
  type = "button",
  ...rest
}) {
  return (
    <button
      type={type}
      disabled={disabled || loading}
      className={cx(
        "inline-flex items-center justify-center gap-2 rounded-lg font-semibold transition disabled:cursor-not-allowed disabled:opacity-60",
        BUTTON_VARIANTS[variant] || BUTTON_VARIANTS.primary,
        BUTTON_SIZES[size] || BUTTON_SIZES.md,
        className,
      )}
      {...rest}
    >
      {loading && <Loader2 size={15} className="animate-spin" />}
      {children}
    </button>
  );
}

export function RefreshButton({ onClick, loading, label = "Refresh" }) {
  return (
    <Button variant="secondary" size="sm" onClick={onClick} disabled={loading}>
      <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
      {label}
    </Button>
  );
}

// ---------------------------------------------------------------------------
// Layout
// ---------------------------------------------------------------------------
export function Card({ children, className = "", as: Tag = "div", ...rest }) {
  return (
    <Tag
      className={cx(
        "rounded-2xl border border-[var(--color-border)] bg-white shadow-[0_1px_2px_rgba(15,23,42,0.04)]",
        className,
      )}
      {...rest}
    >
      {children}
    </Tag>
  );
}

export function CardHeader({ title, subtitle, icon: Icon, action, className = "" }) {
  return (
    <div className={cx("flex flex-wrap items-start justify-between gap-3 border-b border-slate-100 px-5 py-4", className)}>
      <div className="flex items-start gap-3">
        {Icon && (
          <span className="mt-0.5 flex h-8 w-8 items-center justify-center rounded-lg bg-slate-100 text-[var(--color-cobalt)]">
            <Icon size={16} />
          </span>
        )}
        <div>
          <h2 className="text-sm font-bold text-[var(--color-ink)]">{title}</h2>
          {subtitle && <p className="mt-0.5 text-xs text-[var(--color-text-secondary)]">{subtitle}</p>}
        </div>
      </div>
      {action}
    </div>
  );
}

export function PageHeader({ eyebrow, title, description, actions, children }) {
  return (
    <header className="mb-6">
      {eyebrow && (
        <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-[var(--color-cobalt)]">{eyebrow}</p>
      )}
      <div className="mt-1 flex flex-wrap items-start justify-between gap-3">
        <div className="max-w-3xl">
          <h1 className="text-2xl font-bold tracking-tight text-[var(--color-ink)] sm:text-3xl">{title}</h1>
          {description && (
            <p className="mt-2 text-sm leading-relaxed text-[var(--color-text-secondary)]">{description}</p>
          )}
        </div>
        {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
      </div>
      {children}
    </header>
  );
}

export function SectionTitle({ title, subtitle, action, className = "" }) {
  return (
    <div className={cx("mb-3 flex flex-wrap items-end justify-between gap-2", className)}>
      <div>
        <h2 className="text-sm font-bold uppercase tracking-wider text-[var(--color-ink)]">{title}</h2>
        {subtitle && <p className="mt-0.5 text-xs text-[var(--color-text-secondary)]">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}

export function Divider({ className = "" }) {
  return <div className={cx("h-px bg-slate-100", className)} />;
}

// ---------------------------------------------------------------------------
// Data display
// ---------------------------------------------------------------------------
export function Badge({ children, tone: toneName = "neutral", icon: Icon, className = "" }) {
  const styles = tone(toneName);
  return (
    <span
      className={cx(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[11px] font-bold",
        styles.chip,
        className,
      )}
    >
      {Icon && <Icon size={12} />}
      {children}
    </span>
  );
}

export function Stat({ label, value, hint, tone: toneName = "neutral", icon: Icon, className = "" }) {
  const styles = tone(toneName);
  return (
    <Card className={cx("px-4 py-3.5", className)}>
      <div className="flex items-center justify-between gap-2">
        <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--color-text-muted)]">{label}</span>
        {Icon && <Icon size={15} className={styles.text} />}
      </div>
      <p className="mt-1.5 text-2xl font-black leading-none text-[var(--color-ink)]">{value}</p>
      {hint && <p className="mt-1.5 text-xs text-[var(--color-text-secondary)]">{hint}</p>}
    </Card>
  );
}

export function Progress({ value, tone: toneName = "info", className = "", height = "h-2" }) {
  const clamped = Math.max(0, Math.min(100, Number(value) || 0));
  return (
    <div className={cx("w-full overflow-hidden rounded-full bg-slate-100", height, className)}>
      <div
        className={cx("h-full rounded-full transition-all duration-500", tone(toneName).bar)}
        style={{ width: `${clamped}%` }}
      />
    </div>
  );
}

export function ScoreRing({ value, size = 116, label, sublabel, tone: toneName }) {
  const score = Math.max(0, Math.min(100, Number(value) || 0));
  const stroke = size / 10;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const color = tone(toneName || (score >= 80 ? "critical" : score >= 65 ? "high" : score >= 45 ? "medium" : "low")).ring;
  return (
    <div className="flex flex-col items-center">
      <svg width={size} height={size} className="-rotate-90" role="img" aria-label={`${label || "Score"}: ${score}`}>
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="#EEF1F5" strokeWidth={stroke} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={circumference * (1 - score / 100)}
          style={{ transition: "stroke-dashoffset 700ms ease" }}
        />
      </svg>
      <div className="-mt-[calc(50%+6px)] mb-[calc(50%-22px)] text-center">
        <p className="text-3xl font-black leading-none text-[var(--color-ink)]">{Math.round(score)}</p>
        {label && <p className="mt-1 text-[10px] font-bold uppercase tracking-wider text-[var(--color-text-muted)]">{label}</p>}
      </div>
      {sublabel && <p className="mt-2 text-xs text-[var(--color-text-secondary)]">{sublabel}</p>}
    </div>
  );
}

export function KeyValue({ label, value, tone: toneName, className = "" }) {
  return (
    <div className={cx("flex items-center justify-between gap-3 py-1.5 text-xs", className)}>
      <span className="text-[var(--color-text-secondary)]">{label}</span>
      <span className={cx("font-semibold text-[var(--color-ink)]", toneName && tone(toneName).text)}>{value}</span>
    </div>
  );
}

export function SourceChip({ meta, label, className = "" }) {
  if (!meta) return null;
  const source = meta.source || "unavailable";
  const map = {
    live: { tone: "low", text: `${label || "Live"}`, Icon: Wifi },
    cache: { tone: "medium", text: `${label || "Cached"}${meta.age_seconds ? ` · ${Math.round(meta.age_seconds / 60)}m old` : ""}`, Icon: Wifi },
    offline: { tone: "medium", text: `${label || "Offline"} data`, Icon: WifiOff },
    unavailable: { tone: "critical", text: `${label || "Unavailable"}`, Icon: WifiOff },
  };
  const entry = map[source] || map.unavailable;
  return (
    <Badge tone={entry.tone} icon={entry.Icon} className={className}>
      {entry.text}
    </Badge>
  );
}

export function LiveDot({ label = "Live", className = "" }) {
  return (
    <span className={cx("inline-flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wider text-[var(--color-teal)]", className)}>
      <span className="relative flex h-2 w-2">
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[var(--color-teal)] opacity-60" />
        <span className="relative inline-flex h-2 w-2 rounded-full bg-[var(--color-teal)]" />
      </span>
      {label}
    </span>
  );
}

// ---------------------------------------------------------------------------
// States
// ---------------------------------------------------------------------------
export function Skeleton({ className = "" }) {
  return <div className={cx("animate-pulse rounded-lg bg-slate-100", className)} />;
}

export function SkeletonCards({ count = 3, className = "" }) {
  return (
    <div className={cx("grid gap-3 sm:grid-cols-2 lg:grid-cols-3", className)}>
      {Array.from({ length: count }).map((_, index) => (
        <Card key={index} className="p-4">
          <Skeleton className="h-3 w-24" />
          <Skeleton className="mt-3 h-7 w-16" />
          <Skeleton className="mt-3 h-3 w-full" />
        </Card>
      ))}
    </div>
  );
}

export function SkeletonRows({ count = 4, className = "" }) {
  return (
    <div className={cx("space-y-3", className)}>
      {Array.from({ length: count }).map((_, index) => (
        <Card key={index} className="p-4">
          <div className="flex gap-4">
            <Skeleton className="h-20 w-28 shrink-0" />
            <div className="flex-1 space-y-2">
              <Skeleton className="h-3 w-32" />
              <Skeleton className="h-4 w-3/4" />
              <Skeleton className="h-3 w-1/2" />
            </div>
          </div>
        </Card>
      ))}
    </div>
  );
}

export function Spinner({ className = "", size = 18 }) {
  return <Loader2 size={size} className={cx("animate-spin text-[var(--color-text-muted)]", className)} />;
}

export function EmptyState({ icon: Icon = AlertTriangle, title, message, action, className = "" }) {
  return (
    <Card className={cx("flex flex-col items-center px-6 py-12 text-center", className)}>
      <span className="flex h-11 w-11 items-center justify-center rounded-full bg-slate-100 text-[var(--color-text-muted)]">
        <Icon size={20} />
      </span>
      <h3 className="mt-4 text-sm font-bold text-[var(--color-ink)]">{title}</h3>
      {message && <p className="mt-1 max-w-md text-xs leading-relaxed text-[var(--color-text-secondary)]">{message}</p>}
      {action && <div className="mt-4">{action}</div>}
    </Card>
  );
}

export function ErrorState({ error, onRetry, title = "Something went wrong" }) {
  const message =
    typeof error === "string"
      ? error
      : error?.message || "The request failed. Check that the API is running.";
  return (
    <Card className="border-red-200 bg-red-50/60 px-5 py-5">
      <div className="flex items-start gap-3">
        <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-red-100 text-red-600">
          <AlertTriangle size={16} />
        </span>
        <div className="flex-1">
          <h3 className="text-sm font-bold text-red-900">{title}</h3>
          <p className="mt-1 text-xs leading-relaxed text-red-800">{message}</p>
          {onRetry && (
            <Button variant="secondary" size="sm" className="mt-3" onClick={onRetry}>
              <RefreshCw size={14} /> Try again
            </Button>
          )}
        </div>
      </div>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Forms
// ---------------------------------------------------------------------------
export function Field({ label, hint, error, required, children, className = "" }) {
  return (
    <label className={cx("block", className)}>
      <span className="mb-1.5 flex items-center gap-1 text-xs font-bold text-[var(--color-text-primary)]">
        {label}
        {required && <span className="text-red-500">*</span>}
      </span>
      {children}
      {hint && !error && <span className="mt-1 block text-[11px] text-[var(--color-text-muted)]">{hint}</span>}
      {error && <span className="mt-1 block text-[11px] font-semibold text-red-600">{error}</span>}
    </label>
  );
}

const INPUT_CLASS =
  "w-full rounded-lg border border-[var(--color-border)] bg-white px-3 py-2.5 text-sm text-[var(--color-text-primary)] outline-none transition placeholder:text-slate-400 focus:border-[var(--color-cobalt)] focus:ring-2 focus:ring-blue-100 disabled:bg-slate-50";

export function Input({ className = "", ...rest }) {
  return <input className={cx(INPUT_CLASS, className)} {...rest} />;
}

export function Textarea({ className = "", rows = 4, ...rest }) {
  return <textarea rows={rows} className={cx(INPUT_CLASS, "resize-y", className)} {...rest} />;
}

export function Select({ className = "", children, ...rest }) {
  return (
    <div className="relative">
      <select className={cx(INPUT_CLASS, "appearance-none pr-9", className)} {...rest}>
        {children}
      </select>
      <ChevronDown size={15} className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-slate-400" />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tabs & modal
// ---------------------------------------------------------------------------
export function Tabs({ tabs, value, onChange, className = "" }) {
  return (
    <div className={cx("flex gap-1.5 overflow-x-auto pb-1", className)} role="tablist">
      {tabs.map((tab) => {
        const active = tab.value === value;
        return (
          <button
            key={tab.value}
            role="tab"
            aria-selected={active}
            onClick={() => onChange(tab.value)}
            className={cx(
              "whitespace-nowrap rounded-lg px-3.5 py-1.5 text-xs font-semibold transition",
              active
                ? "bg-[var(--color-ink)] text-white shadow-sm"
                : "border border-[var(--color-border)] bg-white text-[var(--color-text-secondary)] hover:bg-slate-50",
            )}
          >
            {tab.label}
            {tab.count !== undefined && (
              <span className={cx("ml-1.5 rounded-full px-1.5 py-0.5 text-[10px]", active ? "bg-white/20" : "bg-slate-100")}>
                {tab.count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}

export function Modal({ open, onClose, title, description, children, footer, wide = false }) {
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (event) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-slate-950/50 p-0 backdrop-blur-sm sm:items-center sm:p-4">
      <div
        className={cx(
          "max-h-[92vh] w-full overflow-y-auto rounded-t-2xl border border-[var(--color-border)] bg-white shadow-2xl sm:rounded-2xl",
          wide ? "sm:max-w-2xl" : "sm:max-w-lg",
        )}
        role="dialog"
        aria-modal="true"
      >
        <div className="flex items-start justify-between gap-4 border-b border-slate-100 px-5 py-4">
          <div>
            <h3 className="text-base font-bold text-[var(--color-ink)]">{title}</h3>
            {description && <p className="mt-0.5 text-xs text-[var(--color-text-secondary)]">{description}</p>}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1.5 text-slate-400 transition hover:bg-slate-100 hover:text-slate-700"
            aria-label="Close dialog"
          >
            ✕
          </button>
        </div>
        <div className="px-5 py-4">{children}</div>
        {footer && <div className="flex flex-wrap justify-end gap-2 border-t border-slate-100 px-5 py-4">{footer}</div>}
      </div>
    </div>
  );
}

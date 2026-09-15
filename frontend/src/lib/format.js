/** Shared display formatting so numbers and labels stay consistent. */

export function formatNumber(value, digits = 0) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
  return Number(value).toLocaleString("en-IN", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

export function formatScore(value) {
  if (value === null || value === undefined) return "—";
  return Math.round(Number(value)).toString();
}

export function formatPercent(value, digits = 0) {
  if (value === null || value === undefined) return "—";
  return `${Number(value).toFixed(digits)}%`;
}

export function formatRelativeTime(iso) {
  if (!iso) return "unknown";
  const then = new Date(iso.endsWith("Z") || iso.includes("+") ? iso : `${iso}Z`);
  const seconds = Math.max(0, (Date.now() - then.getTime()) / 1000);
  if (seconds < 60) return "just now";
  const minutes = seconds / 60;
  if (minutes < 60) return `${Math.round(minutes)} min ago`;
  const hours = minutes / 60;
  if (hours < 24) return `${Math.round(hours)}h ago`;
  const days = hours / 24;
  if (days < 30) return `${Math.round(days)}d ago`;
  return then.toLocaleDateString("en-IN", { day: "numeric", month: "short" });
}

export function formatDateTime(iso) {
  if (!iso) return "—";
  const value = new Date(iso.endsWith("Z") || iso.includes("+") ? iso : `${iso}Z`);
  return value.toLocaleString("en-IN", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatHours(hours) {
  if (hours === null || hours === undefined) return "—";
  const value = Math.abs(Number(hours));
  if (value < 1) return `${Math.round(value * 60)} min`;
  if (value < 48) return `${value % 1 === 0 ? value : value.toFixed(1)} h`;
  return `${(value / 24).toFixed(1)} d`;
}

export const SEVERITY_TONE = (severity) => {
  const value = Number(severity) || 0;
  if (value >= 80) return "critical";
  if (value >= 65) return "high";
  if (value >= 45) return "medium";
  return "low";
};

export const SEVERITY_LABEL = (severity) => {
  const tone = SEVERITY_TONE(severity);
  return { critical: "Critical", high: "High", medium: "Medium", low: "Low" }[tone];
};

export const BAND_TONE = (band) => {
  const value = (band || "").toString().toUpperCase();
  if (value === "CRITICAL" || value === "UNHEALTHY") return "critical";
  if (value === "HIGH" || value === "ELEVATED") return "high";
  if (value === "MODERATE" || value === "NORMAL" || value === "WATCH") return "medium";
  if (value === "LOW" || value === "HEALTHY" || value === "IMPROVING" || value === "STABLE") return "low";
  return "neutral";
};

export const SLA_TONE = (state) => {
  switch (state) {
    case "breached":
      return "critical";
    case "due_soon":
      return "high";
    case "on_track":
      return "low";
    case "closed":
      return "neutral";
    default:
      return "neutral";
  }
};

export const SLA_LABEL = (state) => {
  switch (state) {
    case "breached":
      return "SLA breached";
    case "due_soon":
      return "Due soon";
    case "on_track":
      return "On track";
    case "closed":
      return "Closed";
    default:
      return "No deadline";
  }
};

export const TRUST_TONE = (status) => {
  switch (status) {
    case "Verified":
      return "low";
    case "Suspicious":
      return "critical";
    case "Needs Verification":
      return "medium";
    default:
      return "neutral";
  }
};

/** Category → accent colour, used for chips and charts. */
export const CATEGORY_COLORS = {
  Infrastructure: "#2457D6",
  Electricity: "#B7791F",
  Sanitation: "#167C80",
  Water: "#0E7490",
  "Public Safety": "#C73E3E",
  Overall: "#5B6472",
};

export const categoryColor = (category) => CATEGORY_COLORS[category] || "#5B6472";

/** A stable, data-independent placeholder so cards never show a broken image. */
export const PLACEHOLDER_BY_CATEGORY = {
  Infrastructure: "/placeholders/infrastructure.svg",
  Electricity: "/placeholders/electricity.svg",
  Sanitation: "/placeholders/sanitation.svg",
  Water: "/placeholders/water.svg",
  "Public Safety": "/placeholders/safety.svg",
};

export const placeholderFor = (category) =>
  PLACEHOLDER_BY_CATEGORY[category] || "/placeholders/generic.svg";

export function titleCase(text) {
  if (!text) return "";
  return text
    .toString()
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

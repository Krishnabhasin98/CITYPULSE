import { Clock, Eye, Flag, MapPin, MessageSquarePlus, ThumbsUp, Users } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { apiPost, endpoints } from "../../lib/api";
import {
  SLA_LABEL,
  SLA_TONE,
  TRUST_TONE,
  formatHours,
  formatRelativeTime,
  titleCase,
} from "../../lib/format";
import { useSession } from "../../lib/session";
import { useToast } from "../../lib/toast";
import EvidenceImage from "../EvidenceImage";
import { Badge, Button, Card, Progress, cx } from "../ui";

export default function IncidentCard({ incident, onActionComplete, compact = false }) {
  const { user } = useSession();
  const toast = useToast();
  const [busy, setBusy] = useState(null);
  const [local, setLocal] = useState(incident);

  const current = local || incident;
  const sla = current.sla || { state: "unknown", label: "No deadline" };

  const act = async (actionType, label) => {
    if (!user) {
      toast.info("Sign in to act on this incident");
      return;
    }
    setBusy(actionType);
    try {
      const result = await apiPost(endpoints.actions(current.id), {
        action_type: actionType,
        description: `${label} from ${user.name}`,
      });
      setLocal(result.incident);
      if (result.credits_released) {
        toast.success(`${label} recorded`, `+${result.credits_awarded} credits added to your balance.`);
      } else {
        toast.info(`${label} recorded`, "Another citizen or an authority confirms it before credits are paid.");
      }
      onActionComplete?.();
    } catch (error) {
      if (error.status === 409) toast.info("Already recorded", error.message);
      else toast.error("Action failed", error.message);
    } finally {
      setBusy(null);
    }
  };

  return (
    <Card className="overflow-hidden transition hover:border-slate-300">
      <div className={cx("flex flex-col gap-4 p-4", compact ? "" : "sm:flex-row")}>
        <EvidenceImage
          src={current.primary_image_url}
          category={current.category}
          alt={current.title}
          className={cx("shrink-0 rounded-xl", compact ? "h-36 w-full sm:h-32 sm:w-44" : "h-40 w-full sm:h-28 sm:w-40")}
          imgClassName="object-cover"
        />

        <div className="flex min-w-0 flex-1 flex-col justify-between">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="info">{titleCase(current.category)}</Badge>
              <Badge tone={TRUST_TONE(current.trust_status)}>{current.trust_status}</Badge>
              <Badge tone={SLA_TONE(sla.state)} icon={Clock}>
                {SLA_LABEL(sla.state)}
                {sla.state === "breached" ? ` · ${formatHours(sla.hours_overdue)} over` : ""}
                {sla.state === "on_track" || sla.state === "due_soon" ? ` · ${formatHours(sla.hours_remaining)} left` : ""}
              </Badge>
            </div>

            <h3 className="mt-2 text-base font-bold leading-snug text-[var(--color-ink)]">
              <Link to={`/incidents/${current.id}`} className="hover:text-[var(--color-cobalt)]">
                {current.title}
              </Link>
            </h3>

            <p className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-[var(--color-text-secondary)]">
              <span className="inline-flex items-center gap-1">
                <MapPin size={13} className="text-[var(--color-text-muted)]" />
                {current.affected_area || "Delhi"}
              </span>
              {current.pincode && <span className="text-[var(--color-text-muted)]">PIN {current.pincode}</span>}
              <span className="text-[var(--color-text-muted)]">{formatRelativeTime(current.first_report_at)}</span>
            </p>
          </div>

          <div className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1 text-xs font-medium text-[var(--color-text-muted)] sm:grid-cols-4">
            <span>
              <strong className="text-[var(--color-ink)]">{current.report_count}</strong> report(s)
            </span>
            <span>
              <strong className="text-[var(--color-ink)]">{current.support_count}</strong> confirmed
            </span>
            <span>
              <strong className="text-[var(--color-ink)]">{current.evidence_count}</strong> evidence
            </span>
            <span>
              severity <strong className="text-[var(--color-ink)]">{Math.round(current.severity)}</strong>
            </span>
          </div>

          <div className="mt-2.5">
            <Progress
              value={current.severity}
              tone={current.severity >= 80 ? "critical" : current.severity >= 65 ? "high" : current.severity >= 45 ? "medium" : "low"}
              height="h-1.5"
            />
            <div className="mt-1 flex flex-wrap items-center justify-between gap-2 text-[11px] text-[var(--color-text-muted)]">
              <span>
                {current.priority_level} priority · respond within {current.action_sla_hours}h
              </span>
              {current.report_count > 1 && (
                <span className="font-semibold text-[var(--color-cobalt)]">
                  {current.report_count} reports merged into 1 incident
                </span>
              )}
            </div>
          </div>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2 border-t border-slate-100 bg-slate-50/60 px-4 py-2.5 text-xs">
        <Button
          variant="secondary"
          size="sm"
          loading={busy === "support"}
          onClick={() => act("support", "Confirmed on ground")}
          title="Confirm this problem is real (once per incident)"
        >
          <ThumbsUp size={14} /> Confirm
        </Button>
        <Button
          variant="secondary"
          size="sm"
          loading={busy === "verify"}
          onClick={() => act("verify", "Verified on ground")}
          title="Independent on-ground verification"
        >
          <Eye size={14} /> Verify
        </Button>
        <Button
          variant="ghost"
          size="sm"
          loading={busy === "flag"}
          onClick={() => act("flag", "Flagged as inaccurate")}
          title="Report inaccurate or suspicious evidence"
        >
          <Flag size={14} /> Flag
        </Button>
        <Link to={`/incidents/${current.id}`} className="ml-auto">
          <Button size="sm">
            <MessageSquarePlus size={14} /> Help / details
          </Button>
        </Link>
        <span className="inline-flex items-center gap-1 text-[11px] text-[var(--color-text-muted)]">
          <Users size={12} /> {current.zone || "Delhi"}
        </span>
      </div>
    </Card>
  );
}

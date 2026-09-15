import { AlertTriangle, CheckCircle2, Clock, ClipboardCheck, ShieldCheck, X } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  PageHeader,
  Progress,
  RefreshButton,
  SectionTitle,
  SkeletonRows,
  Stat,
  Tabs,
  cx,
} from "../components/ui";
import { apiGet, apiPost, endpoints } from "../lib/api";
import { SLA_LABEL, SLA_TONE, formatHours, formatNumber, formatRelativeTime } from "../lib/format";
import { useApiData } from "../lib/hooks";
import { useSession } from "../lib/session";
import { useToast } from "../lib/toast";

export default function AuthorityDashboard() {
  const { isAuthority, user } = useSession();
  const toast = useToast();
  const [filter, setFilter] = useState("all");
  const [busy, setBusy] = useState(null);

  const queue = useApiData(() => apiGet(endpoints.queue(100)), []);
  const pending = useApiData(() => apiGet(endpoints.actionsPending()), []);
  const departments = useApiData(() => apiGet(endpoints.departments()), []);
  const scorecard = useApiData(() => apiGet(endpoints.scorecard()), []);

  const reload = () => {
    queue.reload();
    pending.reload();
    departments.reload();
    scorecard.reload();
  };

  const rows = useMemo(() => queue.data || [], [queue.data]);
  const filtered = useMemo(() => {
    if (filter === "breached") return rows.filter((row) => row.sla.state === "breached");
    if (filter === "open") return rows.filter((row) => !["resolved", "closed"].includes(row.status));
    if (filter === "resolved") return rows.filter((row) => ["resolved", "closed"].includes(row.status));
    return rows;
  }, [rows, filter]);

  const decide = async (action, approve) => {
    setBusy(`${action.action_id}-${approve}`);
    try {
      await apiPost(endpoints.verifyAction(action.incident_id, action.action_id), {
        approve,
        note: approve ? "Confirmed at the municipal desk" : "Rejected at the municipal desk",
      });
      toast.success(approve ? "Claim confirmed" : "Claim rejected", `“${action.label}” by ${action.claimant}.`);
      reload();
    } catch (error) {
      toast.error("Could not record the decision", error.message);
    } finally {
      setBusy(null);
    }
  };

  const closeIncident = async (incidentId) => {
    setBusy(`close-${incidentId}`);
    try {
      await apiPost(endpoints.resolveIncident(incidentId), { verification_notes: "Closed from the authority console" });
      toast.success("Incident closed", "The deadline clock stopped and the ledger was updated.");
      reload();
    } catch (error) {
      toast.error("Could not close the incident", error.message);
    } finally {
      setBusy(null);
    }
  };

  const summary = scorecard.data?.sla;

  return (
    <>
      <PageHeader
        eyebrow="Accountability"
        title="Municipal dispatch queue"
        description="Ordered by urgency: deadline breaches first, then severity and public corroboration. Citizens see the same deadline data — that is the point."
        actions={<RefreshButton onClick={reload} loading={queue.loading} />}
      />

      {!isAuthority && (
        <Card className="mb-4 border-amber-200 bg-amber-50/70 p-4 text-xs text-amber-900">
          You are signed in as a citizen. You can review the queue and confirm other people's claims, but only an
          authority account can officially close an incident. Demo authority: <strong>authority@citypulse.local</strong> /{" "}
          <strong>password123</strong>.
        </Card>
      )}

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="In queue" value={formatNumber(rows.length)} hint="Clustered incidents, not raw complaints" icon={ClipboardCheck} />
        <Stat
          label="Past deadline"
          value={formatNumber(summary?.breached ?? rows.filter((row) => row.sla.state === "breached").length)}
          hint={summary ? `${formatNumber(summary.overdue_hours)} hours overdue in total` : "—"}
          tone={summary?.breached ? "critical" : "low"}
          icon={Clock}
        />
        <Stat
          label="Due within 6h"
          value={formatNumber(summary?.due_soon ?? 0)}
          hint={`${summary ? formatNumber(summary.compliance_percent) : "—"}% compliance`}
          tone="high"
          icon={AlertTriangle}
        />
        <Stat
          label="Claims to confirm"
          value={formatNumber((pending.data || []).length)}
          hint="Citizen claims holding unreleased credits"
          tone="info"
          icon={ShieldCheck}
        />
      </div>

      <section className="mt-5">
        <SectionTitle
          title={`Claims awaiting confirmation (${(pending.data || []).length})`}
          subtitle="Confirming releases the claimant's credits. You cannot confirm your own claim."
        />
        {pending.error ? (
          <ErrorState error={pending.error} onRetry={pending.reload} />
        ) : pending.loading && !pending.data ? (
          <SkeletonRows count={2} />
        ) : (pending.data || []).length ? (
          <div className="space-y-2">
            {pending.data.map((action) => {
              const blocked = action.is_mine || (action.requires_authority && !isAuthority);
              return (
                <Card key={action.action_id} className="p-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge tone="medium">{action.label}</Badge>
                        <Badge tone="neutral">{action.credits} credits pending</Badge>
                        {action.requires_authority && <Badge tone="info">authority-only</Badge>}
                        {action.is_mine && <Badge tone="neutral">your claim</Badge>}
                      </div>
                      <p className="mt-2 text-sm font-bold text-[var(--color-ink)]">{action.incident_title}</p>
                      <p className="text-[11px] text-[var(--color-text-secondary)]">
                        {action.claimant} · {action.affected_area} · {formatRelativeTime(action.created_at)}
                      </p>
                      <p className="mt-1 text-xs text-[var(--color-text-secondary)]">{action.description}</p>
                      {action.evidence_url && (
                        <a
                          href={action.evidence_url}
                          target="_blank"
                          rel="noreferrer"
                          className="mt-2 inline-block text-[11px] font-semibold text-[var(--color-cobalt)]"
                        >
                          View attached evidence
                        </a>
                      )}
                    </div>
                    <div className="flex shrink-0 gap-2">
                      <Link to={`/incidents/${action.incident_id}`}>
                        <Button variant="secondary" size="sm">
                          Open incident
                        </Button>
                      </Link>
                      <Button
                        size="sm"
                        disabled={blocked}
                        loading={busy === `${action.action_id}-true`}
                        onClick={() => decide(action, true)}
                        title={blocked ? "You cannot confirm this claim" : "Confirm and release credits"}
                      >
                        <CheckCircle2 size={14} /> Confirm
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        disabled={action.is_mine}
                        loading={busy === `${action.action_id}-false`}
                        onClick={() => decide(action, false)}
                      >
                        <X size={14} /> Reject
                      </Button>
                    </div>
                  </div>
                </Card>
              );
            })}
          </div>
        ) : (
          <EmptyState title="No claims waiting" message="Every citizen contribution has been reviewed. Claims appear here as soon as someone submits one." />
        )}
      </section>

      <section className="mt-6">
        <SectionTitle
          title="Dispatch queue"
          subtitle="Urgency = priority score + breach penalty + corroboration"
          action={
            <Tabs
              value={filter}
              onChange={setFilter}
              tabs={[
                { value: "all", label: "All", count: rows.length },
                { value: "breached", label: "Breached", count: rows.filter((row) => row.sla.state === "breached").length },
                { value: "open", label: "Open" },
                { value: "resolved", label: "Closed" },
              ]}
            />
          }
        />

        {queue.error ? (
          <ErrorState error={queue.error} onRetry={queue.reload} />
        ) : queue.loading && !rows.length ? (
          <SkeletonRows count={4} />
        ) : (
          <Card className="overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[880px] text-left text-xs">
                <thead className="bg-slate-50 text-[10px] uppercase tracking-wider text-[var(--color-text-muted)]">
                  <tr>
                    <th className="px-4 py-3">Urgency</th>
                    <th className="px-4 py-3">Incident</th>
                    <th className="px-4 py-3">Department</th>
                    <th className="px-4 py-3">Deadline</th>
                    <th className="px-4 py-3">Severity</th>
                    <th className="px-4 py-3">Evidence</th>
                    <th className="px-4 py-3"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {filtered.map((row) => (
                    <tr key={row.incident_id} className={cx("hover:bg-slate-50/60", row.sla.state === "breached" && "bg-red-50/40")}>
                      <td className="px-4 py-3">
                        <span className="text-sm font-black text-[var(--color-ink)]">{formatNumber(row.urgency, 1)}</span>
                      </td>
                      <td className="max-w-[260px] px-4 py-3">
                        <Link to={`/incidents/${row.incident_id}`} className="font-bold text-[var(--color-ink)] hover:text-[var(--color-cobalt)]">
                          {row.title}
                        </Link>
                        <span className="mt-0.5 block text-[10px] text-[var(--color-text-muted)]">
                          {row.affected_area} · {row.report_count} report(s) · {row.trust_status}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <Badge tone="neutral">{row.department}</Badge>
                      </td>
                      <td className="px-4 py-3">
                        <Badge tone={SLA_TONE(row.sla.state)} icon={Clock}>
                          {SLA_LABEL(row.sla.state)}
                        </Badge>
                        <span className="mt-1 block text-[10px] text-[var(--color-text-muted)]">
                          {row.sla.state === "breached"
                            ? `${formatHours(row.sla.hours_overdue)} late`
                            : `${formatHours(row.sla.hours_remaining)} left of ${row.sla.sla_hours}h`}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <span className="w-8 font-bold text-[var(--color-ink)]">{formatNumber(row.severity)}</span>
                          <Progress
                            value={row.severity}
                            tone={row.severity >= 80 ? "critical" : row.severity >= 65 ? "high" : "medium"}
                            height="h-1.5"
                            className="w-16"
                          />
                        </div>
                        <span className="mt-1 block text-[10px] text-[var(--color-text-muted)]">{row.priority_level}</span>
                      </td>
                      <td className="px-4 py-3">
                        <span className="text-[11px] text-[var(--color-text-secondary)]">
                          {row.support_count} confirmed · {row.report_count} report(s)
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right">
                        {["resolved", "closed"].includes(row.status) ? (
                          <Badge tone="low">closed</Badge>
                        ) : isAuthority ? (
                          <Button
                            size="sm"
                            variant="teal"
                            loading={busy === `close-${row.incident_id}`}
                            onClick={() => closeIncident(row.incident_id)}
                          >
                            <ShieldCheck size={13} /> Resolve
                          </Button>
                        ) : (
                          <Link to={`/incidents/${row.incident_id}`}>
                            <Button size="sm" variant="secondary">
                              Open
                            </Button>
                          </Link>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        )}
      </section>

      <section className="mt-6">
        <SectionTitle
          title="Department workload"
          subtitle={`Signed in as ${user?.name || "guest"} · accountability scores blend compliance, resolution and citizen verification`}
          action={
            <Link to="/departments">
              <Button variant="secondary" size="sm">
                Full ledger
              </Button>
            </Link>
          }
        />
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {(departments.data || []).slice(0, 6).map((row) => (
            <Card key={row.department} className="p-4">
              <div className="flex items-center justify-between">
                <p className="text-sm font-bold text-[var(--color-ink)]">{row.department}</p>
                <Badge tone={row.breached ? "critical" : "low"}>{row.breached} breached</Badge>
              </div>
              <div className="mt-2 space-y-1.5 text-[11px] text-[var(--color-text-secondary)]">
                <div className="flex justify-between">
                  <span>Received / resolved</span>
                  <span className="font-semibold text-[var(--color-ink)]">
                    {row.received} / {row.resolved}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>SLA compliance</span>
                  <span className="font-semibold text-[var(--color-ink)]">{formatNumber(row.sla_compliance)}%</span>
                </div>
                <Progress value={row.sla_compliance} tone={row.breached ? "high" : "low"} height="h-1.5" />
                <div className="flex justify-between">
                  <span>Accountability</span>
                  <span className="font-semibold text-[var(--color-ink)]">{formatNumber(row.accountability_score)}/100</span>
                </div>
              </div>
            </Card>
          ))}
        </div>
      </section>
    </>
  );
}

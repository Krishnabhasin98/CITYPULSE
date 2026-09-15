import { FileText, Layers, Sparkles, TrendingDown, TrendingUp } from "lucide-react";
import { Link } from "react-router-dom";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  ErrorState,
  PageHeader,
  Progress,
  RefreshButton,
  SectionTitle,
  SkeletonRows,
  Stat,
  cx,
} from "../components/ui";
import { apiGet, endpoints } from "../lib/api";
import { formatNumber, formatPercent } from "../lib/format";
import { useApiData } from "../lib/hooks";

export default function PolicyLab() {
  const policy = useApiData(() => apiGet(endpoints.policy()), []);
  const rows = policy.data || [];
  const summary = useApiData(() => apiGet(endpoints.cityHealth()), []);
  const monsoon = useApiData(() => apiGet(endpoints.monsoon()), []);

  const totals = rows.reduce(
    (acc, row) => ({
      reports: acc.reports + (row.measured_outcome?.reports || 0),
      breaches: acc.breaches + (row.measured_outcome?.sla_breaches || 0),
      resolved: acc.resolved + (row.measured_outcome?.resolved || 0),
    }),
    { reports: 0, breaches: 0, resolved: 0 },
  );

  return (
    <>
      <PageHeader
        eyebrow="PolicyLab"
        title="Patterns that are actually recurring"
        description="PolicyLab only names a pattern when the incident ledger shows repetition: three or more reports, or two clustered incidents in the same area. Every number below is counted from stored incidents — the projected reduction is labelled as an assumption, not a result."
        actions={<RefreshButton onClick={policy.reload} loading={policy.loading} />}
      />

      {policy.error ? (
        <ErrorState error={policy.error} onRetry={policy.reload} />
      ) : policy.loading && !rows.length ? (
        <SkeletonRows count={2} />
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Stat label="Patterns detected" value={formatNumber(rows.length)} hint="Groups with real repetition" icon={FileText} />
            <Stat label="Reports behind them" value={formatNumber(totals.reports)} hint="Clustered citizen reports" icon={Layers} />
            <Stat
              label="Deadline breaches"
              value={formatNumber(totals.breaches)}
              hint="Inside these recurring groups"
              tone={totals.breaches ? "critical" : "low"}
              icon={TrendingDown}
            />
            <Stat
              label="Resolution rate"
              value={formatPercent(totals.reports ? (totals.resolved / Math.max(rows.length, 1)) * 100 : 0)}
              hint="Groups already resolved"
              tone="info"
              icon={TrendingUp}
            />
          </div>

          {monsoon.data && (
            <Card className="mt-4 border-sky-200 bg-sky-50/60 p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-xs font-bold uppercase tracking-wider text-sky-900">Monsoon escalation window</p>
                  <p className="mt-1 text-sm text-sky-900">{monsoon.data.risk_note}</p>
                </div>
                <Badge tone={monsoon.data.escalation === "ROUTINE" ? "low" : "high"}>
                  {monsoon.data.escalation.replace(/_/g, " ").toLowerCase()}
                </Badge>
              </div>
            </Card>
          )}

          <section className="mt-5 space-y-4">
            <SectionTitle title={`Evidence-backed interventions (${rows.length})`} subtitle="Ordered by breaches, then severity, then volume" />
            {rows.map((row) => {
              const outcome = row.measured_outcome || {};
              const exposure = row.exposure || {};
              const impact = row.estimated_impact_if_applied || {};
              const resolvedRatio = outcome.incidents ? ((outcome.resolved || 0) / outcome.incidents) * 100 : 0;
              return (
                <Card key={row.id}>
                  <CardHeader
                    icon={FileText}
                    title={row.title}
                    subtitle={`${row.category} · ${row.target_area}${row.departments?.length ? ` · ${row.departments.join(", ")}` : ""}`}
                    action={
                      <Badge tone={outcome.sla_breaches ? "critical" : outcome.still_open ? "medium" : "low"}>
                        {outcome.sla_breaches
                          ? `${outcome.sla_breaches} breach(es)`
                          : outcome.still_open
                          ? `${outcome.still_open} open`
                          : "closed out"}
                      </Badge>
                    }
                  />

                  <div className="grid gap-4 p-5 lg:grid-cols-2">
                    <div className="rounded-xl border border-amber-100 bg-amber-50/60 p-4">
                      <p className="flex items-center gap-2 text-xs font-bold text-amber-900">
                        <Layers size={14} /> Recurring pattern
                      </p>
                      <p className="mt-2 text-xs leading-relaxed text-[var(--color-text-primary)]">{row.recurring_pattern}</p>
                      <p className="mt-2 text-[10px] font-semibold uppercase tracking-wider text-amber-800">
                        {outcome.basis}
                      </p>
                    </div>

                    <div className="rounded-xl border border-indigo-100 bg-indigo-50/60 p-4">
                      <p className="flex items-center gap-2 text-xs font-bold text-indigo-900">
                        <Sparkles size={14} /> Recommended intervention
                      </p>
                      <p className="mt-2 text-xs leading-relaxed text-[var(--color-text-primary)]">{row.policy_intervention}</p>
                      <p className="mt-2 text-[10px] font-semibold uppercase tracking-wider text-indigo-800">
                        {row.human_oversight_status} · evidence quality: {row.evidence_quality}
                      </p>
                    </div>

                    <div className="lg:col-span-2">
                      <div className="grid gap-3 sm:grid-cols-4">
                        {[
                          { label: "Incidents", value: outcome.incidents, hint: "clustered" },
                          { label: "Reports", value: outcome.reports, hint: "citizen submissions" },
                          { label: "Resolved", value: outcome.resolved, hint: `${formatPercent(resolvedRatio)} of the group` },
                          { label: "Worst severity", value: formatNumber(exposure.worst_severity), hint: `avg ${formatNumber(exposure.avg_severity)}` },
                        ].map((metric) => (
                          <div key={metric.label} className="rounded-xl bg-slate-50 p-3">
                            <p className="text-[10px] font-bold uppercase tracking-wider text-[var(--color-text-muted)]">{metric.label}</p>
                            <p className="text-lg font-bold text-[var(--color-ink)]">{metric.value}</p>
                            <p className="text-[10px] text-[var(--color-text-muted)]">{metric.hint}</p>
                          </div>
                        ))}
                      </div>

                      <div className="mt-3 rounded-xl border border-[var(--color-border)] p-4">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <p className="text-xs font-bold text-[var(--color-ink)]">Measured progress vs assumption</p>
                          <Badge tone="neutral">assumption, not a measurement</Badge>
                        </div>
                        <div className="mt-3 space-y-2">
                          <div>
                            <div className="flex justify-between text-[11px] text-[var(--color-text-secondary)]">
                              <span>Resolved so far</span>
                              <span className="font-semibold">
                                {outcome.resolved}/{outcome.incidents}
                              </span>
                            </div>
                            <Progress value={resolvedRatio} tone="low" height="h-1.5" className="mt-1" />
                          </div>
                          <div>
                            <div className="flex justify-between text-[11px] text-[var(--color-text-secondary)]">
                              <span>Projected reduction if the intervention is executed</span>
                              <span className="font-semibold">{impact.assumed_reduction_percent}%</span>
                            </div>
                            <Progress
                              value={impact.assumed_reduction_percent}
                              tone="info"
                              height="h-1.5"
                              className={cx("mt-1", "opacity-70")}
                            />
                          </div>
                        </div>
                        <p className="mt-2 text-[10px] text-[var(--color-text-muted)]">{impact.basis}</p>
                      </div>

                      <div className="mt-3 flex flex-wrap gap-2">
                        <Link to={`/map`}>
                          <Button variant="secondary" size="sm">
                            See these incidents on the map
                          </Button>
                        </Link>
                        <Link to="/departments">
                          <Button variant="secondary" size="sm">
                            Department scorecard
                          </Button>
                        </Link>
                      </div>
                    </div>
                  </div>
                </Card>
              );
            })}
          </section>

          {summary.data && (
            <Card className="mt-5">
              <CardHeader icon={FileText} title="How PolicyLab decides" subtitle="No invented before/after numbers" />
              <ul className="space-y-2 p-5 text-xs text-[var(--color-text-secondary)]">
                <li>• A pattern needs 3+ reports, or 2+ clustered incidents, in the same category and area.</li>
                <li>• Outcomes count incidents closed against incidents recorded, straight from the ledger.</li>
                <li>• Projected reductions are explicitly labelled assumptions with a 30-day re-measurement window.</li>
                <li>• Every recommendation still requires a named municipal officer to authorise dispatch.</li>
              </ul>
            </Card>
          )}
        </>
      )}
    </>
  );
}

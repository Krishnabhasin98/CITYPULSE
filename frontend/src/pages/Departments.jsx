import { Building2, Clock, Layers, ShieldCheck, Users } from "lucide-react";
import { Link } from "react-router-dom";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  EmptyState,
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
import { formatHours, formatNumber } from "../lib/format";
import { useApiData } from "../lib/hooks";

export default function Departments() {
  const departments = useApiData(() => apiGet(endpoints.departments()), []);
  const rows = departments.data || [];

  const totals = rows.reduce(
    (acc, row) => ({
      received: acc.received + row.received,
      resolved: acc.resolved + row.resolved,
      breached: acc.breached + row.breached,
      critical: acc.critical + row.critical_open,
    }),
    { received: 0, resolved: 0, breached: 0, critical: 0 },
  );

  return (
    <>
      <PageHeader
        eyebrow="Department intelligence"
        title="Who is keeping up with their deadlines"
        description="Workload and compliance per municipal department, computed from clustered incidents and the deadline attached to each one — not from complaint volume."
        actions={<RefreshButton onClick={departments.reload} loading={departments.loading} />}
      />

      {departments.error ? (
        <ErrorState error={departments.error} onRetry={departments.reload} />
      ) : departments.loading && !rows.length ? (
        <SkeletonRows count={3} />
      ) : !rows.length ? (
        <EmptyState title="No department activity yet" message="Departments appear here once incidents are classified to them." />
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Stat label="Incidents received" value={formatNumber(totals.received)} hint={`${formatNumber(totals.resolved)} resolved`} icon={Layers} />
            <Stat label="Critical open" value={formatNumber(totals.critical)} hint="Severity 75 or above" tone="high" icon={Building2} />
            <Stat label="Past deadline" value={formatNumber(totals.breached)} hint="Across all departments" tone={totals.breached ? "critical" : "low"} icon={Clock} />
            <Stat
              label="Citizen verification"
              value={formatNumber(rows.reduce((sum, row) => sum + row.verified_citizen_actions, 0))}
              hint="Community actions that cleared review"
              tone="info"
              icon={Users}
            />
          </div>

          <section className="mt-5">
            <SectionTitle title={`Department ledger (${rows.length})`} subtitle="Sorted by breaches, then critical load" />
            <div className="space-y-3">
              {rows.map((row) => (
                <Card key={row.department} className="p-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="text-base font-bold text-[var(--color-ink)]">{row.department}</h3>
                        {row.breached > 0 ? (
                          <Badge tone="critical">{row.breached} past deadline</Badge>
                        ) : (
                          <Badge tone="low">no breaches</Badge>
                        )}
                        {row.critical_open > 0 && <Badge tone="high">{row.critical_open} critical open</Badge>}
                        {row.recurring > 0 && <Badge tone="info">{row.recurring} recurring</Badge>}
                      </div>
                      <p className="mt-1 text-xs text-[var(--color-text-secondary)]">
                        {row.received} received · {row.open} open · {row.resolved} resolved · average open age{" "}
                        {formatHours(row.avg_open_age_hours)}
                        {row.avg_resolution_hours !== null ? ` · average close time ${formatHours(row.avg_resolution_hours)}` : ""}
                      </p>
                    </div>
                    <div className="min-w-[180px]">
                      <div className="flex items-center justify-between text-[11px] font-semibold text-[var(--color-text-secondary)]">
                        <span>Accountability score</span>
                        <span className="text-[var(--color-ink)]">{formatNumber(row.accountability_score)}/100</span>
                      </div>
                      <Progress
                        className="mt-1.5"
                        value={row.accountability_score}
                        tone={row.accountability_score >= 75 ? "low" : row.accountability_score >= 50 ? "medium" : "critical"}
                      />
                    </div>
                  </div>

                  <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                    {[
                      { label: "SLA compliance", value: `${formatNumber(row.sla_compliance)}%`, ratio: row.sla_compliance },
                      { label: "Resolution rate", value: `${formatNumber(row.resolution_rate)}%`, ratio: row.resolution_rate },
                      {
                        label: "Citizen actions",
                        value: `${row.verified_citizen_actions}/${row.citizen_actions}`,
                        ratio: row.citizen_actions ? (row.verified_citizen_actions / row.citizen_actions) * 100 : 0,
                      },
                      {
                        label: "Recurring incidents",
                        value: `${row.recurring}`,
                        ratio: row.received ? (row.recurring / row.received) * 100 : 0,
                      },
                    ].map((metric) => (
                      <div key={metric.label} className="rounded-xl bg-slate-50 p-3">
                        <p className="text-[10px] font-bold uppercase tracking-wider text-[var(--color-text-muted)]">{metric.label}</p>
                        <p className={cx("text-lg font-bold", metric.ratio < 50 ? "text-amber-700" : "text-[var(--color-ink)]")}>
                          {metric.value}
                        </p>
                        <Progress
                          className="mt-1.5"
                          value={metric.ratio}
                          tone={metric.ratio >= 75 ? "low" : metric.ratio >= 40 ? "medium" : "critical"}
                          height="h-1.5"
                        />
                      </div>
                    ))}
                  </div>
                </Card>
              ))}
            </div>
          </section>

          <Card className="mt-5">
            <CardHeader
              icon={ShieldCheck}
              title="How the accountability score works"
              subtitle="55% deadline compliance + 25% resolution rate + 20% verified citizen actions"
            />
            <div className="grid gap-3 p-5 text-xs text-[var(--color-text-secondary)] sm:grid-cols-3">
              <p>
                <strong className="text-[var(--color-ink)]">Compliance</strong> counts how many open incidents are still
                inside the response window derived from their severity.
              </p>
              <p>
                <strong className="text-[var(--color-ink)]">Resolution</strong> counts incidents actually closed, not
                reports that were filed.
              </p>
              <p>
                <strong className="text-[var(--color-ink)]">Citizen verification</strong> rewards departments where
                community claims get confirmed rather than rejected.
              </p>
            </div>
            <div className="border-t border-slate-100 px-5 py-4">
              <Link to="/policylab">
                <Button variant="secondary" size="sm">
                  See the policy interventions this implies
                </Button>
              </Link>
            </div>
          </Card>
        </>
      )}
    </>
  );
}

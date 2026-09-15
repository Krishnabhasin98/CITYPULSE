import { Activity, AlertTriangle, Clock, Gauge, Layers, ShieldCheck, Users } from "lucide-react";
import { Bar, BarChart, CartesianGrid, Cell, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Link } from "react-router-dom";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  ErrorState,
  LiveDot,
  PageHeader,
  Progress,
  RefreshButton,
  ScoreRing,
  SectionTitle,
  SkeletonCards,
  Stat,
  cx,
} from "../components/ui";
import { apiGet, endpoints } from "../lib/api";
import { BAND_TONE, formatHours, formatNumber, formatPercent, categoryColor } from "../lib/format";
import { useApiData } from "../lib/hooks";

export default function CityHealth() {
  const health = useApiData(() => apiGet(endpoints.cityHealth()), []);
  const scorecard = useApiData(() => apiGet(endpoints.scorecard()), []);
  const anomalies = health.data?.anomalies || [];

  const reload = () => {
    health.reload();
    scorecard.reload();
  };

  if (health.error) {
    return (
      <>
        <PageHeader eyebrow="City health" title="Delhi civic health" />
        <ErrorState error={health.error} onRetry={reload} />
      </>
    );
  }

  const data = health.data;

  return (
    <>
      <PageHeader
        eyebrow="City health"
        title="Delhi civic health index"
        description="One score for the city, computed from clustered incident severity, how much has been resolved, and how many deadlines have been missed. Duplicate complaints cannot inflate it."
        actions={<RefreshButton onClick={reload} loading={health.loading || scorecard.loading} />}
      />

      {health.loading && !data ? (
        <SkeletonCards count={4} />
      ) : (
        <>
          <div className="grid gap-4 lg:grid-cols-[auto_1fr]">
            <Card className="flex flex-col items-center justify-center px-6 py-6">
              <ScoreRing
                value={data.score}
                size={140}
                label="Civic health"
                tone={data.score >= 70 ? "low" : data.score >= 50 ? "medium" : "critical"}
              />
              <div className="mt-4 flex flex-wrap justify-center gap-1.5">
                <Badge tone={data.score >= 70 ? "low" : data.score >= 50 ? "medium" : "critical"}>
                  {data.score >= 70 ? "healthy" : data.score >= 50 ? "strained" : "unhealthy"}
                </Badge>
                <LiveDot label="Live" />
              </div>
              <p className="mt-3 max-w-[16rem] text-center text-[11px] leading-relaxed text-[var(--color-text-secondary)]">
                {scorecard.data?.headline || "Deadline compliance is sampled from the live incident ledger."}
              </p>
            </Card>

            <div className="grid gap-3 sm:grid-cols-2">
              <Stat label="Open incidents" value={formatNumber(data.open_incidents)} hint={`${formatNumber(data.resolved_incidents)} resolved`} icon={Layers} />
              <Stat
                label="Past deadline"
                value={formatNumber(data.sla?.breached)}
                hint={data.sla ? `${formatPercent(data.sla.compliance_percent)} inside their window` : "—"}
                tone={data.sla?.breached ? "critical" : "low"}
                icon={Clock}
              />
              <Stat
                label="Verified rate"
                value={formatPercent(data.verified_rate)}
                hint={`${formatNumber(data.people_helping)} citizens contributing`}
                tone="info"
                icon={Users}
              />
              <Stat
                label="Duplicate reports absorbed"
                value={formatNumber(data.duplicate_reports_absorbed)}
                hint={`${formatNumber(data.total_reports)} reports → ${formatNumber(data.open_incidents + data.resolved_incidents)} incidents`}
                tone="low"
                icon={ShieldCheck}
              />
            </div>
          </div>

          {/* Breakdown chart */}
          <section className="mt-5">
            <SectionTitle
              title="Category breakdown"
              subtitle="Bar height is the category health value (higher is healthier); the number above each bar is open incidents"
              action={
                <Link to="/departments">
                  <Button variant="secondary" size="sm">
                    Department ledger
                  </Button>
                </Link>
              }
            />
            <Card className="p-4">
              <div className="h-64 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={data.breakdown} margin={{ top: 12, right: 12, left: -18, bottom: 4 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#EEF1F5" vertical={false} />
                    <XAxis dataKey="label" tick={{ fontSize: 11, fill: "#5B6472" }} axisLine={false} tickLine={false} />
                    <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: "#8A93A1" }} axisLine={false} tickLine={false} />
                    <Tooltip
                      contentStyle={{ borderRadius: 12, border: "1px solid #D9DEE5", fontSize: 12 }}
                      formatter={(value, _name, entry) => [
                        `${value}/100 (${entry.payload.open} open, ${entry.payload.resolved} resolved)`,
                        entry.payload.label,
                      ]}
                    />
                    <Legend wrapperStyle={{ fontSize: 11 }} />
                    <Bar dataKey="value" name="Health value" radius={[6, 6, 0, 0]}>
                      {data.breakdown.map((row) => (
                        <Cell key={row.label} fill={categoryColor(row.label)} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Card>
          </section>

          {/* Areas */}
          <section className="mt-5 grid gap-4 lg:grid-cols-[1.4fr_1fr]">
            <Card className="overflow-hidden">
              <CardHeader
                icon={Gauge}
                title={`Neighbourhood bands (${data.areas.length})`}
                subtitle="UNHEALTHY when deadlines are missed or load is high; EMERGING when resolutions are landing"
              />
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-50 text-[10px] uppercase tracking-wider text-[var(--color-text-muted)]">
                    <tr>
                      <th className="px-4 py-2.5">Area</th>
                      <th className="px-4 py-2.5">Band</th>
                      <th className="px-4 py-2.5">Open</th>
                      <th className="px-4 py-2.5">Breached</th>
                      <th className="px-4 py-2.5">Avg severity</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {data.areas.map((row) => (
                      <tr key={row.area} className="hover:bg-slate-50/60">
                        <td className="px-4 py-2.5">
                          <span className="font-semibold text-[var(--color-ink)]">{row.area}</span>
                          {row.zone && <span className="block text-[10px] text-[var(--color-text-muted)]">{row.zone}</span>}
                        </td>
                        <td className="px-4 py-2.5">
                          <Badge tone={BAND_TONE(row.band)}>{row.band}</Badge>
                        </td>
                        <td className="px-4 py-2.5">{row.open_incidents}</td>
                        <td className={cx("px-4 py-2.5 font-bold", row.breached ? "text-red-600" : "text-[var(--color-text-secondary)]")}>
                          {row.breached}
                        </td>
                        <td className="px-4 py-2.5">
                          <div className="flex items-center gap-2">
                            <Progress
                              value={row.avg_severity}
                              tone={row.avg_severity >= 80 ? "critical" : row.avg_severity >= 65 ? "high" : "medium"}
                              height="h-1.5"
                              className="w-20"
                            />
                            {formatNumber(row.avg_severity)}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>

            <div className="space-y-4">
              <Card>
                <CardHeader icon={Activity} title="Accountability snapshot" subtitle="Deadline compliance across the city" />
                <div className="p-5">
                  <Progress
                    value={data.sla?.compliance_percent}
                    tone={data.sla?.breached ? "high" : "low"}
                  />
                  <div className="mt-3 grid grid-cols-2 gap-3 text-xs">
                    <div className="rounded-lg bg-slate-50 p-3">
                      <p className="text-[10px] font-bold uppercase text-[var(--color-text-muted)]">Overdue work</p>
                      <p className="text-lg font-bold text-[var(--color-ink)]">{formatHours(data.sla?.overdue_hours)}</p>
                    </div>
                    <div className="rounded-lg bg-slate-50 p-3">
                      <p className="text-[10px] font-bold uppercase text-[var(--color-text-muted)]">Due within 6h</p>
                      <p className="text-lg font-bold text-[var(--color-ink)]">{data.sla?.due_soon ?? 0}</p>
                    </div>
                  </div>
                  {scorecard.data?.worst_department && (
                    <p className="mt-3 text-[11px] text-[var(--color-text-secondary)]">
                      Most breaches: <strong>{scorecard.data.worst_department}</strong>. Best record:{" "}
                      <strong>{scorecard.data.least_breached_department}</strong>.
                    </p>
                  )}
                </div>
              </Card>

              <Card>
                <CardHeader
                  icon={AlertTriangle}
                  title={`Anomaly watch (${anomalies.length})`}
                  subtitle="Areas where report volume or severity is abnormal"
                />
                <div className="divide-y divide-slate-100">
                  {anomalies.length ? (
                    anomalies.slice(0, 5).map((row) => (
                      <div key={row.area} className="px-5 py-3">
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-xs font-bold text-[var(--color-ink)]">{row.area}</span>
                          <Badge tone={row.spike_level === "HIGH" ? "critical" : "high"}>{row.spike_level}</Badge>
                        </div>
                        <p className="mt-1 text-[11px] leading-relaxed text-[var(--color-text-secondary)]">{row.alert}</p>
                        <p className="mt-1 text-[11px] font-semibold text-[var(--color-cobalt)]">{row.recommendation}</p>
                      </div>
                    ))
                  ) : (
                    <p className="px-5 py-6 text-xs text-[var(--color-text-secondary)]">
                      No abnormal spikes detected. Report volume and severity are within normal bands.
                    </p>
                  )}
                </div>
              </Card>
            </div>
          </section>
        </>
      )}
    </>
  );
}

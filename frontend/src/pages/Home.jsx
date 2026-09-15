import {
  Activity,
  AlertTriangle,
  ArrowRight,
  Bot,
  Clock,
  Gauge,
  Layers,
  MapPin,
  Plus,
  ShieldCheck,
  Sparkles,
  Users,
} from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import CitySkyline from "../components/CitySkyline";
import IncidentCard from "../components/incident/IncidentCard";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  EmptyState,
  ErrorState,
  LiveDot,
  PageHeader,
  Progress,
  RefreshButton,
  ScoreRing,
  SkeletonCards,
  SkeletonRows,
  Stat,
  Tabs,
} from "../components/ui";
import { apiGet, endpoints } from "../lib/api";
import { formatNumber, formatPercent } from "../lib/format";
import { useApiData } from "../lib/hooks";
import { useSession } from "../lib/session";

export default function Home() {
  const { user, meta } = useSession();
  const [filter, setFilter] = useState("open");

  const incidents = useApiData(() => apiGet(endpoints.incidents({ limit: 200 })), []);
  const health = useApiData(() => apiGet(endpoints.cityHealth()), []);
  const areas = useApiData(() => apiGet(endpoints.areaSummary()), []);
  const monsoon = useApiData(() => apiGet(endpoints.monsoon()), []);

  const reloadAll = () => {
    incidents.reload();
    health.reload();
    areas.reload();
    monsoon.reload();
  };

  const filtered = useMemo(() => {
    const rows = incidents.data || [];
    if (filter === "breached") return rows.filter((row) => row.sla?.state === "breached");
    if (filter === "open") return rows.filter((row) => row.status !== "resolved");
    if (filter === "resolved") return rows.filter((row) => row.status === "resolved");
    return rows;
  }, [incidents.data, filter]);

  const loadingCore = incidents.loading && !incidents.data;
  const healthData = health.data;
  const sla = healthData?.sla;

  return (
    <>
      <PageHeader
        eyebrow="Delhi civic intelligence"
        title={user ? `Namaste, ${user.name.split(" ")[0]}` : "Civic intelligence for Delhi"}
        description={
          meta?.live_data_enabled
            ? "Clustered incidents, live weather and municipal deadlines — every number on this page comes from the incident ledger or an open data source."
            : "Live external lookups are switched off in this environment, so area and weather signals fall back to bundled reference data."
        }
        actions={
          <>
            <RefreshButton onClick={reloadAll} loading={incidents.loading || health.loading} />
            <Link to="/report">
              <Button>
                <Plus size={15} /> Report a problem
              </Button>
            </Link>
          </>
        }
      />

      {incidents.error && <ErrorState error={incidents.error} onRetry={reloadAll} className="mb-4" />}

      {/* Headline metrics */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {loadingCore ? (
          <SkeletonCards count={4} className="lg:col-span-4" />
        ) : (
          <>
            <Stat
              label="City health"
              value={healthData ? `${healthData.score}` : "—"}
              hint="Weighted from open severity, resolutions and deadline breaches"
              tone={healthData?.score >= 70 ? "low" : healthData?.score >= 50 ? "medium" : "critical"}
              icon={Gauge}
            />
            <Stat
              label="Open incidents"
              value={formatNumber(healthData?.open_incidents)}
              hint={`${formatNumber(healthData?.total_reports)} reports clustered`}
              tone="info"
              icon={Layers}
            />
            <Stat
              label="Past deadline"
              value={formatNumber(sla?.breached)}
              hint={sla ? `${formatPercent(sla.compliance_percent)} inside their window` : "—"}
              tone={sla?.breached ? "critical" : "low"}
              icon={Clock}
            />
            <Stat
              label="Duplicate reports absorbed"
              value={formatNumber(healthData?.duplicate_reports_absorbed)}
              hint="Reports merged into existing incidents instead of new complaints"
              tone="low"
              icon={Users}
            />
          </>
        )}
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        {/* City health summary */}
        <Card className="lg:col-span-2">
          <CardHeader
            icon={Gauge}
            title="Where Delhi stands right now"
            subtitle="Area bands use clustered incidents, severity and resolution — not complaint volume"
            action={
              <Link to="/city-health">
                <Button variant="secondary" size="sm">
                  Full health report <ArrowRight size={14} />
                </Button>
              </Link>
            }
          />
          <div className="grid gap-4 p-5 sm:grid-cols-[auto_1fr]">
            <div className="flex justify-center">
              {healthData ? (
                <ScoreRing
                  value={healthData.score}
                  label="City health"
                  sublabel={`${formatPercent(healthData.resolved_rate)} resolved`}
                  tone={healthData.score >= 70 ? "low" : healthData.score >= 50 ? "medium" : "critical"}
                />
              ) : (
                <div className="h-[140px] w-[140px] animate-pulse rounded-full bg-slate-100" />
              )}
            </div>
            <div className="space-y-3">
              <div>
                <div className="flex items-center justify-between text-xs font-semibold text-[var(--color-text-secondary)]">
                  <span>Deadline compliance</span>
                  <span>{sla ? `${sla.total - sla.breached}/${sla.total}` : "—"}</span>
                </div>
                <Progress
                  className="mt-1.5"
                  value={sla?.compliance_percent ?? 0}
                  tone={sla?.breached ? "high" : "low"}
                />
                <p className="mt-1 text-[11px] text-[var(--color-text-muted)]">
                  {sla?.overdue_hours ? `${formatNumber(sla.overdue_hours, 0)} hours of overdue work outstanding` : "No overdue work outstanding"}
                </p>
              </div>

              {(healthData?.breakdown || []).slice(0, 4).map((row) => (
                <div key={row.label}>
                  <div className="flex items-center justify-between text-xs font-semibold text-[var(--color-text-secondary)]">
                    <span>{row.label}</span>
                    <span>
                      {row.open} open · worst severity {formatNumber(row.worst_severity)}
                    </span>
                  </div>
                  <Progress
                    className="mt-1.5"
                    value={row.value}
                    tone={row.worst_severity >= 80 ? "critical" : row.worst_severity >= 65 ? "high" : "medium"}
                  />
                </div>
              ))}
            </div>
          </div>
        </Card>

        {/* Live conditions */}
        <Card>
          <CardHeader
            icon={Sparkles}
            title="Live conditions"
            subtitle="Open-Meteo forecast for the city centre"
            action={monsoon.data?.weather_meta?.source === "live" ? <LiveDot /> : null}
          />
          <div className="space-y-3 p-5 text-sm">
            {monsoon.loading && !monsoon.data ? (
              <div className="space-y-2">
                <div className="h-4 w-32 animate-pulse rounded bg-slate-100" />
                <div className="h-3 w-full animate-pulse rounded bg-slate-100" />
                <div className="h-3 w-2/3 animate-pulse rounded bg-slate-100" />
              </div>
            ) : monsoon.data?.weather ? (
              <>
                <div className="flex items-baseline justify-between">
                  <span className="text-2xl font-black text-[var(--color-ink)]">
                    {monsoon.data.weather.temperature_c !== null && monsoon.data.weather.temperature_c !== undefined
                      ? `${Math.round(monsoon.data.weather.temperature_c)}°C`
                      : "—"}
                  </span>
                  <span className="text-xs font-semibold text-[var(--color-text-secondary)]">
                    {monsoon.data.weather.condition}
                  </span>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  <Badge tone={monsoon.data.escalation === "ROUTINE" ? "low" : "high"}>
                    {monsoon.data.escalation.replace(/_/g, " ").toLowerCase()}
                  </Badge>
                  <Badge tone="info">
                    {formatNumber(monsoon.data.weather.rain_next_7d_mm, 1)} mm rain / 7d
                  </Badge>
                  <Badge tone="neutral">
                    {formatNumber(monsoon.data.weather.humidity)}% humidity
                  </Badge>
                </div>
                <p className="text-xs leading-relaxed text-[var(--color-text-secondary)]">{monsoon.data.risk_note}</p>
                <div className="grid grid-cols-4 gap-1.5">
                  {(monsoon.data.weather.forecast || []).slice(1, 5).map((day) => (
                    <div key={day.date} className="rounded-lg bg-slate-50 p-2 text-center">
                      <p className="text-[10px] font-bold text-[var(--color-text-muted)]">
                        {new Date(day.date).toLocaleDateString("en-IN", { weekday: "short" })}
                      </p>
                      <p className="text-xs font-bold text-[var(--color-ink)]">{formatNumber(day.rain_mm, 0)}mm</p>
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <p className="text-xs text-[var(--color-text-secondary)]">
                Live weather is unavailable right now. Everything else on this page still works from the incident ledger.
              </p>
            )}
          </div>
        </Card>
      </div>

      {/* Area skyline */}
      <section className="mt-4">
        {areas.loading && !areas.data ? (
          <Card className="h-[280px] animate-pulse bg-slate-50" />
        ) : (
          <CitySkyline areas={areas.data?.areas || []} onSelect={() => {}} />
        )}
      </section>

      {/* Incident feed */}
      <section className="mt-6">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-bold uppercase tracking-wider text-[var(--color-ink)]">Civic incident feed</h2>
            <p className="text-xs text-[var(--color-text-secondary)]">
              One card per real-world problem. Reports that describe the same problem within 180 m are merged into it.
            </p>
          </div>
          <Tabs
            value={filter}
            onChange={setFilter}
            tabs={[
              { value: "open", label: "Open" },
              { value: "breached", label: "Past deadline" },
              { value: "resolved", label: "Resolved" },
              { value: "all", label: "All" },
            ]}
          />
        </div>

        {loadingCore ? (
          <SkeletonRows count={3} />
        ) : filtered.length ? (
          <div className="space-y-3">
            {filtered.slice(0, 12).map((incident) => (
              <IncidentCard key={incident.id} incident={incident} onActionComplete={reloadAll} />
            ))}
          </div>
        ) : (
          <EmptyState
            icon={AlertTriangle}
            title="Nothing in this view"
            message="No incident matches this filter yet. Try another tab, or be the first to report a problem near you."
            action={
              <Link to="/report">
                <Button>
                  <Plus size={15} /> Report a problem
                </Button>
              </Link>
            }
          />
        )}
      </section>

      {/* Quick links */}
      <section className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {[
          { to: "/area", label: "Area intelligence", hint: "Any pincode or GPS point", icon: MapPin },
          { to: "/authority", label: "Dispatch queue", hint: "SLA-first triage", icon: ShieldCheck },
          { to: "/map", label: "Live map", hint: "OpenStreetMap view", icon: Activity },
          { to: "/assistant", label: "Civic assistant", hint: "Ask about the data", icon: Bot },
        ].map((item) => (
          <Link
            key={item.to}
            to={item.to}
            className="rounded-2xl border border-[var(--color-border)] bg-white p-4 transition hover:border-[var(--color-cobalt)] hover:shadow-sm"
          >
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-100 text-[var(--color-cobalt)]">
              <item.icon size={16} />
            </span>
            <p className="mt-2 text-sm font-bold text-[var(--color-ink)]">{item.label}</p>
            <p className="text-xs text-[var(--color-text-secondary)]">{item.hint}</p>
          </Link>
        ))}
      </section>
    </>
  );
}

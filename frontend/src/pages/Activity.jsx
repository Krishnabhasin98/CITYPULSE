import { Activity as ActivityIcon, Award, FileText, LogIn, MapPin, Plus } from "lucide-react";
import { useMemo } from "react";
import { Link } from "react-router-dom";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  EmptyState,
  ErrorState,
  PageHeader,
  RefreshButton,
  SkeletonRows,
  Stat,
  cx,
} from "../components/ui";
import { apiGet, endpoints } from "../lib/api";
import { SLA_TONE, formatDateTime, formatNumber, formatRelativeTime, titleCase } from "../lib/format";
import { useApiData } from "../lib/hooks";
import { useSession } from "../lib/session";

export default function Activity() {
  const { isAuthenticated, user } = useSession();
  const reports = useApiData(() => apiGet(endpoints.myReports()), [], { skip: !isAuthenticated });
  const ledger = useApiData(() => apiGet(endpoints.ledger()), [], { skip: !isAuthenticated });
  const incidents = useApiData(() => apiGet(endpoints.incidents({ limit: 300 })), []);

  // Hooks must run unconditionally, before any early return.
  const timeline = useMemo(() => {
    const entries = [
      ...(ledger.data?.entries || []).map((entry) => ({
        id: `credit-${entry.id}`,
        kind: "credit",
        at: entry.created_at,
        title: entry.reason,
        detail: `${entry.amount >= 0 ? "+" : ""}${entry.amount} credits`,
        tone: entry.amount >= 0 ? "low" : "critical",
      })),
      ...(reports.data || []).map((report) => ({
        id: `report-${report.id}`,
        kind: "report",
        at: report.created_at,
        title: (report.description || "Report").slice(0, 110),
        detail: `${titleCase(report.category || "unclassified")} · ${report.trust_status || "unreviewed"}${
          report.address ? ` · ${report.address}` : ""
        }`,
        tone: "info",
      })),
    ];
    return entries
      .filter((entry) => entry.at)
      .sort((a, b) => (a.at < b.at ? 1 : -1))
      .slice(0, 40);
  }, [ledger.data, reports.data]);

  if (!isAuthenticated) {
    return (
      <>
        <PageHeader eyebrow="My activity" title="Your civic record" description="Sign in to see your reports, the credits they earned and the incidents they helped shape." />
        <EmptyState
          icon={LogIn}
          title="Sign in to view your activity"
          message="Demo credentials: citizen@citypulse.local / password123. Everything you do is written to an auditable ledger."
          action={
            <Link to="/login">
              <Button>Sign in</Button>
            </Link>
          }
        />
      </>
    );
  }

  const myIncidentIds = new Set((reports.data || []).map((report) => report.incident_id).filter(Boolean));
  // Incidents this citizen's own reports were clustered into.
  const participating = (incidents.data || []).filter((incident) => myIncidentIds.has(incident.id));

  const creditedTotal = (ledger.data?.entries || []).reduce((sum, entry) => sum + entry.amount, 0);

  return (
    <>
      <PageHeader
        eyebrow="My activity"
        title={`${user?.name || "Citizen"} · civic record`}
        description="Every report you file and every credit you earn is recorded here, with timestamps, so your contribution is auditable."
        actions={<RefreshButton onClick={() => { reports.reload(); ledger.reload(); }} loading={reports.loading || ledger.loading} />}
      />

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Reports filed" value={formatNumber((reports.data || []).length)} hint="With photo, GPS and description" icon={FileText} />
        <Stat label="Credits earned" value={formatNumber(creditedTotal)} hint={`Balance ${formatNumber(ledger.data?.credits ?? user?.credits ?? 0)}`} tone="info" icon={Award} />
        <Stat
          label="Reputation"
          value={ledger.data?.reputation ? `${ledger.data.reputation.reputation_score}/100` : "—"}
          hint={ledger.data?.reputation?.tier}
          tone="low"
          icon={ActivityIcon}
        />
        <Stat
          label="Incidents touched"
          value={formatNumber(myIncidentIds.size)}
          hint="Reports that joined an existing incident"
          tone="medium"
          icon={MapPin}
        />
      </div>

      {reports.error ? (
        <ErrorState className="mt-4" error={reports.error} onRetry={reports.reload} />
      ) : (
        <div className="mt-5 grid gap-4 lg:grid-cols-[1.5fr_1fr]">
          <Card className="overflow-hidden">
            <CardHeader icon={ActivityIcon} title="Timeline" subtitle="Reports and credit movements, newest first" />
            {reports.loading && !reports.data ? (
              <SkeletonRows count={3} className="p-4" />
            ) : timeline.length ? (
              <div className="divide-y divide-slate-100">
                {timeline.map((entry) => (
                  <div key={entry.id} className="flex items-start gap-3 px-5 py-3">
                    <span
                      className={cx(
                        "mt-1 h-2 w-2 shrink-0 rounded-full",
                        entry.kind === "credit" ? "bg-emerald-500" : "bg-[var(--color-cobalt)]",
                      )}
                    />
                    <div className="min-w-0 flex-1">
                      <p className="text-xs font-bold text-[var(--color-ink)]">{entry.title}</p>
                      <p className="text-[11px] text-[var(--color-text-secondary)]">{entry.detail}</p>
                      <p className="text-[10px] text-[var(--color-text-muted)]">{formatDateTime(entry.at)}</p>
                    </div>
                    <Badge tone={entry.tone}>{entry.kind === "credit" ? "credits" : "report"}</Badge>
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-5">
                <EmptyState
                  title="Nothing recorded yet"
                  message="File your first report and it will appear here immediately, along with the credits it earns."
                  action={
                    <Link to="/report">
                      <Button>
                        <Plus size={15} /> Report a problem
                      </Button>
                    </Link>
                  }
                />
              </div>
            )}
          </Card>

          <div className="space-y-4">
            <Card>
              <CardHeader icon={FileText} title="Your reports" subtitle={`${(reports.data || []).length} submitted`} />
              <div className="max-h-[420px] divide-y divide-slate-100 overflow-y-auto">
                {(reports.data || []).length ? (
                  reports.data.map((report) => (
                    <div key={report.id} className="px-5 py-3">
                      <p className="text-xs font-semibold text-[var(--color-ink)]">{(report.description || "Report").slice(0, 100)}</p>
                      <div className="mt-1 flex flex-wrap items-center gap-2 text-[10px] text-[var(--color-text-muted)]">
                        <Badge tone="info">{titleCase(report.category || "unclassified")}</Badge>
                        <Badge tone={report.trust_status === "Suspicious" ? "critical" : "neutral"}>{report.trust_status}</Badge>
                        <span>{formatRelativeTime(report.created_at)}</span>
                      </div>
                    </div>
                  ))
                ) : (
                  <p className="px-5 py-6 text-xs text-[var(--color-text-secondary)]">No reports yet.</p>
                )}
              </div>
            </Card>

            <Card>
              <CardHeader
                icon={MapPin}
                title="Incidents you are part of"
                subtitle={participating.length ? "Your reports were clustered into these" : "Open problems elsewhere in the city"}
              />
              <div className="divide-y divide-slate-100">
                {(participating.length
                  ? participating
                  : (incidents.data || []).filter((incident) => incident.status !== "resolved")
                )
                  .slice(0, 5)
                  .map((incident) => (
                    <Link
                      key={incident.id}
                      to={`/incidents/${incident.id}`}
                      className="block px-5 py-3 transition hover:bg-slate-50"
                    >
                      <p className="text-xs font-bold text-[var(--color-ink)]">{incident.title}</p>
                      <div className="mt-1 flex items-center gap-2 text-[10px] text-[var(--color-text-muted)]">
                        <Badge tone={SLA_TONE(incident.sla?.state)}>{incident.sla?.label}</Badge>
                        <span>{incident.affected_area}</span>
                      </div>
                    </Link>
                  ))}
              </div>
            </Card>
          </div>
        </div>
      )}
    </>
  );
}

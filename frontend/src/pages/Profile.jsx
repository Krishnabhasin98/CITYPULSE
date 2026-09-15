import { Link } from "react-router-dom";
import { Award, BadgeCheck, CalendarDays, FileText, Grid3x3, MapPin, ShieldCheck, TrendingUp, Trophy, Zap } from "lucide-react";
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
  SkeletonCards,
  Stat,
  cx,
} from "../components/ui";
import { apiGet, endpoints } from "../lib/api";
import { formatDateTime, formatNumber, titleCase } from "../lib/format";
import { useApiData } from "../lib/hooks";
import { useSession } from "../lib/session";

export default function Profile() {
  const { user, isAuthenticated, logout } = useSession();
  const profile = useApiData(() => apiGet(endpoints.me()), [isAuthenticated], { skip: !isAuthenticated });
  const mine = useApiData(() => apiGet(endpoints.myReports()), [], { skip: !isAuthenticated });

  if (!isAuthenticated) {
    return (
      <>
        <PageHeader eyebrow="Profile" title="Your civic identity" description="Sign in to see your credits, reputation and report history." />
        <EmptyState
          icon={ShieldCheck}
          title="You are browsing anonymously"
          message="Sign in with the seeded demo account (citizen@citypulse.local / password123) or create your own to track contributions."
          action={
            <Link to="/login">
              <Button>Sign in</Button>
            </Link>
          }
        />
      </>
    );
  }

  const data = profile.data || user || {};
  const detail = data.reputation_detail || {};
  const reports = mine.data || [];
  const score = detail.reputation_score ?? data.reputation ?? 100;
  const tier = detail.tier || "New contributor";

  return (
    <>
      <PageHeader
        eyebrow="Profile"
        title={data.name || "Citizen"}
        description="Everything here is computed from your own action ledger — credits, reputation and the reports you filed."
        actions={
          <div className="flex gap-2">
            <RefreshButton onClick={() => { profile.reload(); mine.reload(); }} loading={profile.loading || mine.loading} />
            <Button variant="secondary" onClick={logout}>Sign out</Button>
          </div>
        }
      />

      {profile.error ? (
        <ErrorState error={profile.error} onRetry={profile.reload} />
      ) : profile.loading && !profile.data ? (
        <SkeletonCards count={4} />
      ) : (
        <>
          <Card className="p-5">
            <div className="flex flex-wrap items-center gap-5">
              <span className="flex h-16 w-16 items-center justify-center rounded-2xl bg-[var(--color-ink)] text-2xl font-black text-white">
                {(data.name || "C").slice(0, 1).toUpperCase()}
              </span>
              <div className="min-w-[200px] flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="text-lg font-bold text-[var(--color-ink)]">{data.name}</h2>
                  <Badge tone={data.is_authority ? "info" : "low"} icon={data.is_authority ? ShieldCheck : BadgeCheck}>
                    {data.is_authority ? "Authority account" : "Verified citizen"}
                  </Badge>
                </div>
                <p className="mt-0.5 text-xs text-[var(--color-text-secondary)]">{data.email}</p>
                <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-[var(--color-text-muted)]">
                  <span className="inline-flex items-center gap-1">
                    <MapPin size={12} /> {data.ward || "Neighbourhood not set"}
                  </span>
                  <span className="inline-flex items-center gap-1">
                    <CalendarDays size={12} /> Joined {data.created_at ? formatDateTime(data.created_at) : "—"}
                  </span>
                  <span className="inline-flex items-center gap-1">
                    <Grid3x3 size={12} /> Role: {titleCase(data.role)}
                  </span>
                </div>
              </div>
              <div className="w-full sm:w-56">
                <div className="flex items-center justify-between text-[11px] font-bold text-[var(--color-text-secondary)]">
                  <span className="inline-flex items-center gap-1">
                    <Trophy size={12} /> Reputation
                  </span>
                  <span>{score}/100</span>
                </div>
                <Progress className="mt-1.5" value={score} tone={score >= 78 ? "low" : score >= 55 ? "medium" : "high"} />
                <p className="mt-1.5 text-[11px] text-[var(--color-text-muted)]">{tier}</p>
              </div>
            </div>
          </Card>

          <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Stat label="Credit balance" value={formatNumber(data.credits)} hint="Spendable on nothing — it is a record of verified help" tone="info" icon={Award} />
            <Stat label="Lifetime earned" value={formatNumber(detail.lifetime_earned)} hint={`${detail.ledger_entries ?? 0} ledger entries`} tone="low" icon={TrendingUp} />
            <Stat label="Penalties" value={formatNumber(detail.penalties)} hint="Deducted only through review" tone={detail.penalties ? "critical" : "neutral"} icon={ShieldCheck} />
            <Stat label="Reports filed" value={formatNumber(reports.length)} hint="Clustered into city incidents" icon={FileText} />
          </div>

          <section className="mt-5 grid gap-4 lg:grid-cols-[1.4fr_1fr]">
            <Card className="overflow-hidden">
              <CardHeader
                icon={FileText}
                title="Your reports"
                subtitle={reports.length ? "Newest first" : "Nothing filed yet"}
                action={
                  <Link to="/report">
                    <Button size="sm" variant="secondary">New report</Button>
                  </Link>
                }
              />
              {reports.length ? (
                <div className="divide-y divide-slate-100">
                  {reports.slice(0, 8).map((report) => (
                    <Link
                      key={report.id ?? report.post_id}
                      to={report.incident_id ? `/incidents/${report.incident_id}` : "/report"}
                      className="flex items-start justify-between gap-3 px-5 py-3 transition hover:bg-slate-50"
                    >
                      <div className="min-w-0">
                        <p className="truncate text-xs font-bold text-[var(--color-ink)]">{report.description || report.title || "Report"}</p>
                        <p className="mt-0.5 text-[10px] text-[var(--color-text-muted)]">
                          {report.category || "Unclassified"} · {report.affected_area || "Location hidden"} ·{" "}
                          {formatDateTime(report.created_at)}
                        </p>
                      </div>
                      <Badge tone={report.clustered ? "info" : "neutral"}>
                        {report.clustered ? "clustered" : report.status || "received"}
                      </Badge>
                    </Link>
                  ))}
                </div>
              ) : (
                <div className="px-5 py-8 text-center text-xs text-[var(--color-text-secondary)]">
                  Report a pothole, outage or dumping spot and it will appear here with its live incident status.
                </div>
              )}
            </Card>

            <Card className="overflow-hidden">
              <CardHeader icon={Zap} title="Recent credit activity" subtitle="The audit trail behind your balance" />
              {(data.ledger || []).length ? (
                <div className="divide-y divide-slate-100">
                  {data.ledger.slice(0, 10).map((entry) => (
                    <div key={entry.id} className="flex items-center justify-between gap-3 px-5 py-2.5">
                      <div>
                        <p className="text-xs font-semibold text-[var(--color-ink)]">{entry.reason}</p>
                        <p className="text-[10px] text-[var(--color-text-muted)]">{formatDateTime(entry.created_at)}</p>
                      </div>
                      <span
                        className={cx(
                          "rounded-full px-2.5 py-1 text-xs font-bold",
                          entry.amount >= 0 ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-700",
                        )}
                      >
                        {entry.amount >= 0 ? `+${entry.amount}` : entry.amount}
                      </span>
                    </div>
                  ))}
                  <div className="px-5 py-3">
                    <Link to="/credits" className="text-xs font-semibold text-[var(--color-cobalt)] hover:underline">
                      See how credits are earned →
                    </Link>
                  </div>
                </div>
              ) : (
                <p className="px-5 py-8 text-center text-xs text-[var(--color-text-secondary)]">
                  No ledger entries yet. Confirming a neighbour's report is the fastest way to start.
                </p>
              )}
            </Card>
          </section>
        </>
      )}
    </>
  );
}

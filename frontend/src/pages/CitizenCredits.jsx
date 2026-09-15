import { Award, CheckCircle2, Clock, Scale, Sparkles, TrendingUp, Trophy } from "lucide-react";
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
  SkeletonCards,
  Stat,
  cx,
} from "../components/ui";
import { apiGet, endpoints } from "../lib/api";
import { formatDateTime, formatNumber } from "../lib/format";
import { useApiData } from "../lib/hooks";
import { useSession } from "../lib/session";

export default function CitizenCredits() {
  const { user, isAuthenticated } = useSession();
  const catalog = useApiData(() => apiGet(endpoints.creditCatalog()), []);
  const ledger = useApiData(() => apiGet(endpoints.ledger()), [], { skip: !isAuthenticated });

  const actions = catalog.data?.actions || [];
  const immediate = actions.filter((action) => action.verification === "immediate");
  const pending = actions.filter((action) => action.verification === "peer");
  const authorityOnly = actions.filter((action) => action.verification === "authority");
  const reputation = ledger.data?.reputation;

  return (
    <>
      <PageHeader
        eyebrow="Citizen credits"
        title="Credits reward verified help"
        description="This page is generated from the same table the backend enforces, so what you read here is what actually pays out. Immediate actions pay once per citizen per incident; higher-value claims wait for another human to confirm them."
        actions={<RefreshButton onClick={() => { catalog.reload(); ledger.reload(); }} loading={catalog.loading || ledger.loading} />}
      />

      {catalog.error ? (
        <ErrorState error={catalog.error} onRetry={catalog.reload} />
      ) : catalog.loading && !actions.length ? (
        <SkeletonCards count={3} />
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Stat
              label="Your balance"
              value={isAuthenticated ? formatNumber(user?.credits ?? ledger.data?.credits) : "—"}
              hint={isAuthenticated ? "Spendable on nothing but reputation — priority cannot be bought" : "Sign in to see your balance"}
              tone="info"
              icon={Award}
            />
            <Stat
              label="Reputation"
              value={reputation ? `${reputation.reputation_score}/100` : "—"}
              hint={reputation?.tier || "Derived from your ledger"}
              tone={(reputation?.reputation_score ?? 0) >= 78 ? "low" : "medium"}
              icon={Trophy}
            />
            <Stat
              label="Lifetime earned"
              value={reputation ? formatNumber(reputation.lifetime_earned) : "—"}
              hint={reputation ? `${reputation.ledger_entries} ledger entries` : "No ledger yet"}
              icon={TrendingUp}
            />
            <Stat
              label="Daily cap"
              value={formatNumber(catalog.data?.daily_cap)}
              hint="Credits any single day can add"
              tone="neutral"
              icon={Scale}
            />
          </div>

          <Card className="mt-4 bg-[var(--color-ink)] p-5 text-white">
            <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-indigo-300">Governance principle</p>
            <h2 className="mt-2 text-xl font-bold">Trust first → credits second → influence third</h2>
            <p className="mt-2 max-w-3xl text-sm leading-relaxed text-slate-300">
              Verification builds trust, trust earns credits, and credits reflect real civic impact. Credits are never
              accepted as payment and never change an incident's priority: severity, corroboration and deadlines do.
            </p>
            {reputation && (
              <div className="mt-4 max-w-sm">
                <div className="flex items-center justify-between text-[11px] text-slate-300">
                  <span>{reputation.tier}</span>
                  <span>{reputation.reputation_score}/100</span>
                </div>
                <Progress
                  className="mt-1.5 bg-white/10"
                  value={reputation.reputation_score}
                  tone={reputation.reputation_score >= 78 ? "low" : "medium"}
                />
              </div>
            )}
          </Card>

          <section className="mt-5">
            <SectionTitle title="Pays out immediately" subtitle="Once per citizen per incident — repeating the action earns nothing" />
            <div className="grid gap-3 md:grid-cols-3">
              {immediate.map((action) => (
                <Card key={action.key} className="p-4">
                  <div className="flex items-center justify-between">
                    <h3 className="text-sm font-bold text-[var(--color-ink)]">{action.label}</h3>
                    <Badge tone="low">+{action.credits}</Badge>
                  </div>
                  <p className="mt-1.5 text-[11px] leading-relaxed text-[var(--color-text-secondary)]">{action.description}</p>
                </Card>
              ))}
            </div>
          </section>

          <section className="mt-5">
            <SectionTitle title="Pending confirmation" subtitle="Recorded instantly, released when another citizen or a department confirms it" />
            <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
              {pending.map((action) => (
                <Card key={action.key} className="p-4">
                  <div className="flex items-center justify-between">
                    <h3 className="text-sm font-bold text-[var(--color-ink)]">{action.label}</h3>
                    <Badge tone="medium">+{action.credits}</Badge>
                  </div>
                  <p className="mt-1.5 text-[11px] leading-relaxed text-[var(--color-text-secondary)]">{action.description}</p>
                  {action.needs_evidence && (
                    <p className="mt-2 text-[10px] font-bold uppercase tracking-wider text-amber-700">photo required</p>
                  )}
                </Card>
              ))}
            </div>
          </section>

          {authorityOnly.length > 0 && (
            <section className="mt-5">
              <SectionTitle title="Authority verified" subtitle="A municipal officer must sign these off" />
              <div className="grid gap-3 md:grid-cols-2">
                {authorityOnly.map((action) => (
                  <Card key={action.key} className="p-4">
                    <div className="flex items-center justify-between">
                      <h3 className="text-sm font-bold text-[var(--color-ink)]">{action.label}</h3>
                      <Badge tone="info">+{action.credits}</Badge>
                    </div>
                    <p className="mt-1.5 text-[11px] leading-relaxed text-[var(--color-text-secondary)]">{action.description}</p>
                  </Card>
                ))}
              </div>
            </section>
          )}

          <section className="mt-5 grid gap-4 lg:grid-cols-[1.4fr_1fr]">
            <Card className="overflow-hidden">
              <CardHeader
                icon={Clock}
                title="Your credit ledger"
                subtitle={isAuthenticated ? "Newest entries first — this is the audit trail" : "Sign in to see your own entries"}
              />
              {!isAuthenticated ? (
                <div className="p-5 text-xs text-[var(--color-text-secondary)]">
                  <Link to="/login">
                    <Button size="sm">Sign in</Button>
                  </Link>
                  <span className="ml-3">Demo: citizen@citypulse.local / password123</span>
                </div>
              ) : (ledger.data?.entries || []).length ? (
                <div className="divide-y divide-slate-100">
                  {ledger.data.entries.map((entry) => (
                    <div key={entry.id} className="flex items-center justify-between gap-3 px-5 py-3">
                      <div>
                        <p className="text-xs font-bold text-[var(--color-ink)]">{entry.reason}</p>
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
                </div>
              ) : (
                <p className="px-5 py-6 text-xs text-[var(--color-text-secondary)]">
                  No credits yet. Confirm, verify or report something to start the ledger.
                </p>
              )}
            </Card>

            <div className="space-y-4">
              <Card>
                <CardHeader icon={Sparkles} title="Penalties" subtitle="Applied only through review" />
                <div className="space-y-2 p-5 text-xs">
                  {Object.entries(catalog.data?.penalties || {}).map(([key, value]) => (
                    <div key={key} className="flex items-center justify-between rounded-lg bg-red-50 px-3 py-2">
                      <span className="font-semibold capitalize text-red-800">{key.replace(/_/g, " ")}</span>
                      <span className="font-bold text-red-700">{value}</span>
                    </div>
                  ))}
                  <p className="text-[11px] leading-relaxed text-[var(--color-text-secondary)]">
                    A rejected claim costs the claimant half of the value they attempted to claim. Flags work the same
                    way: they lower the incident's trust score immediately.
                  </p>
                </div>
              </Card>

              <Card>
                <CardHeader icon={CheckCircle2} title="Anti-gaming rules" />
                <ul className="space-y-2 p-5 text-[11px] text-[var(--color-text-secondary)]">
                  <li>• One credit payout per citizen per incident per action type.</li>
                  <li>• You cannot confirm your own claim, ever.</li>
                  <li>• Credit farming cannot raise an incident's priority score.</li>
                  <li>• Daily ceiling of {catalog.data?.daily_cap} credits per account.</li>
                  <li>• Credits are recorded in a ledger you can audit line by line.</li>
                </ul>
              </Card>
            </div>
          </section>

          <Card className="mt-5">
            <CardHeader icon={Scale} title="Policy as enforced" subtitle={catalog.data?.policy} />
            <div className="p-5 text-[11px] text-[var(--color-text-secondary)]">
              Highest single payout: {formatNumber(catalog.data?.max_credits_per_incident_per_user)} credits. Values come
              from the same table the API validates against, so the UI can never advertise a reward that is not paid.
            </div>
          </Card>
        </>
      )}
    </>
  );
}

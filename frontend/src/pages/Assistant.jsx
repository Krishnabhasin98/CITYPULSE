import { useState } from "react";
import { Link } from "react-router-dom";
import {
  Activity,
  AlertTriangle,
  Bot,
  Brain,
  CheckCircle2,
  CircleSlash,
  CloudRain,
  Compass,
  FileSearch,
  Gauge,
  MapPin,
  Route,
  Search,
  ShieldCheck,
  Sparkles,
  TrendingUp,
} from "lucide-react";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  Divider,
  ErrorState,
  Input,
  KeyValue,
  LiveDot,
  PageHeader,
  Progress,
  SectionTitle,
  Skeleton,
  SourceChip,
  Stat,
  Tabs,
  cx,
} from "../components/ui";
import { apiGet, endpoints } from "../lib/api";
import { BAND_TONE, formatNumber, formatPercent } from "../lib/format";
import { useApiData } from "../lib/hooks";
import IncidentCard from "../components/incident/IncidentCard";

const STATUS_TONE = { COMPLETED: "low", PARTIAL: "medium", SKIPPED: "neutral", FAILED: "critical" };
const RISK_TONE = { CRITICAL: "critical", HIGH: "high", MEDIUM: "medium", LOW: "low" };
// Answered immediately so the page never opens empty; the suggestion chips below
// let a reader swap in a question grounded in the current live data.
const DEFAULT_QUESTION = "Which incidents in Delhi are past their response deadline?";

function AgentRow({ entry, index }) {
  const tone = STATUS_TONE[entry.status] || "neutral";
  const Icon = entry.status === "COMPLETED" ? CheckCircle2 : entry.status === "SKIPPED" ? CircleSlash : AlertTriangle;
  return (
    <div className="flex items-start gap-3 px-4 py-3">
      <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-[11px] font-black text-[var(--color-text-secondary)]">
        {index + 1}
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <p className="text-xs font-bold text-[var(--color-ink)]">{entry.agent}</p>
          <Badge tone={tone} icon={Icon}>{entry.status}</Badge>
        </div>
        <p className="mt-0.5 text-[11px] text-[var(--color-text-muted)]">{entry.role}</p>
        <p className="mt-1 text-xs leading-relaxed text-[var(--color-text-primary)]">{entry.summary}</p>
      </div>
    </div>
  );
}

export default function Assistant() {
  const [query, setQuery] = useState(DEFAULT_QUESTION);
  const [submitted, setSubmitted] = useState(DEFAULT_QUESTION);
  const [tab, setTab] = useState("answer");

  const suggestions = useApiData(() => apiGet(endpoints.assistantSuggestions()), []);
  const answer = useApiData(
    () => apiGet(endpoints.assistant(submitted)),
    [submitted],
    { skip: !submitted },
  );
  const agentic = useApiData(
    () => (tab === "agents" ? apiGet(endpoints.assistantAgentic(submitted)) : Promise.resolve(null)),
    [submitted, tab],
    { skip: !submitted || tab !== "agents" },
  );

  const submit = (event) => {
    event.preventDefault();
    const text = query.trim();
    if (text) setSubmitted(text);
  };

  const result = answer.data;
  const trace = agentic.data;

  return (
    <>
      <PageHeader
        eyebrow="Civic assistant"
        title="Ask about live Delhi data"
        description="Every answer is assembled from the incidents in the database plus live OpenStreetMap and Open-Meteo lookups. There is no language model inventing numbers — the two views below show the plain answer and the reasoning trace behind it."
      />

      <Card className="p-4">
        <form onSubmit={submit} className="flex flex-col gap-2 sm:flex-row">
          <div className="relative flex-1">
            <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <Input
              className="pl-9"
              placeholder="e.g. What is the risk in pincode 110092?"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </div>
          <Button type="submit" loading={answer.loading && submitted === query}>
            <Sparkles size={15} /> Ask
          </Button>
        </form>
        {(suggestions.data?.suggestions || []).length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1.5">
            {suggestions.data.suggestions.map((prompt) => (
              <button
                key={prompt}
                type="button"
                onClick={() => {
                  setQuery(prompt);
                  setSubmitted(prompt);
                }}
                className="rounded-full border border-[var(--color-border)] bg-white px-3 py-1 text-[11px] font-semibold text-[var(--color-text-secondary)] transition hover:border-[var(--color-cobalt)] hover:text-[var(--color-cobalt)]"
              >
                {prompt}
              </button>
            ))}
          </div>
        )}
      </Card>

      <div className="mt-4">
        <Tabs
          value={tab}
          onChange={setTab}
          tabs={[
            { value: "answer", label: "Answer" },
            { value: "agents", label: "Agent trace" },
          ]}
        />
      </div>

      {tab === "answer" ? (
        <div className="mt-4">
          {answer.error ? (
            <ErrorState error={answer.error} onRetry={answer.reload} />
          ) : answer.loading ? (
            <Card className="space-y-3 p-5">
              <Skeleton className="h-4 w-40" />
              <Skeleton className="h-3 w-full" />
              <Skeleton className="h-3 w-4/5" />
            </Card>
          ) : !result ? (
            <Card className="p-6 text-sm text-[var(--color-text-secondary)]">Ask a question to see the live answer.</Card>
          ) : (
            <>
              <Card className="p-5">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <Badge tone="info" icon={Bot}>{result.intent?.replace(/_/g, " ")}</Badge>
                  <span className="text-[11px] text-[var(--color-text-muted)]">{result.question}</span>
                </div>
                <p className="mt-3 text-sm leading-relaxed text-[var(--color-text-primary)]">{result.answer}</p>
                <p className="mt-3 text-[11px] font-semibold text-[var(--color-text-muted)]">{result.disclaimer}</p>
              </Card>

              {result.area && (
                <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                  <Stat label="Risk score" value={formatNumber(result.risk?.score)} hint={result.risk?.band} tone={BAND_TONE(result.risk?.band)} icon={Gauge} />
                  <Stat label="Confidence" value={formatPercent(result.risk?.confidence)} hint="Data completeness" icon={Compass} />
                  <Stat label="Open incidents" value={formatNumber(result.civic?.open_incidents)} hint={`${result.civic?.reports_clustered ?? 0} reports clustered`} tone="info" icon={Activity} />
                  <Stat label="Past deadline" value={formatNumber(result.civic?.breached_incidents)} hint="SLA breached" tone={result.civic?.breached_incidents ? "critical" : "low"} icon={AlertTriangle} />
                </div>
              )}

              {result.health && (
                <Card className="mt-4">
                  <CardHeader icon={Activity} title="City snapshot" subtitle="Same figures the health dashboard uses" />
                  <div className="grid gap-2 p-5 sm:grid-cols-2 lg:grid-cols-4">
                    <KeyValue label="Civic health" value={`${result.health.score}/100`} />
                    <KeyValue label="Open incidents" value={formatNumber(result.health.open_incidents)} />
                    <KeyValue label="Total reports" value={formatNumber(result.health.total_reports)} />
                    <KeyValue label="Duplicates absorbed" value={formatNumber(result.health.duplicate_reports_absorbed)} />
                  </div>
                </Card>
              )}

              {(result.incidents || []).length > 0 && (
                <section className="mt-5">
                  <SectionTitle title="Highest severity open incidents" subtitle="The live set these answers were drawn from" />
                  <div className="grid gap-3 lg:grid-cols-2">
                    {result.incidents.slice(0, 4).map((incident) => (
                      <IncidentCard key={incident.id} incident={incident} />
                    ))}
                  </div>
                </section>
              )}
            </>
          )}
        </div>
      ) : (
        <div className="mt-4">
          {agentic.error ? (
            <ErrorState error={agentic.error} onRetry={agentic.reload} />
          ) : agentic.loading && !trace ? (
            <Card className="space-y-3 p-5">
              <Skeleton className="h-4 w-48" />
              <Skeleton className="h-3 w-full" />
              <Skeleton className="h-3 w-3/4" />
            </Card>
          ) : !trace ? (
            <Card className="p-6 text-sm text-[var(--color-text-secondary)]">Ask a question to run the agent pipeline.</Card>
          ) : (
            <>
              <Card className="border-indigo-200 bg-indigo-50/50 p-5">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="inline-flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-indigo-900">
                    <Brain size={15} /> Synthesis
                  </p>
                  <div className="flex items-center gap-2">
                    {trace.human_confirmation_required && <Badge tone="medium" icon={ShieldCheck}>human decision required</Badge>}
                    {(trace.data_sources?.osm_nominatim || trace.data_sources?.open_meteo) && <LiveDot label="Live sources" />}
                  </div>
                </div>
                <p className="mt-3 text-sm leading-relaxed text-indigo-950">{trace.synthesis}</p>
              </Card>

              <Card className="mt-4 overflow-hidden">
                <CardHeader
                  icon={Route}
                  title="Agent reasoning trace"
                  subtitle="Six specialists, each reporting COMPLETED, PARTIAL or SKIPPED — never a fabricated number"
                />
                <div className="divide-y divide-slate-100">
                  {(trace.agent_trace || []).map((entry, index) => (
                    <AgentRow key={entry.agent} entry={entry} index={index} />
                  ))}
                </div>
              </Card>

              {trace.limitations?.length > 0 && (
                <Card className="mt-4 border-amber-200 bg-amber-50/60 p-4">
                  <p className="inline-flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-amber-900">
                    <AlertTriangle size={14} /> What this answer does not know
                  </p>
                  <ul className="mt-2 space-y-1 text-xs text-amber-900">
                    {trace.limitations.map((item) => (
                      <li key={item}>• {item}</li>
                    ))}
                  </ul>
                </Card>
              )}

              <div className="mt-4 grid gap-4 lg:grid-cols-2">
                <Card>
                  <CardHeader icon={FileSearch} title="Classification" subtitle="Keyword evidence, not a trained model" />
                  <div className="space-y-1 p-5">
                    <KeyValue label="Category" value={trace.classification?.category} />
                    <KeyValue label="Owning department" value={trace.classification?.department} />
                    <KeyValue label="Baseline severity" value={`${formatNumber(trace.classification?.severity)}/100`} />
                    <KeyValue label="Confidence" value={formatPercent((trace.classification?.confidence ?? 0) * 100)} />
                    <KeyValue label="Matched by" value={trace.classification?.matched_by} />
                    <div className="pt-2">
                      <div className="flex flex-wrap gap-1.5">
                        {(trace.classification?.hazard_tags || []).map((tag) => (
                          <Badge key={tag} tone="neutral">{tag}</Badge>
                        ))}
                      </div>
                    </div>
                  </div>
                </Card>

                <Card>
                  <CardHeader icon={ShieldCheck} title="Trust audit" subtitle={trace.trust?.trust_status} />
                  <div className="p-5">
                    <div className="flex items-center justify-between text-xs font-bold text-[var(--color-text-secondary)]">
                      <span>Trust score</span>
                      <span>{formatNumber(trace.trust?.trust_score)}/100</span>
                    </div>
                    <Progress className="mt-1.5" value={trace.trust?.trust_score} tone={trace.trust?.trust_score >= 70 ? "low" : "medium"} />
                    <div className="mt-3 space-y-1.5">
                      {(trace.trust_signals || []).map((signal) => (
                        <div key={signal.name || signal.signal} className="flex items-start justify-between gap-3 text-[11px]">
                          <span className="text-[var(--color-text-secondary)]">{signal.name || signal.signal}</span>
                          <span className={cx("text-right font-semibold", signal.passed === false ? "text-red-600" : "text-[var(--color-ink)]")}>
                            {signal.detail || signal.value || (signal.passed === false ? "flag" : "ok")}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                </Card>

                <Card>
                  <CardHeader
                    icon={MapPin}
                    title="Geo clustering"
                    subtitle={`${(trace.geo?.matches || []).length} match(es) of ${trace.geo?.candidates ?? 0} within ${formatNumber(trace.geo?.radius_m)} m`}
                  />
                  <div className="divide-y divide-slate-100">
                    {(trace.geo?.matches || []).length ? (
                      trace.geo.matches.slice(0, 5).map((match) => (
                        <div key={match.incident_id} className="flex items-center justify-between gap-3 px-5 py-3">
                          <div className="min-w-0">
                            <p className="truncate text-xs font-bold text-[var(--color-ink)]">{match.title}</p>
                            <p className="text-[10px] text-[var(--color-text-muted)]">
                              {formatNumber(match.distance_meters)} m · confidence {formatPercent((match.confidence ?? 0) * 100)}
                            </p>
                          </div>
                          <Link to={`/incidents/${match.incident_id}`}>
                            <Button size="sm" variant="secondary">Open</Button>
                          </Link>
                        </div>
                      ))
                    ) : (
                      <p className="px-5 py-6 text-xs text-[var(--color-text-secondary)]">
                        No existing incident within the clustering radius — this would open a new one.
                      </p>
                    )}
                  </div>
                </Card>

                <Card>
                  <CardHeader icon={Gauge} title="Risk matrix" subtitle={`${trace.risk?.level} priority`} />
                  <div className="space-y-1 p-5">
                    <div className="flex items-center gap-2 pb-1">
                      <Badge tone={RISK_TONE[trace.risk?.level] || "neutral"}>{trace.risk?.level}</Badge>
                      <span className="text-[11px] text-[var(--color-text-muted)]">
                        {trace.risk?.action_sla_hours}h response window
                      </span>
                    </div>
                    <KeyValue label="Priority score" value={`${formatNumber(trace.risk?.priority_score, 1)}/99`} />
                    <Divider className="my-2" />
                    <p className="text-[11px] leading-relaxed text-[var(--color-text-secondary)]">
                      Priority blends severity, corroborating reports and category weight — crowding cannot raise it,
                      because only verified reports and confirmations count.
                    </p>
                  </div>
                </Card>

                <Card>
                  <CardHeader icon={TrendingUp} title="Policy match" subtitle={trace.policy_status} />
                  <div className="space-y-1 p-5">
                    {trace.policy?.title ? (
                      <>
                        <p className="text-xs font-bold text-[var(--color-ink)]">{trace.policy.title}</p>
                        <p className="text-[11px] leading-relaxed text-[var(--color-text-secondary)]">
                          {trace.policy.policy_intervention || trace.policy.recurring_pattern}
                        </p>
                        {trace.policy.evidence && (
                          <KeyValue label="Evidence reports" value={formatNumber(trace.policy.evidence.reports)} />
                        )}
                      </>
                    ) : (
                      <p className="text-xs text-[var(--color-text-secondary)]">
                        No recurring pattern in the live data matches this category yet.
                      </p>
                    )}
                  </div>
                </Card>

                <Card>
                  <CardHeader
                    icon={CloudRain}
                    title="Forecast"
                    subtitle={trace.forecast?.band ? `${trace.forecast.band} · ${trace.forecast_status}` : trace.forecast_status}
                  />
                  <div className="space-y-1 p-5">
                    {trace.forecast?.score !== undefined ? (
                      <>
                        <KeyValue label="Risk score" value={formatNumber(trace.forecast.score)} />
                        <KeyValue label="Expected incidents / 7d" value={formatNumber(trace.forecast.predicted_incidents_next_7d)} />
                        <KeyValue label="Trend" value={trace.forecast.trend} />
                        <p className="pt-1 text-[11px] leading-relaxed text-[var(--color-text-secondary)]">
                          {trace.forecast.preventive_action || trace.forecast.forecast_30d}
                        </p>
                      </>
                    ) : trace.forecast?.zone ? (
                      <>
                        <p className="text-xs font-bold text-[var(--color-ink)]">{trace.forecast.zone}</p>
                        <KeyValue label="Risk score" value={formatNumber(trace.forecast.risk_score)} />
                        <p className="pt-1 text-[11px] leading-relaxed text-[var(--color-text-secondary)]">
                          {trace.forecast.preventive_action}
                        </p>
                      </>
                    ) : (
                      <p className="text-xs text-[var(--color-text-secondary)]">No forecast inputs were available.</p>
                    )}
                    {trace.weather && (
                      <div className="pt-2">
                        <SourceChip meta={{ source: trace.data_sources?.open_meteo }} label="Weather" />
                      </div>
                    )}
                  </div>
                </Card>
              </div>

              <Card className="mt-4">
                <CardHeader icon={Activity} title="Data provenance" subtitle="Where each number in the trace came from" />
                <div className="grid gap-2 p-5 sm:grid-cols-2 lg:grid-cols-4">
                  <KeyValue label="Area resolution" value={trace.data_sources?.osm_nominatim || "not used"} />
                  <KeyValue label="Weather source" value={trace.data_sources?.open_meteo || "unavailable"} />
                  <KeyValue label="Incidents compared" value={formatNumber(trace.data_sources?.incidents)} />
                  <KeyValue label="Clustering radius" value={`${formatNumber(trace.geo?.radius_m)} m`} />
                </div>
              </Card>
            </>
          )}
        </div>
      )}
    </>
  );
}

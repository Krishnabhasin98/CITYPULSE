import { Clock, Layers, MapPin, Search } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import IncidentMap from "../components/IncidentMap";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  Field,
  Input,
  PageHeader,
  RefreshButton,
  SkeletonRows,
  Tabs,
  cx,
} from "../components/ui";
import { apiGet, endpoints } from "../lib/api";
import { SLA_LABEL, SLA_TONE, categoryColor, formatNumber, formatRelativeTime } from "../lib/format";
import { useApiData } from "../lib/hooks";

export default function LiveMap() {
  const incidents = useApiData(() => apiGet(endpoints.incidents({ limit: 500 })), []);
  const [category, setCategory] = useState("all");
  const [slaFilter, setSlaFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState(null);

  const rows = useMemo(() => incidents.data || [], [incidents.data]);
  const categories = useMemo(() => ["all", ...new Set(rows.map((row) => row.category).filter(Boolean))], [rows]);

  const visible = useMemo(
    () =>
      rows.filter((row) => {
        if (category !== "all" && row.category !== category) return false;
        if (slaFilter === "breached" && row.sla?.state !== "breached") return false;
        if (slaFilter === "open" && row.status === "resolved") return false;
        if (slaFilter === "resolved" && row.status !== "resolved") return false;
        if (search.trim()) {
          const needle = search.trim().toLowerCase();
          const haystack = `${row.title} ${row.affected_area} ${row.pincode || ""} ${row.department}`.toLowerCase();
          if (!haystack.includes(needle)) return false;
        }
        return true;
      }),
    [rows, category, slaFilter, search],
  );

  return (
    <>
      <PageHeader
        eyebrow="Live map"
        title="Every clustered incident on OpenStreetMap"
        description="Each marker is one real-world problem, not one complaint. Red outlines mean the incident is past its own response deadline."
        actions={<RefreshButton onClick={incidents.reload} loading={incidents.loading} />}
      />

      <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
        <div>
          {incidents.error ? (
            <ErrorState error={incidents.error} onRetry={incidents.reload} />
          ) : incidents.loading && !rows.length ? (
            <Card className="h-[520px] animate-pulse bg-slate-50" />
          ) : (
            <IncidentMap incidents={visible} height={520} zoom={11} follow />
          )}

          <div className="mt-3 flex flex-wrap items-center gap-3 text-[11px] text-[var(--color-text-secondary)]">
            <span className="font-bold uppercase tracking-wider text-[var(--color-text-muted)]">Category colour</span>
            {categories.slice(1, 7).map((name) => (
              <span key={name} className="inline-flex items-center gap-1.5">
                <span className="h-2.5 w-2.5 rounded-full" style={{ background: categoryColor(name) }} />
                {name}
              </span>
            ))}
            <span className="inline-flex items-center gap-1.5">
              <span className="h-3 w-3 rounded-full border-2 border-red-900 bg-transparent" /> past deadline
            </span>
          </div>
        </div>

        <Card className="flex max-h-[720px] flex-col overflow-hidden">
          <div className="space-y-3 border-b border-slate-100 p-4">
            <Field label="Search incidents">
              <div className="relative">
                <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <Input
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Title, area or pincode"
                  className="pl-9"
                />
              </div>
            </Field>
            <Tabs
              value={slaFilter}
              onChange={setSlaFilter}
              tabs={[
                { value: "all", label: "All", count: rows.length },
                { value: "open", label: "Open", count: rows.filter((row) => row.status !== "resolved").length },
                { value: "breached", label: "Past deadline", count: rows.filter((row) => row.sla?.state === "breached").length },
                { value: "resolved", label: "Resolved", count: rows.filter((row) => row.status === "resolved").length },
              ]}
            />
            <div className="flex flex-wrap gap-1.5">
              {categories.map((name) => (
                <button
                  key={name}
                  type="button"
                  onClick={() => setCategory(name)}
                  className={cx(
                    "rounded-full border px-2.5 py-1 text-[11px] font-semibold transition",
                    category === name
                      ? "border-[var(--color-cobalt)] bg-blue-50 text-[var(--color-cobalt)]"
                      : "border-[var(--color-border)] bg-white text-[var(--color-text-secondary)] hover:bg-slate-50",
                  )}
                >
                  {name === "all" ? "All categories" : name}
                </button>
              ))}
            </div>
          </div>

          <div className="flex-1 overflow-y-auto p-2">
            {incidents.loading && !rows.length ? (
              <SkeletonRows count={3} className="p-2" />
            ) : visible.length ? (
              <ul className="space-y-1.5">
                {visible.map((incident) => (
                  <li key={incident.id}>
                    <button
                      type="button"
                      onClick={() => setSelected(incident.id)}
                      className={cx(
                        "w-full rounded-xl border p-3 text-left transition",
                        selected === incident.id
                          ? "border-[var(--color-cobalt)] bg-blue-50/60"
                          : "border-transparent hover:bg-slate-50",
                      )}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <Badge tone="info">{incident.category}</Badge>
                        <Badge tone={SLA_TONE(incident.sla?.state)} icon={Clock}>
                          {SLA_LABEL(incident.sla?.state)}
                        </Badge>
                      </div>
                      <p className="mt-1.5 text-xs font-bold leading-snug text-[var(--color-ink)]">{incident.title}</p>
                      <p className="mt-1 flex flex-wrap items-center gap-x-2 text-[11px] text-[var(--color-text-secondary)]">
                        <span className="inline-flex items-center gap-1">
                          <MapPin size={11} /> {incident.affected_area}
                        </span>
                        <span className="inline-flex items-center gap-1">
                          <Layers size={11} /> {incident.report_count} report(s)
                        </span>
                        <span>{formatRelativeTime(incident.first_report_at)}</span>
                      </p>
                      <div className="mt-1.5 flex items-center justify-between text-[11px]">
                        <span className="text-[var(--color-text-muted)]">
                          severity {formatNumber(incident.severity)} · {incident.department}
                        </span>
                        <Link
                          to={`/incidents/${incident.id}`}
                          className="font-bold text-[var(--color-cobalt)]"
                          onClick={(event) => event.stopPropagation()}
                        >
                          Open →
                        </Link>
                      </div>
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <EmptyState
                title="No incidents match"
                message="Clear the filters or search for another area."
                action={
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => {
                      setCategory("all");
                      setSlaFilter("all");
                      setSearch("");
                    }}
                  >
                    Reset filters
                  </Button>
                }
              />
            )}
          </div>
        </Card>
      </div>
    </>
  );
}

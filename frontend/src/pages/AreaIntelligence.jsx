import {
  AlertTriangle,
  Building2,
  Clock,
  Compass,
  Crosshair,
  Droplets,
  Layers,
  MapPin,
  Radar,
  Search,
  Sparkles,
  Thermometer,
  TrendingUp,
} from "lucide-react";
import { useCallback, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  ErrorState,
  Field,
  Input,
  KeyValue,
  LiveDot,
  PageHeader,
  Progress,
  ScoreRing,
  SectionTitle,
  SkeletonRows,
  SourceChip,
  Spinner,
  Stat,
  cx,
} from "../components/ui";
import { apiGet, endpoints } from "../lib/api";
import { BAND_TONE, SLA_LABEL, SLA_TONE, formatHours, formatNumber, formatPercent, titleCase } from "../lib/format";
import { useApiData, useDebounced } from "../lib/hooks";
import { useToast } from "../lib/toast";

const QUICK_AREAS = [
  { label: "Connaught Place", value: "110001" },
  { label: "Karol Bagh", value: "110005" },
  { label: "Laxmi Nagar", value: "110092" },
  { label: "Rohini", value: "110085" },
  { label: "Saket", value: "110017" },
  { label: "Dwarka", value: "110075" },
  { label: "Chandni Chowk", value: "110006" },
];

export default function AreaIntelligence() {
  const toast = useToast();
  const navigate = useNavigate();
  const [query, setQuery] = useState("110001");
  const [submitted, setSubmitted] = useState("110001");
  const [deep, setDeep] = useState(false);
  const [deepLoading, setDeepLoading] = useState(false);
  const [deepData, setDeepData] = useState(null);
  const [suggestOpen, setSuggestOpen] = useState(false);

  const debounced = useDebounced(query, 400);
  const suggestions = useApiData(
    () => apiGet(endpoints.areaSearch(debounced)),
    [debounced],
    { skip: debounced.trim().length < 3 || !suggestOpen },
  );

  const analysis = useApiData(
    () => apiGet(endpoints.areaAnalyze({ query: submitted, deep })),
    [submitted, deep],
  );

  const summary = useApiData(() => apiGet(endpoints.areaSummary()), []);

  const data = analysis.data;
  const risk = data?.risk;
  const area = data?.area;
  const civic = data?.civic;
  const weather = data?.live?.weather;
  const footprint = data?.live?.footprint || deepData?.live?.footprint;

  const runDeepScan = useCallback(async () => {
    setDeepLoading(true);
    try {
      const payload = await apiGet(endpoints.areaAnalyze({ query: submitted, deep: true }));
      setDeepData(payload);
      if (!payload?.live?.footprint) {
        toast.info("Exposure scan unavailable", "The OpenStreetMap Overpass service did not respond. Core analysis is unaffected.");
      }
    } catch (error) {
      toast.error("Exposure scan failed", error.message);
    } finally {
      setDeepLoading(false);
    }
  }, [submitted, toast]);

  const useGps = () => {
    if (!navigator.geolocation) {
      toast.error("Geolocation unavailable", "This browser cannot share a location.");
      return;
    }
    toast.info("Reading GPS…", "Allow location access to analyse your surroundings.");
    navigator.geolocation.getCurrentPosition(
      async (position) => {
        const { latitude, longitude } = position.coords;
        try {
          const place = await apiGet(endpoints.areaResolve({ lat: latitude, lon: longitude }));
          if (place?.place?.postcode) setQuery(place.place.postcode);
          else if (place?.place?.area_name) setQuery(place.place.area_name);
          setSubmitted(`${latitude.toFixed(5)},${longitude.toFixed(5)}`);
        } catch (error) {
          toast.error("GPS analysis failed", error.message);
        }
      },
      () => toast.error("Location denied", "Type a pincode or area name instead."),
    );
  };

  const nearbyIncidents = useMemo(() => data?.incidents || [], [data]);

  return (
    <>
      <PageHeader
        eyebrow="Area intelligence"
        title="Analyse any Delhi location"
        description="Type a 6-digit pincode, a locality, or share your GPS. CityPulse resolves the place through OpenStreetMap, then blends the live incident ledger, real forecast weather and municipal deadlines into one explainable risk score."
      />

      {/* Search */}
      <Card className="p-4">
        <form
          className="flex flex-col gap-3 sm:flex-row sm:items-end"
          onSubmit={(event) => {
            event.preventDefault();
            if (!query.trim()) return;
            setSubmitted(query.trim());
            setSuggestOpen(false);
            setDeepData(null);
            setDeep(false);
          }}
        >
          <div className="relative flex-1">
            <Field label="Pincode, locality or coordinates">
              <div className="relative">
                <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <Input
                  value={query}
                  onChange={(event) => {
                    setQuery(event.target.value);
                    setSuggestOpen(true);
                  }}
                  onFocus={() => setSuggestOpen(true)}
                  placeholder="110092 · Karol Bagh · 28.6139,77.2090"
                  className="pl-9"
                />
              </div>
            </Field>

            {suggestOpen && debounced.trim().length >= 3 && (suggestions.data?.results?.length > 0) && (
              <div className="absolute z-30 mt-1 w-full overflow-hidden rounded-xl border border-[var(--color-border)] bg-white shadow-lg">
                {suggestions.data.results.slice(0, 5).map((row) => (
                  <button
                    key={`${row.label}-${row.latitude}`}
                    type="button"
                    onClick={() => {
                      setQuery(row.postcode || row.area || row.label);
                      setSubmitted(row.postcode || `${row.latitude.toFixed(5)},${row.longitude.toFixed(5)}`);
                      setSuggestOpen(false);
                      setDeepData(null);
                      setDeep(false);
                    }}
                    className="flex w-full items-center gap-2 px-3 py-2.5 text-left text-xs transition hover:bg-slate-50"
                  >
                    <MapPin size={14} className="shrink-0 text-[var(--color-cobalt)]" />
                    <span className="flex-1">
                      <span className="block font-semibold text-[var(--color-ink)]">
                        {row.area || row.label?.split(",")[0]}
                      </span>
                      <span className="block text-[var(--color-text-muted)]">{row.label?.slice(0, 80)}</span>
                    </span>
                    {row.postcode && <Badge tone="neutral">PIN {row.postcode}</Badge>}
                  </button>
                ))}
                <div className="border-t border-slate-100 px-3 py-2 text-[10px] text-[var(--color-text-muted)]">
                  Suggestions come from OpenStreetMap Nominatim
                </div>
              </div>
            )}
          </div>

          <div className="flex gap-2">
            <Button type="submit" loading={analysis.loading}>
              <Radar size={15} /> Analyse area
            </Button>
            <Button variant="secondary" onClick={useGps}>
              <Crosshair size={15} /> Use my GPS
            </Button>
          </div>
        </form>

        <div className="mt-3 flex flex-wrap items-center gap-1.5">
          <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--color-text-muted)]">Quick picks</span>
          {QUICK_AREAS.map((item) => (
            <button
              key={item.value}
              type="button"
              onClick={() => {
                setQuery(item.value);
                setSubmitted(item.value);
                setDeepData(null);
              }}
              className={cx(
                "rounded-full border px-3 py-1 text-[11px] font-semibold transition",
                submitted === item.value
                  ? "border-[var(--color-cobalt)] bg-blue-50 text-[var(--color-cobalt)]"
                  : "border-[var(--color-border)] bg-white text-[var(--color-text-secondary)] hover:bg-slate-50",
              )}
            >
              {item.label}
            </button>
          ))}
        </div>
      </Card>

      {/* Result */}
      <div className="mt-5">
        {analysis.loading && !data ? (
          <SkeletonRows count={2} />
        ) : analysis.error ? (
          <ErrorState error={analysis.error} onRetry={analysis.reload} title="Could not analyse this area" />
        ) : data && !data.resolved ? (
          <Card className="border-amber-200 bg-amber-50/70 p-5">
            <div className="flex items-start gap-3">
              <AlertTriangle size={18} className="mt-0.5 text-amber-600" />
              <div>
                <h3 className="text-sm font-bold text-amber-900">Location not recognised</h3>
                <p className="mt-1 text-xs leading-relaxed text-amber-800">{data.error}</p>
                <p className="mt-2 text-[11px] text-amber-700">
                  Tried using OpenStreetMap{data.provenance?.geocode?.error ? ` (last error: ${data.provenance.geocode.error})` : ""}.
                </p>
              </div>
            </div>
          </Card>
        ) : data ? (
          <div className="space-y-4">
            {/* Area header */}
            <Card className="p-5">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone="info">{area.zone}</Badge>
                    {area.postcode && <Badge tone="neutral">PIN {area.postcode}</Badge>}
                    <SourceChip meta={{ source: area.resolution_source }} label="Resolved" />
                    {analysis.data?.provenance?.prior_available ? (
                      <Badge tone="medium">ward baseline applied</Badge>
                    ) : (
                      <Badge tone="low">evidence-only score</Badge>
                    )}
                  </div>
                  <h2 className="mt-2 text-xl font-bold text-[var(--color-ink)]">{area.area_name}</h2>
                  <p className="mt-0.5 text-xs text-[var(--color-text-secondary)]">
                    {area.display_name?.slice(0, 120) || `${area.latitude?.toFixed(4)}, ${area.longitude?.toFixed(4)}`}
                  </p>
                  <p className="mt-1 text-[11px] text-[var(--color-text-muted)]">
                    Analysis radius {formatNumber(data.radius_m)} m · matched by {area.matched_by?.replace(/-/g, " ")}
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button
                    variant="secondary"
                    onClick={() =>
                      navigate("/report", {
                        state: {
                          latitude: area.latitude,
                          longitude: area.longitude,
                          address: area.area_name,
                          pincode: area.postcode,
                        },
                      })
                    }
                  >
                    Report a problem here
                  </Button>
                  <Button variant="secondary" loading={deepLoading} onClick={runDeepScan} disabled={Boolean(footprint)}>
                    {footprint ? "Exposure scanned" : "Run exposure scan"}
                  </Button>
                </div>
              </div>
            </Card>

            {/* Risk + drivers */}
            <div className="grid gap-4 lg:grid-cols-3">
              <Card className="flex flex-col items-center justify-center p-5">
                <ScoreRing
                  value={risk.score}
                  label="Area risk"
                  tone={BAND_TONE(risk.band)}
                  sublabel={`${risk.confidence}% confidence · ${risk.priority_level} priority`}
                />
                <div className="mt-4 w-full space-y-1.5">
                  <div className="flex justify-between text-xs">
                    <span className="text-[var(--color-text-secondary)]">Live evidence score</span>
                    <span className="font-bold text-[var(--color-ink)]">{formatNumber(risk.evidence_score, 1)}</span>
                  </div>
                  <Progress value={risk.score} tone={BAND_TONE(risk.band)} />
                  <div className="flex justify-between text-[11px] text-[var(--color-text-muted)]">
                    <span>30-day failure probability</span>
                    <span className="font-semibold">{risk.failure_probability_30d}</span>
                  </div>
                  <div className="flex justify-between text-[11px] text-[var(--color-text-muted)]">
                    <span>Expected incidents next 7 days</span>
                    <span className="font-semibold">{risk.predicted_incidents_next_7d}</span>
                  </div>
                  <div className="flex justify-between text-[11px] text-[var(--color-text-muted)]">
                    <span>Response window</span>
                    <span className="font-semibold">{risk.sla_hours}h</span>
                  </div>
                  <div className="flex justify-between text-[11px] text-[var(--color-text-muted)]">
                    <span>Monsoon vulnerability</span>
                    <span className="font-semibold">{risk.monsoon_vulnerability}</span>
                  </div>
                </div>
              </Card>

              <Card className="lg:col-span-2">
                <CardHeader
                  icon={TrendingUp}
                  title="Why this score"
                  subtitle="Each weighted driver is traceable to a source, and the biggest contributors are listed first"
                />
                <ul className="divide-y divide-slate-100">
                  {risk.drivers.map((driver) => (
                    <li key={driver.label} className="flex items-start gap-3 px-5 py-3">
                      <span
                        className={cx(
                          "mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg text-[11px] font-black",
                          driver.weight >= 15
                            ? "bg-red-50 text-red-700"
                            : driver.weight >= 7
                            ? "bg-amber-50 text-amber-800"
                            : "bg-slate-100 text-slate-600",
                        )}
                      >
                        {driver.weight >= 1 ? `+${Math.round(driver.weight)}` : "·"}
                      </span>
                      <div className="min-w-0">
                        <p className="text-xs font-bold text-[var(--color-ink)]">{driver.label}</p>
                        <p className="text-[11px] leading-relaxed text-[var(--color-text-secondary)]">{driver.detail}</p>
                        <p className="mt-0.5 text-[10px] font-semibold uppercase tracking-wider text-[var(--color-text-muted)]">
                          {driver.source}
                        </p>
                      </div>
                    </li>
                  ))}
                </ul>
              </Card>
            </div>

            {/* Local evidence */}
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <Stat label="Open incidents" value={formatNumber(civic.open_incidents)} hint={`${formatNumber(civic.total_incidents)} total in radius`} icon={Layers} />
              <Stat
                label="Past deadline"
                value={formatNumber(civic.breached_incidents)}
                hint={`${formatNumber(civic.due_soon_incidents)} due within 6h`}
                tone={civic.breached_incidents ? "critical" : "low"}
                icon={Clock}
              />
              <Stat
                label="Reports clustered"
                value={formatNumber(civic.reports_clustered)}
                hint={`${formatNumber(civic.duplicate_reports_absorbed)} duplicate(s) absorbed`}
                tone="info"
                icon={Building2}
              />
              <Stat
                label="Worst severity"
                value={formatNumber(civic.worst_severity)}
                hint={`Average ${formatNumber(civic.avg_severity)} · ${formatPercent(civic.resolution_rate)} resolved`}
                tone={BAND_TONE(civic.worst_severity >= 80 ? "CRITICAL" : civic.worst_severity >= 65 ? "HIGH" : "MODERATE")}
                icon={AlertTriangle}
              />
            </div>

            <div className="grid gap-4 lg:grid-cols-3">
              {/* Weather */}
              <Card className="lg:col-span-1">
                <CardHeader
                  icon={Droplets}
                  title="Live conditions"
                  subtitle="Open-Meteo forecast for this location"
                  action={data.live.weather_meta?.source === "live" ? <LiveDot /> : <SourceChip meta={data.live.weather_meta} />}
                />
                <div className="p-5">
                  {weather ? (
                    <>
                      <div className="flex items-baseline justify-between">
                        <span className="text-3xl font-black text-[var(--color-ink)]">
                          {weather.temperature_c !== null ? `${Math.round(weather.temperature_c)}°` : "—"}
                        </span>
                        <span className="text-right text-xs font-semibold text-[var(--color-text-secondary)]">
                          {weather.condition}
                          <span className="block text-[10px] font-normal text-[var(--color-text-muted)]">
                            {weather.humidity !== null ? `${weather.humidity}% humidity` : ""}
                          </span>
                        </span>
                      </div>
                      <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
                        <div className="rounded-lg bg-slate-50 p-2">
                          <p className="text-[10px] font-bold uppercase text-[var(--color-text-muted)]">Rain next 7d</p>
                          <p className="font-bold text-[var(--color-ink)]">{formatNumber(weather.rain_next_7d_mm, 1)} mm</p>
                        </div>
                        <div className="rounded-lg bg-slate-50 p-2">
                          <p className="text-[10px] font-bold uppercase text-[var(--color-text-muted)]">Peak day</p>
                          <p className="font-bold text-[var(--color-ink)]">{formatNumber(weather.peak_daily_rain_mm, 1)} mm</p>
                        </div>
                        <div className="rounded-lg bg-slate-50 p-2">
                          <p className="text-[10px] font-bold uppercase text-[var(--color-text-muted)]">Max temp 7d</p>
                          <p className="font-bold text-[var(--color-ink)]">
                            {weather.max_temp_next_7d_c !== null ? `${Math.round(weather.max_temp_next_7d_c)}°C` : "—"}
                          </p>
                        </div>
                        <div className="rounded-lg bg-slate-50 p-2">
                          <p className="text-[10px] font-bold uppercase text-[var(--color-text-muted)]">Wind</p>
                          <p className="font-bold text-[var(--color-ink)]">
                            {weather.wind_kph !== null ? `${Math.round(weather.wind_kph)} kph` : "—"}
                          </p>
                        </div>
                      </div>
                      <div className="mt-3 flex items-end justify-between gap-1">
                        {(weather.forecast || []).slice(1, 8).map((day) => {
                          const max = Math.max(...(weather.forecast || []).map((row) => Number(row.rain_mm) || 0), 1);
                          const height = Math.max(6, ((Number(day.rain_mm) || 0) / max) * 48);
                          return (
                            <div key={day.date} className="flex flex-1 flex-col items-center gap-1">
                              <span className="text-[9px] text-[var(--color-text-muted)]">
                                {formatNumber(day.rain_mm, 0)}
                              </span>
                              <div
                                className="w-full rounded-t bg-sky-400/70"
                                style={{ height: `${height}px` }}
                                title={`${day.date}: ${day.summary}, ${day.rain_mm} mm`}
                              />
                              <span className="text-[9px] font-semibold text-[var(--color-text-muted)]">
                                {new Date(day.date).toLocaleDateString("en-IN", { weekday: "narrow" })}
                              </span>
                            </div>
                          );
                        })}
                      </div>
                    </>
                  ) : (
                    <p className="text-xs text-[var(--color-text-secondary)]">
                      Live weather unavailable{data.live.weather_meta?.error ? ` (${data.live.weather_meta.error})` : ""}.
                      Risk is computed from incident evidence alone.
                    </p>
                  )}
                </div>
              </Card>

              {/* Directives */}
              <Card className="lg:col-span-2">
                <CardHeader
                  icon={Sparkles}
                  title="Recommended intervention"
                  subtitle="For the department that owns this risk — a human still authorises dispatch"
                />
                <div className="space-y-3 p-5">
                  {risk.recommended_actions.map((action, index) => (
                    <div key={index} className="flex gap-3 rounded-xl bg-slate-50 p-3">
                      <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-[var(--color-ink)] text-[11px] font-black text-white">
                        {index + 1}
                      </span>
                      <p className="text-xs leading-relaxed text-[var(--color-text-primary)]">{action}</p>
                    </div>
                  ))}

                  <div className="grid gap-3 pt-1 sm:grid-cols-3">
                    {[
                      { label: "Electrical risk", value: risk.electrical_risk, icon: Sparkles },
                      { label: "Infrastructure stress", value: risk.infrastructure_stress, icon: Building2 },
                      { label: "Sanitation risk", value: risk.sanitation_risk, icon: Layers },
                    ].map((row) => (
                      <div key={row.label} className="rounded-xl border border-[var(--color-border)] p-3">
                        <p className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-[var(--color-text-muted)]">
                          <row.icon size={12} /> {row.label}
                        </p>
                        <p className="mt-1 text-sm font-bold text-[var(--color-ink)]">{row.value || "—"}</p>
                      </div>
                    ))}
                  </div>

                  {footprint && (
                    <div className="rounded-xl border border-teal-200 bg-teal-50/60 p-3">
                      <p className="text-xs font-bold text-teal-900">Public exposure scan ({formatNumber(footprint.radius_m)} m)</p>
                      <div className="mt-2 grid grid-cols-2 gap-2 text-[11px] text-teal-900 sm:grid-cols-4">
                        <span>Schools: <strong>{footprint.counts.schools}</strong></span>
                        <span>Clinics: <strong>{footprint.counts.healthcare}</strong></span>
                        <span>Markets: <strong>{footprint.counts.markets}</strong></span>
                        <span>Transit: <strong>{footprint.counts.transit}</strong></span>
                      </div>
                      <p className="mt-1 text-[10px] text-teal-800">
                        Sensitivity {footprint.sensitivity} · source OpenStreetMap Overpass
                        {footprint.samples?.schools?.length ? ` · e.g. ${footprint.samples.schools.slice(0, 2).join(", ")}` : ""}
                      </p>
                    </div>
                  )}

                  {risk.ward_officer && (
                    <p className="text-[11px] text-[var(--color-text-muted)]">
                      Curated baseline lists {risk.ward_officer} as the responsible officer for this ward.
                    </p>
                  )}
                </div>
              </Card>
            </div>

            {/* Nearby incidents */}
            <div>
              <SectionTitle
                title={`Nearby incidents (${nearbyIncidents.length})`}
                subtitle={`Within ${formatNumber(data.radius_m)} m of ${area.area_name}`}
                action={
                  <Link to="/map">
                    <Button variant="secondary" size="sm">
                      Open the map
                    </Button>
                  </Link>
                }
              />
              {nearbyIncidents.length ? (
                <div className="grid gap-3 md:grid-cols-2">
                  {nearbyIncidents.map((incident) => (
                    <Card key={incident.id} className="p-4">
                      <div className="flex items-center justify-between gap-2">
                        <Badge tone="info">{titleCase(incident.category)}</Badge>
                        <Badge tone={SLA_TONE(incident.sla?.state)}>
                          {SLA_LABEL(incident.sla?.state)} · {formatHours(incident.sla?.hours_remaining)}
                        </Badge>
                      </div>
                      <Link
                        to={`/incidents/${incident.id}`}
                        className="mt-2 block text-sm font-bold leading-snug text-[var(--color-ink)] hover:text-[var(--color-cobalt)]"
                      >
                        {incident.title}
                      </Link>
                      <KeyValue label="Distance" value={`${formatNumber(incident.distance_m)} m`} />
                      <KeyValue label="Severity" value={`${formatNumber(incident.severity)} · ${incident.priority_level}`} />
                      <KeyValue label="Reports" value={`${incident.report_count} clustered`} />
                      <KeyValue label="Department" value={incident.department} />
                    </Card>
                  ))}
                </div>
              ) : (
                <Card className="flex items-center gap-3 p-4 text-xs text-[var(--color-text-secondary)]">
                  <Compass size={16} className="text-[var(--color-teal)]" />
                  No clustered incident inside this radius yet. The score above is driven by exposure and weather only —
                  a good sign for the area.
                </Card>
              )}
            </div>

            {/* Provenance */}
            <Card className="p-4">
              <SectionTitle title="Where these numbers came from" className="mb-2" />
              <div className="grid gap-2 sm:grid-cols-3">
                {[
                  { label: "Place resolution", meta: { source: area.resolution_source, age_seconds: null, error: area.resolution_meta?.error } },
                  { label: "Weather", meta: data.live.weather_meta },
                  { label: "Exposure scan", meta: data.live.footprint_meta },
                ].map((row) => (
                  <div key={row.label} className="rounded-lg border border-[var(--color-border)] p-3">
                    <p className="text-[10px] font-bold uppercase tracking-wider text-[var(--color-text-muted)]">{row.label}</p>
                    <div className="mt-1">
                      <SourceChip meta={row.meta} />
                    </div>
                    {row.meta?.error && (
                      <p className="mt-1 break-words text-[10px] text-[var(--color-text-muted)]">{String(row.meta.error).slice(0, 120)}</p>
                    )}
                  </div>
                ))}
              </div>
              <p className="mt-3 text-[11px] text-[var(--color-text-muted)]">
                Generated {data.generated_at ? new Date(`${data.generated_at}Z`).toLocaleString("en-IN") : "—"} ·{" "}
                {risk.human_oversight}
              </p>
            </Card>
          </div>
        ) : (
          <Card className="flex items-center gap-3 p-5 text-sm text-[var(--color-text-secondary)]">
            <Spinner /> Preparing area intelligence…
          </Card>
        )}
      </div>

      {/* City-wide comparison */}
      {summary.data?.areas?.length ? (
        <section className="mt-6">
          <SectionTitle
            title="How other areas compare"
            subtitle="Ranked by deadline breaches, then incident pressure"
            action={
              <Link to="/city-health">
                <Button variant="secondary" size="sm">
                  City health
                </Button>
              </Link>
            }
          />
          <Card className="overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 text-[10px] uppercase tracking-wider text-[var(--color-text-muted)]">
                  <tr>
                    <th className="px-4 py-2.5">Area</th>
                    <th className="px-4 py-2.5">Open</th>
                    <th className="px-4 py-2.5">Past deadline</th>
                    <th className="px-4 py-2.5">Reports</th>
                    <th className="px-4 py-2.5">Avg severity</th>
                    <th className="px-4 py-2.5">Pressure</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {summary.data.areas.slice(0, 8).map((row) => (
                    <tr key={row.area} className="hover:bg-slate-50/60">
                      <td className="px-4 py-2.5 font-semibold text-[var(--color-ink)]">{row.area}</td>
                      <td className="px-4 py-2.5">{row.open}</td>
                      <td className={cx("px-4 py-2.5 font-bold", row.breached ? "text-red-600" : "text-[var(--color-text-secondary)]")}>
                        {row.breached}
                      </td>
                      <td className="px-4 py-2.5">{row.reports}</td>
                      <td className="px-4 py-2.5">{formatNumber(row.avg_severity)}</td>
                      <td className="px-4 py-2.5">
                        <div className="flex items-center gap-2">
                          <Progress value={row.pressure * 12} tone={row.breached ? "critical" : "medium"} height="h-1.5" className="w-20" />
                          <span className="font-semibold">{formatNumber(row.pressure, 2)}</span>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </section>
      ) : null}

      <p className="mt-6 flex items-center gap-2 text-[11px] text-[var(--color-text-muted)]">
        <Thermometer size={12} /> Weather from Open-Meteo · boundaries from OpenStreetMap · no API keys, no billing.
      </p>
    </>
  );
}

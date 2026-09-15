import { AlertTriangle, CloudRain, LineChart, MapPin, Sparkles, Thermometer } from "lucide-react";
import { Link } from "react-router-dom";
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
  SectionTitle,
  SkeletonRows,
  SourceChip,
  Stat,
  cx,
} from "../components/ui";
import { apiGet, endpoints } from "../lib/api";
import { BAND_TONE, formatNumber, formatPercent } from "../lib/format";
import { useApiData } from "../lib/hooks";

export default function Forecasts() {
  const forecasts = useApiData(() => apiGet(endpoints.forecasts()), []);
  const monsoon = useApiData(() => apiGet(endpoints.monsoon()), []);
  const rows = forecasts.data || [];

  const totalPredicted = rows.reduce((sum, row) => sum + (row.predicted_incidents_next_7d || 0), 0);
  const totalBreaches = rows.reduce((sum, row) => sum + (row.sla_breaches || 0), 0);

  return (
    <>
      <PageHeader
        eyebrow="Forecasts"
        title="Where the next failures are likely"
        description="Each area's outlook is computed from its own open incidents, severity, deadline breaches and the live 7-day weather forecast — then translated into a preventive action for the owning department."
        actions={<RefreshButton onClick={() => { forecasts.reload(); monsoon.reload(); }} loading={forecasts.loading} />}
      />

      {forecasts.error ? (
        <ErrorState error={forecasts.error} onRetry={forecasts.reload} />
      ) : forecasts.loading && !rows.length ? (
        <SkeletonRows count={3} />
      ) : !rows.length ? (
        <EmptyState title="Not enough history to forecast" message="Forecasts appear once incidents exist across areas." />
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Stat label="Areas tracked" value={formatNumber(rows.length)} hint="Grouped by recorded area" icon={MapPin} />
            <Stat label="Expected incidents / 7d" value={formatNumber(totalPredicted)} hint="Sum of area forecasts" tone="high" icon={LineChart} />
            <Stat label="Outstanding breaches" value={formatNumber(totalBreaches)} hint="Feeding the elevated forecasts" tone={totalBreaches ? "critical" : "low"} icon={AlertTriangle} />
            <Stat
              label="Rain next 7 days"
              value={monsoon.data?.weather ? `${formatNumber(monsoon.data.weather.rain_next_7d_mm, 1)} mm` : "—"}
              hint={monsoon.data ? monsoon.data.escalation.replace(/_/g, " ").toLowerCase() : "Live forecast unavailable"}
              tone="info"
              icon={CloudRain}
            />
          </div>

          {monsoon.data && (
            <Card className="mt-4 border-sky-200 bg-sky-50/60 p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="max-w-2xl">
                  <p className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-sky-900">
                    <CloudRain size={14} /> Monsoon outlook
                  </p>
                  <p className="mt-1 text-sm text-sky-900">{monsoon.data.risk_note}</p>
                  <p className="mt-1 text-[11px] text-sky-800">
                    {monsoon.data.water_sensitive_open_incidents} open water-sensitive incident(s) in scope.
                  </p>
                </div>
                <div className="flex flex-col items-end gap-2">
                  <SourceChip meta={monsoon.data.weather_meta} label="Forecast" />
                  {monsoon.data.weather_meta?.source === "live" && <LiveDot label="Live" />}
                </div>
              </div>
            </Card>
          )}

          <section className="mt-5">
            <SectionTitle title="Area outlook" subtitle="Ranked by forecast risk score" />
            <div className="grid gap-3 lg:grid-cols-2">
              {rows.map((row) => (
                <Card key={row.zone} className="p-4">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="text-sm font-bold text-[var(--color-ink)]">{row.zone}</h3>
                        <Badge tone={BAND_TONE(row.band)}>{row.band}</Badge>
                        <Badge tone={row.trend === "INCREASING" ? "critical" : row.trend === "WATCH" ? "medium" : "low"}>
                          {row.trend.toLowerCase()}
                        </Badge>
                      </div>
                      <p className="mt-1 text-[11px] text-[var(--color-text-secondary)]">
                        {row.categories?.join(" · ") || "Unclassified"} · {row.reports} report(s) · {row.open_incidents} open
                      </p>
                    </div>
                    <div className="text-right">
                      <span className="text-2xl font-black text-[var(--color-ink)]">{formatNumber(row.risk_score, 1)}</span>
                      <span className="block text-[10px] font-bold uppercase tracking-wider text-[var(--color-text-muted)]">
                        risk score
                      </span>
                    </div>
                  </div>

                  <Progress className="mt-3" value={row.risk_score} tone={BAND_TONE(row.band)} />

                  <p className="mt-3 text-xs leading-relaxed text-[var(--color-text-primary)]">{row.forecast_30d}</p>

                  <div className="mt-3 rounded-xl bg-slate-50 p-3 text-[11px] text-[var(--color-text-secondary)]">
                    <p className="flex items-start gap-2">
                      <Sparkles size={13} className="mt-0.5 shrink-0 text-[var(--color-cobalt)]" />
                      {row.preventive_action}
                    </p>
                  </div>

                  <div className="mt-3 grid grid-cols-2 gap-2 text-[11px] sm:grid-cols-4">
                    <div>
                      <p className="text-[10px] font-bold uppercase text-[var(--color-text-muted)]">Avg severity</p>
                      <p className="font-bold text-[var(--color-ink)]">{formatNumber(row.drivers?.avg_severity)}</p>
                    </div>
                    <div>
                      <p className="text-[10px] font-bold uppercase text-[var(--color-text-muted)]">Breaches</p>
                      <p className={cx("font-bold", row.drivers?.sla_breaches ? "text-red-600" : "text-[var(--color-ink)]")}>
                        {row.drivers?.sla_breaches}
                      </p>
                    </div>
                    <div>
                      <p className="text-[10px] font-bold uppercase text-[var(--color-text-muted)]">Rain 7d</p>
                      <p className="font-bold text-[var(--color-ink)]">{formatNumber(row.drivers?.rain_next_7d_mm, 0)} mm</p>
                    </div>
                    <div>
                      <p className="text-[10px] font-bold uppercase text-[var(--color-text-muted)]">Peak temp</p>
                      <p className="font-bold text-[var(--color-ink)]">
                        {row.drivers?.max_temp_next_7d_c !== null && row.drivers?.max_temp_next_7d_c !== undefined
                          ? `${Math.round(row.drivers.max_temp_next_7d_c)}°C`
                          : "—"}
                      </p>
                    </div>
                  </div>

                  <div className="mt-3 flex flex-wrap items-center gap-2">
                    <SourceChip meta={row.weather_meta} label="Weather" />
                    {row.coordinates?.latitude && (
                      <Link to="/area">
                        <Button variant="secondary" size="sm">
                          <MapPin size={13} /> Analyse this area
                        </Button>
                      </Link>
                    )}
                  </div>
                </Card>
              ))}
            </div>
          </section>

          <Card className="mt-5">
            <CardHeader icon={Thermometer} title="How the forecast is produced" subtitle="Deterministic, explainable, no black box" />
            <div className="grid gap-3 p-5 text-xs text-[var(--color-text-secondary)] sm:grid-cols-3">
              <p>
                <strong className="text-[var(--color-ink)]">Incident pressure</strong> blends average severity, report
                volume and outstanding deadline breaches for the area.
              </p>
              <p>
                <strong className="text-[var(--color-ink)]">Weather adjustment</strong> adds risk when rain is forecast
                for water-sensitive categories, or heat for electricity load.
              </p>
              <p>
                <strong className="text-[var(--color-ink)]">Expected incidents</strong> divides the score by eight — a
                transparent rule of thumb you can inspect, not a hidden model.
              </p>
            </div>
            {monsoon.data?.weather && (
              <div className="border-t border-slate-100 px-5 py-3 text-[11px] text-[var(--color-text-muted)]">
                Forecast centre {monsoon.data.centre.latitude.toFixed(3)}, {monsoon.data.centre.longitude.toFixed(3)} ·
                peak rain {formatNumber(monsoon.data.weather.peak_daily_rain_mm, 1)} mm · humidity{" "}
                {formatPercent(monsoon.data.weather.humidity)}
              </div>
            )}
          </Card>
        </>
      )}
    </>
  );
}

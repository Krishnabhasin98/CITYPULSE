import { useMemo } from "react";
import { BAND_TONE, formatNumber } from "../lib/format";
import { Badge, Card, EmptyState, tone } from "./ui";

/**
 * A "spatial city model" built from real data: one tower per area, height by
 * incident load, colour by health band. It replaced a Three.js scene that
 * rendered decorative geometry unrelated to the database (and cost ~1 MB of
 * bundle for the privilege).
 */
export default function CitySkyline({ areas = [], height = 220, onSelect }) {
  const towers = useMemo(() => {
    const rows = areas.slice(0, 14);
    const maxPressure = Math.max(1, ...rows.map((row) => Number(row.pressure) || 0));
    return rows.map((row) => ({
      ...row,
      ratio: Math.max(0.12, (Number(row.pressure) || 0) / maxPressure),
    }));
  }, [areas]);

  if (!towers.length) {
    return (
      <EmptyState
        title="No area load yet"
        message="Once citizens start reporting, each neighbourhood gets a tower here sized by incident pressure."
      />
    );
  }

  return (
    <Card className="p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="text-sm font-bold text-[var(--color-ink)]">Area load skyline</h3>
          <p className="text-xs text-[var(--color-text-secondary)]">
            Tower height is incident pressure (severity + reports + deadline breaches) per area.
          </p>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {["critical", "high", "medium", "low"].map((bandTone) => (
            <Badge key={bandTone} tone={bandTone}>
              {bandTone}
            </Badge>
          ))}
        </div>
      </div>

      <div className="mt-4 overflow-x-auto">
        <svg
          viewBox={`0 0 ${towers.length * 62} ${height}`}
          className="h-[220px] w-full min-w-[520px]"
          role="img"
          aria-label="Incident pressure by area"
        >
          <defs>
            <linearGradient id="skylineBase" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#EEF1F5" stopOpacity="0.2" />
              <stop offset="100%" stopColor="#D9DEE5" stopOpacity="0.7" />
            </linearGradient>
          </defs>
          {[0.25, 0.5, 0.75, 1].map((line) => (
            <line
              key={line}
              x1="0"
              x2={towers.length * 62}
              y1={height - 34 - (height - 60) * line}
              y2={height - 34 - (height - 60) * line}
              stroke="#EEF1F5"
              strokeWidth="1"
            />
          ))}
          {towers.map((tower, index) => {
            const barHeight = (height - 66) * tower.ratio;
            const x = index * 62 + 14;
            const width = 34;
            const y = height - 34 - barHeight;
            const fill = tone(BAND_TONE(tower.band)).ring;
            return (
              <g
                key={tower.area}
                className={onSelect ? "cursor-pointer" : undefined}
                onClick={() => onSelect?.(tower.area)}
              >
                <title>
                  {`${tower.area}: ${formatNumber(tower.open)} open · avg severity ${formatNumber(tower.avg_severity)} · ${tower.breached} breached`}
                </title>
                <rect x={x} y={y} width={width} height={barHeight} rx="4" fill={fill} opacity="0.9" />
                <rect x={x} y={height - 34} width={width} height="6" rx="3" fill="url(#skylineBase)" />
                {tower.breached > 0 && (
                  <circle cx={x + width / 2} cy={y - 7} r="4" fill="#C73E3E">
                    <title>{`${tower.breached} past deadline`}</title>
                  </circle>
                )}
                <text
                  x={x + width / 2}
                  y={height - 18}
                  textAnchor="middle"
                  className="fill-[var(--color-text-secondary)] text-[9px] font-semibold"
                >
                  {tower.area.split(",")[0].slice(0, 9)}
                </text>
                <text
                  x={x + width / 2}
                  y={height - 6}
                  textAnchor="middle"
                  className="fill-[var(--color-text-muted)] text-[8px]"
                >
                  {tower.band}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
    </Card>
  );
}

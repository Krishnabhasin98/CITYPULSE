import { CircleMarker, MapContainer, Popup, TileLayer, Tooltip, useMap } from "react-leaflet";
import { useEffect } from "react";
import { Link } from "react-router-dom";
import "leaflet/dist/leaflet.css";
import { SLA_LABEL, categoryColor, formatNumber, formatRelativeTime, placeholderFor } from "../lib/format";
import { Badge, cx } from "./ui";

const DELHI_CENTER = [28.6139, 77.209];

function FitBounds({ points, follow }) {
  const map = useMap();
  useEffect(() => {
    if (!follow || points.length < 2) return;
    const bounds = points.map((point) => [point.latitude, point.longitude]);
    map.fitBounds(bounds, { padding: [40, 40], maxZoom: 14 });
  }, [map, points, follow]);
  return null;
}

export default function IncidentMap({
  incidents = [],
  height = 420,
  zoom = 11,
  center,
  follow = true,
  className = "",
}) {
  const points = incidents.filter((incident) => incident.latitude && incident.longitude);
  const mapCenter = center || (points[0] ? [points[0].latitude, points[0].longitude] : DELHI_CENTER);

  return (
    <div className={cx("overflow-hidden rounded-2xl border border-[var(--color-border)] bg-slate-100", className)} style={{ height }}>
      <MapContainer center={mapCenter} zoom={zoom} style={{ height: "100%", width: "100%" }} scrollWheelZoom>
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <FitBounds points={points} follow={follow} />
        {points.map((incident) => {
          const breached = incident.sla?.state === "breached";
          return (
            <CircleMarker
              key={incident.id}
              center={[incident.latitude, incident.longitude]}
              radius={breached ? 12 : 9}
              pathOptions={{
                color: breached ? "#7f1d1d" : "#ffffff",
                weight: breached ? 3 : 2,
                fillColor: categoryColor(incident.category),
                fillOpacity: 0.9,
              }}
            >
              <Tooltip direction="top" offset={[0, -8]} opacity={0.95}>
                <span className="text-[11px] font-semibold">{incident.title?.slice(0, 60)}</span>
              </Tooltip>
              <Popup>
                <div className="min-w-[220px] space-y-2">
                  <img
                    src={incident.primary_image_url ? incident.primary_image_url : placeholderFor(incident.category)}
                    alt=""
                    className="h-24 w-full rounded-lg object-cover"
                  />
                  <div className="flex flex-wrap gap-1">
                    <Badge tone="info">{incident.category}</Badge>
                    <Badge tone={breached ? "critical" : incident.severity >= 65 ? "high" : "low"}>
                      {SLA_LABEL(incident.sla?.state)}
                    </Badge>
                  </div>
                  <p className="text-xs font-bold text-slate-900">{incident.title}</p>
                  <p className="text-[11px] text-slate-600">
                    {incident.affected_area} · severity {formatNumber(incident.severity)} · {incident.report_count} report(s)
                  </p>
                  <p className="text-[11px] text-slate-500">
                    {formatRelativeTime(incident.first_report_at)} · {incident.department}
                  </p>
                  <Link to={`/incidents/${incident.id}`} className="text-xs font-bold text-[var(--color-cobalt)]">
                    Open incident →
                  </Link>
                </div>
              </Popup>
            </CircleMarker>
          );
        })}
      </MapContainer>
    </div>
  );
}

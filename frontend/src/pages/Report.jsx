import { AlertTriangle, Camera, CheckCircle2, Crosshair, Layers, MapPin, Send, Sparkles, Trash2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  Field,
  Input,
  KeyValue,
  PageHeader,
  Progress,
  Select,
  Textarea,
  cx,
} from "../components/ui";
import { apiGet, apiPostForm, endpoints } from "../lib/api";
import { formatNumber, titleCase } from "../lib/format";
import { useDebounced } from "../lib/hooks";
import { useSession } from "../lib/session";
import { useToast } from "../lib/toast";

const CATEGORY_OPTIONS = ["Infrastructure", "Electricity", "Sanitation", "Water", "Public Safety"];

export default function Report() {
  const { user, meta } = useSession();
  const toast = useToast();
  const navigate = useNavigate();
  const location = useLocation();
  const prefill = location.state || {};

  const [form, setForm] = useState({
    title: "",
    description: "",
    category: "",
    address: prefill.address || "",
    pincode: prefill.pincode || "",
    latitude: prefill.latitude ? String(prefill.latitude) : "",
    longitude: prefill.longitude ? String(prefill.longitude) : "",
  });
  const [image, setImage] = useState(null);
  const [preview, setPreview] = useState(null);
  const [locating, setLocating] = useState(false);
  const [areaInfo, setAreaInfo] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  const coordinates = useMemo(() => {
    const latitude = Number(form.latitude);
    const longitude = Number(form.longitude);
    if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) return null;
    if (Math.abs(latitude) > 90 || Math.abs(longitude) > 180) return null;
    return { latitude, longitude };
  }, [form.latitude, form.longitude]);

  const debouncedCoords = useDebounced(coordinates, 600);

  // Resolve the neighbourhood as soon as we have coordinates, so the reporter
  // sees which ward their report will land in before submitting.
  useEffect(() => {
    let cancelled = false;
    if (!debouncedCoords || !meta?.live_data_enabled) return undefined;
    (async () => {
      try {
        const resolved = await apiGet(endpoints.areaResolve({ lat: debouncedCoords.latitude, lon: debouncedCoords.longitude }));
        if (!cancelled) setAreaInfo(resolved);
      } catch {
        if (!cancelled) setAreaInfo(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [debouncedCoords, meta?.live_data_enabled]);

  // Show what the clusterer will find before the citizen commits.
  const [nearby, setNearby] = useState([]);
  useEffect(() => {
    let cancelled = false;
    if (!debouncedCoords) return undefined;
    (async () => {
      try {
        const rows = await apiGet(endpoints.incidents({ limit: 200 }));
        if (cancelled) return;
        const close = rows
          .map((row) => ({
            ...row,
            distance: haversine(debouncedCoords.latitude, debouncedCoords.longitude, row.latitude, row.longitude),
          }))
          .filter((row) => row.distance !== null && row.distance <= (meta?.cluster_radius_m || 180) && row.status !== "resolved")
          .sort((a, b) => a.distance - b.distance)
          .slice(0, 3);
        setNearby(close);
      } catch {
        if (!cancelled) setNearby([]);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [debouncedCoords, meta?.cluster_radius_m]);

  // Results from a previous location are hidden until the new lookup resolves.
  const nearbyVisible = debouncedCoords ? nearby : [];

  const locate = useCallback(() => {
    if (!navigator.geolocation) {
      toast.error("Geolocation unavailable", "This browser cannot share a location.");
      return;
    }
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setForm((current) => ({
          ...current,
          latitude: position.coords.latitude.toFixed(6),
          longitude: position.coords.longitude.toFixed(6),
        }));
        setLocating(false);
        toast.success("GPS captured", `Accuracy about ${Math.round(position.coords.accuracy)} m.`);
      },
      () => {
        setLocating(false);
        toast.error("Location denied", "You can type coordinates or an address instead.");
      },
      { enableHighAccuracy: true, timeout: 12000 },
    );
  }, [toast]);

  const onPickFile = (file) => {
    if (!file) {
      setImage(null);
      setPreview(null);
      return;
    }
    if (file.size > (meta?.max_upload_mb || 8) * 1024 * 1024) {
      toast.error("Image too large", `Keep photos under ${meta?.max_upload_mb || 8} MB.`);
      return;
    }
    setImage(file);
    setPreview(URL.createObjectURL(file));
  };

  const submit = async (event) => {
    event.preventDefault();
    setError("");
    if (!user) {
      toast.info("Sign in required", "Use the demo citizen account to try reporting.");
      navigate("/login", { state: { from: "/report" } });
      return;
    }
    if (form.description.trim().length < 8) {
      setError("Please describe the problem in at least 8 characters.");
      return;
    }
    setSubmitting(true);
    try {
      const payload = new FormData();
      payload.append("description", form.description.trim());
      if (form.title.trim()) payload.append("title", form.title.trim());
      if (form.category) payload.append("category", form.category);
      if (form.address.trim()) payload.append("address", form.address.trim());
      if (form.pincode.trim()) payload.append("pincode", form.pincode.trim());
      if (coordinates) {
        payload.append("latitude", String(coordinates.latitude));
        payload.append("longitude", String(coordinates.longitude));
      }
      if (image) payload.append("image", image);

      const response = await apiPostForm(endpoints.report(), payload);
      setResult(response);
      toast.success(
        response.clustered ? "Merged into an existing incident" : "New incident created",
        `${response.credits_awarded >= 0 ? "+" : ""}${response.credits_awarded} credits · trust: ${response.trust?.trust_status}`,
      );
      if (response.incident?.id) {
        setTimeout(() => navigate(`/incidents/${response.incident.id}`), 1200);
      }
    } catch (err) {
      setError(err.message);
      toast.error("Report not submitted", err.message);
    } finally {
      setSubmitting(false);
    }
  };

  if (result) {
    const incident = result.incident;
    return (
      <>
        <PageHeader
          eyebrow="Report received"
          title={result.clustered ? "Merged into an existing incident" : "New incident created"}
          description={result.match_reason}
        />
        <Card className="p-5">
          <div className="flex items-start gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600">
              <CheckCircle2 size={20} />
            </span>
            <div className="flex-1">
              <h2 className="text-base font-bold text-[var(--color-ink)]">{incident.title}</h2>
              <div className="mt-2 flex flex-wrap gap-1.5">
                <Badge tone="info">{titleCase(incident.category)}</Badge>
                <Badge tone="neutral">{incident.department}</Badge>
                <Badge tone={result.credits_awarded < 0 ? "critical" : "low"}>
                  {result.credits_awarded >= 0 ? "+" : ""}{result.credits_awarded} credits
                </Badge>
                <Badge tone="medium">trust: {result.trust?.trust_status}</Badge>
              </div>
              <div className="mt-4 grid gap-x-6 sm:grid-cols-2">
                <KeyValue label="Clustered reports" value={incident.report_count} />
                <KeyValue label="Severity" value={`${formatNumber(incident.severity)} (${incident.severity_label})`} />
                <KeyValue label="Priority" value={`${incident.priority_level} · ${incident.action_sla_hours}h window`} />
                <KeyValue label="Your credit balance" value={result.credits} />
              </div>
              {result.area_context?.area_name && (
                <p className="mt-3 text-xs text-[var(--color-text-secondary)]">
                  Resolved location: {result.area_context.area_name}
                  {result.area_context.zone ? `, ${result.area_context.zone}` : ""}
                  {result.area_context.pincode ? ` · PIN ${result.area_context.pincode}` : ""}
                  {" "}
                  <span className="text-[var(--color-text-muted)]">({result.area_context.source})</span>
                </p>
              )}
              <p className={cx(
                "mt-3 text-xs",
                result.trust?.ai_image_suspected ? "font-semibold text-red-700" : "text-[var(--color-text-muted)]",
              )}>
                AI image screen: {result.trust?.ai_image_suspected
                  ? `suspected · ${result.trust?.ai_image_detection?.reason || "human review required"} · 50 credits deducted · human review required`
                  : "no explicit generator marker found"}
              </p>
              <div className="mt-4 flex flex-wrap gap-2">
                <Link to={`/incidents/${incident.id}`}>
                  <Button>Open the incident</Button>
                </Link>
                <Link to="/">
                  <Button variant="secondary">Back to home</Button>
                </Link>
              </div>
            </div>
          </div>
        </Card>
      </>
    );
  }

  return (
    <>
      <PageHeader
        eyebrow="Report a problem"
        title="Tell CityPulse what is wrong nearby"
        description="Photo, location and a clear description. If a neighbour already reported the same problem within 180 m, your report strengthens that incident instead of creating a duplicate complaint."
      />

      {!user && (
        <Card className="mb-4 border-amber-200 bg-amber-50/70 p-4 text-xs text-amber-900">
          You are not signed in. You can fill the form now, and you will be asked to sign in before submitting.
          Demo: <strong>citizen@citypulse.local</strong> / <strong>password123</strong>
        </Card>
      )}

      <div className="grid gap-4 lg:grid-cols-[1.5fr_1fr]">
        <Card as="form" className="p-5" onSubmit={submit}>
          <div className="space-y-4">
            <Field label="Short title" hint="Optional — a headline makes the map easier to read">
              <Input
                value={form.title}
                onChange={(event) => setForm({ ...form, title: event.target.value })}
                placeholder="Deep pothole outside the metro gate"
                maxLength={120}
              />
            </Field>

            <Field label="What is happening?" required hint={`${form.description.trim().length}/5000 characters`}>
              <Textarea
                required
                minLength={8}
                rows={5}
                value={form.description}
                onChange={(event) => setForm({ ...form, description: event.target.value })}
                placeholder="Describe the hazard, who it affects, and when you saw it."
              />
            </Field>

            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Department guess" hint="Optional — the classifier decides from your text anyway">
                <Select value={form.category} onChange={(event) => setForm({ ...form, category: event.target.value })}>
                  <option value="">Let CityPulse decide</option>
                  {CATEGORY_OPTIONS.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="Area / address">
                <Input
                  value={form.address}
                  onChange={(event) => setForm({ ...form, address: event.target.value })}
                  placeholder="Connaught Place, New Delhi"
                />
              </Field>
            </div>

            <div className="grid gap-4 sm:grid-cols-3">
              <Field label="Latitude">
                <Input
                  value={form.latitude}
                  onChange={(event) => setForm({ ...form, latitude: event.target.value })}
                  placeholder="28.6328"
                  inputMode="decimal"
                />
              </Field>
              <Field label="Longitude">
                <Input
                  value={form.longitude}
                  onChange={(event) => setForm({ ...form, longitude: event.target.value })}
                  placeholder="77.2197"
                  inputMode="decimal"
                />
              </Field>
              <Field label="Pincode" hint="Filled automatically when GPS works">
                <Input
                  value={form.pincode}
                  onChange={(event) => setForm({ ...form, pincode: event.target.value })}
                  placeholder="110001"
                  maxLength={6}
                />
              </Field>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <Button variant="secondary" onClick={locate} loading={locating}>
                <Crosshair size={15} /> Use my GPS
              </Button>
              {coordinates && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setForm({ ...form, latitude: "", longitude: "" })}
                >
                  Clear coordinates
                </Button>
              )}
              {meta?.live_data_enabled && coordinates && (
                <span className="text-[11px] text-[var(--color-text-muted)]">
                  {areaInfo?.place?.area_name
                    ? `Located in ${areaInfo.place.area_name}${areaInfo.place.zone ? `, ${areaInfo.place.zone}` : ""}`
                    : "Resolving neighbourhood…"}
                </span>
              )}
            </div>

            <Field label="Photo evidence" hint="Optional, but a photo raises the trust score from the first report">
              <div className="flex flex-wrap items-center gap-3">
                <label className="inline-flex cursor-pointer items-center gap-2 rounded-lg border border-[var(--color-border)] bg-white px-3.5 py-2 text-xs font-semibold text-[var(--color-text-primary)] transition hover:bg-slate-50">
                  <Camera size={15} /> {image ? "Change photo" : "Add a photo"}
                  <input
                    type="file"
                    accept="image/*"
                    className="hidden"
                    onChange={(event) => onPickFile(event.target.files?.[0] || null)}
                  />
                </label>
                {image && (
                  <Button variant="ghost" size="sm" onClick={() => onPickFile(null)}>
                    <Trash2 size={14} /> Remove
                  </Button>
                )}
                {image && <span className="text-[11px] text-[var(--color-text-muted)]">{image.name}</span>}
              </div>
            </Field>

            {preview && (
              <img src={preview} alt="Selected evidence" className="h-44 w-full rounded-xl object-cover" />
            )}

            {error && (
              <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs font-semibold text-red-700">
                {error}
              </div>
            )}

            <Button type="submit" size="lg" loading={submitting} className="w-full">
              <Send size={15} /> {submitting ? "Clustering with nearby incidents…" : "Submit report"}
            </Button>
          </div>
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader
              icon={MapPin}
              title="Clustering preview"
              subtitle={`Anything within ${meta?.cluster_radius_m || 180} m of your location`}
            />
            <div className="p-4">
              {!coordinates ? (
                <p className="text-xs text-[var(--color-text-secondary)]">
                  Add coordinates or use GPS to see whether your report will join an existing incident.
                </p>
              ) : nearbyVisible.length ? (
                <div className="space-y-2.5">
                  <p className="text-xs font-semibold text-[var(--color-cobalt)]">
                    Your report will strengthen {nearbyVisible.length === 1 ? "this incident" : "one of these incidents"}:
                  </p>
                  {nearbyVisible.map((row) => (
                    <div key={row.id} className="rounded-xl border border-blue-100 bg-blue-50/60 p-3">
                      <p className="text-xs font-bold text-[var(--color-ink)]">{row.title}</p>
                      <div className="mt-1 flex flex-wrap items-center gap-2 text-[10px] text-blue-900">
                        <Badge tone="info">{row.category}</Badge>
                        <span>{formatNumber(row.distance)} m away</span>
                        <span>{row.report_count} report(s)</span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="flex items-start gap-2 text-xs text-[var(--color-text-secondary)]">
                  <Sparkles size={15} className="mt-0.5 text-[var(--color-teal)]" />
                  <p>
                    Nothing reported within the cluster radius yet — this will open a new incident for the ward.
                  </p>
                </div>
              )}
            </div>
          </Card>

          <Card>
            <CardHeader icon={Layers} title="How your report is processed" />
            <ol className="space-y-3 p-4 text-xs text-[var(--color-text-secondary)]">
              {[
                "Classified into a civic category and department from your description.",
                "Scored for severity, with danger words raising the priority and shortening the response deadline.",
                "Spatially clustered against open incidents within the radius on a Haversine distance.",
                "Scored for trust from photo, GPS precision and description quality.",
                "Screened for explicit AI-generator provenance; confirmed markers trigger review and a 50-credit penalty.",
                "Credits awarded: +10 for a standard report, with penalties recorded separately in the ledger.",
              ].map((step, index) => (
                <li key={step} className="flex gap-2.5">
                  <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-slate-100 text-[10px] font-black text-slate-600">
                    {index + 1}
                  </span>
                  {step}
                </li>
              ))}
            </ol>
          </Card>

          {coordinates && (
            <Card className="p-4">
              <p className="text-xs font-bold text-[var(--color-ink)]">Evidence strength</p>
              <div className="mt-2 space-y-2 text-[11px] text-[var(--color-text-secondary)]">
                <div>
                  <div className="flex justify-between">
                    <span>GPS precision</span>
                    <span className="font-semibold">{coordinates ? "provided" : "missing"}</span>
                  </div>
                  <Progress value={coordinates ? 100 : 0} tone="low" height="h-1.5" className="mt-1" />
                </div>
                <div>
                  <div className="flex justify-between">
                    <span>Photo evidence</span>
                    <span className="font-semibold">{image ? "attached" : "none"}</span>
                  </div>
                  <Progress value={image ? 100 : 20} tone={image ? "low" : "medium"} height="h-1.5" className="mt-1" />
                </div>
                <div>
                  <div className="flex justify-between">
                    <span>Description quality</span>
                    <span className="font-semibold">{form.description.trim().length} chars</span>
                  </div>
                  <Progress
                    value={Math.min(100, (form.description.trim().length / 40) * 100)}
                    tone={form.description.trim().length >= 40 ? "low" : "medium"}
                    height="h-1.5"
                    className="mt-1"
                  />
                </div>
              </div>
              <p className={cx("mt-3 flex items-start gap-2 text-[11px]", image ? "text-[var(--color-text-muted)]" : "text-amber-700")}>
                {!image && <AlertTriangle size={13} className="mt-0.5" />}
                {image
                  ? "A photo plus GPS is what moves an incident to Verified."
                  : "Without a photo the report is marked Needs Verification and is easier for others to flag."}
              </p>
            </Card>
          )}
        </div>
      </div>
    </>
  );
}

function haversine(lat1, lon1, lat2, lon2) {
  if ([lat1, lon1, lat2, lon2].some((value) => value === null || value === undefined)) return null;
  const R = 6371000;
  const toRad = (value) => (Number(value) * Math.PI) / 180;
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2;
  return Math.round(R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a)));
}

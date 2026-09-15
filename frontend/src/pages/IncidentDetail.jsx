import {
  AlertTriangle,
  CheckCircle2,
  ChevronLeft,
  ClipboardCheck,
  Clock,
  Eye,
  Flag,
  Image as ImageIcon,
  Layers,
  MapPin,
  ShieldCheck,
  Sparkles,
  ThumbsUp,
  Upload,
  Users,
  X,
} from "lucide-react";
import { useCallback, useState } from "react";
import { Link, useParams } from "react-router-dom";
import EvidenceImage from "../components/EvidenceImage";
import IncidentMap from "../components/IncidentMap";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  ErrorState,
  Field,
  KeyValue,
  LiveDot,
  Modal,
  PageHeader,
  Progress,
  Select,
  SkeletonRows,
  Textarea,
  cx,
} from "../components/ui";
import { apiGet, apiPost, apiPostForm, endpoints } from "../lib/api";
import {
  SLA_LABEL,
  SLA_TONE,
  TRUST_TONE,
  formatDateTime,
  formatHours,
  formatNumber,
  formatRelativeTime,
  titleCase,
} from "../lib/format";
import { useApiData } from "../lib/hooks";
import { useSession } from "../lib/session";
import { useToast } from "../lib/toast";

export default function IncidentDetail() {
  const { id } = useParams();
  const toast = useToast();
  const { user, isAuthority } = useSession();
  const detail = useApiData(() => apiGet(endpoints.incident(id)), [id]);
  const [busy, setBusy] = useState(null);
  const [helpOpen, setHelpOpen] = useState(false);
  const [evidenceOpen, setEvidenceOpen] = useState(false);

  const incident = detail.data;
  const reload = detail.reload;

  const act = useCallback(
    async (actionType, extra = {}) => {
      if (!user) {
        toast.info("Sign in required", "Sign in to confirm, flag or help resolve this incident.");
        return;
      }
      setBusy(actionType);
      try {
        const response = await apiPost(endpoints.actions(id), {
          action_type: actionType,
          description: extra.description || `${actionType} from ${user.name}`,
          evidence_url: extra.evidence_url || null,
        });
        if (response.credits_released) {
          toast.success(`${response.action.label} recorded`, `+${response.credits_awarded} credits released.`);
        } else {
          toast.info(`${response.action.label} recorded`, `${response.pending_credits} credits pending confirmation.`);
        }
        reload();
      } catch (error) {
        if (error.status === 409) toast.info("Already recorded", error.message);
        else toast.error("Action failed", error.message);
      } finally {
        setBusy(null);
      }
    },
    [id, reload, toast, user],
  );

  const verifyAction = async (actionId, approve) => {
    setBusy(`verify-${actionId}`);
    try {
      await apiPost(endpoints.verifyAction(id, actionId), {
        approve,
        note: approve ? "Confirmed by community review" : "Rejected by community review",
      });
      toast.success(approve ? "Action confirmed" : "Action rejected", approve ? "Credits released to the claimant." : "Claimant penalised.");
      reload();
    } catch (error) {
      toast.error("Could not verify", error.message);
    } finally {
      setBusy(null);
    }
  };

  const resolveIncident = async () => {
    setBusy("resolve");
    try {
      await apiPost(endpoints.resolveIncident(id), { verification_notes: "Officially closed from the authority console" });
      toast.success("Incident closed", "The deadline clock has stopped and the ledger updated.");
      reload();
    } catch (error) {
      toast.error("Could not close the incident", error.message);
    } finally {
      setBusy(null);
    }
  };

  if (detail.error) {
    return (
      <>
        <Link to="/" className="mb-4 inline-flex items-center gap-1 text-xs font-semibold text-[var(--color-text-secondary)]">
          <ChevronLeft size={15} /> Back to the feed
        </Link>
        <ErrorState error={detail.error} onRetry={reload} title="Could not load this incident" />
      </>
    );
  }

  if (!incident) {
    return (
      <>
        <PageHeader eyebrow="Incident" title="Loading incident workspace…" />
        <SkeletonRows count={3} />
      </>
    );
  }

  const sla = incident.sla || {};
  const trust = incident.trust_audit || {};
  const pendingActions = (incident.actions || []).filter((action) => action.verification_status === "pending");

  return (
    <>
      <Link to="/" className="mb-4 inline-flex items-center gap-1 text-xs font-semibold text-[var(--color-text-secondary)] hover:text-[var(--color-cobalt)]">
        <ChevronLeft size={15} /> Back to the feed
      </Link>

      <div className="grid gap-4 lg:grid-cols-[1.5fr_1fr]">
        {/* Main column */}
        <div className="space-y-4">
          <Card className="overflow-hidden">
            <EvidenceImage
              src={incident.primary_image_url}
              category={incident.category}
              alt={incident.title}
              className="h-56 w-full sm:h-72"
            />
            <div className="p-5">
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone="info">{titleCase(incident.category)}</Badge>
                <Badge tone="neutral">{incident.department}</Badge>
                <Badge tone={TRUST_TONE(incident.trust_status)}>{incident.trust_status}</Badge>
                <Badge tone={SLA_TONE(sla.state)} icon={Clock}>
                  {SLA_LABEL(sla.state)}
                </Badge>
                <Badge tone="neutral">{incident.status}</Badge>
                {incident.escalated && <Badge tone="critical">escalated</Badge>}
              </div>
              <h1 className="mt-3 text-xl font-bold tracking-tight text-[var(--color-ink)] sm:text-2xl">{incident.title}</h1>
              <p className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-[var(--color-text-secondary)]">
                <span className="inline-flex items-center gap-1">
                  <MapPin size={13} /> {incident.affected_area}
                </span>
                {incident.zone && <span>{incident.zone}</span>}
                {incident.pincode && <span>PIN {incident.pincode}</span>}
                <span>first reported {formatRelativeTime(incident.first_report_at)}</span>
              </p>
              <p className="mt-3 text-sm leading-relaxed text-[var(--color-text-primary)]">{incident.description}</p>

              <div className="mt-4 grid grid-cols-2 gap-x-6 sm:grid-cols-4">
                <KeyValue label="Reports" value={incident.report_count} />
                <KeyValue label="Confirmed" value={incident.support_count} />
                <KeyValue label="Evidence items" value={incident.evidence_count} />
                <KeyValue label="Flags" value={incident.flag_count} />
              </div>
            </div>
          </Card>

          {/* Actions */}
          <Card>
            <CardHeader
              icon={Sparkles}
              title="Act on this incident"
              subtitle="Immediate actions pay credits at once. Higher-value claims wait for confirmation."
              action={<LiveDot label="Community" />}
            />
            <div className="flex flex-wrap gap-2 p-5">
              <Button variant="secondary" loading={busy === "support"} onClick={() => act("support")}>
                <ThumbsUp size={15} /> I can confirm this
              </Button>
              <Button variant="secondary" loading={busy === "verify"} onClick={() => act("verify")}>
                <Eye size={15} /> Verified on ground
              </Button>
              <Button variant="secondary" onClick={() => setEvidenceOpen(true)}>
                <Upload size={15} /> Add photo evidence
              </Button>
              <Button variant="ghost" loading={busy === "flag"} onClick={() => act("flag")}>
                <Flag size={15} /> Flag as inaccurate
              </Button>
              <Button className="sm:ml-auto" onClick={() => setHelpOpen(true)}>
                <Users size={15} /> I can help resolve
              </Button>
              {isAuthority && incident.status !== "resolved" && (
                <Button variant="teal" loading={busy === "resolve"} onClick={resolveIncident}>
                  <ShieldCheck size={15} /> Mark officially resolved
                </Button>
              )}
            </div>
          </Card>

          {/* Cluster explanation */}
          <Card>
            <CardHeader
              icon={Layers}
              title="Why these reports are one incident"
              subtitle={`Clustered within ${formatNumber(incident.cluster?.radius_m)} m — ${incident.cluster?.would_be_duplicate_complaints} duplicate complaint(s) absorbed`}
            />
            <div className="overflow-x-auto p-5 pt-0">
              <table className="w-full text-left text-xs">
                <thead className="text-[10px] uppercase tracking-wider text-[var(--color-text-muted)]">
                  <tr>
                    <th className="py-2 pr-3">Report</th>
                    <th className="py-2 pr-3">Reporter</th>
                    <th className="py-2 pr-3">Distance</th>
                    <th className="py-2 pr-3">Match confidence</th>
                    <th className="py-2">Trust</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {(incident.cluster?.explanation || []).map((row) => (
                    <tr key={row.report_id}>
                      <td className="py-2.5 pr-3">
                        <span className="font-semibold text-[var(--color-ink)]">#{row.report_id}</span>
                        <span className="ml-2 text-[11px] text-[var(--color-text-muted)]">{row.match_reason?.slice(0, 60)}</span>
                      </td>
                      <td className="py-2.5 pr-3">{row.reporter}</td>
                      <td className="py-2.5 pr-3">{row.distance_from_centre_m !== null ? `${formatNumber(row.distance_from_centre_m)} m` : "—"}</td>
                      <td className="py-2.5 pr-3">{row.match_confidence !== null ? `${Math.round((row.match_confidence || 0) * 100)}%` : "first report"}</td>
                      <td className="py-2.5">{row.trust_status}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          {/* Evidence submissions */}
          <Card>
            <CardHeader
              icon={ImageIcon}
              title={`Evidence submissions (${incident.reports?.length || 0})`}
              subtitle={`${incident.evidence?.image_count || 0} photo(s) attached · ${incident.evidence?.fingerprint_duplicates || 0} recycled-image match(es)`}
            />
            <div className="space-y-3 p-5">
              {(incident.reports || []).map((report) => (
                <div key={report.id} className="rounded-xl border border-[var(--color-border)] p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="text-xs font-bold text-[var(--color-ink)]">
                      {report.reporter} · {formatRelativeTime(report.created_at)}
                    </span>
                    <Badge tone={TRUST_TONE(report.trust_status)}>{report.trust_status}</Badge>
                  </div>
                  <p className="mt-1.5 text-xs leading-relaxed text-[var(--color-text-primary)]">{report.description}</p>
                  <div className="mt-2 flex flex-wrap items-center gap-3 text-[11px] text-[var(--color-text-muted)]">
                    {report.address && <span>{report.address}</span>}
                    {report.ai_severity !== null && <span>severity {formatNumber(report.ai_severity)}</span>}
                    {report.image_url && (
                      <a href={report.image_url} target="_blank" rel="noreferrer" className="font-semibold text-[var(--color-cobalt)]">
                        view photo
                      </a>
                    )}
                  </div>
                  {report.image_url && (
                    <img src={report.image_url} alt="" className="mt-2 h-32 w-full rounded-lg object-cover sm:w-56" />
                  )}
                </div>
              ))}
            </div>
          </Card>

          {/* Action log */}
          <Card>
            <CardHeader
              icon={ClipboardCheck}
              title={`Community ledger (${incident.actions?.length || 0})`}
              subtitle="Every claim, its confirmation state and the credits that were actually released"
            />
            <div className="divide-y divide-slate-100">
              {(incident.actions || []).length ? (
                incident.actions.map((action) => (
                  <div key={action.id} className="flex flex-wrap items-center justify-between gap-3 px-5 py-3">
                    <div className="min-w-0">
                      <p className="text-xs font-bold text-[var(--color-ink)]">
                        {action.label} · {action.author}
                      </p>
                      <p className="text-[11px] text-[var(--color-text-secondary)]">{action.description}</p>
                      <p className="text-[10px] text-[var(--color-text-muted)]">
                        {formatDateTime(action.created_at)}
                        {action.verified_by ? ` · confirmed by ${action.verified_by}` : ""}
                        {action.verification_note ? ` · “${action.verification_note}”` : ""}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge
                        tone={
                          action.verification_status === "verified"
                            ? "low"
                            : action.verification_status === "rejected"
                            ? "critical"
                            : "medium"
                        }
                      >
                        {action.verification_status}
                      </Badge>
                      <Badge tone={action.credits_released ? "low" : "neutral"}>
                        {action.credits_released ? `+${action.credits_awarded} cr` : "credits pending"}
                      </Badge>
                      {action.verification_status === "pending" && (
                        <div className="flex gap-1">
                          <Button size="sm" variant="secondary" loading={busy === `verify-${action.id}`} onClick={() => verifyAction(action.id, true)}>
                            <CheckCircle2 size={13} /> Confirm
                          </Button>
                          <Button size="sm" variant="ghost" onClick={() => verifyAction(action.id, false)}>
                            <X size={13} /> Reject
                          </Button>
                        </div>
                      )}
                    </div>
                  </div>
                ))
              ) : (
                <p className="px-5 py-6 text-xs text-[var(--color-text-secondary)]">
                  No community actions yet. Confirming the problem takes one tap and helps the authority prioritise.
                </p>
              )}
            </div>
          </Card>
        </div>

        {/* Side column */}
        <div className="space-y-4">
          <Card>
            <CardHeader icon={Clock} title="Response deadline" subtitle="Derived from severity, reports and confirmation" />
            <div className="p-5">
              <div className="flex items-baseline justify-between">
                <span className={cx("text-2xl font-black", sla.state === "breached" ? "text-red-600" : "text-[var(--color-ink)]")}>
                  {sla.state === "breached" ? `${formatHours(sla.hours_overdue)} overdue` : sla.state === "closed" ? "Closed" : formatHours(sla.hours_remaining)}
                </span>
                <Badge tone={SLA_TONE(sla.state)}>{SLA_LABEL(sla.state)}</Badge>
              </div>
              <Progress
                className="mt-3"
                value={sla.elapsed_percent}
                tone={sla.state === "breached" ? "critical" : sla.state === "due_soon" ? "high" : "low"}
              />
              <div className="mt-3 space-y-0.5">
                <KeyValue label="Response window" value={`${sla.sla_hours} h`} />
                <KeyValue label="Due" value={formatDateTime(sla.due_at)} />
                <KeyValue label="Priority" value={`${incident.priority_level} (${formatNumber(incident.priority_score, 1)})`} />
                <KeyValue label="Severity" value={`${formatNumber(incident.severity)} · ${incident.severity_label}`} />
              </div>
            </div>
          </Card>

          <Card>
            <CardHeader icon={ShieldCheck} title="Trust audit" subtitle={`${trust.trust_score ?? "—"}/100 · ${trust.trust_status || "unknown"}`} />
            <div className="p-5">
              <Progress
                value={trust.trust_score || 0}
                tone={(trust.trust_score || 0) >= 70 ? "low" : (trust.trust_score || 0) <= 35 ? "critical" : "medium"}
              />
              <ul className="mt-3 space-y-2">
                {(trust.signals || []).map((signal) => (
                  <li key={signal.check} className="flex items-start gap-2 text-[11px]">
                    {signal.passed ? (
                      <CheckCircle2 size={13} className="mt-0.5 shrink-0 text-emerald-600" />
                    ) : (
                      <AlertTriangle size={13} className="mt-0.5 shrink-0 text-amber-600" />
                    )}
                    <span>
                      <strong className="text-[var(--color-ink)]">{signal.check}</strong>
                      <span className="block text-[var(--color-text-secondary)]">{signal.detail}</span>
                    </span>
                  </li>
                ))}
              </ul>
              {trust.requires_human_review && (
                <p className="mt-3 rounded-lg bg-amber-50 px-3 py-2 text-[11px] font-semibold text-amber-800">
                  Flagged for human review — an authority should confirm this evidence.
                </p>
              )}
            </div>
          </Card>

          <Card>
            <CardHeader icon={MapPin} title="Location" subtitle={incident.affected_area} />
            <div className="p-3">
              <IncidentMap incidents={[incident]} height={220} zoom={15} follow={false} className="rounded-xl" />
              <div className="mt-3 space-y-0.5 px-1">
                <KeyValue label="Coordinates" value={`${incident.latitude?.toFixed(5)}, ${incident.longitude?.toFixed(5)}`} />
                <KeyValue label="Zone" value={incident.zone || "—"} />
                <KeyValue label="Pincode" value={incident.pincode || "—"} />
              </div>
            </div>
          </Card>

          {pendingActions.length > 0 && (
            <Card className="border-amber-200 bg-amber-50/60">
              <div className="p-4">
                <p className="text-xs font-bold text-amber-900">{pendingActions.length} claim(s) awaiting confirmation</p>
                <p className="mt-1 text-[11px] text-amber-800">
                  Confirm a claim you can see for yourself to release the claimant's credits. You cannot confirm your own.
                </p>
              </div>
            </Card>
          )}
        </div>
      </div>

      {/* CivicHelp modal */}
      <CivicHelpModal
        open={helpOpen}
        onClose={() => setHelpOpen(false)}
        incident={incident}
        onSubmit={async (actionType, description, evidenceUrl) => {
          await act(actionType, { description, evidence_url: evidenceUrl });
          setHelpOpen(false);
        }}
        busy={busy}
      />

      {/* Evidence modal */}
      <EvidenceModal
        open={evidenceOpen}
        onClose={() => setEvidenceOpen(false)}
        onSubmit={async (url, description) => {
          await act("add_evidence", { description, evidence_url: url });
          setEvidenceOpen(false);
        }}
        busy={busy === "add_evidence"}
      />
    </>
  );
}

function CivicHelpModal({ open, onClose, incident, onSubmit, busy }) {
  const catalog = useApiData(() => apiGet(endpoints.creditCatalog()), [], { skip: !open });
  const actions = (catalog.data?.actions || incident.available_actions || []).filter(
    (action) => action.verification !== "immediate",
  );
  const [selected, setSelected] = useState("");
  const [description, setDescription] = useState("");
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);

  const chosen = actions.find((action) => action.key === selected) || actions[0];

  const submit = async (event) => {
    event.preventDefault();
    if (!chosen) return;
    let evidenceUrl = null;
    if (file) {
      setUploading(true);
      try {
        const form = new FormData();
        form.append("file", file);
        const uploaded = await apiPostForm(endpoints.uploadEvidence(), form);
        evidenceUrl = uploaded.url;
      } catch {
        evidenceUrl = null;
      } finally {
        setUploading(false);
      }
    }
    await onSubmit(chosen.key, description, evidenceUrl);
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="I can help resolve this"
      description="Higher-value contributions are recorded immediately and pay out once another citizen or an authority confirms them."
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" form="civic-help-form" loading={busy || uploading}>
            Submit contribution
          </Button>
        </>
      }
    >
      <form id="civic-help-form" onSubmit={submit} className="space-y-4">
        <Field label="What will you do?">
          <Select value={chosen?.key || ""} onChange={(event) => setSelected(event.target.value)}>
            {actions.map((action) => (
              <option key={action.key} value={action.key}>
                {action.label} (+{action.credits} credits)
              </option>
            ))}
          </Select>
        </Field>
        {chosen && <p className="text-[11px] leading-relaxed text-[var(--color-text-secondary)]">{chosen.description}</p>}

        <Field label="Details" required hint="Be specific: what you did, saw or organised">
          <Textarea
            rows={3}
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            placeholder="Cleared the drain inlet with two neighbours this morning…"
          />
        </Field>

        <Field label="Photo proof" hint={chosen?.needs_evidence ? "Required for this action type" : "Optional but speeds up confirmation"}>
          <label className="inline-flex cursor-pointer items-center gap-2 rounded-lg border border-[var(--color-border)] px-3.5 py-2 text-xs font-semibold transition hover:bg-slate-50">
            <Upload size={14} /> {file ? file.name : "Attach a photo"}
            <input type="file" accept="image/*" className="hidden" onChange={(event) => setFile(event.target.files?.[0] || null)} />
          </label>
        </Field>

        <div className="rounded-lg bg-slate-50 p-3 text-[11px] text-[var(--color-text-secondary)]">
          Credits for “{chosen?.label}” are {chosen?.credits ?? 0} and are released only after confirmation. Rejected claims
          cost half of that value.
        </div>
      </form>
    </Modal>
  );
}

function EvidenceModal({ open, onClose, onSubmit, busy }) {
  const [file, setFile] = useState(null);
  const [description, setDescription] = useState("");
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");

  const submit = async (event) => {
    event.preventDefault();
    setError("");
    if (!file) {
      setError("Choose a photo to upload.");
      return;
    }
    setUploading(true);
    try {
      const form = new FormData();
      form.append("file", file);
      const uploaded = await apiPostForm(endpoints.uploadEvidence(), form);
      await onSubmit(uploaded.url, description || "Additional photo evidence attached.");
      setFile(null);
      setDescription("");
    } catch (err) {
      setError(err.message);
    } finally {
      setUploading(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Add photo evidence"
      description="A fresh photo from a different angle makes the incident harder to fake and easier to verify."
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" form="evidence-form" loading={busy || uploading}>
            Upload evidence
          </Button>
        </>
      }
    >
      <form id="evidence-form" onSubmit={submit} className="space-y-4">
        <Field label="Photo" required>
          <label className="inline-flex cursor-pointer items-center gap-2 rounded-lg border border-[var(--color-border)] px-3.5 py-2 text-xs font-semibold transition hover:bg-slate-50">
            <ImageIcon size={14} /> {file ? file.name : "Choose an image"}
            <input type="file" accept="image/*" className="hidden" onChange={(event) => setFile(event.target.files?.[0] || null)} />
          </label>
        </Field>
        <Field label="What does this photo show?">
          <Textarea rows={2} value={description} onChange={(event) => setDescription(event.target.value)} />
        </Field>
        {file && <img src={URL.createObjectURL(file)} alt="preview" className="h-40 w-full rounded-xl object-cover" onError={() => {}} />}
        {error && <p className="text-xs font-semibold text-red-600">{error}</p>}
      </form>
    </Modal>
  );
}

import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { ArrowRight, Lock, Mail, ShieldCheck, Sparkles, Zap } from "lucide-react";
import { Button, Card, Field, Input } from "../components/ui";
import { useToast } from "../lib/toast";
import { useSession } from "../lib/session";

const DEMO_ACCOUNTS = [
  { role: "citizen", label: "Citizen", detail: "Report, verify, earn credits" },
  { role: "authority", label: "Authority", detail: "Resolve, verify, audit SLAs" },
];

export default function Login() {
  const { login, demoLogin, isAuthenticated } = useSession();
  const toast = useToast();
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  if (isAuthenticated) return <Navigate to="/" replace />;

  const submit = async (event) => {
    event.preventDefault();
    setError("");
    setBusy("form");
    try {
      const user = await login(email.trim(), password);
      toast.success(`Welcome back, ${user.name}`);
      navigate("/", { replace: true });
    } catch (err) {
      setError(err.message || "Sign in failed");
    } finally {
      setBusy("");
    }
  };

  const demo = async (role) => {
    setError("");
    setBusy(role);
    try {
      await demoLogin(role);
      toast.success(`Signed in as the demo ${role} account`);
      navigate("/", { replace: true });
    } catch (err) {
      setError(err.message || "Demo sign-in is unavailable on this deployment");
    } finally {
      setBusy("");
    }
  };

  return (
    <div className="flex min-h-screen flex-col lg:flex-row">
      <section className="flex flex-col justify-between bg-[var(--color-ink)] px-6 py-10 text-white lg:w-[46%] lg:px-12 lg:py-14">
        <Link to="/" className="flex items-center gap-2.5">
          <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-[var(--color-cobalt)]">
            <Zap size={18} />
          </span>
          <span className="text-lg font-bold tracking-tight">CityPulse Delhi</span>
        </Link>
        <div className="my-10 max-w-md">
          <h1 className="text-3xl font-black leading-tight sm:text-4xl">
            One clustered report instead of forty duplicate complaints.
          </h1>
          <p className="mt-4 text-sm leading-relaxed text-slate-300">
            Reports from the same spot are merged into a single incident, every incident carries a response deadline,
            and Citizen Credits pay out only when help is verified by another human.
          </p>
          <ul className="mt-8 space-y-3 text-sm text-slate-200">
            <li className="flex items-start gap-2.5">
              <ShieldCheck size={17} className="mt-0.5 shrink-0 text-emerald-400" />
              Live OpenStreetMap and Open-Meteo data — no API keys, no mock numbers.
            </li>
            <li className="flex items-start gap-2.5">
              <Sparkles size={17} className="mt-0.5 shrink-0 text-indigo-300" />
              Any Delhi pincode resolves to a real ward, risk score and owning department.
            </li>
          </ul>
        </div>
        <p className="text-[11px] text-slate-400">
          AI surfaces evidence and deadlines. Humans decide official action.
        </p>
      </section>

      <section className="flex flex-1 items-center justify-center px-5 py-10 sm:px-8">
        <div className="w-full max-w-sm">
          <h2 className="text-2xl font-bold text-[var(--color-ink)]">Sign in</h2>
          <p className="mt-1 text-sm text-[var(--color-text-secondary)]">
            New here?{" "}
            <Link to="/register" className="font-semibold text-[var(--color-cobalt)] hover:underline">
              Create an account
            </Link>
          </p>

          <form className="mt-6 space-y-4" onSubmit={submit}>
            <Field label="Email" required>
              <div className="relative">
                <Mail size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <Input
                  type="email"
                  required
                  autoComplete="email"
                  className="pl-9"
                  placeholder="citizen@citypulse.local"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                />
              </div>
            </Field>
            <Field label="Password" required>
              <div className="relative">
                <Lock size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <Input
                  type="password"
                  required
                  autoComplete="current-password"
                  className="pl-9"
                  placeholder="••••••••"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                />
              </div>
            </Field>

            {error && (
              <p className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs font-semibold text-red-700">
                {error}
              </p>
            )}

            <Button type="submit" size="lg" className="w-full" loading={busy === "form"}>
              Sign in <ArrowRight size={15} />
            </Button>
          </form>

          <Card className="mt-6 p-4">
            <p className="text-[11px] font-bold uppercase tracking-wider text-[var(--color-text-muted)]">
              Try it without an account
            </p>
            <div className="mt-3 grid gap-2 sm:grid-cols-2">
              {DEMO_ACCOUNTS.map((account) => (
                <Button
                  key={account.role}
                  variant="secondary"
                  size="sm"
                  loading={busy === account.role}
                  onClick={() => demo(account.role)}
                >
                  {account.label}
                </Button>
              ))}
            </div>
            <p className="mt-3 text-[11px] leading-relaxed text-[var(--color-text-secondary)]">
              Seeded demo credentials: <span className="font-semibold text-[var(--color-ink)]">citizen@citypulse.local</span> /{" "}
              <span className="font-semibold text-[var(--color-ink)]">password123</span>. One-click demo sign-in is
              disabled when the server runs in production mode.
            </p>
          </Card>
        </div>
      </section>
    </div>
  );
}

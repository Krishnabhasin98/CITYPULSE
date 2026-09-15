import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { ArrowRight, Lock, Mail, MapPin, User, Zap } from "lucide-react";
import { Button, Field, Input } from "../components/ui";
import { useToast } from "../lib/toast";
import { useSession } from "../lib/session";

const MIN_PASSWORD = 6;

export default function Register() {
  const { register, isAuthenticated } = useSession();
  const toast = useToast();
  const navigate = useNavigate();

  const [form, setForm] = useState({ name: "", email: "", password: "", ward: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  if (isAuthenticated) return <Navigate to="/" replace />;

  const update = (key) => (event) => setForm((current) => ({ ...current, [key]: event.target.value }));

  const submit = async (event) => {
    event.preventDefault();
    setError("");
    if (form.password.length < MIN_PASSWORD) {
      setError(`Password must be at least ${MIN_PASSWORD} characters.`);
      return;
    }
    setBusy(true);
    try {
      const user = await register({
        name: form.name.trim(),
        email: form.email.trim(),
        password: form.password,
        ward: form.ward.trim() || null,
      });
      toast.success(`Account created — welcome, ${user.name}`);
      navigate("/", { replace: true });
    } catch (err) {
      setError(err.message || "Could not create the account");
    } finally {
      setBusy(false);
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
            Join the citizens who make Delhi's repair queue visible.
          </h1>
          <div className="mt-8 space-y-4 text-sm text-slate-200">
            <p>
              <strong className="text-white">Report once.</strong> GPS and text clustering fold duplicate complaints
              about the same pothole into a single incident, so pressure builds on the right department.
            </p>
            <p>
              <strong className="text-white">Verify and earn.</strong> Confirming a neighbour's report pays credits
              once — and you can never confirm your own claim.
            </p>
            <p>
              <strong className="text-white">Hold the city to its deadlines.</strong> Every incident has a response
              window published on the public scorecard.
            </p>
          </div>
        </div>
        <p className="text-[11px] text-slate-400">Your email is only used to sign in and to attribute reports.</p>
      </section>

      <section className="flex flex-1 items-center justify-center px-5 py-10 sm:px-8">
        <div className="w-full max-w-sm">
          <h2 className="text-2xl font-bold text-[var(--color-ink)]">Create your account</h2>
          <p className="mt-1 text-sm text-[var(--color-text-secondary)]">
            Already registered?{" "}
            <Link to="/login" className="font-semibold text-[var(--color-cobalt)] hover:underline">
              Sign in
            </Link>
          </p>

          <form className="mt-6 space-y-4" onSubmit={submit}>
            <Field label="Full name" required>
              <div className="relative">
                <User size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <Input
                  required
                  minLength={2}
                  maxLength={100}
                  autoComplete="name"
                  className="pl-9"
                  placeholder="Asha Verma"
                  value={form.name}
                  onChange={update("name")}
                />
              </div>
            </Field>
            <Field label="Email" required>
              <div className="relative">
                <Mail size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <Input
                  type="email"
                  required
                  autoComplete="email"
                  className="pl-9"
                  placeholder="you@example.com"
                  value={form.email}
                  onChange={update("email")}
                />
              </div>
            </Field>
            <Field label="Password" hint={`At least ${MIN_PASSWORD} characters`} required>
              <div className="relative">
                <Lock size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <Input
                  type="password"
                  required
                  minLength={MIN_PASSWORD}
                  autoComplete="new-password"
                  className="pl-9"
                  placeholder="••••••••"
                  value={form.password}
                  onChange={update("password")}
                />
              </div>
            </Field>
            <Field label="Neighbourhood (optional)" hint="Shown on your profile, never publicly">
              <div className="relative">
                <MapPin size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <Input
                  className="pl-9"
                  maxLength={120}
                  placeholder="Karol Bagh"
                  value={form.ward}
                  onChange={update("ward")}
                />
              </div>
            </Field>

            {error && (
              <p className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs font-semibold text-red-700">
                {error}
              </p>
            )}

            <Button type="submit" size="lg" className="w-full" loading={busy}>
              Create account <ArrowRight size={15} />
            </Button>
          </form>

          <p className="mt-5 text-[11px] leading-relaxed text-[var(--color-text-secondary)]">
            By registering you can report problems, verify your neighbours' reports and earn Citizen Credits. Credits
            reward verified help and never buy an incident's priority.
          </p>
        </div>
      </section>
    </div>
  );
}

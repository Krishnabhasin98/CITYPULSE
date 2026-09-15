import { Component } from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    // Keep the console useful for developers without needing a logging service.
    console.error("CityPulse UI error:", error, info?.componentStack);
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="flex min-h-screen items-center justify-center bg-[var(--color-off-white)] px-4">
        <div className="w-full max-w-md rounded-2xl border border-red-200 bg-white p-6 shadow-sm">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-red-50 text-red-600">
            <AlertTriangle size={20} />
          </span>
          <h1 className="mt-4 text-lg font-bold text-[var(--color-ink)]">This screen hit an error</h1>
          <p className="mt-1 text-sm text-[var(--color-text-secondary)]">
            {this.state.error?.message || "An unexpected error occurred while rendering."}
          </p>
          <pre className="mt-3 max-h-40 overflow-auto rounded-lg bg-slate-50 p-3 text-[11px] text-slate-600">
            {String(this.state.error?.stack || "").split("\n").slice(0, 6).join("\n")}
          </pre>
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="mt-4 inline-flex items-center gap-2 rounded-lg bg-[var(--color-cobalt)] px-4 py-2 text-sm font-semibold text-white"
          >
            <RefreshCw size={15} /> Reload the app
          </button>
        </div>
      </div>
    );
  }
}

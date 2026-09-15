import { createContext, useCallback, useContext, useMemo, useRef, useState } from "react";
import { AlertTriangle, CheckCircle2, Info, X } from "lucide-react";

const ToastContext = createContext(null);

const TONES = {
  success: { icon: CheckCircle2, classes: "border-emerald-200 bg-emerald-50 text-emerald-900", accent: "text-emerald-600" },
  error: { icon: AlertTriangle, classes: "border-red-200 bg-red-50 text-red-900", accent: "text-red-600" },
  info: { icon: Info, classes: "border-slate-200 bg-white text-slate-900", accent: "text-[var(--color-cobalt)]" },
};

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const counter = useRef(0);

  const dismiss = useCallback((id) => {
    setToasts((current) => current.filter((toast) => toast.id !== id));
  }, []);

  const push = useCallback(
    (message, { tone = "info", detail, duration = 5000 } = {}) => {
      const id = ++counter.current;
      setToasts((current) => [...current.slice(-3), { id, message, detail, tone }]);
      if (duration) setTimeout(() => dismiss(id), duration);
      return id;
    },
    [dismiss],
  );

  const value = useMemo(
    () => ({
      push,
      success: (message, detail) => push(message, { tone: "success", detail }),
      error: (message, detail) => push(message, { tone: "error", detail, duration: 7000 }),
      info: (message, detail) => push(message, { tone: "info", detail }),
      dismiss,
    }),
    [push, dismiss],
  );

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="pointer-events-none fixed inset-x-0 bottom-24 z-[60] flex flex-col items-center gap-2 px-4 sm:bottom-6 sm:right-6 sm:left-auto sm:items-end">
        {toasts.map((toast) => {
          const tone = TONES[toast.tone] || TONES.info;
          const Icon = tone.icon;
          return (
            <div
              key={toast.id}
              role="status"
              className={`pointer-events-auto flex w-full max-w-sm items-start gap-3 rounded-xl border px-4 py-3 shadow-lg ${tone.classes}`}
            >
              <Icon size={18} className={`mt-0.5 shrink-0 ${tone.accent}`} />
              <div className="flex-1 text-sm">
                <p className="font-semibold leading-snug">{toast.message}</p>
                {toast.detail && <p className="mt-0.5 text-xs opacity-80">{toast.detail}</p>}
              </div>
              <button
                type="button"
                onClick={() => dismiss(toast.id)}
                className="rounded-md p-1 opacity-60 transition hover:opacity-100"
                aria-label="Dismiss notification"
              >
                <X size={14} />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) throw new Error("useToast must be used inside <ToastProvider>");
  return context;
}

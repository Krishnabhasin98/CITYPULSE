import { Activity, LogOut, Menu, Plus, User as UserIcon, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link, NavLink, useLocation, useNavigate } from "react-router-dom";
import { useSession } from "../../lib/session";
import { Badge, Button, cx } from "../ui";
import { NAV_SECTIONS } from "./links";

export default function Navbar() {
  const { user, isAuthority, logout, meta } = useSession();
  const navigate = useNavigate();
  const location = useLocation();
  // The drawer tracks the path it was opened on, so navigating closes it without
  // a state-syncing effect.
  const [drawer, setDrawer] = useState({ open: false, path: location.pathname });
  const drawerOpen = drawer.open && drawer.path === location.pathname;
  const setDrawerOpen = (open) => setDrawer({ open, path: location.pathname });
  const drawerRef = useRef(null);

  useEffect(() => {
    document.body.style.overflow = drawerOpen ? "hidden" : "";
    return () => {
      document.body.style.overflow = "";
    };
  }, [drawerOpen]);

  const handleLogout = () => {
    logout();
    navigate("/");
  };

  return (
    <header className="sticky top-0 z-40 border-b border-[var(--color-border)] bg-white/95 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-7xl items-center gap-3 px-4 sm:px-6 lg:px-8">
        <Link to="/" className="flex items-center gap-2.5">
          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-[var(--color-ink)] text-white">
            <Activity size={19} />
          </span>
          <span className="leading-tight">
            <span className="block text-base font-bold tracking-tight text-[var(--color-ink)]">
              City<span className="text-[var(--color-cobalt)]">Pulse</span>
            </span>
            <span className="hidden text-[9px] font-semibold uppercase tracking-[0.18em] text-[var(--color-text-muted)] sm:block">
              Delhi civic intelligence
            </span>
          </span>
        </Link>

        <nav className="ml-4 hidden flex-1 items-center gap-1 lg:flex">
          {NAV_SECTIONS.slice(0, 2).reduce((acc, section) => [...acc, ...section.links], []).map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              end={link.to === "/"}
              className={({ isActive }) =>
                cx(
                  "flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition",
                  isActive
                    ? "bg-slate-100 text-[var(--color-ink)]"
                    : "text-[var(--color-text-secondary)] hover:bg-slate-50 hover:text-[var(--color-text-primary)]",
                )
              }
            >
              <link.icon size={15} />
              {link.label}
            </NavLink>
          ))}
        </nav>

        <div className="ml-auto flex items-center gap-2">
          {meta?.live_data_enabled ? (
            <Badge tone="low" className="hidden xl:inline-flex">
              live data on
            </Badge>
          ) : (
            <Badge tone="medium" className="hidden xl:inline-flex">
              offline mode
            </Badge>
          )}

          {user ? (
            <>
              <Link
                to="/profile"
                className="hidden items-center gap-2 rounded-lg border border-[var(--color-border)] px-3 py-1.5 text-xs font-semibold text-[var(--color-text-primary)] transition hover:bg-slate-50 sm:flex"
              >
                <UserIcon size={14} className="text-[var(--color-cobalt)]" />
                <span className="max-w-[120px] truncate">{user.name}</span>
                <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-bold text-[var(--color-cobalt)]">
                  {user.credits ?? 0} cr
                </span>
              </Link>
              {isAuthority && (
                <Link to="/authority" className="hidden sm:block">
                  <Badge tone="info">authority</Badge>
                </Link>
              )}
              <button
                type="button"
                onClick={handleLogout}
                title="Sign out"
                className="rounded-lg p-2 text-[var(--color-text-muted)] transition hover:bg-slate-100 hover:text-[var(--color-text-primary)]"
              >
                <LogOut size={16} />
              </button>
            </>
          ) : (
            <Link to="/login">
              <Button variant="secondary" size="sm">
                Sign in
              </Button>
            </Link>
          )}

          <Link to="/report" className="hidden sm:block">
            <Button size="sm">
              <Plus size={15} /> Report
            </Button>
          </Link>

          <button
            type="button"
            onClick={() => setDrawerOpen(true)}
            className="rounded-lg p-2 text-[var(--color-text-secondary)] transition hover:bg-slate-100 lg:hidden"
            aria-label="Open navigation"
          >
            <Menu size={20} />
          </button>
        </div>
      </div>

      {drawerOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div className="absolute inset-0 bg-slate-950/40" onClick={() => setDrawerOpen(false)} />
          <div ref={drawerRef} className="absolute right-0 top-0 h-full w-[86%] max-w-sm overflow-y-auto bg-white p-5 shadow-2xl">
            <div className="mb-4 flex items-center justify-between">
              <span className="text-sm font-bold text-[var(--color-ink)]">Navigate</span>
              <button
                type="button"
                onClick={() => setDrawerOpen(false)}
                className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100"
                aria-label="Close navigation"
              >
                <X size={18} />
              </button>
            </div>

            {user && (
              <div className="mb-5 rounded-xl border border-[var(--color-border)] bg-slate-50 p-3">
                <p className="text-sm font-bold text-[var(--color-ink)]">{user.name}</p>
                <p className="text-[11px] text-[var(--color-text-secondary)]">{user.email}</p>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  <Badge tone="info">{user.credits ?? 0} credits</Badge>
                  {isAuthority && <Badge tone="low">authority</Badge>}
                </div>
              </div>
            )}

            {NAV_SECTIONS.map((section) => (
              <div key={section.title} className="mb-5">
                <p className="mb-2 text-[10px] font-bold uppercase tracking-[0.16em] text-[var(--color-text-muted)]">
                  {section.title}
                </p>
                <div className="space-y-1">
                  {section.links.map((link) => (
                    <NavLink
                      key={link.to}
                      to={link.to}
                      end={link.to === "/"}
                      className={({ isActive }) =>
                        cx(
                          "flex items-center gap-2.5 rounded-lg px-3 py-2.5 text-sm font-semibold transition",
                          isActive
                            ? "bg-[var(--color-ink)] text-white"
                            : "text-[var(--color-text-primary)] hover:bg-slate-100",
                        )
                      }
                    >
                      <link.icon size={17} />
                      {link.label}
                    </NavLink>
                  ))}
                </div>
              </div>
            ))}

            {!user && (
              <Link to="/login" className="block">
                <Button className="w-full">Sign in</Button>
              </Link>
            )}
          </div>
        </div>
      )}
    </header>
  );
}

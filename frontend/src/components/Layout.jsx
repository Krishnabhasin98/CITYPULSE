import { Link, Outlet } from "react-router-dom";
import BottomNav from "./navigation/BottomNav";
import Navbar from "./navigation/Navbar";

/** Shell for every authenticated/primary page: header, content container, footer. */
function Layout() {
  return (
    <div className="flex min-h-screen flex-col bg-[var(--color-off-white)] text-[var(--color-text-primary)] antialiased">
      <Navbar />
      <main className="flex-1 pb-24 lg:pb-10">
        <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
          <Outlet />
        </div>
      </main>

      <footer className="hidden border-t border-[var(--color-border)] bg-white px-4 py-6 lg:block">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 text-xs text-[var(--color-text-secondary)]">
          <p>CityPulse · boundaries and weather from OpenStreetMap and Open-Meteo · no paid APIs or keys</p>
          <div className="flex flex-wrap items-center gap-4">
            <Link to="/area" className="font-semibold hover:text-[var(--color-cobalt)]">
              Area intelligence
            </Link>
            <Link to="/authority" className="font-semibold hover:text-[var(--color-cobalt)]">
              Accountability
            </Link>
            <a href="/docs" className="font-semibold hover:text-[var(--color-cobalt)]">
              API docs
            </a>
            <span className="text-[var(--color-text-muted)]">AI surfaces evidence. Humans decide action.</span>
          </div>
        </div>
      </footer>

      <BottomNav />
    </div>
  );
}

export default Layout;

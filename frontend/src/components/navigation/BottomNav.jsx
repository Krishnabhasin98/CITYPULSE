import { NavLink } from "react-router-dom";
import { cx } from "../ui";
import { MOBILE_TABS } from "./links";

export default function BottomNav() {
  return (
    <nav className="fixed inset-x-0 bottom-0 z-40 border-t border-[var(--color-border)] bg-white/95 backdrop-blur-md lg:hidden">
      <div className="mx-auto flex max-w-md items-stretch justify-between px-2 py-1.5">
        {MOBILE_TABS.map((tab) => (
          <NavLink
            key={tab.to}
            to={tab.to}
            end={tab.to === "/"}
            className={({ isActive }) =>
              cx(
                "flex flex-1 flex-col items-center gap-0.5 rounded-lg px-1 py-1.5 text-[10px] font-bold transition",
                isActive ? "text-[var(--color-cobalt)]" : "text-[var(--color-text-muted)]",
              )
            }
          >
            {({ isActive }) => (
              <>
                <span
                  className={cx(
                    "flex h-8 w-11 items-center justify-center rounded-lg transition",
                    isActive ? "bg-blue-50" : "",
                  )}
                >
                  <tab.icon size={18} />
                </span>
                {tab.label}
              </>
            )}
          </NavLink>
        ))}
      </div>
    </nav>
  );
}

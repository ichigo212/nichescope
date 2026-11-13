import { NavLink, Outlet, useLocation } from "react-router-dom";

import { JobBar, Toasts } from "./JobBar";

const LINKS: [string, string][] = [
  ["/", "Channels"],
  ["/projects", "Projects"],
  ["/mesh", "Mesh"],
  ["/tools", "Tools"],
  ["/settings", "Settings"],
];

export function Layout() {
  const { pathname } = useLocation();
  const full = pathname.startsWith("/mesh");
  return (
    <div className={"flex flex-col " + (full ? "h-screen overflow-hidden" : "min-h-screen")}>
      <header className="sticky top-0 z-30 border-b border-line bg-base/60 backdrop-blur-xl">
        <div className="mx-auto flex h-14 w-full max-w-[1320px] items-center gap-8 px-6">
          <NavLink to="/" className="display flex items-center gap-2.5 text-[22px] text-ink">
            <Mark />
            Nichescope
          </NavLink>
          <nav aria-label="Main" className="flex items-center gap-1">
            {LINKS.map(([to, label]) => (
              <NavLink
                key={to}
                to={to}
                end={to === "/"}
                className={({ isActive }) =>
                  "rounded-sm px-3 py-1.5 text-sm font-medium transition-colors " +
                  (isActive || (to === "/" && pathname.startsWith("/c/")) ? "bg-white/[0.07] text-ink shadow-[inset_0_0_0_1px_rgb(140_162_210/0.18)]" : "text-ink-3 hover:text-ink-2")
                }
              >
                {label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>
      <main className={full ? "min-h-0 flex-1" : "mx-auto w-full max-w-[1320px] flex-1 px-6 pt-8 pb-28"}>
        <Outlet />
      </main>
      <JobBar />
      <Toasts />
    </div>
  );
}

/** The logo: a channel with its first two rings of neighbours. */
export function Mark({ size = 22 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden>
      <circle cx="12" cy="12" r="10.5" fill="none" stroke="#a48bff" strokeOpacity="0.55" strokeWidth="1" />
      <circle cx="12" cy="12" r="6.5" fill="none" stroke="#5ec8f2" strokeOpacity="0.8" strokeWidth="1.2" />
      <circle cx="12" cy="12" r="2.6" fill="#ffffff" />
      <circle cx="18.5" cy="12" r="1.7" fill="#5ec8f2" />
      <circle cx="5.2" cy="8.4" r="1.3" fill="#a48bff" />
      <circle cx="15.8" cy="21.6" r="1.1" fill="#f5a524" />
    </svg>
  );
}

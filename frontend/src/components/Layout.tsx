import { NavLink, Outlet } from "react-router-dom";
import { useTheme } from "../theme/useTheme";

const navItems = [
  { to: "/dashboard", label: "Dashboard" },
  { to: "/triage", label: "Triagem" },
  { to: "/chat", label: "Chat" },
  { to: "/reports", label: "Relatorios" },
  { to: "/upload", label: "Upload" },
];

export default function Layout() {
  const { theme, toggleTheme } = useTheme();

  return (
    <div className="min-h-screen text-slate-900 dark:text-slate-100">
      <header className="border-b border-slate-200 bg-white/70 backdrop-blur dark:border-slate-700 dark:bg-slate-900/80">
        <div className="mx-auto flex w-full max-w-6xl items-center justify-between px-6 py-4">
          <div>
            <div className="text-lg font-semibold">FleetDoctor</div>
            <div className="text-xs uppercase tracking-[0.3em] text-slate-500 dark:text-slate-400">
              Assistente Operacional
            </div>
          </div>
          <div className="flex items-center gap-3">
            <nav className="flex gap-4 text-sm">
              {navItems.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={({ isActive }) =>
                    `rounded-full px-3 py-1 transition ${
                      isActive
                        ? "bg-slate-900 text-white dark:bg-slate-100 dark:!text-slate-900"
                        : "text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
                    }`
                  }
                >
                  {item.label}
                </NavLink>
              ))}
            </nav>
            <button
              type="button"
              onClick={toggleTheme}
              aria-label={theme === "dark" ? "Ativar modo claro" : "Ativar modo escuro"}
              className="rounded-full border border-slate-200 px-3 py-1 text-sm text-slate-700 transition hover:bg-slate-100 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800"
            >
              {theme === "dark" ? "Sun" : "Moon"}
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto w-full max-w-6xl px-6 py-8">
        <Outlet />
      </main>
    </div>
  );
}

import { NavLink, Outlet } from "react-router-dom";

const navItems = [
  { to: "/dashboard", label: "Dashboard" },
  { to: "/triage", label: "Triagem" },
  { to: "/reports", label: "Relatorios" },
  { to: "/upload", label: "Upload" },
];

export default function Layout() {
  return (
    <div className="min-h-screen text-slate-900">
      <header className="border-b border-slate-200 bg-white/70 backdrop-blur">
        <div className="mx-auto flex w-full max-w-6xl items-center justify-between px-6 py-4">
          <div>
            <div className="text-lg font-semibold">FleetDoctor</div>
            <div className="text-xs uppercase tracking-[0.3em] text-slate-500">
              Assistente Operacional
            </div>
          </div>
          <nav className="flex gap-4 text-sm">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  `rounded-full px-3 py-1 transition ${
                    isActive ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-100"
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>
      <main className="mx-auto w-full max-w-6xl px-6 py-8">
        <Outlet />
      </main>
    </div>
  );
}

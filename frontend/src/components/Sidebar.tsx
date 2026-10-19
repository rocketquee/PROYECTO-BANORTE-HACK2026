"use client";

interface Props {
  view: "dashboard" | "asistente";
  onChange: (view: "dashboard" | "asistente") => void;
}

const NAV = [
  { id: "dashboard", label: "Dashboard", icon: "M3 12l9-9 9 9M5 10v10h5v-6h4v6h5V10" },
  { id: "asistente", label: "Asistente IA", icon: "M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" },
] as const;

export default function Sidebar({ view, onChange }: Props) {
  return (
    <aside className="flex h-screen w-60 shrink-0 flex-col bg-ink text-neutral-300">
      <div className="flex items-center gap-3 px-5 py-5">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-brand font-bold text-white">
          BF
        </div>
        <div>
          <p className="text-sm font-semibold text-white">Banorte AI Finanzas</p>
          <p className="text-[11px] text-neutral-500">Prototipo educativo</p>
        </div>
      </div>

      <nav className="mt-2 flex-1 px-3">
        {NAV.map((item) => (
          <button
            key={item.id}
            onClick={() => onChange(item.id)}
            className={`mb-1 flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors ${
              view === item.id
                ? "bg-brand/20 font-medium text-white"
                : "hover:bg-white/5 hover:text-white"
            }`}
          >
            <svg className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.8" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d={item.icon} />
            </svg>
            {item.label}
          </button>
        ))}
      </nav>

      <div className="border-t border-white/10 px-5 py-4 text-[11px] leading-relaxed text-neutral-500">
        Datos sintéticos de demostración.
        <br />
        No afiliado a Banorte.
      </div>
    </aside>
  );
}

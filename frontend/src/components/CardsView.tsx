"use client";

import { useState } from "react";
import TwinklingSquares from "./TwinklingSquares";

type CardControls = {
  online: boolean;
  contactless: boolean;
  atm: boolean;
  abroad: boolean;
};

type DemoCard = {
  id: string;
  name: string;
  ending: string;
  color: "black" | "orange";
  frozen: boolean;
  controls: CardControls;
};

const initialControls: CardControls = {
  online: true,
  contactless: true,
  atm: true,
  abroad: false,
};

const initialCards: DemoCard[] = [
  {
    id: "primary",
    name: "Negra",
    ending: "6782",
    color: "black",
    frozen: false,
    controls: { ...initialControls },
  },
  {
    id: "secondary",
    name: "Naranja",
    ending: "4356",
    color: "orange",
    frozen: false,
    controls: { ...initialControls },
  },
];

const controlItems: {
  id: keyof CardControls;
  title: string;
  description: string;
  icon: string;
}[] = [
  {
    id: "online",
    title: "Pagos en línea",
    description: "Compras web y en aplicaciones.",
    icon: "M3 5h18v14H3zM3 10h18M7 15h3",
  },
  {
    id: "contactless",
    title: "Sin contacto",
    description: "Pagos acercando la tarjeta.",
    icon: "M5 8a10 10 0 000 8m4-5a3 3 0 000 2m4-5a6 6 0 010 8m4-11a11 11 0 010 14",
  },
  {
    id: "atm",
    title: "Retiros en cajero",
    description: "Retiros en cajeros.",
    icon: "M4 4h16v16H4zM8 8h8v3H8zM8 15h2m4 0h2",
  },
  {
    id: "abroad",
    title: "Uso en el extranjero",
    description: "Pagos fuera del país.",
    icon: "M12 3a9 9 0 100 18 9 9 0 000-18zm-8 9h16m-8-9a14 14 0 010 18m0-18a14 14 0 000 18",
  },
];

function CardIcon({ path }: { path: string }) {
  return (
    <svg
      className="h-6 w-6 shrink-0"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      viewBox="0 0 24 24"
      aria-hidden="true"
    >
      <path strokeLinecap="round" strokeLinejoin="round" d={path} />
    </svg>
  );
}

function DemoSwitch({
  label,
  enabled,
  onToggle,
}: {
  label: string;
  enabled: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={enabled}
      aria-label={label}
      onClick={onToggle}
      className="flex min-h-[48px] w-[176px] min-w-[176px] shrink-0 items-center justify-between gap-1 rounded-full border border-[var(--line)] bg-[var(--surface-subtle)] px-2 text-[18px] font-semibold text-[var(--text)]"
    >
      <span className="whitespace-nowrap">{enabled ? "Activado" : "Desactivado"}</span>
      <span
        aria-hidden="true"
        className={`relative h-6 w-10 rounded-full transition-colors motion-reduce:transition-none ${
          enabled ? "bg-[#9E321D]" : "bg-[#55545D]"
        }`}
      >
        <span
          className={`absolute top-1 h-4 w-4 rounded-full bg-white transition-transform motion-reduce:transition-none ${
            enabled ? "translate-x-5" : "translate-x-1"
          }`}
        />
      </span>
    </button>
  );
}

export default function CardsView({
  variant = "cards",
  onOpenSummary,
}: {
  variant?: "home" | "cards";
  onOpenSummary?: () => void;
}) {
  const isHome = variant === "home";
  const [cards, setCards] = useState<DemoCard[]>(initialCards);
  const [selectedId, setSelectedId] = useState(initialCards[0].id);
  const [flipped, setFlipped] = useState(false);
  const [numberRequested, setNumberRequested] = useState(false);
  const [status, setStatus] = useState("");
  const selected = cards.find((card) => card.id === selectedId) ?? cards[0];

  function addCard() {
    const ending = String(1200 + cards.length * 137).slice(-4);
    const card: DemoCard = {
      id: `virtual-${cards.length + 1}`,
      name: "Virtual",
      ending,
      color: cards.length % 2 === 0 ? "orange" : "black",
      frozen: false,
      controls: { ...initialControls },
    };
    setCards((current) => [...current, card]);
    setSelectedId(card.id);
    setFlipped(false);
    setNumberRequested(false);
    setStatus("Tarjeta ficticia agregada a esta demostración.");
  }

  function updateSelected(update: (card: DemoCard) => DemoCard) {
    setCards((current) => current.map((card) => card.id === selected.id ? update(card) : card));
  }

  function toggleControl(control: keyof CardControls) {
    updateSelected((card) => ({
      ...card,
      controls: { ...card.controls, [control]: !card.controls[control] },
    }));
  }

  function selectCard(id: string) {
    setSelectedId(id);
    setFlipped(false);
    setNumberRequested(false);
    setStatus("");
  }

  return (
    <div className={`mx-auto w-full max-w-[1500px] ${
      isHome ? "p-0" : "p-5 pt-3 sm:px-7 lg:px-9"
    }`}>
      {!isHome && (
        <div className="mb-5 flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight text-[var(--text)] sm:text-3xl">
              Tarjetas
            </h1>
            <p className="mt-1 text-base text-[var(--muted)]">
              Administra tarjetas de demostración. No representan productos ni cuentas reales.
            </p>
          </div>
          <button
            type="button"
            onClick={addCard}
            className="min-h-[48px] rounded-full bg-[#17171D] px-6 font-semibold text-white hover:bg-[#33333D]"
          >
            + Nueva tarjeta
          </button>
        </div>
      )}

      <div className={`grid grid-cols-1 items-start gap-5 ${
        isHome
          ? "xl:grid-cols-[minmax(0,1.08fr)_minmax(0,.92fr)]"
          : "xl:grid-cols-[minmax(0,1.05fr)_minmax(0,.95fr)]"
      }`}>
        <section
          aria-labelledby="your-cards-heading"
          className={`relative min-w-0 rounded-2xl border p-5 shadow-sm sm:p-6 ${
            isHome
              ? "overflow-hidden border-[#30303A] bg-black"
              : "border-[var(--line)] bg-[var(--surface)]"
          }`}
        >
          {isHome && <TwinklingSquares />}
          <div className="relative z-10">
            <h3 id="your-cards-heading" className={`w-fit text-xl font-semibold ${
              isHome ? "bg-black px-2 text-white" : "text-[var(--text)]"
            }`}>
              Tus tarjetas
            </h3>
            <div className="mt-4 [perspective:1200px]">
              <div
                className={`relative h-[360px] w-full transition-transform duration-500 motion-reduce:transition-none [transform-style:preserve-3d] sm:h-[264px] ${
                  flipped ? "[transform:rotateY(180deg)]" : ""
                }`}
              >
              <button
                type="button"
                aria-label={flipped ? "Voltear tarjeta al frente" : "Voltear tarjeta al reverso"}
                aria-pressed={flipped}
                aria-hidden={flipped}
                tabIndex={flipped ? -1 : 0}
                onClick={() => setFlipped((value) => !value)}
                className={`absolute inset-0 flex h-full w-full flex-col justify-between overflow-hidden rounded-3xl p-4 text-left text-white shadow-xl [backface-visibility:hidden] sm:p-8 ${
                  selected.color === "black"
                    ? "bg-[#17171D]"
                    : "bg-[#9E321D]"
                }`}
              >
                <div className="flex flex-col items-start justify-between gap-3 sm:flex-row sm:items-start">
                  <div className="min-w-0">
                    <p className="text-[18px] font-semibold">Prototipo educativo</p>
                  </div>
                  <span
                    className={`rounded-full px-4 py-2 font-semibold ${
                      selected.frozen
                        ? "bg-[#fff1d6] text-[#593500]"
                        : "bg-[#d9f2df] text-[#174b2d]"
                    }`}
                  >
                    {selected.frozen ? "Congelada" : "Activa"}
                  </span>
                </div>
                <div>
                  <p className="whitespace-nowrap text-xl font-semibold tracking-[0.12em] sm:text-3xl">
                    **** {selected.ending}
                  </p>
                  <div className="mt-4 flex flex-wrap items-end justify-between gap-x-4 gap-y-2">
                    <div>
                      <p className="text-base text-white">Vence</p>
                      <p className="font-semibold">08/29</p>
                    </div>
                    <div>
                      <p className="text-base text-white">CVV</p>
                      <p className="font-semibold tracking-widest">•••</p>
                    </div>
                    <p className="w-full text-base font-medium text-white">Toca la tarjeta para voltearla</p>
                  </div>
                </div>
              </button>
              <button
                type="button"
                aria-label="Voltear tarjeta al frente"
                aria-hidden={!flipped}
                tabIndex={flipped ? 0 : -1}
                onClick={() => setFlipped(false)}
                className="absolute inset-0 flex h-full w-full flex-col justify-between rounded-3xl bg-[#24242D] p-4 text-left text-white shadow-xl [backface-visibility:hidden] [transform:rotateY(180deg)] sm:p-8"
              >
                <p className="font-semibold">Prototipo educativo</p>
                <p className="text-base text-white">
                  Esta tarjeta es ficticia. No incluye un número completo ni datos de pago reales.
                </p>
                <p className="text-base font-medium text-white">Toca para volver al frente</p>
              </button>
              </div>
            </div>

            <div className="mt-5 flex flex-wrap items-center gap-3" aria-label="Seleccionar tarjeta">
              {cards.map((card) => (
              <button
                key={card.id}
                type="button"
                aria-pressed={selected.id === card.id}
                onClick={() => selectCard(card.id)}
                className={`flex min-h-[48px] items-center gap-3 rounded-full border px-5 font-medium ${
                  selected.id === card.id
                    ? isHome
                      ? "border-white bg-[#ffffff] text-[#17171D]"
                      : "border-[#9E321D] bg-[#FCE8E2] text-[#742515]"
                    : isHome
                      ? "border-white/50 bg-black text-white hover:bg-[#24242D]"
                      : "border-[var(--line)] text-[var(--text)] hover:bg-[var(--surface-subtle)]"
                }`}
              >
                <span
                  aria-hidden="true"
                  className={`h-4 w-4 rounded-full ${
                    card.color === "black" ? "bg-[#17171D]" : "bg-[#9E321D]"
                  }`}
                />
                {card.name} •• {card.ending}
              </button>
              ))}
              <button
              type="button"
              onClick={addCard}
              aria-label="Agregar tarjeta ficticia"
              className={`flex min-h-[48px] min-w-[48px] items-center justify-center rounded-full border border-dashed text-2xl font-semibold ${
                isHome
                  ? "border-white bg-black text-white hover:bg-[#24242D]"
                  : "border-[#9E321D] text-[#742515] hover:bg-[#FCE8E2]"
              }`}
            >
              +
              </button>
            </div>

            <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <button
              type="button"
              aria-pressed={selected.frozen}
              onClick={() => {
                updateSelected((card) => ({ ...card, frozen: !card.frozen }));
                setStatus(selected.frozen ? "Tarjeta descongelada (demostración)." : "Tarjeta congelada (demostración).");
              }}
              className={`min-h-[48px] rounded-xl border px-3 font-medium ${
                isHome
                  ? "border-white/50 bg-black text-white hover:bg-[#24242D]"
                  : "border-[var(--line)] text-[var(--text)] hover:bg-[var(--surface-subtle)]"
              }`}
            >
              {selected.frozen ? "Descongelar" : "Congelar"}
            </button>
            <button
              type="button"
              aria-pressed={numberRequested}
              onClick={() => {
                setNumberRequested((value) => !value);
                setStatus("El número completo no se muestra en este prototipo.");
              }}
              className={`min-h-[48px] rounded-xl border px-3 font-medium ${
                isHome
                  ? "border-white/50 bg-black text-white hover:bg-[#24242D]"
                  : "border-[var(--line)] text-[var(--text)] hover:bg-[var(--surface-subtle)]"
              }`}
            >
              {numberRequested ? "Ocultar número" : "Mostrar número"}
            </button>
            <button
              type="button"
              onClick={() => setStatus("Copia simulada: no se copió ningún número real.")}
              className={`min-h-[48px] rounded-xl border px-3 font-medium ${
                isHome
                  ? "border-white/50 bg-black text-white hover:bg-[#24242D]"
                  : "border-[var(--line)] text-[var(--text)] hover:bg-[var(--surface-subtle)]"
              }`}
            >
              Copiar número
            </button>
            <button
              type="button"
              aria-pressed={flipped}
              onClick={() => setFlipped((value) => !value)}
              className={`min-h-[48px] rounded-xl border px-3 font-medium ${
                isHome
                  ? "border-white/50 bg-black text-white hover:bg-[#24242D]"
                  : "border-[var(--line)] text-[var(--text)] hover:bg-[var(--surface-subtle)]"
              }`}
            >
              Voltear
            </button>
            </div>
            <p className={`mt-4 min-h-6 text-base font-medium ${
              isHome ? "bg-black text-white" : "text-[#742515]"
            }`} aria-live="polite">
            {status}
            </p>
          </div>
        </section>

        <section
          aria-labelledby="card-controls-heading"
          className="min-w-0 rounded-2xl border border-[var(--line)] bg-[var(--surface)] p-5 shadow-sm sm:p-6"
        >
          <h3 id="card-controls-heading" className="text-xl font-semibold text-[var(--text)]">
            Controles de la tarjeta
          </h3>
          <p className="mt-1 text-base text-[var(--muted)]">
            Cambios locales de demostración para {selected.name.toLowerCase()} •• {selected.ending}.
          </p>
          <div className="mt-4 divide-y divide-[var(--line)]">
            {controlItems.map((item) => (
              <div key={item.id} className="flex min-h-[92px] flex-wrap items-center justify-between gap-4 py-4">
                <div className="flex min-w-0 flex-1 items-center gap-4">
                  <span className="text-[#9E321D]">
                    <CardIcon path={item.icon} />
                  </span>
                  <div className="min-w-0">
                    <h4 className="font-semibold text-[var(--text)]">{item.title}</h4>
                    <p className="text-base text-[var(--muted)]">{item.description}</p>
                  </div>
                </div>
                <DemoSwitch
                  label={item.title}
                  enabled={selected.controls[item.id]}
                  onToggle={() => toggleControl(item.id)}
                />
              </div>
            ))}
          </div>
        </section>
      </div>
      {isHome && (
        <section className="mt-5 flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-[var(--line)] bg-[var(--surface)] p-5 shadow-sm sm:p-6">
          <div>
            <p className="font-medium text-[var(--muted)]">Saldo total de demostración</p>
            <p className="mt-1 text-2xl font-semibold text-[var(--text)]">$85,921</p>
          </div>
          <button
            type="button"
            onClick={onOpenSummary}
            className="min-h-[48px] rounded-full bg-[#17171D] px-6 font-semibold text-white hover:bg-[#33333D]"
          >
            Ver resumen completo
          </button>
        </section>
      )}
    </div>
  );
}

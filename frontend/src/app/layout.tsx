import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Banorte AI Finanzas — Prototipo",
  description:
    "Prototipo educativo: agente financiero con MCP e interfaces dinámicas generadas en tiempo real. Datos sintéticos; no afiliado a Banorte.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es">
      {/* The app owns the viewport height (100dvh) and the page itself never
          scrolls: only the message list, the content panel and the history
          list scroll internally (UI-1). */}
      <body className="h-[100dvh] overflow-hidden">{children}</body>
    </html>
  );
}

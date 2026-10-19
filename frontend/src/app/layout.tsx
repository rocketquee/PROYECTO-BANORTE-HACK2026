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
      <body>{children}</body>
    </html>
  );
}

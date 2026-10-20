export function money(value: number, decimals = 2): string {
  return new Intl.NumberFormat("es-MX", {
    style: "currency",
    currency: "MXN",
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value);
}

export function fmtDate(iso: string): string {
  const months = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
  ];
  const [y, m, d] = iso.split("-").map(Number);
  if (!y || !m || !d) return iso;
  return `${d} de ${months[m - 1]} de ${y}`;
}

export function fmtDateShort(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  if (!y || !m || !d) return iso;
  return `${String(d).padStart(2, "0")}/${String(m).padStart(2, "0")}/${y}`;
}

// WCAG 2.2 AA: every color has >= 3:1 contrast against white when used for
// graphic elements, and >= 4.5:1 for text on white.
export const CHART_COLORS = [
  "#9E0C24", // red
  "#1D6F8C", // teal blue
  "#7A4E2D", // brown
  "#5B3E96", // purple
  "#1F6E43", // green
  "#8C6D1F", // dark gold
  "#B0446C", // magenta
  "#42525B", // slate
  "#C2410C", // dark orange
  "#4D7C0F", // olive
];

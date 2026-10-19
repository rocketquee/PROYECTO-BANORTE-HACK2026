export function money(value: number, decimals = 0): string {
  return new Intl.NumberFormat("es-MX", {
    style: "currency",
    currency: "MXN",
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value);
}

export function fmtDate(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  if (!y || !m || !d) return iso;
  return `${String(d).padStart(2, "0")}/${String(m).padStart(2, "0")}/${y}`;
}

export const CHART_COLORS = [
  "#C8102E", "#E4572E", "#F3A712", "#2E86AB", "#4C9F70",
  "#7D5BA6", "#D06FA8", "#5C6B73", "#9E2B25", "#88A09E",
];

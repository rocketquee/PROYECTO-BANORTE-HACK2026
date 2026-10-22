const SENSITIVE_TEXT_PATTERNS = [
  /\b(?:nip|cvv|cvc|contrase(?:n|ñ)a|password|clave|token|c[oó]digo(?:\s+de)?\s+(?:verificaci[oó]n|seguridad|acceso))\b/i,
  /(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)/,
  /(?<!\d)(?:\d[ -]?){9,}\d(?!\d)/,
  /\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/i,
];

export function sanitizeUserText(text) {
  return SENSITIVE_TEXT_PATTERNS.some((pattern) => pattern.test(text))
    ? "*".repeat(Math.max(8, text.length))
    : text;
}

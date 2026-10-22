import assert from "node:assert/strict";
import test from "node:test";

import { sanitizeUserText } from "../src/lib/chatSecurity.mjs";

test("masks authentication secrets before chat persistence", () => {
  for (const secret of [
    "mi NIP es 1234",
    "mi CVV es 987",
    "mi tarjeta es 4111 1111 1111 1111",
    "mi cuenta es 1234 5678 90",
    "mi correo es ejemplo@correo.com",
  ]) {
    const saved = sanitizeUserText(secret);
    assert.match(saved, /^\*+$/);
    assert.equal(saved.includes(secret), false);
  }
});

test("preserves ordinary chat messages", () => {
  assert.equal(sanitizeUserText("¿En qué gasté este mes?"), "¿En qué gasté este mes?");
});

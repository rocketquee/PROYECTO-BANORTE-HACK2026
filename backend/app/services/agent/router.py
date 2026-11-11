"""Router determinista demo/think (sin ML).

El puntaje se calcula con reglas explícitas sobre el texto normalizado:

- +0.60 si aparece un verbo de escritura o de operación multi-paso
  (crear, aportar, transferir, comparar, simular, proyectar, analizar, ...).
- +0.60 si hay una marca de secuencia ("luego", "después", "primero", ...).
- +0.10 si el mensaje tiene 12 palabras o más.
- +0.10 si contiene un monto explícito.
- +0.10 si usa una referencia ambigua ("eso", "lo mismo", "ahí").
- El puntaje se acota a [0, 1].

`AGENT_ROUTER_THRESHOLD` (default 0.6) decide: puntaje >= umbral → `think`;
en caso contrario → `demo` (respuesta local instantánea). Si el proveedor no
está disponible, `think` degrada a `demo` con `degraded=True` y motivo
`provider_unavailable`. No hay aprendizaje automático ni modelo de intención.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from app.core import config
from app.services.agent.providers import get_provider

WRITE_PHRASES = (
    "crear", "crea una", "creo una", "quiero ahorrar", "ahorrar", "apartar",
    "aportar", "aporta", "abonar", "abona", "transferir", "transfiere",
    "mover", "mueve", "actualizar", "actualiza", "cambiar", "cambia",
    "configurar", "configura", "fijar", "fija", "establecer", "poner",
    "guardar", "guarda", "retirar", "retira", "eliminar", "elimina",
    "borrar", "borra",
)

ACTION_PHRASES = (
    "simular", "simula", "comparar", "compara", "proyectar", "proyecta",
    "calcular", "calcula", "analizar", "analiza", "planear", "planea",
    "detectar", "detecta", "revisar", "revisa", "desglosar", "desglosa",
)

MULTI_STEP_PHRASES = (
    "luego", "despues", "primero", "finalmente", "ademas", "a continuacion",
    "por ultimo", "y tambien", "y despues",
)

AMBIGUITY_PHRASES = ("eso", "lo mismo", "ahi", "aqui", "aquello", "asi")

_AMOUNT_RE = re.compile(r"\$\s?\d|\b\d{3,}\b")


@dataclass(frozen=True)
class Decision:
    mode: str
    score: float
    reason: str
    degraded: bool = False


def normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", (text or "").lower())
    without_accents = "".join(
        char for char in decomposed if unicodedata.category(char) != "Mn"
    )
    return " ".join(re.sub(r"[^a-z0-9$%]+", " ", without_accents).split())


def _has_phrase(text: str, phrases: tuple[str, ...]) -> bool:
    return any(phrase in text for phrase in phrases)


def score_message(message: str) -> float:
    """Puntaje determinista de complejidad; ver el docstring del módulo."""
    text = normalize(message)
    if not text:
        return 0.0
    score = 0.0
    if _has_phrase(text, WRITE_PHRASES) or _has_phrase(text, ACTION_PHRASES):
        score += 0.60
    if _has_phrase(text, MULTI_STEP_PHRASES):
        score += 0.60
    if len(text.split()) >= 12:
        score += 0.10
    if _AMOUNT_RE.search(text):
        score += 0.10
    if _has_phrase(text, AMBIGUITY_PHRASES):
        score += 0.10
    return round(min(1.0, score), 4)


def decide(message: str) -> Decision:
    """Elige `think` o `demo`; nunca lanza si el proveedor falta."""
    score = score_message(message)
    threshold = config.AGENT_ROUTER_THRESHOLD
    if score < threshold:
        return Decision(mode="demo", score=score, reason="simple_query")
    if get_provider() is None:
        return Decision(
            mode="demo", score=score, reason="provider_unavailable", degraded=True,
        )
    return Decision(mode="think", score=score, reason="write_or_multi_step")

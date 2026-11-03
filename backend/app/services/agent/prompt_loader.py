"""Carga y valida el prompt del agente desde `system_prompt.md`."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

PROMPT_PATH = Path(__file__).with_name("system_prompt.md")

REQUIRED_SECTIONS = (
    "Rol y alcance",
    "Tono",
    "Reglas de verdad",
    "Uso de herramientas",
    "Elección de interfaz",
    "Aclaraciones",
    "Seguridad",
)

_VERSION_RE = re.compile(r"^<!--\s*version:\s*(\d+\.\d+\.\d+)\s*-->\s*$")
_SECTION_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
_INTENT_RE = re.compile(r"^###\s+(\w+)\s*$", re.MULTILINE)


class PromptError(RuntimeError):
    """El prompt no existe o no cumple el formato obligatorio."""


@dataclass(frozen=True)
class PromptBundle:
    version: str
    text: str
    intent_sections: dict[str, str]


def load_system_prompt(path: Path | None = None) -> PromptBundle:
    prompt_path = path or PROMPT_PATH
    try:
        raw = prompt_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise PromptError(
            f"No se pudo cargar el prompt del agente en {prompt_path}: {exc}"
        ) from exc

    lines = raw.splitlines()
    if not lines:
        raise PromptError(f"El prompt del agente está vacío: {prompt_path}")
    version_match = _VERSION_RE.match(lines[0].strip())
    if not version_match:
        raise PromptError(
            f"El prompt del agente no declara versión en su primera línea: {prompt_path}"
        )
    version = version_match.group(1)

    body = "\n".join(lines[1:]).strip()
    if not body:
        raise PromptError(f"El prompt del agente no tiene contenido: {prompt_path}")

    headings = [match.group(1).strip() for match in _SECTION_RE.finditer(body)]
    missing = [section for section in REQUIRED_SECTIONS if section not in headings]
    if missing:
        raise PromptError(
            "El prompt del agente no contiene las secciones obligatorias "
            f"{', '.join(missing)}: {prompt_path}"
        )

    base_text, intent_text = body, ""
    marker = body.find("## Instrucciones por intención")
    if marker != -1:
        base_text = body[:marker].rstrip()
        intent_text = body[marker:]

    intent_sections: dict[str, str] = {}
    if intent_text:
        matches = list(_INTENT_RE.finditer(intent_text))
        if not matches:
            raise PromptError(
                "La sección de instrucciones por intención no tiene subsecciones: "
                f"{prompt_path}"
            )
        for index, match in enumerate(matches):
            start = match.end()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(intent_text)
            section = intent_text[start:end].strip()
            if not section:
                raise PromptError(
                    f"La instrucción por intención '{match.group(1)}' está vacía: {prompt_path}"
                )
            intent_sections[match.group(1)] = section

    return PromptBundle(version=version, text=base_text, intent_sections=intent_sections)

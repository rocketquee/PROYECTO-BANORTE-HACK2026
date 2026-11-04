"""Guardia de privacidad: rutas personales y PII conocida fuera del repositorio."""
import re
import sqlite3
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"

PATTERNS = {
    "ruta_windows_usuario": re.compile(r"[A-Za-z]:\\+Users\\+", re.IGNORECASE),
    "ruta_windows_usuario_fwd": re.compile(r"[A-Za-z]:/+Users/", re.IGNORECASE),
    "ruta_macos_usuario": re.compile(r"(?<![\w.])" + "/" + r"Users/[^/\s]+"),
    "perfil_temporal": re.compile(
        r"AppData\\+Local\\+Temp|AppData/+Local/+Temp", re.IGNORECASE,
    ),
    "usuario_local": re.compile("jon" + "na", re.IGNORECASE),
    "pii_conocida": re.compile("ROSALES" + r"\s+" + "PEDRO", re.IGNORECASE),
}


def _tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    names = result.stdout.decode("utf-8").split("\0")
    return [ROOT / name for name in names if name]


def _find(text: str) -> list[str]:
    return [
        f"{label}: {match.group(0)!r}"
        for label, pattern in PATTERNS.items()
        if (match := pattern.search(text))
    ]


def test_tracked_files_have_no_personal_paths_or_known_pii():
    offenders: list[str] = []
    for path in _tracked_files():
        if not path.is_file():
            continue
        data = path.read_bytes()
        if b"\x00" in data:
            continue
        matches = _find(data.decode("utf-8", errors="replace"))
        if matches:
            offenders.append(f"{path.relative_to(ROOT)}: {'; '.join(matches)}")
    assert not offenders, "\n".join(offenders)


def test_local_databases_have_no_known_pii():
    offenders: list[str] = []
    for db_path in (BACKEND / "data").rglob("*.db"):
        conn = sqlite3.connect(db_path)
        try:
            for table in ("savings_goals", "accounts", "cards", "transactions"):
                try:
                    rows = conn.execute(f'SELECT * FROM "{table}"').fetchall()
                except sqlite3.OperationalError:
                    continue
                for row in rows:
                    for value in row:
                        if not isinstance(value, str):
                            continue
                        matches = _find(value)
                        if matches:
                            offenders.append(
                                f"{db_path.relative_to(ROOT)} ({table}): "
                                f"{'; '.join(matches)}"
                            )
        finally:
            conn.close()
    assert not offenders, "\n".join(offenders)

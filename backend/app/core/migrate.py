"""Migraciones versionadas de la base (docs/MIGRACION-FASE1.md y diseño D1).

Cadena de versiones:
- `ledger-v1`: reforma el libro para el tipo `transfer` (INV-1) y reclasifica
  los gastos mal tipados vinculados a metas por idempotencia (Fase 1).
- `ledger-v2`: convierte el dinero de `REAL` a **centavos enteros**
  (decisión aprobada) en las cinco tablas con importes, verificando que cada
  total coincida **al centavo** antes y después.

Garantías de cada migración: se registra en `schema_migrations` (versión,
fecha, checksum, resultado, respaldo); corre dentro de **una transacción**;
exige **copia de seguridad previa** verificada; valida integridad referencial
(`PRAGMA foreign_key_check`) antes del `COMMIT`; y es **idempotente** (si la
versión ya está registrada, no se vuelve a ejecutar).

Uso:
    python -m app.core.migrate --dry-run   # solo diagnostica, no escribe
    python -m app.core.migrate             # respaldo + aplica pendientes
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from app.core import money, seed
from app.core.config import DB_PATH


class MigrationError(RuntimeError):
    """Fallo de migración: la base queda intacta y se explica el motivo."""


#: Versión de esquema que el código espera **hoy**. Las bases anteriores a la
#: última migración (p. ej. el libro REAL sin tipo `transfer`) se migran hasta
#: esta versión al arrancar; una base que no pueda llegar a ella se niega a
#: servir datos en lugar de leer columnas inexistentes.
CURRENT_SCHEMA_VERSION = "goal-status-v1"


# ------------------------------------------------------------------ utilidades

#: Carpeta dentro de la carpeta de datos donde viven las copias de seguridad.
BACKUP_DIRNAME = "backups"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _table_ddl(conn, name: str) -> str:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return row["sql"] if row else ""


def _columns(conn, name: str) -> set[str]:
    if not _table_ddl(conn, name):
        return set()
    return {r["name"] for r in conn.execute(f"PRAGMA table_info({name})")}


def _column_types(conn, name: str) -> dict[str, str]:
    if not _table_ddl(conn, name):
        return {}
    return {r["name"]: (r["type"] or "").upper()
            for r in conn.execute(f"PRAGMA table_info({name})")}


def current_version(conn) -> str | None:
    """Versión de esquema registrada en la base (la última aplicada)."""
    row = conn.execute(
        "SELECT version FROM schema_migrations ORDER BY rowid DESC LIMIT 1"
    ).fetchone()
    return row["version"] if row else None


def assert_schema_compatible(conn) -> None:
    """Guardián de arranque: la base debe estar en `CURRENT_SCHEMA_VERSION`.

    Nunca se leen columnas inexistentes ni se convierten en silencio. Si el
    esquema no coincide con la versión que el código espera, se aborta la
    operación con un mensaje claro (la migración pendiente debe haberlo traído
    al estado actual antes de llegar aquí).
    """
    problems: list[str] = []
    for table, columns in MONEY_COLUMNS.items():
        types = _column_types(conn, table)
        if not types:
            problems.append(f"tabla {table} ausente")
            continue
        for old, new in columns:
            if new not in types:
                problems.append(f"{table}.{new} no existe (migración incompleta o esquema no reconocido)")
            elif (types[new] or "").upper() != "INTEGER":
                problems.append(f"{table}.{new} debe ser INTEGER, es {(types[new] or '').upper()}")
        for old, _new in columns:
            if old in types:
                problems.append(f"{table}.{old} aún existe (debe renombrarse a {dict(columns)[old]})")
    tx_types = _column_types(conn, "transactions")
    ddl = _table_ddl(conn, "transactions") or ""
    if "transactions" in tx_types and "type" in tx_types and "transfer" not in ddl:
        problems.append("transactions.type no admite el valor 'transfer'")
    if not _table_ddl(conn, "pending_confirmations"):
        problems.append("tabla pending_confirmations ausente")
    if not _table_ddl(conn, "auth_sessions"):
        problems.append("tabla auth_sessions ausente")
    goals_ddl = " ".join((_table_ddl(conn, "savings_goals") or "").lower().split())
    if goals_ddl and "status in ('activa', 'completada')" not in goals_ddl:
        problems.append("savings_goals.status no tiene dominio cerrado")
    if problems:
        raise MigrationError(
            "La base no está en la versión de esquema esperada "
            f"({CURRENT_SCHEMA_VERSION}): " + "; ".join(problems)
            + ". Se recomienda ejecutar `python -m app.core.migrate`."
        )


def _db_path_from_conn(conn) -> Path:
    """Ruta del archivo principal de la conexión (PRAGMA database_list)."""
    row = conn.execute("PRAGMA database_list").fetchone()
    if row is None:
        raise MigrationError(
            "No se pudo determinar la ruta de la base de datos para verificar el respaldo."
        )
    try:
        path = row["file"]
    except (TypeError, IndexError, KeyError):
        path = row[2]
    if not path:
        raise MigrationError(
            "La conexión no apunta a un archivo de base de datos; no se puede verificar el respaldo."
        )
    return Path(path)


def _latest_backup(db_path: Path) -> Path | None:
    """Respaldo más reciente de `db_path` en su carpeta `backups`."""
    backup_dir = db_path.parent / BACKUP_DIRNAME
    if not backup_dir.is_dir():
        return None
    candidates = [
        path
        for path in backup_dir.glob(f"{db_path.name}.bak-*")
        if not path.name.endswith(".sha256")
    ]
    return sorted(candidates)[-1] if candidates else None


def require_verified_backup(
    conn,
    motivo: str,
    *,
    db_path: Path | str | None = None,
    backup_path: Path | str | None = None,
) -> dict:
    """Exige un respaldo verificado **antes** de escribir en la base.

    Verifica, en este orden: que el archivo de respaldo existe y no está vacío;
    que su suma SHA-256 coincide con la declarada en `<respaldo>.sha256`; que
    `PRAGMA integrity_check` devuelve `ok`; que `PRAGMA foreign_key_check` está
    vacío; y que el SHA-256 del respaldo es idéntico al de la base actual (es
    decir, que respalda exactamente el estado previo a la transacción).

    Si cualquiera de estas condiciones falla, lanza `MigrationError` y el
    llamador no debe abrir la transacción. Es la puerta común para migraciones,
    reparaciones y cualquier normalización que escriba en `banorte.db`.
    """
    if not str(motivo or "").strip():
        raise MigrationError("La verificación del respaldo exige un motivo no vacío.")

    db_file = Path(db_path) if db_path is not None else _db_path_from_conn(conn)
    if not db_file.exists():
        raise MigrationError(f"No existe la base de datos a respaldar: {db_file}")

    backup_file = Path(backup_path) if backup_path is not None else _latest_backup(db_file)
    if backup_file is None or not backup_file.is_file():
        backup_dir = db_file.parent / BACKUP_DIRNAME
        raise MigrationError(
            f"Escritura bloqueada ({motivo}): se requiere un respaldo verificado "
            f"antes de la transacción y no hay ninguno válido en {backup_dir}."
        )
    if backup_file.stat().st_size == 0:
        raise MigrationError(
            f"Escritura bloqueada ({motivo}): el respaldo {backup_file.name} está vacío."
        )

    sidecar = backup_file.with_name(backup_file.name + ".sha256")
    if not sidecar.is_file():
        raise MigrationError(
            f"Escritura bloqueada ({motivo}): falta la suma SHA-256 de "
            f"{backup_file.name} ({sidecar.name})."
        )
    declared = sidecar.read_text(encoding="utf-8").strip().split()
    declared_sha = declared[0].lower() if declared else ""
    if len(declared_sha) != 64 or any(c not in "0123456789abcdef" for c in declared_sha):
        raise MigrationError(
            f"Escritura bloqueada ({motivo}): la suma SHA-256 declarada para "
            f"{backup_file.name} no es válida."
        )

    actual_sha = _sha256(backup_file)
    if actual_sha != declared_sha:
        raise MigrationError(
            f"Escritura bloqueada ({motivo}): el SHA-256 de {backup_file.name} "
            "no coincide con su archivo de verificación."
        )

    check_conn = sqlite3.connect(str(backup_file))
    try:
        integrity = check_conn.execute("PRAGMA integrity_check").fetchone()[0]
        foreign_keys = check_conn.execute("PRAGMA foreign_key_check").fetchall()
    finally:
        check_conn.close()
    if integrity != "ok":
        raise MigrationError(
            f"Escritura bloqueada ({motivo}): integrity_check del respaldo "
            f"{backup_file.name} devolvió {integrity!r}."
        )
    if foreign_keys:
        raise MigrationError(
            f"Escritura bloqueada ({motivo}): el respaldo {backup_file.name} "
            f"tiene {len(foreign_keys)} referencias foráneas rotas."
        )

    if _sha256(db_file) != actual_sha:
        raise MigrationError(
            f"Escritura bloqueada ({motivo}): el respaldo {backup_file.name} no "
            "corresponde al estado actual de la base; crea uno nuevo antes de escribir."
        )

    return {
        "motivo": motivo,
        "db_path": str(db_file),
        "backup_file": str(backup_file),
        "backup_sha256": actual_sha,
        "integrity_check": integrity,
        "foreign_key_check": [],
    }


def backup(db_path: Path) -> Path:
    """Copia de seguridad obligatoria con marca de tiempo; nunca sobreescribe.

    Va a `<carpeta de datos>/<backups>/banorte.db.bak-<YYYYMMDD-HHMMSS>` (crea la
    carpeta si no existe), nunca sobreescribe (`.bak-<marca>` con marca de
    segundo, aborta si ya existe esa marca), guarda la suma de verificación
    SHA-256 en `<archivo>.sha256` **junto al archivo** y confirma que la copia
    se puede abrir (`PRAGMA quick_check`) antes de continuar.
    """
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = f"{db_path.name}.bak-{stamp}"
    backup_dir = db_path.parent / BACKUP_DIRNAME
    target = backup_dir / filename
    if target.exists():
        raise MigrationError(
            f"Ya existe una copia de seguridad con la misma marca de tiempo: {target.name}. "
            "Espera un segundo y vuelve a intentarlo."
        )
    backup_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(db_path, target)
    if _sha256(db_path) != _sha256(target):
        raise MigrationError("La copia de seguridad no coincide con el original; se aborta.")
    target.with_name(target.name + ".sha256").write_text(_sha256(target) + "\n", encoding="utf-8")
    check_conn = sqlite3.connect(str(target))
    try:
        check_result = check_conn.execute("PRAGMA quick_check").fetchone()[0]
    finally:
        check_conn.close()
    if check_result != "ok":
        raise MigrationError(
            f"La copia de seguridad {target.name} no se puede abrir (quick_check={check_result}); se aborta."
        )
    return target


# --------------------------------------------------------- registro de versiones

REGISTRY_DDL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version     TEXT PRIMARY KEY,
    applied_at  TEXT NOT NULL DEFAULT (datetime('now')),
    checksum    TEXT NOT NULL,
    result_json TEXT NOT NULL,
    backup_file TEXT
);
"""


def _checksum(version: str) -> str:
    """Identificador estable de la versión (detección de alteraciones)."""
    return hashlib.sha256(f"banorte-migration:{version}".encode("utf-8")).hexdigest()


def _applied(conn) -> dict[str, sqlite3.Row]:
    return {r["version"]: r for r in conn.execute("SELECT * FROM schema_migrations")}


def _register(conn, version: str, result: dict, backup_file: str | None) -> None:
    conn.execute(
        "INSERT INTO schema_migrations (version, checksum, result_json, backup_file)"
        " VALUES (?,?,?,?)",
        (version, _checksum(version), json.dumps(result, ensure_ascii=False, sort_keys=True),
         backup_file),
    )


def mark_fresh_install(conn) -> None:
    """Registra todas las versiones en una base recién creada.

    La semilla crea el esquema en la **última** versión (centavos), así que
    las migraciones históricas se marcan como ya cubiertas, no se ejecutan.
    """
    conn.executescript(REGISTRY_DDL)
    for version, _needed, _apply in MIGRATIONS:
        if version in _applied(conn):
            continue
        _register(conn, version, {"mode": "fresh_install"}, None)


# ------------------------------------------------------------- ledger-v1 (REAL)

# Acciones cuyo registro de idempotencia declara (meta, monto) de una aportación.
CONTRIBUTION_ACTIONS = ("apply_savings_contribution", "update_savings_goal")


def _goal_amount_pairs(conn) -> set[tuple[int, int]]:
    """Pares (meta, centavos) declarados por los registros de idempotencia."""
    pairs: set[tuple[int, int]] = set()
    rows = conn.execute(
        "SELECT action, result_json FROM idempotency_records WHERE action IN (?,?)",
        CONTRIBUTION_ACTIONS,
    ).fetchall()
    for row in rows:
        try:
            payload = json.loads(row["result_json"])
        except (TypeError, ValueError):
            continue
        goal = payload.get("goal") or {}
        goal_id = goal.get("id")
        amount = payload.get("amount")
        if isinstance(goal_id, int) and isinstance(amount, (int, float)) and amount > 0:
            pairs.add((goal_id, money.to_cents(amount)))
    return pairs


def _ledger_v1_needed(conn) -> bool:
    ddl = _table_ddl(conn, "transactions")
    if not ddl:
        return False
    if "'transfer'" not in ddl:
        return True
    # Esquema con transfer: ¿quedan gastos mal clasificados?
    taxonomy = {r["category"] for r in conn.execute("SELECT category FROM budgets")}
    stray = [
        r["category"] for r in conn.execute(
            "SELECT DISTINCT category FROM transactions WHERE type='expense'"
        ) if r["category"] not in taxonomy
    ]
    return bool(stray)


def _ledger_v1_apply(conn) -> dict:
    """Reconstruye el libro para `transfer` y reclasifica gastos vinculados.

    Solo opera sobre bases del esquema REAL con DDL viejo; el rebuild produce
    directamente el libro en centavos (el DDL canónico ya es INTEGER).
    """
    ddl = _table_ddl(conn, "transactions")
    rebuilt_needed = "'transfer'" not in ddl
    reclassified: list[dict] = []
    unclassified: list[dict] = []

    if rebuilt_needed:
        # Candidatas: gastos cuya categoría no está en la taxonomía declarada
        # y cuyo monto casa con un par (meta, monto) de la idempotencia.
        taxonomy = {r["category"] for r in conn.execute("SELECT category FROM budgets")}
        pairs = _goal_amount_pairs(conn)
        candidates = conn.execute(
            "SELECT id, date, description, amount, type, category, account_id"
            " FROM transactions ORDER BY id"
        ).fetchall()
        plan: dict[int, int] = {}
        for row in candidates:
            if row["type"] != "expense" or row["category"] in taxonomy:
                continue
            amount_c = money.to_cents(row["amount"])
            matches = sorted(gid for gid, cents in pairs if cents == amount_c)
            goal_id = None
            for candidate_id in matches:
                goal_row = conn.execute(
                    "SELECT id, saved_amount FROM savings_goals WHERE id=?", (candidate_id,)
                ).fetchone()
                if goal_row and money.to_cents(goal_row["saved_amount"]) >= amount_c:
                    goal_id = goal_row["id"]
                    break
            entry = {"id": row["id"], "amount": money.boundary(row["amount"]),
                     "goal_id": goal_id}
            if goal_id is None:
                entry["reason"] = "sin vínculo corroborado con una meta en idempotency_records"
                unclassified.append(entry)
            else:
                reclassified.append(entry)
                plan[row["id"]] = goal_id

        # Instantánea previa al rebuild, en centavos exactos.
        before = {
            "rows": conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0],
            "sum_income_c": money.to_cents(conn.execute(
                "SELECT COALESCE(SUM(amount),0) FROM transactions WHERE type='income'"
            ).fetchone()[0]),
            "sum_expense_c": money.to_cents(conn.execute(
                "SELECT COALESCE(SUM(amount),0) FROM transactions WHERE type='expense'"
            ).fetchone()[0]),
        }
        moved_c = sum(money.to_cents(r["amount"]) for r in reclassified)

        new_table = seed.TRANSACTIONS_DDL.replace(
            "CREATE TABLE IF NOT EXISTS transactions", "CREATE TABLE transactions_new")
        conn.execute(new_table)
        for row in candidates:
            if row["id"] in plan:
                conn.execute(
                    "INSERT INTO transactions_new"
                    " (id, date, description, amount_cents, type, category, account_id,"
                    "  goal_id, direction)"
                    " VALUES (?,?,?,?,'transfer',NULL,?,?,'account_to_goal')",
                    (row["id"], row["date"], row["description"], money.to_cents(row["amount"]),
                     row["account_id"], plan[row["id"]]),
                )
            else:
                conn.execute(
                    "INSERT INTO transactions_new"
                    " (id, date, description, amount_cents, type, category, account_id,"
                    "  goal_id, direction)"
                    " VALUES (?,?,?,?,?,?,?,NULL,NULL)",
                    (row["id"], row["date"], row["description"], money.to_cents(row["amount"]),
                     row["type"], row["category"], row["account_id"]),
                )
        # Verificación por fila: el mapeo reclasificado debe conservar la cuenta
        # original y apuntar exactamente a la meta planeada.
        originals = {row["id"]: row for row in candidates}
        for tx_id, goal_id in plan.items():
            got = conn.execute(
                "SELECT account_id, goal_id FROM transactions_new WHERE id=?",
                (tx_id,),
            ).fetchone()
            if (got is None
                    or got["goal_id"] != goal_id
                    or got["account_id"] != originals[tx_id]["account_id"]):
                raise MigrationError(
                    f"ledger-v1: la fila {tx_id} no conservó su mapeo "
                    f"(esperado account_id={originals[tx_id]['account_id']}, "
                    f"goal_id={goal_id})."
                )

        conn.execute("DROP TABLE transactions")
        conn.execute("ALTER TABLE transactions_new RENAME TO transactions")
        conn.executescript(seed.TRANSACTIONS_INDEXES)

        # Verificación: conservación exacta al centavo.
        after = {
            "rows": conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0],
            "sum_income_c": conn.execute(
                "SELECT COALESCE(SUM(amount_cents),0) FROM transactions WHERE type='income'"
            ).fetchone()[0],
            "sum_expense_c": conn.execute(
                "SELECT COALESCE(SUM(amount_cents),0) FROM transactions WHERE type='expense'"
            ).fetchone()[0],
        }
        problems = []
        if after["rows"] != before["rows"]:
            problems.append("conteo de filas")
        if after["sum_income_c"] != before["sum_income_c"]:
            problems.append("Σ ingreso cambió")
        if after["sum_expense_c"] != before["sum_expense_c"] - moved_c:
            problems.append("Σ gasto no refleja lo reclasificado")
        if problems:
            raise MigrationError("Comprobaciones fallidas: " + "; ".join(problems))

    return {
        "schema_rebuilt": rebuilt_needed,
        "reclassified": reclassified,
        "unclassified": unclassified,
    }


# ------------------------------------------------------------- ledger-v2 (cents)

# Columnas de dinero por tabla: (columna REAL, columna centavos). El DDL
# canónico de cada tabla vive en `seed.TABLE_DDL`; aquí solo se mapea.
MONEY_COLUMNS: dict[str, tuple[tuple[str, str], ...]] = {
    "transactions": (("amount", "amount_cents"),),
    "accounts": (("balance", "balance_cents"),),
    "cards": (("balance", "balance_cents"), ("credit_limit", "credit_limit_cents")),
    "savings_goals": (("target_amount", "target_amount_cents"),
                      ("saved_amount", "saved_amount_cents")),
    "budgets": (("monthly_limit", "monthly_limit_cents"),),
}


def _ledger_v2_needed(conn) -> bool:
    for table, columns in MONEY_COLUMNS.items():
        types = _column_types(conn, table)
        if not types:
            continue
        if any(types.get(old) == "REAL" for old, _ in columns):
            return True
    return False


def _ledger_v2_apply(conn) -> dict:
    """Convierte las columnas de dinero de REAL a centavos enteros.

    Por tabla: instantánea del total en centavos, rebuild con el DDL canónico
    de `seed` (CHECK e índices incluidos), copia fila a fila vía
    `money.to_cents`, y verificación de que cada total coincide **al centavo**.
    """
    converted: dict[str, dict] = {}
    for table, columns in MONEY_COLUMNS.items():
        types = _column_types(conn, table)
        if not types or not any(types.get(old) == "REAL" for old, _ in columns):
            continue
        new_names = {old: new for old, new in columns}
        all_cols = [r["name"] for r in conn.execute(f"PRAGMA table_info({table})")]

        # Instantánea previa: total por columna de dinero, en centavos exactos.
        before_totals = {}
        for old, _ in columns:
            raw = conn.execute(f"SELECT COALESCE(SUM({old}),0) FROM {table}").fetchone()[0]
            before_totals[old] = money.to_cents(raw)

        rows = [dict(r) for r in conn.execute(f"SELECT * FROM {table}").fetchall()]
        new_cols = [new_names.get(c, c) for c in all_cols]
        cents_rows = []
        for item in rows:
            for old, new in columns:
                item[new] = money.to_cents(item.pop(old))
            cents_rows.append(tuple(item[c] for c in new_cols))

        new_table = seed.TABLE_DDL[table].replace(
            f"CREATE TABLE IF NOT EXISTS {table}", f"CREATE TABLE {table}_new")
        conn.execute(new_table)
        conn.executemany(
            f"INSERT INTO {table}_new ({','.join(new_cols)})"
            f" VALUES ({','.join('?' * len(new_cols))})",
            cents_rows,
        )
        conn.execute(f"DROP TABLE {table}")
        conn.execute(f"ALTER TABLE {table}_new RENAME TO {table}")

        # Totales después: igualdad exacta al centavo.
        for old, new in new_names.items():
            after_total = conn.execute(f"SELECT COALESCE(SUM({new}),0) FROM {table}").fetchone()[0]
            if after_total != before_totals[old]:
                raise MigrationError(
                    f"ledger-v2: Σ {table}.{new} = {after_total} ≠ {before_totals[old]} (antes)."
                )
        converted[table] = {
            "rows": len(cents_rows),
            **{new: before_totals[old] for old, new in new_names.items()},
        }

    # Los triggers del esquema REAL referencian columnas que ya no existen:
    # se reemplazan por los canónicos en centavos.
    conn.executescript(_DROP_TRIGGERS)
    conn.executescript(seed.TRIGGERS)
    conn.executescript(seed.TRANSACTIONS_INDEXES)
    orphans = conn.execute("PRAGMA foreign_key_check").fetchall()
    if orphans:
        raise MigrationError(
            f"ledger-v2: integridad referencial rota ({len(orphans)} referencias)."
        )
    return {"converted": converted}


# ------------------------------------------------------------------ cadena

# Triggers de eras anteriores: se eliminan antes de instalar los canónicos.
_DROP_TRIGGERS = """
DROP TRIGGER IF EXISTS trg_goal_saved_bounds_ins;
DROP TRIGGER IF EXISTS trg_goal_saved_bounds_upd;
DROP TRIGGER IF EXISTS trg_transfer_within_goal_bounds;
DROP TRIGGER IF EXISTS trg_account_balance_non_negative;
"""

def _confirm_v1_needed(conn) -> bool:
    return not bool(_table_ddl(conn, "pending_confirmations"))


def _confirm_v1_apply(conn) -> dict:
    conn.executescript(seed.TABLE_DDL["pending_confirmations"])
    return {"created": "pending_confirmations"}


def _auth_v1_needed(conn) -> bool:
    return not bool(_table_ddl(conn, "auth_sessions"))


def _auth_v1_apply(conn) -> dict:
    conn.executescript(seed.TABLE_DDL["auth_sessions"])
    return {"created": "auth_sessions"}


def _goal_status_v1_needed(conn) -> bool:
    ddl = " ".join((_table_ddl(conn, "savings_goals") or "").lower().split())
    if not ddl:
        return False  # tabla ausente: la crea la semilla o una migración previa
    return "status in ('activa', 'completada')" not in ddl


def _goal_status_v1_apply(conn) -> dict:
    """Cierra el dominio de `savings_goals.status` con un CHECK (INV-11).

    Reconstruye la tabla con el DDL canónico de `seed` sin inventar datos:
    acepta tanto el esquema anterior en pesos como el de centavos, y si hay
    estados fuera del dominio aborta sin dejar cambios.
    """
    existing = {row["name"] for row in conn.execute("PRAGMA table_info(savings_goals)")}
    if not existing:
        raise MigrationError("goal-status-v1: falta la tabla savings_goals.")
    has_cents = {"target_amount_cents", "saved_amount_cents"} <= existing
    target_col = "target_amount_cents" if has_cents else "target_amount"
    saved_col = "saved_amount_cents" if has_cents else "saved_amount"
    source_columns = ["id", "name", target_col, saved_col, "deadline",
                      "status", "created_at"]
    missing = [name for name in source_columns if name not in existing]
    if missing:
        raise MigrationError(
            "goal-status-v1: faltan columnas en savings_goals: "
            + ", ".join(missing)
        )
    rows = [dict(row) for row in conn.execute(
        "SELECT " + ",".join(source_columns) + " FROM savings_goals"
    )]
    invalid = [row for row in rows if row["status"] not in ("activa", "completada")]
    if invalid:
        raise MigrationError(
            "goal-status-v1: hay metas con estado fuera del dominio "
            f"({len(invalid)}); corrígelas antes de migrar."
        )
    if not has_cents:
        for row in rows:
            row["target_amount_cents"] = money.to_cents(row.pop(target_col))
            row["saved_amount_cents"] = money.to_cents(row.pop(saved_col))
    else:
        for row in rows:
            row["target_amount_cents"] = row.pop(target_col)
            row["saved_amount_cents"] = row.pop(saved_col)
    columns = ["id", "name", "target_amount_cents", "saved_amount_cents",
               "deadline", "status", "created_at"]
    new_table = seed.TABLE_DDL["savings_goals"].replace(
        "CREATE TABLE IF NOT EXISTS savings_goals",
        "CREATE TABLE savings_goals_new",
        1,
    )
    conn.execute(new_table)
    conn.executemany(
        "INSERT INTO savings_goals_new (" + ",".join(columns) + ")"
        " VALUES (" + ",".join("?" * len(columns)) + ")",
        [tuple(row[name] for name in columns) for row in rows],
    )
    conn.executescript(_DROP_TRIGGERS)
    conn.execute("DROP TABLE savings_goals")
    conn.execute("ALTER TABLE savings_goals_new RENAME TO savings_goals")
    conn.executescript(seed.TRIGGERS)
    conn.executescript(seed.TRANSACTIONS_INDEXES)
    if conn.execute("PRAGMA foreign_key_check").fetchall():
        raise MigrationError("goal-status-v1: integridad referencial rota.")
    return {"rows": len(rows), "check": "status IN ('activa','completada')"}


MIGRATIONS: list[tuple[str, object, object]] = [
    ("ledger-v1", _ledger_v1_needed, _ledger_v1_apply),
    ("ledger-v2", _ledger_v2_needed, _ledger_v2_apply),
    ("confirm-v1", _confirm_v1_needed, _confirm_v1_apply),
    ("auth-v1", _auth_v1_needed, _auth_v1_apply),
    ("goal-status-v1", _goal_status_v1_needed, _goal_status_v1_apply),
]


def _apply_of(version: str):
    for name, _needed, apply in MIGRATIONS:
        if name == version:
            return apply
    raise MigrationError(f"Versión de migración desconocida: {version}")


def run_pending(db_path: Path | str = DB_PATH, *, dry_run: bool = False) -> dict:
    """Aplica las migraciones pendientes, en orden, con respaldo y transacción."""
    db_path = Path(db_path)
    if not db_path.exists():
        raise MigrationError(f"No existe la base de datos: {db_path}")

    conn = _connect(db_path)
    try:
        # Diagnóstico de solo lectura: no se crea ni se registra nada antes de
        # que la puerta de respaldo verificada haya pasado.
        has_registry = bool(_table_ddl(conn, "schema_migrations"))
        applied = _applied(conn) if has_registry else {}
        pending: list[str] = []
        not_needed: list[str] = []
        for version, needed, _apply in MIGRATIONS:
            if version in applied:
                continue
            if needed(conn):
                pending.append(version)
            else:
                not_needed.append(version)

        report = {"db": str(db_path), "pending": pending, "applied": [], "dry_run": dry_run}
        if dry_run:
            return report
        if has_registry and not pending and not not_needed:
            return report

        # A partir de aquí se escribirán metadatos (registro de versiones) o
        # datos: el respaldo verificado es obligatorio antes de la primera
        # transacción.
        backup_path = backup(db_path)
        require_verified_backup(
            conn,
            "migraciones: " + ", ".join(pending or not_needed or ["registro de versiones"]),
            db_path=db_path,
            backup_path=backup_path,
        )
        conn.executescript(REGISTRY_DDL)
        for version in not_needed:
            # No necesaria: se registra para no reevaluar en cada arranque.
            conn.execute("BEGIN IMMEDIATE")
            try:
                _register(conn, version, {"mode": "not_needed"}, None)
                conn.execute("COMMIT")
            except BaseException:
                try:
                    conn.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
                raise
        # Receta estándar de SQLite para rebuilds de tablas con FK: las llaves
        # foráneas se desactivan ANTES de abrir la transacción (dentro sería un
        # no-op) y la integridad se verifica con `foreign_key_check` antes del
        # COMMIT.
        conn.execute("PRAGMA foreign_keys = OFF")
        for version in pending:
            apply = _apply_of(version)
            conn.execute("BEGIN IMMEDIATE")
            try:
                result = apply(conn)
                orphans = conn.execute("PRAGMA foreign_key_check").fetchall()
                if orphans:
                    raise MigrationError(
                        f"{version}: integridad referencial rota "
                        f"({len(orphans)} referencias)."
                    )
                _register(conn, version, result, backup_path.name)
                conn.execute("COMMIT")
                report["applied"].append({"version": version, "result": result})
            except BaseException:
                try:
                    conn.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
                raise
        conn.execute("PRAGMA foreign_keys = ON")
        report["backup"] = backup_path.name
        return report
    finally:
        conn.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Migraciones versionadas de la base.")
    parser.add_argument("--db", default=str(DB_PATH), help="ruta de la base SQLite")
    parser.add_argument("--dry-run", action="store_true", help="solo diagnostica, no escribe")
    args = parser.parse_args(argv)
    try:
        report = run_pending(Path(args.db), dry_run=args.dry_run)
    except MigrationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

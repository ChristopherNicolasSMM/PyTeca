"""
query_api.py — SQL Playground backend
Executa apenas SELECT via SQLAlchemy e registra em QueryLog.
"""
from __future__ import annotations

import re
import logging
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required
from sqlalchemy import text

from db.database import db
from model.core.admin.query_log import QueryLog
from utils.permissions import permission_required

logger = logging.getLogger(__name__)

query_api = Blueprint("query_api", __name__, url_prefix="/api/builder/query")

# ── Whitelist de tokens proibidos ────────────────────────────────────────────
_FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE|REPLACE|GRANT|REVOKE|EXEC|EXECUTE|PRAGMA|ATTACH)\b",
    re.IGNORECASE,
)


def _is_safe_select(sql: str) -> bool:
    """Retorna True apenas se o SQL começa com SELECT e não contém DDL/DML."""
    stripped = sql.strip()
    if not re.match(r"^SELECT\b", stripped, re.IGNORECASE):
        return False
    if _FORBIDDEN.search(stripped):
        return False
    return True


def _log_query(sql: str, status: str, result_rows: int | None = None, error: str | None = None):
    try:
        log = QueryLog(
            user_id=current_user.id if current_user.is_authenticated else None,
            query_type="sql",
            query_text=sql[:2000],
            status=status,
            result_rows=result_rows,
            error_msg=error,
            executed_at=datetime.now(timezone.utc),
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        logger.warning("Falha ao salvar QueryLog: %s", e)
        db.session.rollback()


@query_api.route("/sql", methods=["POST"])
@login_required
@permission_required("admin")
def execute_sql():
    """
    Executa um SELECT SQL e retorna até 500 linhas.

    Body JSON:
        { "sql": "SELECT * FROM users LIMIT 10" }

    Resposta:
        {
          "success": true,
          "columns": ["id", "username", ...],
          "rows": [[1, "admin", ...], ...],
          "total": 10,
          "truncated": false
        }
    """
    data = request.get_json(silent=True) or {}
    sql = (data.get("sql") or "").strip()

    if not sql:
        return jsonify({"success": False, "error": "Nenhuma query fornecida."}), 400

    if not _is_safe_select(sql):
        _log_query(sql, "blocked")
        return jsonify({
            "success": False,
            "error": "Apenas consultas SELECT são permitidas. Operações de escrita, DDL e PRAGMA são bloqueadas."
        }), 400

    MAX_ROWS = 500
    try:
        result = db.session.execute(text(sql))
        columns = list(result.keys())
        all_rows = result.fetchmany(MAX_ROWS + 1)
        truncated = len(all_rows) > MAX_ROWS
        rows = all_rows[:MAX_ROWS]

        # Converte cada linha para lista serializável
        serialized = []
        for row in rows:
            serialized.append([
                str(v) if not isinstance(v, (int, float, bool, type(None))) else v
                for v in row
            ])

        _log_query(sql, "success", result_rows=len(serialized))
        return jsonify({
            "success": True,
            "columns": columns,
            "rows": serialized,
            "total": len(serialized),
            "truncated": truncated,
        })

    except Exception as e:
        db.session.rollback()
        error_msg = str(e).split("\n")[0]  # primeira linha do erro é suficiente
        _log_query(sql, "failure", error=error_msg)
        logger.warning("Erro ao executar SQL no playground: %s", e)
        return jsonify({"success": False, "error": error_msg}), 400


@query_api.route("/sql/history", methods=["GET"])
@login_required
@permission_required("admin")
def sql_history():
    """Retorna as últimas 20 queries do usuário atual."""
    logs = (
        QueryLog.query
        .filter_by(user_id=current_user.id, query_type="sql")
        .order_by(QueryLog.executed_at.desc())
        .limit(20)
        .all()
    )
    return jsonify({
        "success": True,
        "history": [
            {
                "id": l.id,
                "sql": l.query_text,
                "status": l.status,
                "rows": l.result_rows,
                "error": l.error_msg,
                "executed_at": l.executed_at.isoformat() if l.executed_at else None,
            }
            for l in logs
        ],
    })

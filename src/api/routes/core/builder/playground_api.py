"""
playground_api.py — API Playground backend
Proxy HTTP com whitelist de domínios configurável via SystemConfig.
"""
from __future__ import annotations

import ipaddress
import logging
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests
from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from db.database import db
from model.core.admin.query_log import QueryLog
from services.core.admin.config_service import ConfigService
from utils.permissions import permission_required

logger = logging.getLogger(__name__)

playground_api = Blueprint("playground_api", __name__, url_prefix="/api/builder/playground")

_DEFAULT_TIMEOUT = 10  # segundos

# IPs privados/loopback bloqueados por padrão
_PRIVATE_RANGES = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
]


def _get_whitelist() -> list[str]:
    """Lê whitelist de domínios do SystemConfig. Ex: 'api.github.com, jsonplaceholder.typicode.com'"""
    raw = ConfigService.get("API_WHITELIST", "")
    if not raw:
        return []
    return [d.strip().lower() for d in raw.split(",") if d.strip()]


def _is_private_ip(host: str) -> bool:
    try:
        addr = ipaddress.ip_address(host)
        return any(addr in net for net in _PRIVATE_RANGES)
    except ValueError:
        return False


def _validate_url(url: str) -> str | None:
    """Retorna None se OK, ou string de erro."""
    try:
        parsed = urlparse(url)
    except Exception:
        return "URL inválida."

    if parsed.scheme not in ("http", "https"):
        return "Apenas http:// e https:// são permitidos."

    host = parsed.hostname or ""
    if not host:
        return "Host inválido."

    if _is_private_ip(host):
        return "Acesso a IPs privados não é permitido."

    whitelist = _get_whitelist()
    if whitelist:
        if not any(host == d or host.endswith("." + d) for d in whitelist):
            return (
                f"Domínio '{host}' não está na whitelist. "
                f"Adicione em Administração → Configurações → chave 'API_WHITELIST'."
            )
    return None


def _log_request(method: str, url: str, status: str, result_rows: int | None = None, error: str | None = None):
    try:
        log = QueryLog(
            user_id=current_user.id if current_user.is_authenticated else None,
            query_type="api",
            query_text=f"{method} {url}"[:2000],
            status=status,
            result_rows=result_rows,
            error_msg=error,
            executed_at=datetime.now(timezone.utc),
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        logger.warning("Falha ao salvar log de API: %s", e)
        db.session.rollback()


@playground_api.route("/proxy", methods=["POST"])
@login_required
@permission_required("admin")
def proxy_request():
    """
    Executa uma requisição HTTP em nome do servidor.

    Body JSON:
        {
          "method": "GET",
          "url": "https://jsonplaceholder.typicode.com/posts/1",
          "headers": {"Authorization": "Bearer ..."},
          "body": {},
          "timeout": 10
        }

    Resposta:
        {
          "success": true,
          "status_code": 200,
          "headers": {...},
          "body": {...},
          "elapsed_ms": 142
        }
    """
    data = request.get_json(silent=True) or {}
    method = (data.get("method") or "GET").upper()
    url = (data.get("url") or "").strip()
    headers = data.get("headers") or {}
    body = data.get("body")
    timeout = min(int(data.get("timeout") or _DEFAULT_TIMEOUT), 30)

    if not url:
        return jsonify({"success": False, "error": "URL não fornecida."}), 400

    if method not in ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"):
        return jsonify({"success": False, "error": f"Método '{method}' não suportado."}), 400

    err = _validate_url(url)
    if err:
        _log_request(method, url, "blocked", error=err)
        return jsonify({"success": False, "error": err}), 400

    try:
        kwargs: dict = {"headers": headers, "timeout": timeout, "allow_redirects": True}
        if body and method in ("POST", "PUT", "PATCH"):
            if isinstance(body, dict):
                kwargs["json"] = body
            else:
                kwargs["data"] = str(body)

        resp = requests.request(method, url, **kwargs)
        elapsed_ms = int(resp.elapsed.total_seconds() * 1000)

        # Tenta parsear o body como JSON, senão retorna texto
        try:
            resp_body = resp.json()
            rows = len(resp_body) if isinstance(resp_body, list) else None
        except Exception:
            resp_body = resp.text[:50_000]  # limita texto
            rows = None

        _log_request(method, url, "success", result_rows=rows)

        return jsonify({
            "success": True,
            "status_code": resp.status_code,
            "headers": dict(resp.headers),
            "body": resp_body,
            "elapsed_ms": elapsed_ms,
        })

    except requests.exceptions.Timeout:
        err = f"Timeout após {timeout}s."
        _log_request(method, url, "failure", error=err)
        return jsonify({"success": False, "error": err}), 408

    except requests.exceptions.ConnectionError as e:
        err = f"Erro de conexão: {str(e)[:200]}"
        _log_request(method, url, "failure", error=err)
        return jsonify({"success": False, "error": err}), 502

    except Exception as e:
        err = str(e)[:300]
        _log_request(method, url, "failure", error=err)
        logger.exception("Erro no proxy de API: %s", e)
        return jsonify({"success": False, "error": err}), 500


@playground_api.route("/history", methods=["GET"])
@login_required
@permission_required("admin")
def api_history():
    """Retorna as últimas 20 chamadas de API do usuário atual."""
    logs = (
        QueryLog.query
        .filter_by(user_id=current_user.id, query_type="api")
        .order_by(QueryLog.executed_at.desc())
        .limit(20)
        .all()
    )
    return jsonify({
        "success": True,
        "history": [
            {
                "id": l.id,
                "request": l.query_text,
                "status": l.status,
                "error": l.error_msg,
                "executed_at": l.executed_at.isoformat() if l.executed_at else None,
            }
            for l in logs
        ],
    })

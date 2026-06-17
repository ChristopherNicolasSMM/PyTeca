"""
task_service.py — Serviço de tarefas agendadas
Gerencia ScheduledTask, TaskLog e MessageQueue.
APScheduler é opcional: se não instalado, run_now ainda funciona via execução direta.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from db.database import db
from model.core.admin.message_queue import MessageQueue
from model.core.admin.scheduled_task import ScheduledTask
from model.core.admin.task_log import TaskLog

logger = logging.getLogger(__name__)

# Registro central de funções Python elegíveis como tarefas
TASK_REGISTRY: dict[str, Any] = {
    # "chave": função_python,
    # Exemplo: "backup_db": backup_database_function,
}


class TaskService:

    # ── Listagem ─────────────────────────────────────────────────────────────

    @classmethod
    def list_tasks(cls, page: int = 1, per_page: int = 20, status: str | None = None) -> dict:
        q = ScheduledTask.query
        if status:
            q = q.filter_by(status=status)
        q = q.order_by(ScheduledTask.created_at.desc())
        pag = q.paginate(page=page, per_page=per_page, error_out=False)
        return {
            "items": [cls._task_to_dict(t) for t in pag.items],
            "total": pag.total,
            "page": page,
            "per_page": per_page,
            "pages": pag.pages,
        }

    @classmethod
    def get_task(cls, task_id: int) -> ScheduledTask | None:
        return db.session.get(ScheduledTask, task_id)

    @classmethod
    def count_by_status(cls) -> dict[str, int]:
        from sqlalchemy import func
        rows = (
            db.session.query(ScheduledTask.status, func.count(ScheduledTask.id))
            .group_by(ScheduledTask.status)
            .all()
        )
        return {status: count for status, count in rows}

    # ── CRUD de Tarefas ───────────────────────────────────────────────────────

    @classmethod
    def create_task(cls, data: dict) -> dict:
        required = ("name", "task_type", "target", "schedule")
        missing  = [f for f in required if not data.get(f)]
        if missing:
            return {"success": False, "error": f"Campos obrigatórios: {', '.join(missing)}"}

        task = ScheduledTask(
            name=data["name"],
            task_type=data["task_type"],
            target=data["target"],
            schedule=data["schedule"],
            status="active",
            requires_approval=bool(data.get("requires_approval", False)),
            approved=not bool(data.get("requires_approval", False)),
            created_by=data.get("created_by"),
        )
        task.next_run = cls._calc_next_run(task.schedule)
        db.session.add(task)
        db.session.commit()

        cls._sync_scheduler(task)
        return {"success": True, "data": cls._task_to_dict(task)}

    @classmethod
    def update_task(cls, task_id: int, data: dict) -> dict:
        task = cls.get_task(task_id)
        if not task:
            return {"success": False, "error": "Tarefa não encontrada."}

        for field in ("name", "task_type", "target", "schedule", "requires_approval"):
            if field in data:
                setattr(task, field, data[field])

        if "schedule" in data:
            task.next_run = cls._calc_next_run(task.schedule)

        db.session.commit()
        cls._sync_scheduler(task)
        return {"success": True, "data": cls._task_to_dict(task)}

    @classmethod
    def delete_task(cls, task_id: int) -> dict:
        task = cls.get_task(task_id)
        if not task:
            return {"success": False, "error": "Tarefa não encontrada."}
        cls._remove_from_scheduler(task_id)
        db.session.delete(task)
        db.session.commit()
        return {"success": True}

    @classmethod
    def pause_task(cls, task_id: int) -> dict:
        task = cls.get_task(task_id)
        if not task:
            return {"success": False, "error": "Tarefa não encontrada."}
        task.status = "paused"
        db.session.commit()
        cls._remove_from_scheduler(task_id)
        return {"success": True, "data": cls._task_to_dict(task)}

    @classmethod
    def activate_task(cls, task_id: int) -> dict:
        task = cls.get_task(task_id)
        if not task:
            return {"success": False, "error": "Tarefa não encontrada."}
        task.status = "active"
        task.next_run = cls._calc_next_run(task.schedule)
        db.session.commit()
        cls._sync_scheduler(task)
        return {"success": True, "data": cls._task_to_dict(task)}

    @classmethod
    def approve_task(cls, task_id: int) -> dict:
        task = cls.get_task(task_id)
        if not task:
            return {"success": False, "error": "Tarefa não encontrada."}
        task.approved = True
        task.status   = "active"
        db.session.commit()
        cls._sync_scheduler(task)
        return {"success": True, "data": cls._task_to_dict(task)}

    # ── Execução ──────────────────────────────────────────────────────────────

    @classmethod
    def run_now(cls, task_id: int) -> dict:
        task = cls.get_task(task_id)
        if not task:
            return {"success": False, "error": "Tarefa não encontrada."}
        result = cls._execute_task(task)
        return result

    @classmethod
    def _execute_task(cls, task: ScheduledTask) -> dict:
        started = datetime.now(timezone.utc)
        log = TaskLog(
            task_id=task.id,
            task_name=task.name,
            status="running",
            started_at=started,
        )
        db.session.add(log)
        db.session.commit()

        try:
            result_text = cls._dispatch(task)
            finished   = datetime.now(timezone.utc)
            duration   = int((finished - started).total_seconds() * 1000)

            log.status      = "success"
            log.finished_at = finished
            log.duration_ms = duration
            log.result      = str(result_text)[:2000]

            task.last_run = finished
            task.next_run = cls._calc_next_run(task.schedule)
            task.result   = str(result_text)[:500]
            db.session.commit()

            return {"success": True, "result": result_text, "duration_ms": duration}

        except Exception as e:
            finished   = datetime.now(timezone.utc)
            duration   = int((finished - started).total_seconds() * 1000)
            log.status      = "failure"
            log.finished_at = finished
            log.duration_ms = duration
            log.error       = str(e)[:2000]
            task.last_run   = finished
            db.session.commit()
            logger.exception("Erro ao executar tarefa '%s': %s", task.name, e)
            return {"success": False, "error": str(e)}

    @classmethod
    def _dispatch(cls, task: ScheduledTask) -> str:
        if task.task_type == "python_call":
            fn = TASK_REGISTRY.get(task.target)
            if not fn:
                raise ValueError(f"Função '{task.target}' não registrada em TASK_REGISTRY.")
            result = fn()
            return str(result)

        elif task.task_type == "http_request":
            import requests as req
            resp = req.get(task.target, timeout=30)
            return f"HTTP {resp.status_code}"

        elif task.task_type == "sql":
            from sqlalchemy import text
            result = db.session.execute(text(task.target))
            return f"{result.rowcount} linhas afetadas"

        else:
            raise ValueError(f"task_type '{task.task_type}' desconhecido.")

    # ── Fila de Mensagens ─────────────────────────────────────────────────────

    @classmethod
    def list_queue(cls, page: int = 1, per_page: int = 20, status: str | None = None) -> dict:
        q = MessageQueue.query
        if status:
            q = q.filter_by(status=status)
        q = q.order_by(MessageQueue.created_at.desc())
        pag = q.paginate(page=page, per_page=per_page, error_out=False)
        return {
            "items": [cls._queue_to_dict(m) for m in pag.items],
            "total": pag.total,
            "page": page,
            "per_page": per_page,
            "pages": pag.pages,
        }

    @classmethod
    def enqueue(cls, channel: str, payload: dict, scheduled_for: datetime | None = None) -> MessageQueue:
        msg = MessageQueue(
            channel=channel,
            payload=payload,
            status="pending",
            scheduled_for=scheduled_for or datetime.now(timezone.utc),
        )
        db.session.add(msg)
        db.session.commit()
        return msg

    @classmethod
    def reprocess_message(cls, msg_id: int) -> dict:
        msg = db.session.get(MessageQueue, msg_id)
        if not msg:
            return {"success": False, "error": "Mensagem não encontrada."}
        msg.status  = "pending"
        msg.retries = 0
        msg.error_msg = None
        db.session.commit()
        return {"success": True}

    @classmethod
    def cancel_message(cls, msg_id: int) -> dict:
        msg = db.session.get(MessageQueue, msg_id)
        if not msg:
            return {"success": False, "error": "Mensagem não encontrada."}
        msg.status = "cancelled"
        db.session.commit()
        return {"success": True}

    @classmethod
    def process_queue(cls) -> int:
        """Processa mensagens pendentes. Chamado pelo scheduler a cada 10s."""
        now     = datetime.now(timezone.utc)
        pending = (
            MessageQueue.query
            .filter(MessageQueue.status == "pending")
            .filter(MessageQueue.scheduled_for <= now)
            .filter(MessageQueue.retries < MessageQueue.max_retries)
            .limit(20)
            .all()
        )
        processed = 0
        for msg in pending:
            msg.status = "processing"
            db.session.commit()
            try:
                cls._dispatch_message(msg)
                msg.status       = "done"
                msg.processed_at = datetime.now(timezone.utc)
                processed += 1
            except Exception as e:
                msg.retries   += 1
                msg.error_msg  = str(e)[:500]
                msg.status     = "failed" if msg.retries >= msg.max_retries else "pending"
            db.session.commit()
        return processed

    @classmethod
    def _dispatch_message(cls, msg: MessageQueue) -> None:
        """Despacha a mensagem para o canal correto."""
        if msg.channel == "notification":
            from services.core.notifications_service import create_notification
            payload = msg.payload
            create_notification(
                user_id=payload["user_id"],
                message=payload.get("message", ""),
                title=payload.get("title"),
                notification_type=payload.get("type", "info"),
                icon=payload.get("icon", "bi-bell"),
            )
        elif msg.channel == "email":
            # Flask-Mail (implementar conforme necessidade)
            logger.info("Email channel: %s", msg.payload)
        elif msg.channel == "webhook":
            import requests as req
            url     = msg.payload.get("url")
            payload = msg.payload.get("data", {})
            req.post(url, json=payload, timeout=10)
        else:
            raise ValueError(f"Canal '{msg.channel}' não suportado.")

    # ── Logs ──────────────────────────────────────────────────────────────────

    @classmethod
    def list_logs(cls, task_id: int | None = None, page: int = 1, per_page: int = 20) -> dict:
        q = TaskLog.query
        if task_id:
            q = q.filter_by(task_id=task_id)
        q = q.order_by(TaskLog.started_at.desc())
        pag = q.paginate(page=page, per_page=per_page, error_out=False)
        return {
            "items": [cls._log_to_dict(l) for l in pag.items],
            "total": pag.total,
            "page": page,
            "per_page": per_page,
            "pages": pag.pages,
        }

    @classmethod
    def recent_stats(cls) -> dict:
        """Métricas para o dashboard: totais, falhas 24h, etc."""
        from sqlalchemy import func
        from datetime import timedelta

        now    = datetime.now(timezone.utc)
        day_ago = now - timedelta(hours=24)

        total_tasks   = ScheduledTask.query.count()
        pending_aprov = ScheduledTask.query.filter_by(status="pending_approval").count()
        active_tasks  = ScheduledTask.query.filter_by(status="active").count()
        paused_tasks  = ScheduledTask.query.filter_by(status="paused").count()

        failures_24h = TaskLog.query.filter(
            TaskLog.status == "failure",
            TaskLog.started_at >= day_ago,
        ).count()

        queue_pending = MessageQueue.query.filter_by(status="pending").count()
        queue_failed  = MessageQueue.query.filter_by(status="failed").count()

        # Últimas 7 execuções por dia (para gráfico)
        from sqlalchemy import func as sqlfunc
        daily = (
            db.session.query(
                sqlfunc.date(TaskLog.started_at).label("day"),
                sqlfunc.count(TaskLog.id).label("total"),
                sqlfunc.sum(
                    db.cast(TaskLog.status == "failure", db.Integer)
                ).label("failures"),
            )
            .filter(TaskLog.started_at >= now - timedelta(days=7))
            .group_by(sqlfunc.date(TaskLog.started_at))
            .order_by(sqlfunc.date(TaskLog.started_at))
            .all()
        )

        return {
            "total_tasks": total_tasks,
            "active_tasks": active_tasks,
            "paused_tasks": paused_tasks,
            "pending_approval": pending_aprov,
            "failures_24h": failures_24h,
            "queue_pending": queue_pending,
            "queue_failed": queue_failed,
            "daily_chart": [
                {"day": str(r.day), "total": r.total, "failures": int(r.failures or 0)}
                for r in daily
            ],
        }

    # ── APScheduler ───────────────────────────────────────────────────────────

    @classmethod
    def init_scheduler(cls, app) -> None:
        """Inicializa o APScheduler com os jobs principais. Chamado em create_app()."""
        try:
            from apscheduler.schedulers.background import BackgroundScheduler
            from apscheduler.triggers.interval import IntervalTrigger

            scheduler = BackgroundScheduler(timezone="UTC")

            # Os jobs recebem a app já criada via closure — NUNCA chamam
            # create_app() de novo (isso recriaria blueprints, DB engine, etc.
            # a cada execução do job, o que é um bug grave de duplicação).
            scheduler.add_job(
                func=lambda: cls._job_process_queue(app),
                trigger=IntervalTrigger(seconds=15),
                id="process_queue",
                replace_existing=True,
                max_instances=1,
                coalesce=True,
            )

            scheduler.add_job(
                func=lambda: cls._job_run_due_tasks(app),
                trigger=IntervalTrigger(minutes=1),
                id="run_due_tasks",
                replace_existing=True,
                max_instances=1,
                coalesce=True,
            )

            scheduler.start()
            app._scheduler = scheduler
            logger.info("APScheduler iniciado com sucesso (process_queue=15s, run_due_tasks=60s).")

        except ImportError:
            logger.warning(
                "APScheduler não instalado. Agendamento automático desabilitado. "
                "Execute: pip install apscheduler"
            )
        except Exception as e:
            logger.error("Falha ao iniciar APScheduler: %s", e)

    @classmethod
    def _job_process_queue(cls, app) -> None:
        """Job periódico: processa a fila de mensagens. Usa a app já existente."""
        with app.app_context():
            try:
                n = cls.process_queue()
                if n:
                    logger.info("Fila: %d mensagens processadas.", n)
            except Exception as e:
                logger.error("Erro no job process_queue: %s", e)

    @classmethod
    def _job_run_due_tasks(cls, app) -> None:
        """Job periódico: executa tarefas agendadas vencidas. Usa a app já existente."""
        with app.app_context():
            try:
                now = datetime.now(timezone.utc)
                due = (
                    ScheduledTask.query
                    .filter(ScheduledTask.status == "active")
                    .filter(ScheduledTask.approved == True)
                    .filter(ScheduledTask.next_run <= now)
                    .all()
                )
                for task in due:
                    cls._execute_task(task)
            except Exception as e:
                logger.error("Erro no job run_due_tasks: %s", e)

    @classmethod
    def _sync_scheduler(cls, task: ScheduledTask) -> None:
        """Adiciona/atualiza o job no APScheduler (se disponível)."""
        pass  # APScheduler gerencia via job periódico; não precisa de job por tarefa

    @classmethod
    def _remove_from_scheduler(cls, task_id: int) -> None:
        pass  # idem

    # ── Helpers ───────────────────────────────────────────────────────────────

    @classmethod
    def _calc_next_run(cls, schedule: str) -> datetime | None:
        """Calcula próxima execução a partir de cron string ou intervalo em minutos."""
        from datetime import timedelta
        if not schedule:
            return None
        try:
            minutes = int(schedule)
            return datetime.now(timezone.utc) + timedelta(minutes=minutes)
        except ValueError:
            pass
        try:
            from croniter import croniter
            cron = croniter(schedule, datetime.now(timezone.utc))
            return cron.get_next(datetime)
        except Exception:
            logger.warning("Schedule inválido: %s", schedule)
            return None

    @classmethod
    def _task_to_dict(cls, t: ScheduledTask) -> dict:
        return {
            "id": t.id,
            "name": t.name,
            "task_type": t.task_type,
            "target": t.target,
            "schedule": t.schedule,
            "status": t.status,
            "requires_approval": t.requires_approval,
            "approved": t.approved,
            "last_run": t.last_run.isoformat() if t.last_run else None,
            "next_run": t.next_run.isoformat() if t.next_run else None,
            "result": t.result,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }

    @classmethod
    def _queue_to_dict(cls, m: MessageQueue) -> dict:
        return {
            "id": m.id,
            "channel": m.channel,
            "payload": m.payload,
            "status": m.status,
            "retries": m.retries,
            "max_retries": m.max_retries,
            "scheduled_for": m.scheduled_for.isoformat() if m.scheduled_for else None,
            "processed_at": m.processed_at.isoformat() if m.processed_at else None,
            "error_msg": m.error_msg,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }

    @classmethod
    def _log_to_dict(cls, l: TaskLog) -> dict:
        return {
            "id": l.id,
            "task_id": l.task_id,
            "task_name": l.task_name,
            "status": l.status,
            "started_at": l.started_at.isoformat() if l.started_at else None,
            "finished_at": l.finished_at.isoformat() if l.finished_at else None,
            "duration_ms": l.duration_ms,
            "result": l.result,
            "error": l.error,
        }

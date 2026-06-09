from db.database import db
from datetime import datetime, timezone

class ScheduledTask(db.Model):
    __tablename__ = "scheduled_task"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    task_type = db.Column(db.String(50), nullable=False)   # python_call, http_request, sql
    target = db.Column(db.Text, nullable=False)            # função path, URL, or SQL
    schedule = db.Column(db.String(100), nullable=False)   # cron string (ex: "0 2 * * *") ou intervalo em minutos
    status = db.Column(db.String(20), default="active")    # active, paused, completed, pending_approval, rejected
    last_run = db.Column(db.DateTime, nullable=True)
    next_run = db.Column(db.DateTime, nullable=True)
    result = db.Column(db.Text, nullable=True)
    requires_approval = db.Column(db.Boolean, default=False)
    approved = db.Column(db.Boolean, default=False)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<ScheduledTask {self.name}>"
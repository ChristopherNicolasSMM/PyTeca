from db.database import db
from datetime import datetime, timezone

class TaskLog(db.Model):
    __tablename__ = "task_log"

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey("scheduled_task.id"), nullable=True)
    task_name = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(20), nullable=False)     # success, failure, pending_approval
    started_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    finished_at = db.Column(db.DateTime, nullable=True)
    duration_ms = db.Column(db.Integer, nullable=True)
    result = db.Column(db.Text, nullable=True)
    error = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f"<TaskLog {self.task_name} {self.status}>"
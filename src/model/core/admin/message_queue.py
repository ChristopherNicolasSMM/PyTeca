from db.database import db
from datetime import datetime, timezone

class MessageQueue(db.Model):
    __tablename__ = "message_queue"

    id = db.Column(db.Integer, primary_key=True)
    channel = db.Column(db.String(50), nullable=False)     # email, webhook, notification
    payload = db.Column(db.JSON, nullable=False)
    status = db.Column(db.String(20), default="pending")   # pending, processing, done, failed
    retries = db.Column(db.Integer, default=0)
    max_retries = db.Column(db.Integer, default=3)
    scheduled_for = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    processed_at = db.Column(db.DateTime, nullable=True)
    error_msg = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<MessageQueue id={self.id} channel={self.channel}>"
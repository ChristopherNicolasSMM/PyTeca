from db.database import db
from datetime import datetime, timezone

class SystemConfig(db.Model):
    __tablename__ = "system_config"

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False, index=True)
    value = db.Column(db.Text, nullable=False, default="")
    type = db.Column(db.String(20), default="string")  # string, int, bool, json
    group = db.Column(db.String(50), nullable=True, index=True)
    description = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<SystemConfig {self.key}={self.value}>"
from db.database import db
from datetime import datetime, timezone

class Permission(db.Model):
    __tablename__ = "permissions"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)   # ex: "admin", "manage_users", "view_reports"
    description = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    roles = db.relationship("Role", secondary="role_permissions", back_populates="permissions")

    def __repr__(self):
        return f"<Permission {self.name}>"
from db.database import db
from datetime import datetime, timezone

class Role(db.Model):
    __tablename__ = "roles"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    description = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    users = db.relationship("User", secondary="user_roles", back_populates="roles")
    permissions = db.relationship("Permission", secondary="role_permissions", back_populates="roles")

    def __repr__(self):
        return f"<Role {self.name}>"
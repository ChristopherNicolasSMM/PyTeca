# model/core/config/menu_customization.py
from db.database import db

class MenuCustomization(db.Model):
    __tablename__ = "menu_customization"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)  # None = global
    config = db.Column(db.JSON, nullable=False, default=dict)
    created_at = db.Column(db.DateTime, default=db.func.now())
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())
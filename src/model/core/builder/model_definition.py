from db.database import db
from datetime import datetime, timezone

class ModelDefinition(db.Model):
    __tablename__ = "model_definition"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)          # ex: "Product"
    module = db.Column(db.String(100), nullable=False, default="admin")    # subpasta em model/
    table_name = db.Column(db.String(100), unique=True, nullable=False)
    fields = db.Column(db.JSON, nullable=False, default=list)              # lista de dicts com nome, tipo, etc.
    annotations = db.Column(db.JSON, default=dict)                         # ex: {"label": "Produtos", "plural": "products"}
    generated_file = db.Column(db.String(255), nullable=True)              # caminho relativo do arquivo gerado
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<ModelDefinition {self.name}>"
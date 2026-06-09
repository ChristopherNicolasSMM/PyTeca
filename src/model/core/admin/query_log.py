from db.database import db
from datetime import datetime, timezone

class QueryLog(db.Model):
    __tablename__ = "query_log"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    query_type = db.Column(db.String(20), nullable=False)   # sql, api
    query_text = db.Column(db.Text, nullable=False)         # SQL ou URL
    params = db.Column(db.JSON, nullable=True)              # parâmetros adicionais
    status = db.Column(db.String(20), default="success")
    result_rows = db.Column(db.Integer, nullable=True)
    error_msg = db.Column(db.Text, nullable=True)
    executed_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    def __repr__(self):
        return f"<QueryLog id={self.id} type={self.query_type}>"
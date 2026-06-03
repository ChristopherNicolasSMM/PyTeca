# utils/generate_model/base_model.py 
"""
Modelo base com anotações demonstrativas.
Copie este arquivo para model/<seu_model>.py e edite conforme necessário.
"""
from annotations import (
    label, plural, listview, Column, Filter, form, Group,
    required, max_length, min_length, min_value
)
from db.database import db

@label("Nome da Entidade")                     # singular, amigável
@plural("entidades")                           # nome plural para rotas
@listview(
    columns=[
        Column("id", label="ID", width="60px", sortable=True),
        Column("name", label="Nome", sortable=True, filterable=True),
        Column("status", label="Status", width="100px", align="center"),
    ],
    default_sort="name",
    filters=[
        Filter("name", type="text", placeholder="Buscar por nome..."),
        Filter("status", type="select", options=[("active","Ativo"), ("inactive","Inativo")]),
    ]
)
@form(
    fields=["name", "status", "description"],
    groups=[
        Group("basic", "Informações Básicas", ["name", "status"]),
        Group("details", "Detalhes", ["description"], collapsible=True),
    ]
)
@required("name", "Nome é obrigatório")
@max_length("name", 100)
@min_length("name", 3)
class BaseModel(db.Model):
    __tablename__ = "base_models"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(20), default="active")
    description = db.Column(db.Text)

    def __repr__(self):
        return f"<BaseModel {self.name}>"
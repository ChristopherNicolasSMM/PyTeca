# model/author.py
from annotations import label, plural, listview, Column, Filter, form, Group, required, max_length
from db.database import db

@label("Autores")
@plural("authors")
@listview(
    columns=[
        Column("id", label="ID", width="60px", sortable=True),
        Column("name", label="Nome", sortable=True, filterable=True),
        Column("birth_year", label="Ano Nascimento", width="100px", align="center"),
    ],
    default_sort="name",
    filters=[
        Filter("name", type="text", placeholder="Buscar por nome..."),
    ]
)
@form(
    fields=["name", "birth_year", "bio"],
    groups=[
        Group("basic", "Informações Básicas", ["name", "birth_year"]),
        Group("bio", "Biografia", ["bio"], collapsible=True),
    ]
)
@required("name", "Nome do autor é obrigatório")
@max_length("name", 100)
class Author(db.Model):
    __tablename__ = "authors"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    birth_year = db.Column(db.Integer)
    bio = db.Column(db.Text)
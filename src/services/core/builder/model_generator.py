import os
from pathlib import Path
from flask import current_app
from jinja2 import Environment, FileSystemLoader
from db.database import db
from model.core.builder.model_definition import ModelDefinition
from utils.generate_from_model import generate

class ModelGenerator:
    @classmethod
    def _map_field_type(cls, field_type: str) -> str:
        mapping = {
            "string": "String(255)",
            "text": "Text",
            "integer": "Integer",
            "boolean": "Boolean",
            "datetime": "DateTime(timezone=True)",
            "date": "Date",
            "float": "Float",
        }
        return mapping.get(field_type.lower(), "String(255)")

    @classmethod
    def generate_from_definition(cls, model_def_id: int) -> dict:
        model_def = ModelDefinition.query.get(model_def_id)
        if not model_def:
            return {"success": False, "error": "Definição não encontrada"}

        # Preparar campos
        fields_processed = []
        for f in model_def.fields:
            fields_processed.append({
                "name": f["name"],
                "type": f["type"],
                "type_mapped": cls._map_field_type(f["type"]),
                "nullable": f.get("nullable", True),
                "default": f.get("default"),
                "required": f.get("required", False),
                "max_length": f.get("max_length"),
            })

        # Carregar template com Jinja2
        template_dir = Path(__file__).parent.parent.parent / "utils" / "generate_model" / "templates" / "standard"
        env = Environment(loader=FileSystemLoader(template_dir))
        template = env.get_template("model.py.j2")

        context = {
            "class_name": model_def.name,
            "class_name_lower": model_def.name.lower(),
            "module_name": model_def.module,
            "table_name": model_def.table_name,
            "fields": fields_processed,
            "annotations": model_def.annotations,
        }
        code = template.render(context)

        # Salvar arquivo
        file_path = Path("model") / model_def.module / f"{model_def.name.lower()}.py"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(code, encoding="utf-8")

        model_def.generated_file = str(file_path)
        db.session.commit()

        try:
            generate(str(file_path), theme="standard", overwrite=False, add_to_root_menu=False)
        except Exception as e:
            return {"success": False, "error": f"Modelo criado, mas CRUD falhou: {str(e)}", "file": str(file_path)}

        return {"success": True, "file": str(file_path), "message": "Modelo e CRUD gerados com sucesso"}
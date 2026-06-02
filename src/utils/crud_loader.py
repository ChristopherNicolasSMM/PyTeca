# src/utils/crud_loader.py
from functools import lru_cache
from pathlib import Path
import yaml

@lru_cache(maxsize=128)
def load_crud_config(resource_name: str) -> dict:
    """
    Carrega a configuração YAML para um recurso (ex: 'books', 'maltes').
    Retorna um dicionário vazio se o arquivo não existir.
    """
    yaml_path = Path(__file__).parent.parent / 'templates' / resource_name / 'manage.yaml'
    if not yaml_path.exists():
        return {}
    try:
        with open(yaml_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        print(f"Erro ao carregar YAML para {resource_name}: {e}")
        return {}
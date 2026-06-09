from __future__ import annotations
import json
from typing import Any
from flask import current_app
from db.database import db
from model.core.admin.system_config import SystemConfig

class ConfigService:
    _cache = {}  # cache simples em memória

    @classmethod
    def get(cls, key: str, default: Any = None) -> Any:
        # Tenta cache
        if key in cls._cache:
            return cls._cache[key]

        config = SystemConfig.query.filter_by(key=key).first()
        if not config:
            return default

        value = cls._parse_value(config.value, config.type)
        cls._cache[key] = value
        return value

    @classmethod
    def set(cls, key: str, value: Any, type: str = "string", group: str = None, description: str = None) -> SystemConfig:
        config = SystemConfig.query.filter_by(key=key).first()
        if not config:
            config = SystemConfig(key=key, type=type, group=group, description=description)
            db.session.add(config)

        config.value = cls._serialize_value(value, type)
        if group:
            config.group = group
        if description:
            config.description = description

        db.session.commit()
        cls._cache[key] = value
        return config

    @classmethod
    def get_group(cls, group: str) -> dict[str, Any]:
        configs = SystemConfig.query.filter_by(group=group).all()
        return {cfg.key: cls._parse_value(cfg.value, cfg.type) for cfg in configs}

    @classmethod
    def _parse_value(cls, value: str, type: str) -> Any:
        if type == "int":
            return int(value)
        if type == "bool":
            return value.lower() == "true"
        if type == "json":
            return json.loads(value)
        return value

    @classmethod
    def _serialize_value(cls, value: Any, type: str) -> str:
        if type == "json":
            return json.dumps(value, ensure_ascii=False)
        return str(value)
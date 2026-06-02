"""
Configuração unificada de logging para a aplicação.
"""

from __future__ import annotations

import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path


def configure_logging(app) -> None:
    """
    Configura logging para stdout e arquivo rotativo.
    Evita recriar handlers se já estiverem configurados.
    """
    root_logger = logging.getLogger()
    if root_logger.handlers:
        return

    log_level = logging.DEBUG if app.config.get("DEBUG") else logging.INFO
    root_logger.setLevel(log_level)

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    stream_handler.setLevel(log_level)
    root_logger.addHandler(stream_handler)

    log_dir = Path(app.root_path).parent / "logs"
    log_dir.mkdir(exist_ok=True)

    if app.config.get("DEBUG"):
        timestamp = datetime.now().strftime("%d_%m_%Y_%H_%M_%S")
        log_path = log_dir / f"{timestamp}.log"
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
    else:
        log_path = log_dir / "brewstation.log"
        file_handler = RotatingFileHandler(
            log_path, maxBytes=1_000_000, backupCount=5, encoding="utf-8"
        )

    file_handler.setFormatter(formatter)
    file_handler.setLevel(log_level)
    root_logger.addHandler(file_handler)

    app.logger.info(
        "Logging configurado no nível %s (arquivo: %s).",
        logging.getLevelName(log_level),
        log_path.name,
    )

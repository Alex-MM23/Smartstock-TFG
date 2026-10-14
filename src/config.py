"""Configuración compartida (conexión a MySQL y ruta del modelo).

Todo se lee de variables de entorno, con valores por defecto pensados para
desarrollo local y para el docker-compose del proyecto.
"""
from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import URL, Engine

ROOT_DIR = Path(__file__).resolve().parents[1]
MODEL_PATH = Path(os.getenv("MODEL_PATH", ROOT_DIR / "artifacts" / "demand_model.joblib"))


def get_engine() -> Engine:
    """Crea el engine de SQLAlchemy (la conexión real se abre al primer uso)."""
    url = URL.create(
        "mysql+pymysql",
        username=os.getenv("DB_USER", "smartstock"),
        password=os.getenv("DB_PASSWORD", "smartstock_pass"),
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "3306")),
        database=os.getenv("DB_NAME", "smartstock"),
        query={"charset": "utf8mb4"},
    )
    return create_engine(url, pool_pre_ping=True, pool_recycle=1800)

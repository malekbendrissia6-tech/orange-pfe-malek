"""
=============================================================
  FICHIER : flask_app/config.py
  ROLE   : Configuration de l'application Flask
=============================================================
"""

import os
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def _db_uri():
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        return db_url.replace("postgres://", "postgresql://", 1)
    return (
        f"postgresql+psycopg2://{os.getenv('DB_USER', 'postgres')}:"
        f"{os.getenv('DB_PASSWORD', '')}"
        f"@{os.getenv('DB_HOST', 'localhost')}:"
        f"{os.getenv('DB_PORT', '5432')}/"
        f"{os.getenv('DB_NAME', 'orange_dwh')}"
    )

class Config:
    """Configuration de base partagee."""

    SECRET_KEY = os.getenv("SECRET_KEY", "orange-tunisie-pfe-2026-change-in-prod")

    DB_HOST     = os.getenv("DB_HOST", "localhost")
    DB_PORT     = os.getenv("DB_PORT", "5432")
    DB_NAME     = os.getenv("DB_NAME", "orange_dwh")
    DB_USER     = os.getenv("DB_USER", "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")

    SQLALCHEMY_DATABASE_URI        = _db_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    DEBUG   = False
    TESTING = False


class DevelopmentConfig(Config):
    DEBUG = True
    SESSION_COOKIE_SECURE = False


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True   # exige HTTPS en production
    # En production, SECRET_KEY DOIT etre definie dans .env (pas de fallback)
    SECRET_KEY = os.environ["SECRET_KEY"]

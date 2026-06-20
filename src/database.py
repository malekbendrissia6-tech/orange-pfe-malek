"""
=============================================================
  FICHIER : src/database.py
  ROLE   : Module de connexion PostgreSQL pour le DWH
  PROJET : PFE Orange Tunisie
=============================================================

Ce module gere :
  - La connexion a PostgreSQL
  - L'insertion des donnees dans le DWH
  - La gestion des erreurs de connexion

Utilisation :
  from src.database import get_engine, write_to_dwh
  engine = get_engine()
  write_to_dwh(df, "dim_vendeur")
=============================================================
"""

import os
import logging
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
import pandas as pd

# Charger les variables d'environnement depuis .env
load_dotenv()

logger = logging.getLogger(__name__)


def get_db_config() -> dict:
    """Recupere la configuration BD depuis le fichier .env"""
    return {
        "host":     os.getenv("DB_HOST", "localhost"),
        "port":     os.getenv("DB_PORT", "5432"),
        "database": os.getenv("DB_NAME", "orange_dwh"),
        "user":     os.getenv("DB_USER", "postgres"),
        "password": os.getenv("DB_PASSWORD", ""),
    }


def get_connection_string() -> str:
    """Construit la chaine de connexion PostgreSQL."""
    cfg = get_db_config()
    return (
        f"postgresql+psycopg2://{cfg['user']}:{cfg['password']}"
        f"@{cfg['host']}:{cfg['port']}/{cfg['database']}"
    )


def get_engine():
    """Retourne un moteur SQLAlchemy pour PostgreSQL."""
    try:
        engine = create_engine(get_connection_string(), echo=False)
        # Tester la connexion
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Connexion PostgreSQL etablie avec succes")
        return engine
    except SQLAlchemyError as e:
        logger.error(f"Erreur de connexion PostgreSQL : {e}")
        raise


def test_connection() -> bool:
    """Teste la connexion a PostgreSQL. Retourne True si OK."""
    try:
        engine = get_engine()
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.scalar()
            print(f"Connexion OK : {version}")
        return True
    except Exception as e:
        # Encodage robuste : les messages PostgreSQL en francais peuvent
        # contenir des caracteres cp1252 qui ne passent pas en UTF-8
        try:
            msg = str(e)
        except UnicodeDecodeError:
            msg = repr(e).encode("ascii", errors="replace").decode("ascii")
        print(f"Echec connexion : {msg}")
        return False


def write_to_dwh(df: pd.DataFrame, table_name: str,
                 if_exists: str = "append") -> int:
    """
    Insere un DataFrame dans une table PostgreSQL.

    Args:
        df: DataFrame a inserer
        table_name: Nom de la table cible (ex: "dim_vendeur")
        if_exists: "append" (defaut) ou "replace"

    Returns:
        Nombre de lignes inserees
    """
    if df.empty:
        logger.warning(f"DataFrame vide, aucune insertion dans {table_name}")
        return 0

    try:
        engine = get_engine()
        df.to_sql(
            name=table_name,
            con=engine,
            if_exists=if_exists,
            index=False,
            method="multi",  # Insertion par batch (plus rapide)
            chunksize=1000,
        )
        nb_inserted = len(df)
        logger.info(f"OK : {nb_inserted} lignes inserees dans {table_name}")
        return nb_inserted
    except SQLAlchemyError as e:
        logger.error(f"Erreur insertion {table_name} : {e}")
        raise


def truncate_table(table_name: str) -> None:
    """Vide une table (supprime toutes les lignes)."""
    try:
        engine = get_engine()
        with engine.begin() as conn:
            conn.execute(text(f"TRUNCATE TABLE {table_name} CASCADE"))
        logger.info(f"Table {table_name} videe")
    except SQLAlchemyError as e:
        logger.error(f"Erreur truncate {table_name} : {e}")
        raise


def count_rows(table_name: str) -> int:
    """Compte les lignes dans une table."""
    try:
        engine = get_engine()
        with engine.connect() as conn:
            result = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
            return result.scalar()
    except SQLAlchemyError as e:
        logger.error(f"Erreur count {table_name} : {e}")
        return 0


if __name__ == "__main__":
    print("Test de connexion PostgreSQL...")
    if test_connection():
        print("Tout fonctionne !")
    else:
        print("Probleme de connexion. Verifier .env et PostgreSQL.")

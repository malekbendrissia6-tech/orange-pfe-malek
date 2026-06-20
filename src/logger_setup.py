"""
=============================================================
  MODULE : logger_setup.py
  RÔLE  : Système de logs professionnel
  PROJET: PFE Orange Tunisie - Pipeline de nettoyage
=============================================================

Ce module crée un système de logs qui enregistre :
    - Dans un fichier .log (horodaté) dans le dossier logs/
    - Dans la console (pour voir en direct)

Chaque exécution crée un NOUVEAU fichier log avec horodatage,
ce qui permet de retracer l'historique complet des traitements.
=============================================================
"""

import logging
from datetime import datetime
from pathlib import Path


def setup_logger(table_name: str, log_dir: str = "logs") -> logging.Logger:
    """
    Configure un logger qui écrit à la fois dans un fichier et dans la console.

    Args:
        table_name: nom de la table traitée (ex: 'ventes_contrats')
        log_dir: répertoire où stocker les fichiers de log

    Returns:
        Logger configuré prêt à l'emploi
    """
    # Créer le dossier logs s'il n'existe pas
    Path(log_dir).mkdir(parents=True, exist_ok=True)

    # Nom du fichier log avec horodatage
    # Ex: ventes_contrats_20260418_103015.log
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = Path(log_dir) / f"{table_name}_{timestamp}.log"

    # Créer le logger
    logger = logging.getLogger(table_name)
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()  # Évite les doublons

    # Format des messages :
    # 2026-04-18 10:30:15 | INFO     | Message ici
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Handler 1 : écriture dans le fichier
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Handler 2 : affichage dans la console
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Message de démarrage
    logger.info(f"=== Début traitement table: {table_name} ===")
    logger.info(f"Fichier log: {log_file}")

    return logger
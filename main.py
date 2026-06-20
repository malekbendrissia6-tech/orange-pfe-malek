"""
=============================================================
  FICHIER : main.py
  RÔLE   : Point d'entrée du pipeline de nettoyage
  PROJET : PFE Orange Tunisie
=============================================================

UTILISATION :
    python main.py                       # Traite TOUTES les tables
    python main.py ventes_contrats       # Traite 1 table spécifique
    python main.py offres vendeurs       # Traite plusieurs tables

EXEMPLES :
    python main.py
    python main.py ventes_contrats
    python main.py offres vendeurs boutiques
=============================================================
"""

import sys
from pathlib import Path

# Ajoute le dossier src/ au PATH pour importer les modules
sys.path.insert(0, str(Path(__file__).parent / "src"))

from pipeline import run_pipeline


if __name__ == "__main__":
    # Récupère les arguments de la ligne de commande
    tables = sys.argv[1:] if len(sys.argv) > 1 else None
    run_pipeline(tables)
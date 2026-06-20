"""
=============================================================
  FICHIER : tests/conftest.py
  RÔLE   : Configuration globale des tests pytest
  PROJET : PFE Orange Tunisie
=============================================================

Ce fichier est automatiquement chargé par pytest avant
chaque session de tests. Il sert à :
    1. Ajouter le dossier src/ au PATH Python
    2. Définir des "fixtures" (données de test réutilisables)
=============================================================
"""

import sys
from pathlib import Path
import pandas as pd
import pytest

# ==================================================================
# Ajoute le dossier src/ au PATH pour que pytest trouve les modules
# ==================================================================
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))


# ==================================================================
# FIXTURES : données de test réutilisables
# ==================================================================

@pytest.fixture
def sample_df_ventes():
    """
    Crée un petit DataFrame de test qui imite la vraie table ventes_contrats.
    Contient volontairement des problèmes à nettoyer.
    """
    return pd.DataFrame({
        "ACTION_DATE": ["2025-01-01", "2025-01-02", "2025-01-03", None],
        "DUREE_ENGAGEMENT": ["12Mois", "24 mois", "  12 mois  ", None],
        "TYPE_ENGAGEMENT": ["avec engagement", "sans engagement", "avec engagement", "sans engagement"],
        "CONTRAT_SOUSCRIT": ["CONTR001", "CONTR002", "CONTR003", "CONTR004"],
        "OBJ_ID": ["PRO VOIX", None, "FLYBOX", "PRO VOIX"],
        "ENTITY_CODE": ["KSH0008", "TUN0280", None, "AGPRO001"],
        "SELLER_ID": ["MAMAMOU_EXT", "ZGHORBAL", "MJAAFRA", "PICASSO"],
        "PRODUCT_NUMBER": [43006000003, 43008000001, None, 43006000003],
        "CUSTCODE": [1.203493, 1.224461, 1.293890, 1.171949],
        "TMCODE": [56000000, 11000000, 57000000, 56000000],
        "PRGCODE": [34, 1, 27, 34],
        "FIRST_MONTH_BILL": [1.0, 1.0, 0.0, None],
        "SECOND_MONTH_BILL": [1.0, 0.0, 1.0, None],
        "THIRD_MONTH_BILL": [1.0, 1.0, None, None],
    })


@pytest.fixture
def sample_df_offres():
    """DataFrame de test pour la table offres."""
    return pd.DataFrame({
        "TMCODE": [101, 141, 104, None],
        "OFFRE_NAME": ["3AJAB", "3AJAB INTERNET", None, "OFFRE_TEST"],
        "TYPE_OFFRE": ["PREPAYE", "PREPAYE", "PREPAYE", None],
        "CANAL": ["Voix", "Voix", "Voix", None],
        "FAMILLE": ["MOB-PREPAID", "MOB-PREPAID", None, None],
        "CATEGORIE": ["Voix", "Voix", "Voix", None],
        "CIBLE": ["Twenssa", "Twenssa", "Tourist", None],
    })
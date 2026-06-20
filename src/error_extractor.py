"""
=============================================================
  MODULE : error_extractor.py
  RÔLE   : Extraction automatique des lignes avec erreurs
  PROJET : PFE Orange Tunisie - Pipeline de nettoyage
=============================================================

Principe :
    Avant le nettoyage, identifie les lignes avec des
    problemes de qualite et les sauvegarde dans data/error/
    pour permettre aux equipes metier de les corriger.

Types d'erreurs tracees :
    - rows_dropped   : lignes supprimees (cle primaire vide)
    - column_missing : une colonne importante est vide
    - duplicates     : doublons sur la cle primaire
=============================================================
"""

from pathlib import Path
import pandas as pd
import logging


class ErrorExtractor:
    """
    Classe qui extrait les lignes problematiques d'un DataFrame
    et les sauvegarde dans des fichiers Excel dans data/error/.
    """

    # Dossier ou sauvegarder les fichiers d'erreurs
    ERROR_DIR = Path("data/error")

    def __init__(self, table_name: str, config: dict, logger: logging.Logger):
        """
        Parametres :
            table_name : nom de la table (ex: 'ventes_contrats')
            config     : configuration de la table (TABLES_CONFIG[name])
            logger     : logger pour tracer les operations
        """
        self.table_name = table_name
        self.config = config
        self.logger = logger

        # Creer le dossier data/error/ si il n'existe pas
        self.ERROR_DIR.mkdir(parents=True, exist_ok=True)

    # ==================================================================
    # METHODE 1 : Extraire les lignes a supprimer (cle primaire vide)
    # ==================================================================
    def extract_dropped_rows(self, df: pd.DataFrame) -> int:
        """
        Sauvegarde les lignes qui vont etre supprimees
        (celles ou la cle primaire ou les colonnes critiques sont vides).

        Retourne : nombre de lignes sauvegardees
        """
        drop_cols = self.config.get("drop_if_null", [])
        if not drop_cols:
            return 0

        # Trouver les lignes ou AU MOINS une des colonnes critiques est vide
        mask = df[drop_cols].isna().any(axis=1)
        error_rows = df[mask].copy()

        if len(error_rows) == 0:
            return 0

        # Ajouter une colonne qui indique POURQUOI c'est une erreur
        error_rows["_ERROR_REASON"] = error_rows[drop_cols].apply(
            lambda row: "Colonnes vides: " + ", ".join(
                [c for c in drop_cols if pd.isna(row[c])]
            ),
            axis=1
        )

        # Sauvegarder
        output_path = self.ERROR_DIR / f"{self.table_name}_rows_dropped.xlsx"
        error_rows.to_excel(output_path, index=False, engine="openpyxl")

        self.logger.info(
            f"[error_extract] {len(error_rows)} lignes supprimees sauvegardees "
            f"dans {output_path}"
        )
        return len(error_rows)

    # ==================================================================
    # METHODE 2 : Extraire les lignes avec une colonne vide (non-critique)
    # ==================================================================
    def extract_missing_column(self, df: pd.DataFrame, column: str) -> int:
        """
        Sauvegarde les lignes ou une colonne specifique est vide
        (avant qu'on remplisse avec la valeur par defaut).

        Parametres :
            df     : DataFrame a analyser
            column : nom de la colonne a verifier

        Retourne : nombre de lignes sauvegardees
        """
        if column not in df.columns:
            return 0

        mask = df[column].isna()
        error_rows = df[mask].copy()

        if len(error_rows) == 0:
            return 0

        # Ajouter la raison
        error_rows["_ERROR_REASON"] = f"Colonne {column} vide"

        # Nom du fichier
        col_name = column.lower()
        output_path = self.ERROR_DIR / f"{self.table_name}_{col_name}_missing.xlsx"
        error_rows.to_excel(output_path, index=False, engine="openpyxl")

        self.logger.info(
            f"[error_extract] {len(error_rows)} lignes avec {column} vide "
            f"sauvegardees dans {output_path}"
        )
        return len(error_rows)

    # ==================================================================
    # METHODE 3 : Extraire les doublons sur la cle primaire
    # ==================================================================
    def extract_duplicates(self, df: pd.DataFrame) -> int:
        """
        Sauvegarde les lignes qui sont des doublons (meme cle primaire).
        Retourne : nombre de lignes sauvegardees
        """
        pk = self.config.get("primary_key")
        if not pk or pk not in df.columns:
            return 0

        # Trouver tous les doublons (premiere occurrence + suivantes)
        duplicates = df[df.duplicated(subset=[pk], keep=False)].copy()

        if len(duplicates) == 0:
            return 0

        duplicates["_ERROR_REASON"] = f"Doublon sur cle primaire {pk}"

        # Trier pour faciliter la lecture
        duplicates = duplicates.sort_values(by=pk)

        output_path = self.ERROR_DIR / f"{self.table_name}_duplicates.xlsx"
        duplicates.to_excel(output_path, index=False, engine="openpyxl")

        self.logger.info(
            f"[error_extract] {len(duplicates)} doublons sauvegardes "
            f"dans {output_path}"
        )
        return len(duplicates)

    # ==================================================================
    # METHODE PRINCIPALE : Extraire TOUTES les erreurs en une fois
    # ==================================================================
    def extract_all(self, df: pd.DataFrame) -> dict:
        """
        Methode principale : extrait tous les types d'erreurs.

        Retourne un dictionnaire avec les stats :
            {
                'rows_dropped': 8,
                'entity_code_missing': 189,
                'obj_id_missing': 8435,
                'duplicates': 0,
            }
        """
        stats = {}

        # 1. Lignes a supprimer (cle primaire vide)
        stats["rows_dropped"] = self.extract_dropped_rows(df)

        # 2. Colonnes avec valeurs manquantes (celles qu'on remplit avec fill_na)
        fill_na = self.config.get("fill_na", {})
        for column in fill_na.keys():
            if column in df.columns:
                count = self.extract_missing_column(df, column)
                if count > 0:
                    stats[f"{column.lower()}_missing"] = count

        # 3. Doublons
        stats["duplicates"] = self.extract_duplicates(df)

        return stats
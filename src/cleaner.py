"""
=============================================================
  MODULE : cleaner.py
  ROLE  : Moteur generique de nettoyage des donnees
  PROJET: PFE Orange Tunisie - Pipeline de nettoyage
=============================================================

Classe DataCleaner : applique 10 operations sequentielles
a n'importe quelle table, en suivant les regles definies
dans config.py.

Principe DRY (Don't Repeat Yourself) :
    Un seul moteur pour toutes les tables.
    Zero duplication de code.
=============================================================
"""

import pandas as pd
import numpy as np
import logging
import unicodedata
from typing import Dict, Any, Tuple, List


class DataCleaner:
    """
    Moteur de nettoyage generique configurable.

    Applique un pipeline de 10 operations a un DataFrame :
        0. Renommage des colonnes (NOUVEAU)
        1. Nettoyage des chaines (espaces)
        2. Standardisation des categories
        3. Conversion des dates
        4. Conversion des nombres
        5. Suppression des lignes invalides
        6. Suppression des doublons
        7. Remplissage conditionnel
        8. Remplissage des NaN
        9. Application des types finaux
    """

    def __init__(self, config: Dict[str, Any], logger: logging.Logger):
        self.config = config
        self.logger = logger
        # Historique des transformations (pour le rapport qualite)
        self.transformations: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Utilitaire : enregistre une transformation dans l'historique
    # ------------------------------------------------------------------
    def _record(self, step: str, details: Dict[str, Any]):
        self.transformations.append({"step": step, **details})
        self.logger.info(f"[{step}] {details}")

    # ------------------------------------------------------------------
    # 0. NOUVEAU : Renommage des colonnes (pour harmoniser les noms)
    # ------------------------------------------------------------------
    def rename_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Renomme les colonnes selon la configuration.
        Permet d'harmoniser les noms entre tables (ex: 'CODE ENTITE' -> 'CODE_ENTITY').
        """
        rename_map = self.config.get("rename_columns", {})
        if not rename_map:
            return df

        # Garder seulement les colonnes qui existent vraiment
        actual_renames = {
            old: new for old, new in rename_map.items()
            if old in df.columns
        }

        if actual_renames:
            df = df.rename(columns=actual_renames)
            self._record("rename_columns", {
                "renamed": actual_renames,
                "count": len(actual_renames),
            })
        return df

    # ------------------------------------------------------------------
    # 1. Nettoyage des chaines (espaces, NaN string)
    # ------------------------------------------------------------------
    @staticmethod
    def _normalize_string(s):
        """Trim + suppression espaces multiples + gestion NaN."""
        if pd.isna(s):
            return np.nan
        s = str(s).strip()
        s = " ".join(s.split())  # espaces multiples -> un seul
        return s if s else np.nan

    def clean_strings(self, df: pd.DataFrame) -> pd.DataFrame:
        cols = self.config.get("string_columns", [])
        for col in cols:
            if col not in df.columns:
                self.logger.warning(f"Colonne '{col}' absente - ignoree")
                continue
            before_nulls = df[col].isna().sum()
            df[col] = df[col].apply(self._normalize_string)
            after_nulls = df[col].isna().sum()
            self._record("clean_strings", {
                "column": col,
                "nulls_before": int(before_nulls),
                "nulls_after": int(after_nulls),
            })
        return df

    # ------------------------------------------------------------------
    # 2. Standardisation des categories (ex: "12Mois" -> "12 mois")
    # ------------------------------------------------------------------
    @staticmethod
    def _key_for_matching(s):
        """Normalise une chaine pour matcher : minuscules, sans accents, sans espaces."""
        if pd.isna(s):
            return s
        s = str(s).lower().strip()
        s = "".join(
            c for c in unicodedata.normalize("NFD", s)
            if unicodedata.category(c) != "Mn"
        )
        s = s.replace(" ", "")
        return s

    def standardize_categories(self, df: pd.DataFrame) -> pd.DataFrame:
        mapping_config = self.config.get("categorical_map", {})
        for col, mapping in mapping_config.items():
            if col not in df.columns:
                continue
            before_values = df[col].value_counts(dropna=False).to_dict()

            def transform(val, _map=mapping):
                key = self._key_for_matching(val)
                return _map.get(key, val)

            df[col] = df[col].apply(transform)
            after_values = df[col].value_counts(dropna=False).to_dict()
            self._record("standardize_categories", {
                "column": col,
                "distinct_before": len(before_values),
                "distinct_after": len(after_values),
            })
        return df

    # ------------------------------------------------------------------
    # 3. Conversion des dates
    # ------------------------------------------------------------------
    def parse_dates(self, df: pd.DataFrame) -> pd.DataFrame:
        for col in self.config.get("date_columns", []):
            if col not in df.columns:
                continue
            before = df[col].isna().sum()
            df[col] = pd.to_datetime(df[col], errors="coerce")
            after = df[col].isna().sum()
            self._record("parse_dates", {
                "column": col,
                "failed_conversions": int(after - before),
                "min_date": str(df[col].min()),
                "max_date": str(df[col].max()),
            })
        return df

    # ------------------------------------------------------------------
    # 4. Colonne MONTH (YYYY-MM) a partir d'une date
    # ------------------------------------------------------------------
    def add_month_column(self, df: pd.DataFrame) -> pd.DataFrame:
        source_col = self.config.get("add_month_from")
        if not source_col or source_col not in df.columns:
            return df
        df[source_col] = pd.to_datetime(df[source_col], errors="coerce")
        df["MONTH"] = df[source_col].dt.strftime("%Y-%m")
        self._record("add_month_column", {
            "source_column": source_col,
            "target_column": "MONTH",
            "rows_with_month": int(df["MONTH"].notna().sum()),
        })
        return df

    # ------------------------------------------------------------------
    # 5. Conversion des nombres
    # ------------------------------------------------------------------
    def convert_numerics(self, df: pd.DataFrame) -> pd.DataFrame:
        for col in self.config.get("numeric_columns", []):
            if col not in df.columns:
                continue
            before = df[col].isna().sum()
            df[col] = pd.to_numeric(df[col], errors="coerce")
            after = df[col].isna().sum()
            self._record("convert_numerics", {
                "column": col,
                "failed_conversions": int(after - before),
            })
        return df

    # ------------------------------------------------------------------
    # 5. Suppression des lignes invalides (cle metier vide)
    # ------------------------------------------------------------------
    def drop_null_rows(self, df: pd.DataFrame) -> pd.DataFrame:
        cols = self.config.get("drop_if_null", [])
        cols = [c for c in cols if c in df.columns]
        if not cols:
            return df
        before = len(df)
        df = df.dropna(subset=cols).reset_index(drop=True)
        dropped = before - len(df)
        self._record("drop_null_rows", {
            "columns": cols,
            "rows_dropped": dropped,
            "rows_remaining": len(df),
        })
        return df

    # ------------------------------------------------------------------
    # 6b. Cle primaire composite (ex: SELLER_ID + MONTH)
    # ------------------------------------------------------------------
    def add_composite_key(self, df: pd.DataFrame) -> pd.DataFrame:
        composite = self.config.get("composite_key")
        if not composite:
            return df
        name = composite["name"]
        cols = composite["columns"]
        sep = composite.get("separator", "_")
        missing = [c for c in cols if c not in df.columns]
        if missing:
            self.logger.warning(f"Colonnes manquantes pour cle composite : {missing}")
            return df
        df[name] = df[cols].astype(str).agg(sep.join, axis=1)
        self._record("add_composite_key", {
            "key_name": name,
            "from_columns": cols,
            "unique_keys": int(df[name].nunique()),
        })
        return df

    # ------------------------------------------------------------------
    # 7. Suppression des doublons sur la cle primaire
    # ------------------------------------------------------------------
    def drop_duplicates(self, df: pd.DataFrame) -> pd.DataFrame:
        pk = self.config.get("primary_key")
        if not pk or pk not in df.columns:
            return df
        before = len(df)
        df = df.drop_duplicates(subset=[pk], keep="first").reset_index(drop=True)
        dropped = before - len(df)
        self._record("drop_duplicates", {
            "primary_key": pk,
            "duplicates_dropped": dropped,
        })
        return df

    # ------------------------------------------------------------------
    # 7. Remplissage conditionnel intelligent
    # ------------------------------------------------------------------
    def apply_conditional_fills(self, df: pd.DataFrame) -> pd.DataFrame:
        for rule in self.config.get("conditional_fill", []):
            if_col = rule["if_column"]
            then_col = rule["then_column"]
            if if_col not in df.columns or then_col not in df.columns:
                continue
            mask = df[if_col] == rule["if_value"]
            if rule.get("only_if_null", False):
                mask = mask & df[then_col].isna()
            n = int(mask.sum())
            df.loc[mask, then_col] = rule["then_value"]
            self._record("conditional_fill", {
                "rule": f"{if_col}='{rule['if_value']}' -> {then_col}='{rule['then_value']}'",
                "rows_affected": n,
            })
        return df

    # ------------------------------------------------------------------
    # 8. Remplissage des NaN avec valeurs par defaut
    # ------------------------------------------------------------------
    def fill_missing(self, df: pd.DataFrame) -> pd.DataFrame:
        for col, value in self.config.get("fill_na", {}).items():
            if col not in df.columns:
                continue
            n = int(df[col].isna().sum())
            df[col] = df[col].fillna(value)
            self._record("fill_missing", {
                "column": col, "fill_value": value, "rows_filled": n,
            })
        return df

    # ------------------------------------------------------------------
    # 9. Application des types finaux (optimisation Power BI)
    # ------------------------------------------------------------------
    def apply_output_types(self, df: pd.DataFrame) -> pd.DataFrame:
        for col, dtype in self.config.get("output_types", {}).items():
            if col not in df.columns:
                continue
            try:
                df[col] = df[col].astype(dtype)
            except Exception as e:
                self.logger.warning(f"Conversion {col}->{dtype} echouee: {e}")
        return df

    # ==================================================================
    # Pipeline complet : enchaine les 10 operations dans l'ordre
    # ==================================================================
    def run(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        initial_rows = len(df)
        self.logger.info(f"Lignes initiales: {initial_rows}")
        initial_nulls = int(df.isna().sum().sum())

        # Ordre optimal des etapes
        df = self.rename_columns(df)
        df = self.clean_strings(df)
        df = self.standardize_categories(df)
        df = self.parse_dates(df)
        df = self.add_month_column(df)
        df = self.convert_numerics(df)
        df = self.drop_null_rows(df)
        df = self.add_composite_key(df)
        df = self.drop_duplicates(df)
        df = self.apply_conditional_fills(df)
        df = self.fill_missing(df)
        df = self.apply_output_types(df)

        final_rows = len(df)
        final_nulls = int(df.isna().sum().sum())

        summary = {
            "initial_rows": initial_rows,
            "final_rows": final_rows,
            "rows_removed": initial_rows - final_rows,
            "initial_nulls": initial_nulls,
            "final_nulls": final_nulls,
            "transformations": self.transformations,
        }

        self.logger.info(
            f"Termine: {initial_rows} -> {final_rows} lignes "
            f"({initial_rows - final_rows} supprimees), "
            f"{initial_nulls} -> {final_nulls} NaN"
        )

        return df, summary
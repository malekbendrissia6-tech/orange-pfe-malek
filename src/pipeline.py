"""
=============================================================
  MODULE : pipeline.py
  ROLE  : Orchestrateur principal du pipeline
  PROJET: PFE Orange Tunisie - Pipeline de nettoyage
=============================================================
"""

import pandas as pd
from pathlib import Path

from config import TABLES_CONFIG
from cleaner import DataCleaner
from logger_setup import setup_logger
from quality_report import generate_report
from error_extractor import ErrorExtractor


def process_table(table_name: str, table_config: dict) -> dict:
    """Traite une seule table de bout en bout."""
    logger = setup_logger(table_name)

    source = table_config["source_file"]
    output = table_config["output_file"]

    # 1. Chargement
    logger.info(f"Chargement: {source}")
    df = pd.read_excel(source)
    logger.info(f"Charge: {df.shape[0]:,} lignes x {df.shape[1]} colonnes")

    # 2. Renommer les colonnes AVANT l'extraction d'erreurs
    rename_map = table_config.get("rename_columns", {})
    if rename_map:
        actual_renames = {old: new for old, new in rename_map.items() if old in df.columns}
        if actual_renames:
            df = df.rename(columns=actual_renames)
            logger.info(f"[rename_columns] Renomme: {actual_renames}")

    # 3. Extraction des erreurs (apres renommage)
    extractor = ErrorExtractor(table_name, table_config, logger)
    error_stats = extractor.extract_all(df)
    total_errors = sum(error_stats.values())
    logger.info(f"[error_summary] {total_errors} lignes avec erreurs extraites dans data/error/")

    # 4. Nettoyage
    cleaner = DataCleaner(table_config, logger)
    df_clean, summary = cleaner.run(df)

    # 5. Export
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    df_clean.to_excel(output, index=False, engine="openpyxl")
    logger.info(f"Fichier nettoye ecrit: {output}")

    # 6. Rapport qualite
    report_path = generate_report(df_clean, summary, table_name)
    logger.info(f"Rapport qualite: {report_path}")

    logger.info(f"=== Fin traitement: {table_name} ===\n")

    return {
        "table": table_name,
        "rows_in": summary["initial_rows"],
        "rows_out": summary["final_rows"],
        "errors_extracted": total_errors,
        "output_file": output,
        "report_file": report_path,
    }


def run_pipeline(tables: list = None) -> pd.DataFrame:
    """Execute le pipeline sur une ou plusieurs tables."""
    tables_to_run = tables or list(TABLES_CONFIG.keys())

    results = []
    for name in tables_to_run:
        if name not in TABLES_CONFIG:
            print(f"!  Table '{name}' absente de la config - ignoree")
            continue
        try:
            results.append(process_table(name, TABLES_CONFIG[name]))
        except Exception as e:
            print(f"ERREUR sur '{name}': {e}")
            raise

    summary_df = pd.DataFrame(results)
    print("\n" + "=" * 70)
    print("RECAPITULATIF GLOBAL DU PIPELINE")
    print("=" * 70)
    print(summary_df.to_string(index=False))
    return summary_df

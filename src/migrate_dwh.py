"""
=============================================================
  FICHIER : src/migrate_dwh.py
  ROLE   : Migration des donnees Excel -> PostgreSQL DWH
  PROJET : PFE Orange Tunisie
=============================================================

Ce module migre les fichiers data/output/*.xlsx vers les tables
PostgreSQL du Data Warehouse orange_dwh.

Mapping fichier -> table :
  vendeurs.xlsx       -> dim_vendeur
  boutiques.xlsx      -> dim_boutique
  articles.xlsx       -> dim_produit
  offres.xlsx         -> dim_offre
  groupes.xlsx        -> dim_groupe
  ref_objectifs.xlsx  -> dim_ref_objectifs
  ventes_contrats.xlsx-> fact_ventes
  objectifs.xlsx      -> fact_objectifs

Utilisation :
  python -m src.migrate_dwh             # migre tout
  python -m src.migrate_dwh vendeurs    # migre une table
=============================================================
"""

import sys
import logging
from pathlib import Path
import pandas as pd

from src.database import get_engine, write_to_dwh, truncate_table, count_rows
from src.logger_setup import setup_logger

# Configuration
PROJECT_ROOT = Path(__file__).parent.parent
OUTPUT_DIR   = PROJECT_ROOT / "data" / "output"

# Mapping : nom de fichier -> nom de table DWH
TABLE_MAPPING = {
    "vendeurs":         "dim_vendeur",
    "boutiques":        "dim_boutique",
    "articles":         "dim_produit",
    "offres":           "dim_offre",
    "groupes":          "dim_groupe",
    "ref_objectifs":    "dim_ref_objectifs",
    # Faits a la fin (apres les dimensions)
    "ventes_contrats":  "fact_ventes",
    "objectifs":        "fact_objectifs",
}

# Mapping des colonnes Excel -> colonnes BD
COLUMN_MAPPING = {
    "vendeurs": {
        "SELLER_ID":            "seller_id",
        "SELLER_NAME":          "seller_name",
        "CODE_STOCK":           "code_stock",
        "MONTH":                "month",
        "SELLER_KEY":           "seller_key_composite",
    },
    "boutiques": {
        "CODE_ENTITY":          "entity_code",
        "ENTITY_NAME":          "entity_name",
        "RESPONSABLE":          "responsable",
        "CANAL_VENTE":          "canal_vente",
    },
    "articles": {
        "PRODUCT_CODE":         "product_code",
        "PRODUCT_NAME":         "product_name",
        "PRODUCT_TYPE":         "product_type",
    },
    "offres": {
        "TMCODE":               "tmcode",
        "OFFRE_NAME":           "offre_name",
        "TYPE_OFFRE":           "type_offre",
        "CANAL":                "canal",
    },
    "groupes": {
        "PRGCODE":              "prgcode",
        "PRGNAME":              "prgname",
    },
    "ref_objectifs": {
        "LIGNE_PDT_OBJ":        "ligne_pdt_obj",
        "DESIGNATION_OBJECTIF": "designation",
    },
}

logger = setup_logger("migrate_dwh")


def load_clean_data(table_name: str) -> pd.DataFrame:
    """Charge un fichier Excel nettoye depuis data/output/"""
    file_path = OUTPUT_DIR / f"{table_name}_clean.xlsx"
    if not file_path.exists():
        logger.warning(f"Fichier non trouve : {file_path}")
        return pd.DataFrame()
    df = pd.read_excel(file_path)
    logger.info(f"Charge {len(df)} lignes depuis {file_path.name}")
    return df


def prepare_dimension_data(table_name: str, df: pd.DataFrame) -> pd.DataFrame:
    """
    Prepare un DataFrame de dimension pour insertion :
    - Renomme les colonnes selon le mapping
    - Garde uniquement les colonnes attendues par la BD
    """
    if table_name not in COLUMN_MAPPING:
        # Pas de mapping defini : on normalise les noms en minuscules
        df.columns = [c.lower().replace(" ", "_") for c in df.columns]
        return df

    mapping = COLUMN_MAPPING[table_name]
    # Colonnes presentes dans le fichier ET dans le mapping
    cols_present = [c for c in mapping.keys() if c in df.columns]
    if not cols_present:
        logger.warning(
            f"Aucune colonne du mapping trouvee pour {table_name}. "
            f"Colonnes disponibles : {list(df.columns)}"
        )
        # Fallback : tout passer avec noms normalises
        df.columns = [c.lower().replace(" ", "_") for c in df.columns]
        return df

    df_filtered = df[cols_present].copy()
    df_filtered.rename(columns=mapping, inplace=True)
    return df_filtered


def migrate_dimension(file_name: str, dwh_table: str) -> int:
    """Migre une table de dimension."""
    print(f"\n{'='*60}")
    print(f"Migration : {file_name}.xlsx -> {dwh_table}")
    print(f"{'='*60}")

    # 1. Charger les donnees
    df = load_clean_data(file_name)
    if df.empty:
        print(f"Aucune donnee a migrer pour {file_name}")
        return 0

    # 2. Preparer les donnees (renommage colonnes)
    df_prepared = prepare_dimension_data(file_name, df)
    print(f"Lignes a inserer  : {len(df_prepared)}")
    print(f"Colonnes          : {list(df_prepared.columns)}")

    # 3. Vider la table avant insertion (idempotent)
    # Si la table existe avec des FK : TRUNCATE CASCADE (ne detruit pas la structure)
    # Si la table n'existe pas : to_sql la creera avec if_exists="replace"
    table_exists = True
    try:
        truncate_table(dwh_table)
    except Exception:
        table_exists = False
        logger.info(f"Table {dwh_table} inexistante, elle sera creee automatiquement")

    # 4. Inserer dans la BD
    # - "append" si la table existe deja (structure preservee, FK intactes)
    # - "replace" si la table n'existe pas encore (creation automatique)
    insert_mode = "append" if table_exists else "replace"
    nb_inserted = write_to_dwh(df_prepared, dwh_table, if_exists=insert_mode)

    # 5. Verifier
    nb_in_db = count_rows(dwh_table)
    print(f"Lignes dans la BD : {nb_in_db}")

    return nb_inserted


def resolve_foreign_keys(df: pd.DataFrame, source_col: str,
                         dim_table: str, dim_col: str, dim_key: str) -> pd.DataFrame:
    """
    Resout une cle etrangere : remplace le code texte par la cle BD.
    Convertit les deux cotes en string avant le merge pour eviter
    les incompatibilites de types (int Excel vs varchar PostgreSQL).
    """
    engine = get_engine()
    df_mapping = pd.read_sql(f"SELECT {dim_col}, {dim_key} FROM {dim_table}", engine)

    # Normaliser en string pour eviter mismatch int64 vs varchar
    df = df.copy()
    df[source_col]      = df[source_col].astype(str)
    df_mapping[dim_col] = df_mapping[dim_col].astype(str)

    # Deduplication critique : certaines dimensions ont plusieurs lignes
    # par cle metier (ex: dim_vendeur une ligne par mois).
    # On garde la premiere occurrence pour eviter le fan-out du merge.
    df_mapping = df_mapping.drop_duplicates(subset=[dim_col], keep="first")

    df_resolved = df.merge(df_mapping, left_on=source_col, right_on=dim_col, how="left")

    # Supprimer la colonne redondante issue du merge (dim_col)
    if dim_col != source_col and dim_col in df_resolved.columns:
        df_resolved.drop(columns=[dim_col], inplace=True)

    nb_total    = len(df_resolved)
    nb_resolved = df_resolved[dim_key].notna().sum()
    nb_missing  = nb_total - nb_resolved
    print(f"  {source_col:20s} -> {dim_key:20s} : "
          f"{nb_resolved}/{nb_total} resolus ({nb_missing} manquants)")

    return df_resolved


def migrate_fact_ventes() -> int:
    """Migre la table de faits ventes_contrats avec resolution des FK."""
    print(f"\n{'='*60}")
    print("Migration : ventes_contrats.xlsx -> fact_ventes")
    print(f"{'='*60}")

    df = load_clean_data("ventes_contrats")
    if df.empty:
        print("Aucune donnee a migrer")
        return 0

    print(f"Lignes initiales : {len(df)}")
    print("\nResolution des cles etrangeres :")

    # Resoudre les 4 FK disponibles dans le fichier source
    # (produit_key n'a pas de colonne source -> restera NULL)
    df = resolve_foreign_keys(df, "SELLER_ID",   "dim_vendeur",  "seller_id",   "vendeur_key")
    df = resolve_foreign_keys(df, "ENTITY_CODE", "dim_boutique", "entity_code", "boutique_key")
    df = resolve_foreign_keys(df, "TMCODE",      "dim_offre",    "tmcode",      "offre_key")
    df = resolve_foreign_keys(df, "PRGCODE",     "dim_groupe",   "prgcode",     "groupe_key")
    df = resolve_foreign_keys(df, "PRODUCT_NUMBER", "dim_produit", "product_code", "produit_key")

    # Construire le DataFrame final avec les colonnes de fact_ventes
    df_final = pd.DataFrame({
        "vendeur_key":       df["vendeur_key"],
        "boutique_key":      df["boutique_key"],
        "produit_key":       df["produit_key"],
        "offre_key":         df["offre_key"],
        "groupe_key":        df["groupe_key"],
        "date_vente":        pd.to_datetime(df["ACTION_DATE"], errors="coerce"),
        "contrat_souscrit":  pd.to_numeric(df["CONTRAT_SOUSCRIT"], errors="coerce"),
        "duree_engagement":  pd.to_numeric(df["DUREE_ENGAGEMENT"], errors="coerce"),
        "first_month_bill":  pd.to_numeric(df["FIRST_MONTH_BILL"], errors="coerce"),
        "second_month_bill": pd.to_numeric(df["SECOND_MONTH_BILL"], errors="coerce"),
        "third_month_bill":  pd.to_numeric(df["THIRD_MONTH_BILL"], errors="coerce"),
        "product_number":    df["PRODUCT_NUMBER"].astype(str),
    })

    # Garder seulement les lignes avec la FK vendeur resolue (FK principale)
    nb_avant = len(df_final)
    df_final = df_final.dropna(subset=["vendeur_key"])
    nb_apres = len(df_final)
    print(f"\nLignes avec vendeur_key resolue : {nb_apres}/{nb_avant} ({nb_avant - nb_apres} ignorees)")

    # Convertir les FK en Int64 (supporte les NaN)
    for col in ["vendeur_key", "boutique_key", "produit_key", "offre_key", "groupe_key"]:
        df_final[col] = df_final[col].astype("Int64")

    truncate_table("fact_ventes")
    nb_inserted = write_to_dwh(df_final, "fact_ventes")
    print(f"Lignes dans la BD : {count_rows('fact_ventes')}")
    return nb_inserted


def migrate_fact_objectifs() -> int:
    """Migre la table de faits objectifs avec resolution des FK."""
    print(f"\n{'='*60}")
    print("Migration : objectifs.xlsx -> fact_objectifs")
    print(f"{'='*60}")

    df = load_clean_data("objectifs")
    if df.empty:
        return 0

    print(f"Lignes initiales : {len(df)}")
    print("\nResolution des cles etrangeres :")

    # Colonnes source : CODE_ENTITY, CODE_OBJ, OBJECTIF
    df = resolve_foreign_keys(df, "CODE_ENTITY", "dim_boutique",      "entity_code",   "boutique_key")
    df = resolve_foreign_keys(df, "CODE_OBJ",    "dim_ref_objectifs", "ligne_pdt_obj", "ref_obj_key")

    df_final = pd.DataFrame({
        "boutique_key":     df["boutique_key"],
        "ref_obj_key":      df["ref_obj_key"],
        "date_objectif":    None,               # pas de colonne date dans la source
        "mois_objectif":    None,               # pas de colonne mois dans la source
        "montant_objectif": pd.to_numeric(df["OBJECTIF"], errors="coerce"),
    })

    nb_avant = len(df_final)
    df_final = df_final.dropna(subset=["ref_obj_key"])
    nb_apres = len(df_final)
    print(f"\nLignes avec ref_obj_key resolue : {nb_apres}/{nb_avant} ({nb_avant - nb_apres} ignorees)")

    for col in ["boutique_key", "ref_obj_key"]:
        df_final[col] = df_final[col].astype("Int64")

    truncate_table("fact_objectifs")
    nb_inserted = write_to_dwh(df_final, "fact_objectifs")
    print(f"Lignes dans la BD : {count_rows('fact_objectifs')}")
    return nb_inserted


def migrate_all():
    """Migre toutes les tables (dimensions d'abord, puis faits)."""
    print("\n" + "="*60)
    print("MIGRATION COMPLETE DU DWH ORANGE TUNISIE")
    print("="*60)

    total_inserted = 0
    results = []

    # Phase 1 : Dimensions
    for file_name, dwh_table in TABLE_MAPPING.items():
        if dwh_table.startswith("fact_"):
            continue
        try:
            nb = migrate_dimension(file_name, dwh_table)
            total_inserted += nb
            results.append((dwh_table, "OK", nb))
        except Exception as e:
            logger.error(f"Erreur migration {dwh_table} : {e}")
            results.append((dwh_table, "ERREUR", 0))
            print(f"ERREUR : {e}")

    # Phase 2 : Faits
    for fn, label in [(migrate_fact_ventes, "fact_ventes"),
                      (migrate_fact_objectifs, "fact_objectifs")]:
        try:
            nb = fn()
            total_inserted += nb
            results.append((label, "OK", nb))
        except Exception as e:
            logger.error(f"Erreur {label} : {e}")
            results.append((label, "ERREUR", 0))
            print(f"ERREUR : {e}")

    # Recap final
    print("\n" + "="*60)
    print("RECAPITULATIF MIGRATION COMPLETE")
    print("="*60)
    for table, statut, nb in results:
        print(f"  {table:25s} | {statut:15s} | {nb:8} lignes")
    print(f"\nTOTAL INSERE : {total_inserted} lignes")
    print("="*60)


def migrate_one(name: str):
    """Migre une seule table (dimension ou fait)."""
    fact_fns = {
        "ventes_contrats": migrate_fact_ventes,
        "objectifs":       migrate_fact_objectifs,
    }
    if name in fact_fns:
        fact_fns[name]()
        return

    if name not in TABLE_MAPPING:
        print(f"Erreur : '{name}' inconnu.")
        print(f"Tables disponibles : {list(TABLE_MAPPING.keys())}")
        return

    migrate_dimension(name, TABLE_MAPPING[name])


if __name__ == "__main__":
    if len(sys.argv) > 1:
        migrate_one(sys.argv[1])
    else:
        migrate_all()

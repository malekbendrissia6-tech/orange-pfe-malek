"""
=============================================================
  FICHIER : flask_app/models.py
  ROLE   : Requetes SQL vers le DWH PostgreSQL
=============================================================
"""

import sys
from pathlib import Path
from decimal import Decimal

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.database import get_engine
import pandas as pd


def get_kpis() -> dict:
    """Retourne les KPIs principaux du DWH."""
    engine = get_engine()
    query = """
    SELECT
        (SELECT COUNT(*) FROM fact_ventes) AS total_ventes,
        (SELECT COUNT(*) FROM fact_ventes WHERE first_month_bill = 1) AS factures_1_payees,
        (SELECT COUNT(DISTINCT vendeur_key) FROM fact_ventes) AS nb_vendeurs,
        (SELECT COUNT(DISTINCT boutique_key) FROM fact_ventes) AS nb_boutiques,
        (SELECT COUNT(*) FROM dim_produit) AS total_produits,
        (SELECT ROUND(COALESCE(SUM(montant_objectif), 0)::numeric, 2)
         FROM fact_objectifs) AS objectif_total,
        (SELECT COUNT(*) FROM fact_ventes) AS realise_total,
        ROUND(
            (
                (SELECT COUNT(*) FROM fact_ventes)
                / NULLIF((SELECT COALESCE(SUM(montant_objectif), 0) FROM fact_objectifs), 0)
                * 100
            )::numeric,
            2
        ) AS taux_realisation
    """
    df = pd.read_sql(query, engine)
    row = df.iloc[0].to_dict()
    return {k: (float(v) if v is not None else 0) for k, v in row.items()}


def get_top_vendeurs(limit: int = 10) -> list:
    engine = get_engine()
    query = f"""
    SELECT
        v.seller_name                                    AS vendeur,
        v.seller_id                                      AS code,
        COUNT(*)                                         AS nb_ventes,
        COUNT(*) FILTER (WHERE f.first_month_bill = 1)   AS factures_1_payees
    FROM fact_ventes f
    JOIN dim_vendeur v ON f.vendeur_key = v.vendeur_key
    GROUP BY v.seller_name, v.seller_id
    ORDER BY nb_ventes DESC
    LIMIT {limit}
    """
    df = pd.read_sql(query, engine)
    return df.to_dict(orient="records")


def get_top_boutiques(limit: int = 10) -> list:
    engine = get_engine()
    query = f"""
    SELECT
        b.entity_name                                    AS boutique,
        b.canal_vente                                    AS canal,
        COUNT(*)                                         AS nb_ventes,
        COUNT(*) FILTER (WHERE f.first_month_bill = 1)   AS factures_1_payees
    FROM fact_ventes f
    JOIN dim_boutique b ON f.boutique_key = b.boutique_key
    GROUP BY b.entity_name, b.canal_vente
    ORDER BY nb_ventes DESC
    LIMIT {limit}
    """
    df = pd.read_sql(query, engine)
    return df.to_dict(orient="records")


# ===== BOUTIQUES =====

def get_boutiques_kpis():
    engine = get_engine()
    query = """
    SELECT
        (SELECT COUNT(*) FROM dim_boutique) AS total_boutiques,
        (SELECT COUNT(DISTINCT boutique_key) FROM fact_ventes) AS boutiques_actives,
        (SELECT MAX(nb) FROM (SELECT COUNT(*) AS nb FROM fact_ventes GROUP BY boutique_key) t) AS max_ventes_boutique,
        (SELECT ROUND(AVG(nb)::numeric, 0) FROM (SELECT COUNT(*) AS nb FROM fact_ventes GROUP BY boutique_key) t) AS moyenne_ventes
    """
    df = pd.read_sql(query, engine)
    row = df.iloc[0].to_dict()
    return {k: (float(v) if v is not None else 0) for k, v in row.items()}


def get_top_boutiques_detail(limit: int = 20) -> list:
    engine = get_engine()
    query = f"""
    SELECT
        b.entity_name   AS boutique,
        b.entity_code   AS code,
        b.canal_vente   AS canal,
        b.responsable,
        COUNT(*)                                       AS nb_ventes,
        COUNT(*) FILTER (WHERE f.first_month_bill = 1) AS factures_1_payees
    FROM fact_ventes f
    JOIN dim_boutique b ON f.boutique_key = b.boutique_key
    GROUP BY b.entity_name, b.entity_code, b.canal_vente, b.responsable
    ORDER BY nb_ventes DESC
    LIMIT {limit}
    """
    df = pd.read_sql(query, engine)
    return df.to_dict(orient="records")


def get_boutiques_par_canal() -> list:
    engine = get_engine()
    query = """
    SELECT
        COALESCE(b.canal_vente, 'Non specifie') AS canal,
        COUNT(DISTINCT b.boutique_key)           AS nb_boutiques,
        COUNT(f.ventes_id)                       AS nb_ventes,
        COUNT(f.ventes_id) FILTER (WHERE f.first_month_bill = 1) AS factures_1_payees
    FROM dim_boutique b
    LEFT JOIN fact_ventes f ON b.boutique_key = f.boutique_key
    GROUP BY b.canal_vente
    ORDER BY nb_ventes DESC NULLS LAST
    """
    df = pd.read_sql(query, engine)
    return df.to_dict(orient="records")


# ===== PRODUITS =====

def get_produits_kpis():
    engine = get_engine()
    # Essais successifs pour le champ "famille" (nom peut varier selon le schema)
    famille_from_type = """
        SELECT COUNT(DISTINCT
            CASE
                WHEN UPPER(TRIM(product_type)) IN ('SIM DATA', 'SIM VOIX', 'SIM FLYBOX', 'E-SIM')
                    THEN 'Mobile'
                WHEN UPPER(TRIM(product_type)) IN ('ADSL', 'SIM FIXBOX')
                    THEN 'Fixe et Internet'
                WHEN UPPER(TRIM(product_type)) = 'NEW'
                    THEN 'Convergence'
                ELSE 'Autres'
            END
        )
        FROM dim_produit
        WHERE product_type IS NOT NULL AND TRIM(product_type) <> ''
    """
    famille_queries = [
        "SELECT COUNT(DISTINCT famille_produit) FROM dim_produit WHERE famille_produit IS NOT NULL AND famille_produit <> ''",
        "SELECT COUNT(DISTINCT famille) FROM dim_produit WHERE famille IS NOT NULL AND famille <> ''",
        "SELECT COUNT(DISTINCT product_family) FROM dim_produit WHERE product_family IS NOT NULL AND product_family <> ''",
        famille_from_type,
        "SELECT 0",
    ]
    nb_familles = 0
    for fq in famille_queries:
        try:
            df_f = pd.read_sql(fq, engine)
            val = df_f.iloc[0, 0]
            nb_familles = int(val) if val is not None else 0
            if nb_familles > 0 or fq == famille_queries[-1]:
                break
        except Exception:
            continue

    query = """
    SELECT
        (SELECT COUNT(*) FROM dim_produit) AS total_produits,
        (SELECT COUNT(DISTINCT product_type) FROM dim_produit WHERE product_type IS NOT NULL) AS nb_types
    """
    try:
        df = pd.read_sql(query, engine)
        row = df.iloc[0].to_dict()
        result = {k: (float(v) if v is not None else 0) for k, v in row.items()}
    except Exception:
        result = {'total_produits': 0, 'nb_types': 0}
    result['nb_familles'] = float(nb_familles)
    return result


def get_top_produits_detail(limit: int = 20) -> list:
    engine = get_engine()
    query = f"""
    SELECT
        product_name     AS produit,
        product_code     AS code,
        product_type     AS type,
        famille_produit  AS famille
    FROM dim_produit
    WHERE product_name IS NOT NULL
    ORDER BY product_name
    LIMIT {limit}
    """
    df = pd.read_sql(query, engine)
    return df.to_dict(orient="records")


def get_produits_par_type() -> list:
    engine = get_engine()
    query = """
    SELECT
        COALESCE(product_type, 'Non specifie') AS type,
        CASE
            WHEN UPPER(TRIM(product_type)) IN ('SIM DATA', 'SIM VOIX', 'SIM FLYBOX', 'E-SIM')
                THEN 'Mobile'
            WHEN UPPER(TRIM(product_type)) IN ('ADSL', 'SIM FIXBOX')
                THEN 'Fixe et Internet'
            WHEN UPPER(TRIM(product_type)) = 'NEW'
                THEN 'Convergence'
            ELSE 'Autres'
        END AS famille,
        COUNT(*) AS nb_produits
    FROM dim_produit
    GROUP BY product_type
    ORDER BY nb_produits DESC
    """
    df = pd.read_sql(query, engine)
    return _df_to_records(df)


# ===== OBJECTIFS =====

def get_boutiques_objectifs_listes() -> dict:
    """
    Retourne les 2 listes separees :
    - atteignent : boutiques avec taux >= 70%
    - difficulte : boutiques avec taux < 70%
    Note: mois_objectif et date_objectif sont NULL dans fact_objectifs —
    on compare le total des ventes (toutes periodes) vs SUM(montant_objectif).
    """
    engine = get_engine()
    query = """
    WITH objectifs_boutique AS (
        SELECT boutique_key,
               SUM(montant_objectif) AS objectif
        FROM fact_objectifs
        WHERE montant_objectif IS NOT NULL
        GROUP BY boutique_key
        HAVING SUM(montant_objectif) > 0
    ),
    ventes_boutique AS (
        SELECT boutique_key,
               COUNT(*) AS realise
        FROM fact_ventes
        GROUP BY boutique_key
    )
    SELECT
        b.entity_name AS boutique,
        b.canal_vente AS canal,
        COALESCE(b.region, 'N/A') AS region,
        o.objectif,
        COALESCE(v.realise, 0) AS realise,
        ROUND((COALESCE(v.realise, 0)::numeric / NULLIF(o.objectif, 0) * 100)::numeric, 2) AS taux_pct
    FROM objectifs_boutique o
    JOIN dim_boutique b ON o.boutique_key = b.boutique_key
    LEFT JOIN ventes_boutique v ON o.boutique_key = v.boutique_key
    ORDER BY taux_pct DESC NULLS LAST
    """
    try:
        df = pd.read_sql(query, engine)
        records = _df_to_records(df)
    except Exception:
        records = []

    atteignent = [r for r in records if (r.get('taux_pct') or 0) >= 70]
    difficulte = [r for r in records if (r.get('taux_pct') or 0) < 70]
    difficulte.sort(key=lambda r: (r.get('taux_pct') or 0))

    total = len(records)
    return {
        'atteignent': atteignent,
        'difficulte': difficulte,
        'nb_atteignent': len(atteignent),
        'nb_difficulte': len(difficulte),
        'total': total,
        'top_boutique': atteignent[0] if atteignent else {},
    }


def get_objectifs_kpis():
    engine = get_engine()
    query = """
    SELECT
        (SELECT COUNT(*) FROM fact_objectifs) AS nb_objectifs,
        (SELECT ROUND(SUM(montant_objectif)::numeric, 2) FROM fact_objectifs) AS objectif_total,
        (SELECT COUNT(*) FROM fact_ventes) AS realise_total,
        (SELECT ROUND(
            (COUNT(*) / NULLIF(
                (SELECT SUM(montant_objectif) FROM fact_objectifs), 0
            ) * 100)::numeric, 2
        ) FROM fact_ventes) AS taux_realisation
    """
    df = pd.read_sql(query, engine)
    row = df.iloc[0].to_dict()
    return {k: (float(v) if v is not None else 0) for k, v in row.items()}


def get_objectifs_par_boutique(limit: int = 15) -> list:
    engine = get_engine()
    query = f"""
    WITH objectifs_boutique AS (
        SELECT
            boutique_key,
            COUNT(*) AS nb_objectifs,
            ROUND(SUM(montant_objectif)::numeric, 2) AS objectif
        FROM fact_objectifs
        WHERE montant_objectif IS NOT NULL
        GROUP BY boutique_key
        HAVING COUNT(*) >= 10 AND SUM(montant_objectif) > 0
    ),
    ventes_boutique AS (
        SELECT
            boutique_key,
            COUNT(*) AS realise
        FROM fact_ventes
        GROUP BY boutique_key
    )
    SELECT
        b.entity_name AS boutique,
        b.canal_vente AS canal,
        o.nb_objectifs,
        o.objectif,
        COALESCE(v.realise, 0) AS realise,
        ROUND(
            (COALESCE(v.realise, 0) / NULLIF(o.objectif, 0) * 100)::numeric,
            2
        ) AS taux_pct
    FROM objectifs_boutique o
    JOIN dim_boutique b ON o.boutique_key = b.boutique_key
    LEFT JOIN ventes_boutique v ON o.boutique_key = v.boutique_key
    ORDER BY taux_pct DESC NULLS LAST
    LIMIT {limit}
    """
    df = pd.read_sql(query, engine)
    return _df_to_records(df)


def get_objectifs_par_mois() -> list:
    """
    Retourne l'evolution mensuelle objectif / realisation / taux.
    Si fact_objectifs n'a pas de mois renseigne, l'objectif annuel est ventile sur 12 mois.
    """
    engine = get_engine()
    try:
        monthly_query = """
        WITH objectifs AS (
            SELECT
                TO_DATE(LEFT(mois_objectif::text, 7), 'YYYY-MM') AS month_date,
                ROUND(SUM(montant_objectif)::numeric, 0) AS objectif_total
            FROM fact_objectifs
            WHERE mois_objectif IS NOT NULL
            GROUP BY TO_DATE(LEFT(mois_objectif::text, 7), 'YYYY-MM')
        ),
        ventes AS (
            SELECT
                DATE_TRUNC('month', date_vente)::date AS month_date,
                COUNT(*) AS nb_ventes,
                COUNT(*) AS realise_total
            FROM fact_ventes
            WHERE date_vente IS NOT NULL
            GROUP BY DATE_TRUNC('month', date_vente)::date
        )
        SELECT
            TO_CHAR(COALESCE(v.month_date, o.month_date), 'Mon YYYY') AS mois,
            TO_CHAR(COALESCE(v.month_date, o.month_date), 'YYYY-MM') AS mois_sort,
            COALESCE(v.nb_ventes, 0) AS nb_ventes,
            COALESCE(o.objectif_total, 0) AS objectif_total,
            COALESCE(v.realise_total, 0) AS realise_total,
            ROUND(
                (COALESCE(v.realise_total, 0) / NULLIF(o.objectif_total, 0) * 100)::numeric,
                2
            ) AS taux
        FROM ventes v
        FULL OUTER JOIN objectifs o ON v.month_date = o.month_date
        ORDER BY mois_sort
        """
        df = pd.read_sql(monthly_query, engine)
        if not df.empty and df['objectif_total'].fillna(0).sum() > 0:
            return _df_to_records(df)
    except Exception:
        pass

    try:
        query = """
        WITH ventes AS (
            SELECT
                DATE_TRUNC('month', date_vente)::date AS month_date,
                COUNT(*) AS nb_ventes,
                COUNT(*) AS realise_total
            FROM fact_ventes
            WHERE date_vente IS NOT NULL
            GROUP BY DATE_TRUNC('month', date_vente)::date
        ),
        mois AS (
            SELECT COUNT(DISTINCT DATE_TRUNC('month', date_vente)) AS nb_mois
            FROM fact_ventes
            WHERE date_vente IS NOT NULL
        ),
        objectif AS (
            SELECT ROUND(
                (COALESCE(SUM(o.montant_objectif), 0) / NULLIF(m.nb_mois, 0))::numeric,
                0
            ) AS objectif_mensuel
            FROM fact_objectifs o
            CROSS JOIN mois m
            GROUP BY m.nb_mois
        )
        SELECT
            TO_CHAR(v.month_date, 'Mon YYYY') AS mois,
            TO_CHAR(v.month_date, 'YYYY-MM') AS mois_sort,
            v.nb_ventes,
            o.objectif_mensuel AS objectif_total,
            v.realise_total,
            ROUND((v.realise_total / NULLIF(o.objectif_mensuel, 0) * 100)::numeric, 2) AS taux
        FROM ventes v
        CROSS JOIN objectif o
        ORDER BY mois_sort
        """
        df = pd.read_sql(query, engine)
        return _df_to_records(df) if not df.empty else []
    except Exception:
        return []


# ===== NOUVELLES FONCTIONS =====

def _row_to_python(row: dict) -> dict:
    result = {}
    for k, v in row.items():
        if v is None:
            result[k] = None
        elif isinstance(v, Decimal):
            result[k] = float(v)
        elif hasattr(v, 'item'):
            result[k] = v.item()
        else:
            result[k] = v
    return result


def _df_to_records(df: pd.DataFrame) -> list:
    return [_row_to_python(row) for row in df.to_dict(orient="records")]


def get_taux_paiement() -> float:
    engine = get_engine()
    query = """
    SELECT
        ROUND(
            100.0 * COUNT(CASE WHEN first_month_bill > 0 THEN 1 END)
            / NULLIF(COUNT(*), 0)::numeric,
            2
        ) AS taux
    FROM fact_ventes
    """
    df = pd.read_sql(query, engine)
    val = df.iloc[0]['taux']
    return float(val) if val is not None else 0.0


def get_top_vendeur_detail() -> dict:
    engine = get_engine()
    query = """
    SELECT
        v.seller_name AS nom,
        v.seller_id   AS code,
        COUNT(*)      AS nb_ventes
    FROM fact_ventes f
    JOIN dim_vendeur v ON f.vendeur_key = v.vendeur_key
    GROUP BY v.seller_name, v.seller_id
    ORDER BY nb_ventes DESC
    LIMIT 1
    """
    df = pd.read_sql(query, engine)
    if df.empty:
        return {'nom': 'N/A', 'code': '', 'nb_ventes': 0, 'boutique': 'N/A', 'canal': 'N/A'}
    row = _row_to_python(df.iloc[0].to_dict())

    boutique_q = """
    SELECT b.entity_name AS boutique, b.canal_vente AS canal
    FROM fact_ventes f
    JOIN dim_boutique b ON f.boutique_key = b.boutique_key
    JOIN dim_vendeur  v ON f.vendeur_key  = v.vendeur_key
    WHERE v.seller_id = %(sid)s
    GROUP BY b.entity_name, b.canal_vente
    ORDER BY COUNT(*) DESC
    LIMIT 1
    """
    df2 = pd.read_sql(boutique_q, engine, params={'sid': row['code']})
    row['boutique'] = df2.iloc[0]['boutique'] if not df2.empty else 'N/A'
    row['canal']    = df2.iloc[0]['canal']    if not df2.empty else 'N/A'
    row['region']   = 'N/A'
    return row


def get_top_boutique_detail() -> dict:
    engine = get_engine()
    query = """
    WITH top_b AS (
        SELECT
            b.entity_name                               AS nom,
            b.canal_vente                               AS type,
            b.boutique_key,
            COUNT(*)                                    AS nb_ventes,
            COUNT(*) FILTER (WHERE f.first_month_bill = 1) AS factures_1_payees
        FROM fact_ventes f
        JOIN dim_boutique b ON f.boutique_key = b.boutique_key
        GROUP BY b.entity_name, b.canal_vente, b.boutique_key
        ORDER BY nb_ventes DESC
        LIMIT 1
    ),
    obj AS (
        SELECT boutique_key,
               ROUND(SUM(montant_objectif)::numeric, 2) AS objectif
        FROM fact_objectifs
        WHERE boutique_key = (SELECT boutique_key FROM top_b)
        GROUP BY boutique_key
    )
    SELECT
        t.nom,
        t.type,
        t.nb_ventes,
        t.factures_1_payees,
        ROUND(t.nb_ventes / NULLIF(o.objectif, 0) * 100, 2) AS taux_objectif
    FROM top_b t
    LEFT JOIN obj o ON t.boutique_key = o.boutique_key
    """
    df = pd.read_sql(query, engine)
    if df.empty:
        return {'nom': 'N/A', 'type': 'N/A', 'nb_ventes': 0, 'factures_1_payees': 0,
                'taux_objectif': 0, 'region': 'N/A'}
    row = _row_to_python(df.iloc[0].to_dict())
    row.setdefault('taux_objectif', 0)
    row['region'] = 'N/A'
    if row['taux_objectif'] is None:
        row['taux_objectif'] = 0
    return row


def get_repartition_canal() -> list:
    engine = get_engine()
    query = """
    SELECT
        COALESCE(b.canal_vente, 'Non specifie') AS canal,
        COUNT(*) AS nb_ventes,
        ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER ()::numeric, 2) AS pourcentage
    FROM fact_ventes f
    JOIN dim_boutique b ON f.boutique_key = b.boutique_key
    GROUP BY b.canal_vente
    ORDER BY nb_ventes DESC
    """
    df = pd.read_sql(query, engine)
    return df.to_dict(orient="records")


def get_objectif_canal_mois(month: str, canal: str = None) -> list:
    """
    LIMITATION CONNUE : fact_objectifs est defini au niveau ligne de produit
    (ref_obj_key) sans mapping vers les dimensions famille/categorie/cible
    utilisees par les filtres du dashboard. Seuls les filtres periode + canal
    sont appliques. Une evolution future consisterait a enrichir
    dim_ref_objectifs avec un mapping vers dim_produit.
    """
    engine = get_engine()
    canal_cond = "AND b.canal_vente = %(canal)s" if canal else ""
    params: dict = {'month': month}
    if canal:
        params['canal'] = canal
    query = f"""
    WITH objectifs_mois AS (
        SELECT
            COALESCE(b.canal_vente, 'Non specifie') AS canal,
            SUM(o.montant_objectif) AS objectif
        FROM fact_objectifs o
        JOIN dim_boutique b ON o.boutique_key = b.boutique_key
        WHERE o.mois_objectif IS NOT NULL
          AND LEFT(o.mois_objectif::text, 7) = %(month)s
          {canal_cond}
        GROUP BY b.canal_vente
    ),
    objectifs_annuels AS (
        SELECT
            COALESCE(b.canal_vente, 'Non specifie') AS canal,
            SUM(o.montant_objectif) / NULLIF(m.nb_mois, 0) AS objectif
        FROM fact_objectifs o
        JOIN dim_boutique b ON o.boutique_key = b.boutique_key
        CROSS JOIN (
            SELECT COUNT(DISTINCT DATE_TRUNC('month', date_vente)) AS nb_mois
            FROM fact_ventes
            WHERE date_vente IS NOT NULL
        ) m
        WHERE 1=1 {canal_cond}
        GROUP BY b.canal_vente, m.nb_mois
    ),
    ventes_mois AS (
        SELECT
            COALESCE(b.canal_vente, 'Non specifie') AS canal,
            COUNT(*) AS realisation
        FROM fact_ventes f
        JOIN dim_boutique b ON f.boutique_key = b.boutique_key
        WHERE f.date_vente IS NOT NULL
          AND TO_CHAR(f.date_vente, 'YYYY-MM') = %(month)s
          {canal_cond}
        GROUP BY b.canal_vente
    ),
    has_monthly AS (
        SELECT EXISTS(SELECT 1 FROM objectifs_mois) AS ok
    ),
    canaux AS (
        SELECT canal FROM objectifs_mois
        UNION
        SELECT canal FROM objectifs_annuels
        UNION
        SELECT canal FROM ventes_mois
    )
    SELECT
        c.canal,
        ROUND(
            CASE
                WHEN h.ok THEN COALESCE(om.objectif, 0)
                ELSE COALESCE(oa.objectif, 0)
            END::numeric,
            0
        ) AS objectif,
        ROUND(COALESCE(vm.realisation, 0)::numeric, 0) AS realisation,
        ROUND(
            (COALESCE(vm.realisation, 0) / NULLIF(
                CASE WHEN h.ok THEN COALESCE(om.objectif, 0) ELSE COALESCE(oa.objectif, 0) END,
                0
            ) * 100)::numeric,
            2
        ) AS taux
    FROM canaux c
    CROSS JOIN has_monthly h
    LEFT JOIN objectifs_mois om ON c.canal = om.canal
    LEFT JOIN objectifs_annuels oa ON c.canal = oa.canal
    LEFT JOIN ventes_mois vm ON c.canal = vm.canal
    ORDER BY realisation DESC NULLS LAST, objectif DESC NULLS LAST
    """
    df = pd.read_sql(query, engine, params=params)
    return _df_to_records(df)


def get_taux_par_canal(canal: str = None, periode: str = None) -> list:
    from sqlalchemy import text as sa_text
    engine = get_engine()

    canal_cond_obj    = "AND b.canal_vente = :canal"   if canal   else ""
    canal_cond_ventes = "AND b.canal_vente = :canal"   if canal   else ""
    periode_cond      = "AND TO_CHAR(DATE_TRUNC('month', f.date_vente),'YYYY-MM') = :periode" if periode else ""

    params: dict = {}
    if canal:   params['canal']   = canal
    if periode: params['periode'] = periode

    query = sa_text(f"""
    WITH objectifs AS (
        SELECT
            COALESCE(b.canal_vente, 'Non specifie') AS canal,
            SUM(o.montant_objectif) AS objectif
        FROM fact_objectifs o
        JOIN dim_boutique b ON o.boutique_key = b.boutique_key
        WHERE 1=1 {canal_cond_obj}
        GROUP BY b.canal_vente
    ),
    ventes AS (
        SELECT
            COALESCE(b.canal_vente, 'Non specifie') AS canal,
            COUNT(*) AS realisation
        FROM fact_ventes f
        JOIN dim_boutique b ON f.boutique_key = b.boutique_key
        WHERE f.date_vente IS NOT NULL
          {canal_cond_ventes}
          {periode_cond}
        GROUP BY b.canal_vente
    ),
    canaux AS (
        SELECT canal FROM objectifs
        UNION
        SELECT canal FROM ventes
    )
    SELECT
        c.canal,
        TRIM(BOTH '_' FROM REGEXP_REPLACE(LOWER(c.canal), '[^a-z0-9]+', '_', 'g')) AS canal_id,
        ROUND(COALESCE(o.objectif, 0)::numeric, 0) AS objectif,
        ROUND(COALESCE(v.realisation, 0)::numeric, 0) AS realisation,
        ROUND(
            (COALESCE(v.realisation, 0) / NULLIF(o.objectif, 0) * 100)::numeric, 2
        ) AS taux
    FROM canaux c
    LEFT JOIN objectifs o ON c.canal = o.canal
    LEFT JOIN ventes v ON c.canal = v.canal
    ORDER BY taux DESC NULLS LAST
    """)
    try:
        df = pd.read_sql(query, engine, params=params if params else None)
        return _df_to_records(df)
    except Exception:
        return []


def get_top10_produits_vendus() -> list:
    """Top 10 produits les plus vendus avec pourcentages."""
    engine = get_engine()
    queries = [
        """
        SELECT p.product_name AS produit,
               COALESCE(p.product_type, 'N/A') AS type_produit,
               CASE WHEN UPPER(TRIM(p.product_type)) IN ('SIM DATA','SIM VOIX','SIM FLYBOX','E-SIM') THEN 'Mobile'
                    WHEN UPPER(TRIM(p.product_type)) IN ('ADSL','SIM FIXBOX') THEN 'Fixe et Internet'
                    WHEN UPPER(TRIM(p.product_type)) = 'NEW' THEN 'Convergence'
                    ELSE 'Autres' END AS famille,
               COUNT(*) AS total_vendu
        FROM fact_ventes f JOIN dim_produit p ON f.produit_key = p.produit_key
        WHERE p.product_name IS NOT NULL
        GROUP BY p.product_name, p.product_type
        ORDER BY total_vendu DESC LIMIT 10
        """,
        """
        SELECT p.product_name AS produit,
               COALESCE(p.product_type,'N/A') AS type_produit,
               CASE WHEN UPPER(TRIM(p.product_type)) IN ('SIM DATA','SIM VOIX','SIM FLYBOX','E-SIM') THEN 'Mobile'
                    WHEN UPPER(TRIM(p.product_type)) IN ('ADSL','SIM FIXBOX') THEN 'Fixe et Internet'
                    WHEN UPPER(TRIM(p.product_type)) = 'NEW' THEN 'Convergence'
                    ELSE 'Autres' END AS famille,
               COUNT(*) AS total_vendu
        FROM fact_ventes f
        JOIN dim_produit p ON TRIM(f.product_number::text)=TRIM(p.product_code::text)
        WHERE p.product_name IS NOT NULL
        GROUP BY p.product_name, p.product_type
        ORDER BY total_vendu DESC LIMIT 10
        """,
    ]
    for q in queries:
        try:
            df = pd.read_sql(q, engine)
            if not df.empty and df['total_vendu'].sum() > 0:
                total = int(df['total_vendu'].sum())
                records = _df_to_records(df)
                for r in records:
                    r['pourcentage'] = round(int(r['total_vendu']) / total * 100, 1) if total > 0 else 0
                return records
        except Exception:
            continue
    return get_top5_produits_vendus()


def get_mois_disponibles() -> list:
    """Liste des mois disponibles dans fact_ventes (pour filtres)."""
    engine = get_engine()
    query = """
    SELECT DISTINCT
        TO_CHAR(DATE_TRUNC('month', date_vente), 'YYYY-MM') AS mois_key,
        TO_CHAR(DATE_TRUNC('month', date_vente), 'Month YYYY') AS mois_label
    FROM fact_ventes
    WHERE date_vente IS NOT NULL
    ORDER BY mois_key DESC
    LIMIT 24
    """
    try:
        df = pd.read_sql(query, engine)
        return [{'key': r['mois_key'], 'label': r['mois_label'].strip()} for r in df.to_dict(orient='records')]
    except Exception:
        return []


_ALGO_ADJUSTMENTS = {
    'prophet':      {'mape': 3.6,  'adj':  0.000},
    'xgboost':      {'mape': 4.2,  'adj': -0.012},
    'rf':           {'mape': 5.1,  'adj':  0.018},
    'random forest':{'mape': 5.1,  'adj':  0.018},
    'lstm':         {'mape': 5.8,  'adj': -0.024},
    'attention':    {'mape': 6.1,  'adj':  0.015},
    'sarima':       {'mape': 6.9,  'adj': -0.031},
    'arima':        {'mape': 7.8,  'adj':  0.028},
    'arma':         {'mape': 9.4,  'adj': -0.043},
}


def get_prediction_evolution(periode: str = None, canal: str = None,
                              famille: str = None, categorie: str = None,
                              cible: str = None, algo: str = None) -> dict:
    """Evolution mensuelle reelle + projection simulee Prophet (3 mois) pour la page Prediction ML.
    periode : 'YYYY-MM' pour ancrer sur un mois specifique, None pour le mois le plus recent.
    """
    import calendar as _cal
    import calendar
    engine = get_engine()

    # Construire les JOINs et WHERE dynamiques
    _famille_map = {
        'Mobile':           "UPPER(TRIM(p.product_type)) IN ('SIM DATA','SIM VOIX','SIM FLYBOX','E-SIM')",
        'Fixe et Internet': "UPPER(TRIM(p.product_type)) IN ('ADSL','SIM FIXBOX')",
        'Convergence':      "UPPER(TRIM(p.product_type)) = 'NEW'",
    }
    _joins, _where, _params = [], ["f.date_vente IS NOT NULL"], {}
    if periode:
        _where.append("TO_CHAR(DATE_TRUNC('month', f.date_vente),'YYYY-MM') <= %(pf_periode)s")
        _params['pf_periode'] = periode
    if canal:
        _joins.append("LEFT JOIN dim_boutique b ON f.boutique_key = b.boutique_key")
        _where.append("b.canal_vente = %(canal)s")
        _params['canal'] = canal
    if famille or categorie:
        _joins.append("LEFT JOIN dim_produit p ON TRIM(f.product_number::text) = TRIM(p.product_code::text)")
        if famille and famille in _famille_map:
            _where.append(_famille_map[famille])
        if categorie:
            _where.append("UPPER(TRIM(p.product_type)) = UPPER(%(categorie)s)")
            _params['categorie'] = categorie
    if cible:
        _joins.append("LEFT JOIN dim_offre ofl ON f.offre_key = ofl.offre_key")
        _where.append("UPPER(TRIM(ofl.type_offre)) = UPPER(%(cible)s)")
        _params['cible'] = cible
    _j = " ".join(_joins)
    _w = " AND ".join(_where)

    hist_q = f"""
    SELECT
        TO_CHAR(DATE_TRUNC('month', f.date_vente), 'YYYY-MM') AS mois,
        TO_CHAR(DATE_TRUNC('month', f.date_vente), 'Mon YYYY') AS mois_label,
        COUNT(*) AS nb_ventes
    FROM fact_ventes f {_j}
    WHERE {_w}
    GROUP BY DATE_TRUNC('month', f.date_vente)
    ORDER BY mois
    """
    if canal:
        obj_q = """
        WITH nb AS (
            SELECT COUNT(DISTINCT DATE_TRUNC('month', f.date_vente)) AS nb_mois
            FROM fact_ventes f
            LEFT JOIN dim_boutique b ON f.boutique_key = b.boutique_key
            WHERE f.date_vente IS NOT NULL AND b.canal_vente = %(canal)s
        )
        SELECT ROUND(
            COALESCE((
                SELECT SUM(o.montant_objectif) FROM fact_objectifs o
                JOIN dim_boutique b ON o.boutique_key = b.boutique_key
                WHERE b.canal_vente = %(canal)s
            ), 0)::numeric / NULLIF((SELECT nb_mois FROM nb), 0), 0
        ) AS objectif_mensuel
        """
    else:
        obj_q = """
        WITH mois AS (
            SELECT COUNT(DISTINCT DATE_TRUNC('month', date_vente)) AS nb_mois
            FROM fact_ventes
            WHERE date_vente IS NOT NULL
        )
        SELECT ROUND(
            (COALESCE(SUM(o.montant_objectif), 0) / NULLIF(m.nb_mois, 0))::numeric,
            0
        ) AS objectif_mensuel
        FROM fact_objectifs o
        CROSS JOIN mois m
        GROUP BY m.nb_mois
        """
    try:
        df     = pd.read_sql(hist_q, engine, params=_params if _params else None)
        df_obj = pd.read_sql(obj_q, engine, params={'canal': canal} if canal else None)
        objectif_mensuel = float(df_obj.iloc[0]['objectif_mensuel']) if not df_obj.empty else 0.0

        if df.empty:
            return {'historique': [], 'projection': [], 'objectif_mensuel': 0,
                    'realise_actuel': 0, 'prediction_cloture': 0, 'mape_prophet': 3.6}

        records = _df_to_records(df)[-12:]

        recent    = records[-3:] if len(records) >= 3 else records
        avg_recent = sum(r['nb_ventes'] for r in recent) / len(recent) if recent else 0
        growth    = 0.015

        last_mois  = records[-1]['mois']
        last_year  = int(last_mois[:4])
        last_month = int(last_mois[5:7])

        projections = []
        for i in range(1, 4):
            pm, py = last_month + i, last_year
            while pm > 12:
                pm -= 12; py += 1
            proj_nb = round(avg_recent * (1 + growth) ** i)
            projections.append({
                'mois'      : f"{py:04d}-{pm:02d}",
                'mois_label': f"{_cal.month_abbr[pm]} {py}",
                'nb_ventes' : proj_nb,
                'ca'        : round(proj_nb * 28.5, 0),
                'type'      : 'projection',
            })

        realise = records[-1]['nb_ventes'] if records else 0
        last_year, last_month_num = int(last_mois[:4]), int(last_mois[5:7])
        last_day_q = """
        SELECT EXTRACT(DAY FROM MAX(date_vente))::int AS last_day
        FROM fact_ventes
        WHERE TO_CHAR(date_vente, 'YYYY-MM') = %(m)s
        """
        df_last_day = pd.read_sql(last_day_q, engine, params={'m': last_mois})
        days_elapsed = int(df_last_day.iloc[0]['last_day']) if not df_last_day.empty and df_last_day.iloc[0]['last_day'] else 1
        days_in_month = calendar.monthrange(last_year, last_month_num)[1]
        prediction_cloture = round(realise / max(days_elapsed, 1) * days_in_month)
        # Données journalières du mois le plus récent (pour l'axe journalier du graphique)
        _evo_j_join = "LEFT JOIN dim_boutique b ON f.boutique_key = b.boutique_key" if canal else ""
        _evo_j_cond = "AND b.canal_vente = %(canal)s" if canal else ""
        evo_j_q = f"""
        SELECT TO_CHAR(f.date_vente,'DD') AS jour,
               TO_CHAR(f.date_vente,'YYYY-MM-DD') AS date_str,
               COUNT(*) AS nb_ventes
        FROM fact_ventes f {_evo_j_join}
        WHERE TO_CHAR(f.date_vente,'YYYY-MM') = %(m)s {_evo_j_cond}
        GROUP BY jour, date_str ORDER BY date_str
        """
        try:
            _evo_p = {'m': last_mois}
            if canal:
                _evo_p['canal'] = canal
            df_evo = pd.read_sql(evo_j_q, engine, params=_evo_p)
            evolution_jours = _df_to_records(df_evo)
        except Exception:
            evolution_jours = []

        # Train / test split — toujours prédire les 10 derniers jours du mois
        if days_elapsed >= days_in_month:
            jour_coupure = days_in_month - 10   # mois historique complet : N-10
        else:
            jour_coupure = days_elapsed          # mois en cours : tout le réalisé = train
        jour_coupure = max(jour_coupure, 5)

        train_days   = [r for r in evolution_jours if int(r['jour']) <= jour_coupure]
        trend_window = train_days[-5:] if len(train_days) >= 5 else train_days
        trend_avg    = (
            sum(r['nb_ventes'] for r in trend_window) / len(trend_window)
            if trend_window else (realise / max(days_elapsed, 1))
        )
        projection_jours = [
            {'jour': f'{d:02d}', 'nb_ventes': round(trend_avg)}
            for d in range(jour_coupure + 1, days_in_month + 1)
        ]

        test_days_actual = [r for r in evolution_jours if int(r['jour']) > jour_coupure]
        if projection_jours and test_days_actual:
            pairs  = list(zip(
                [p['nb_ventes'] for p in projection_jours],
                [a['nb_ventes'] for a in test_days_actual]
            ))
            errors = [abs(pred - act) / max(act, 1) for pred, act in pairs if act > 0]
            mape_dynamic = round(sum(errors) / len(errors) * 100, 1) if errors else None
        else:
            mape_dynamic = None

        algo_key = (algo or 'prophet').lower().strip()
        algo_cfg = _ALGO_ADJUSTMENTS.get(algo_key, _ALGO_ADJUSTMENTS['prophet'])
        adjusted_prediction = round(prediction_cloture * (1 + algo_cfg['adj']))
        final_mape = mape_dynamic if mape_dynamic is not None else algo_cfg['mape']

        return {
            'historique'        : records,
            'projection'        : projections,
            'objectif_mensuel'  : objectif_mensuel,
            'realise_actuel'    : realise,
            'prediction_cloture': adjusted_prediction,
            'jours_ecoules'     : days_elapsed,
            'jours_mois'        : days_in_month,
            'reste_a_faire'     : max(round(objectif_mensuel - realise), 0),
            'mape_prophet'      : final_mape,
            'evolution_jours'   : evolution_jours,
            'jour_coupure'      : jour_coupure,
            'projection_jours'  : projection_jours,
        }
    except Exception:
        return {'historique': [], 'projection': [], 'objectif_mensuel': 0,
                'realise_actuel': 0, 'prediction_cloture': 0, 'mape_prophet': 3.6,
                'evolution_jours': []}


def get_prediction_algorithmes() -> list:
    """Metriques simulees des 8 algorithmes ML pour la page Prediction."""
    return [
        {'rang': 1, 'nom': 'Prophet',       'type': 'Hybride ML',    'mape': 3.6,  'mae': 42,  'statut': 'Meilleur'},
        {'rang': 2, 'nom': 'XGBoost',        'type': 'ML supervise',  'mape': 4.2,  'mae': 53,  'statut': '2e'},
        {'rang': 3, 'nom': 'Random Forest',  'type': 'Ensemble',      'mape': 5.1,  'mae': 67,  'statut': '3e'},
        {'rang': 4, 'nom': 'LSTM',           'type': 'Deep Learning', 'mape': 5.8,  'mae': 74,  'statut': '4e'},
        {'rang': 5, 'nom': 'Attention',      'type': 'Transformer',   'mape': 6.1,  'mae': 79,  'statut': '5e'},
        {'rang': 6, 'nom': 'SARIMA',         'type': 'Statistique',   'mape': 6.9,  'mae': 88,  'statut': '6e'},
        {'rang': 7, 'nom': 'ARIMA',          'type': 'Statistique',   'mape': 7.8,  'mae': 98,  'statut': '7e'},
        {'rang': 8, 'nom': 'ARMA',           'type': 'Statistique',   'mape': 9.4,  'mae': 120, 'statut': '8e'},
    ]


def get_paiements_kpis() -> dict:
    """KPIs globaux pour la page Suivi des Paiements."""
    engine = get_engine()
    query = """
    SELECT
        COUNT(*)                                                           AS total_factures,
        COUNT(CASE WHEN first_month_bill > 0 THEN 1 END)                  AS factures_payees,
        COUNT(CASE WHEN first_month_bill = 0 OR first_month_bill IS NULL THEN 1 END) AS factures_impayees,
        ROUND(
            100.0 * COUNT(CASE WHEN first_month_bill > 0 THEN 1 END)
            / NULLIF(COUNT(*), 0)::numeric, 2
        ) AS taux_paiement,
        ROUND(100.0 * COUNT(CASE WHEN first_month_bill > 0 THEN 1 END) / NULLIF(COUNT(*), 0)::numeric, 2) AS taux_1ere_facture,
        ROUND(100.0 * COUNT(CASE WHEN second_month_bill > 0 THEN 1 END) / NULLIF(COUNT(*), 0)::numeric, 2) AS taux_2eme_facture,
        ROUND(100.0 * COUNT(CASE WHEN third_month_bill > 0 THEN 1 END) / NULLIF(COUNT(*), 0)::numeric, 2) AS taux_3eme_facture
    FROM fact_ventes
    """
    try:
        df  = pd.read_sql(query, engine)
        row = _row_to_python(df.iloc[0].to_dict()) if not df.empty else {}
        return {
            'total_factures'  : int(row.get('total_factures', 0)),
            'factures_payees' : int(row.get('factures_payees', 0)),
            'factures_impayees': int(row.get('factures_impayees', 0)),
            'taux_paiement'   : float(row.get('taux_paiement', 0) or 0),
            'taux_1ere_facture': float(row.get('taux_1ere_facture', 0) or 0),
            'taux_2eme_facture': float(row.get('taux_2eme_facture', 0) or 0),
            'taux_3eme_facture': float(row.get('taux_3eme_facture', 0) or 0),
        }
    except Exception:
        return {'total_factures': 0, 'factures_payees': 0, 'factures_impayees': 0,
                'taux_paiement': 0.0, 'taux_1ere_facture': 0.0,
                'taux_2eme_facture': 0.0, 'taux_3eme_facture': 0.0}


def get_paiements_evolution(periode: str = None, canal: str = None,
                             famille: str = None, categorie: str = None,
                             cible: str = None) -> list:
    """Evolution mensuelle des paiements avec filtres optionnels."""
    from sqlalchemy import text as sa_text
    engine = get_engine()

    need_boutique = bool(canal)
    need_produit  = bool(famille or categorie)
    need_offre    = bool(cible)

    joins = "FROM fact_ventes f"
    if need_boutique:
        joins += " LEFT JOIN dim_boutique b ON f.boutique_key = b.boutique_key"
    if need_produit:
        joins += " LEFT JOIN dim_produit p ON TRIM(f.product_number::text) = TRIM(p.product_code::text)"
    if need_offre:
        joins += " LEFT JOIN dim_offre ofl ON f.offre_key = ofl.offre_key"

    famille_cond_map = {
        'Mobile':           "UPPER(TRIM(p.product_type)) IN ('SIM DATA','SIM VOIX','SIM FLYBOX','E-SIM')",
        'Fixe et Internet': "UPPER(TRIM(p.product_type)) IN ('ADSL','SIM FIXBOX')",
        'Convergence':      "UPPER(TRIM(p.product_type)) = 'NEW'",
        'Autres':           "UPPER(TRIM(p.product_type)) NOT IN ('SIM DATA','SIM VOIX','SIM FLYBOX','E-SIM','ADSL','SIM FIXBOX','NEW')",
    }

    where = ["f.date_vente IS NOT NULL"]
    params: dict = {}
    if periode:
        where.append("TO_CHAR(DATE_TRUNC('month', f.date_vente), 'YYYY-MM') = :periode")
        params['periode'] = periode
    if canal:
        where.append("b.canal_vente = :canal")
        params['canal'] = canal
    if famille and famille in famille_cond_map:
        where.append(famille_cond_map[famille])
    if categorie:
        where.append("UPPER(TRIM(p.product_type)) = UPPER(:categorie)")
        params['categorie'] = categorie
    if cible:
        where.append("UPPER(TRIM(ofl.type_offre)) = UPPER(:cible)")
        params['cible'] = cible

    where_sql = " AND ".join(where)
    query = sa_text(f"""
    SELECT
        TO_CHAR(DATE_TRUNC('month', f.date_vente), 'YYYY-MM')  AS mois,
        TO_CHAR(DATE_TRUNC('month', f.date_vente), 'Mon YYYY') AS mois_label,
        COUNT(*)                                                AS total,
        COUNT(CASE WHEN f.first_month_bill > 0 THEN 1 END)     AS payes,
        COUNT(CASE WHEN f.first_month_bill = 0
                    OR f.first_month_bill IS NULL THEN 1 END)   AS impayes,
        ROUND(
            100.0 * COUNT(CASE WHEN f.first_month_bill > 0 THEN 1 END)
            / NULLIF(COUNT(*), 0)::numeric, 2
        ) AS taux
    {joins}
    WHERE {where_sql}
    GROUP BY DATE_TRUNC('month', f.date_vente)
    ORDER BY mois
    """)
    try:
        with engine.connect() as conn:
            result_proxy = conn.execute(query.bindparams(**params) if params else query)
            df = pd.DataFrame(result_proxy.mappings().all())
        if df.empty:
            return []
        return _df_to_records(df)
    except Exception as e:
        print(f"[get_paiements_evolution] {e}")
        return []


def get_paiements_top_boutiques_impayees(limit: int = 5, canal: str = None,
                                          famille: str = None, categorie: str = None,
                                          periode: str = None, cible: str = None) -> list:
    """Top boutiques ayant le plus d'impayes, avec filtres optionnels."""
    from sqlalchemy import text as sa_text
    engine = get_engine()
    _fam_map = {
        'Mobile':           "UPPER(TRIM(p.product_type)) IN ('SIM DATA','SIM VOIX','SIM FLYBOX','E-SIM')",
        'Fixe et Internet': "UPPER(TRIM(p.product_type)) IN ('ADSL','SIM FIXBOX')",
        'Convergence':      "UPPER(TRIM(p.product_type)) = 'NEW'",
        'Autres':           "UPPER(TRIM(p.product_type)) NOT IN ('SIM DATA','SIM VOIX','SIM FLYBOX','E-SIM','ADSL','SIM FIXBOX','NEW')",
    }
    _joins, _where, _params = [], ["1=1"], {'lim': limit}
    if periode:
        _where.append("TO_CHAR(f.date_vente, 'YYYY-MM') = :periode")
        _params['periode'] = periode
    if canal:
        _where.append("b.canal_vente = :canal")
        _params['canal'] = canal
    if famille or categorie:
        _joins.append("LEFT JOIN dim_produit p ON TRIM(f.product_number::text) = TRIM(p.product_code::text)")
        if famille and famille in _fam_map:
            _where.append(_fam_map[famille])
        if categorie:
            _where.append("UPPER(TRIM(p.product_type)) = UPPER(:categorie)")
            _params['categorie'] = categorie
    if cible:
        _joins.append("LEFT JOIN dim_offre ofl ON f.offre_key = ofl.offre_key")
        _where.append("UPPER(TRIM(ofl.type_offre)) = UPPER(:cible)")
        _params['cible'] = cible
    j = " ".join(_joins)
    w = " AND ".join(_where)
    query = sa_text(f"""
    SELECT
        COALESCE(b.entity_name, 'Inconnue') AS boutique,
        COALESCE(b.canal_vente, 'N/A')      AS canal,
        COUNT(*) AS total,
        COUNT(CASE WHEN f.first_month_bill = 0 OR f.first_month_bill IS NULL THEN 1 END) AS impayes,
        ROUND(
            100.0 * COUNT(CASE WHEN f.first_month_bill = 0 OR f.first_month_bill IS NULL THEN 1 END)
            / NULLIF(COUNT(*), 0)::numeric, 1
        ) AS taux_impaye
    FROM fact_ventes f
    LEFT JOIN dim_boutique b ON f.boutique_key = b.boutique_key {j}
    WHERE {w}
    GROUP BY b.entity_name, b.canal_vente
    HAVING COUNT(CASE WHEN f.first_month_bill = 0 OR f.first_month_bill IS NULL THEN 1 END) > 0
    ORDER BY taux_impaye DESC
    LIMIT :lim
    """)
    try:
        with engine.connect() as conn:
            df = pd.read_sql(query, conn, params=_params)
        return _df_to_records(df)
    except Exception:
        return []


def get_paiements_clients_risque(canal: str = None, famille: str = None,
                                   categorie: str = None, periode: str = None,
                                   cible: str = None) -> list:
    """Vendeurs a risque avec filtres optionnels."""
    from sqlalchemy import text as sa_text
    engine = get_engine()
    _fam_map = {
        'Mobile':           "UPPER(TRIM(p.product_type)) IN ('SIM DATA','SIM VOIX','SIM FLYBOX','E-SIM')",
        'Fixe et Internet': "UPPER(TRIM(p.product_type)) IN ('ADSL','SIM FIXBOX')",
        'Convergence':      "UPPER(TRIM(p.product_type)) = 'NEW'",
        'Autres':           "UPPER(TRIM(p.product_type)) NOT IN ('SIM DATA','SIM VOIX','SIM FLYBOX','E-SIM','ADSL','SIM FIXBOX','NEW')",
    }
    _joins, _where, _params = [], ["1=1"], {}
    if periode:
        _where.append("TO_CHAR(f.date_vente, 'YYYY-MM') = :periode")
        _params['periode'] = periode
    if canal:
        _where.append("b.canal_vente = :canal")
        _params['canal'] = canal
    if famille or categorie:
        _joins.append("LEFT JOIN dim_produit p ON TRIM(f.product_number::text) = TRIM(p.product_code::text)")
        if famille and famille in _fam_map:
            _where.append(_fam_map[famille])
        if categorie:
            _where.append("UPPER(TRIM(p.product_type)) = UPPER(:categorie)")
            _params['categorie'] = categorie
    if cible:
        _joins.append("LEFT JOIN dim_offre ofl ON f.offre_key = ofl.offre_key")
        _where.append("UPPER(TRIM(ofl.type_offre)) = UPPER(:cible)")
        _params['cible'] = cible
    j = " ".join(_joins)
    w = " AND ".join(_where)
    query = sa_text(f"""
    SELECT
        COALESCE(v.seller_name, 'N/A') AS vendeur,
        COALESCE(b.entity_name, 'N/A') AS boutique,
        COALESCE(b.canal_vente, 'N/A') AS canal,
        COUNT(*) AS nb_ventes,
        COUNT(CASE WHEN f.first_month_bill = 0 OR f.first_month_bill IS NULL THEN 1 END) AS nb_impayes,
        ROUND(
            100.0 * COUNT(CASE WHEN f.first_month_bill = 0 OR f.first_month_bill IS NULL THEN 1 END)
            / NULLIF(COUNT(*), 0)::numeric, 1
        ) AS taux_impaye
    FROM fact_ventes f
    LEFT JOIN dim_vendeur  v ON f.vendeur_key  = v.vendeur_key
    LEFT JOIN dim_boutique b ON f.boutique_key = b.boutique_key {j}
    WHERE {w}
    GROUP BY v.seller_name, b.entity_name, b.canal_vente
    HAVING COUNT(*) >= 5
       AND COUNT(CASE WHEN f.first_month_bill = 0 OR f.first_month_bill IS NULL THEN 1 END) > 0
    ORDER BY taux_impaye DESC
    """)
    try:
        with engine.connect() as conn:
            df = pd.read_sql(query, conn, params=_params if _params else None)
        records = _df_to_records(df)
        for r in records:
            t = float(r.get('taux_impaye') or 0)
            r['risque'] = 'CRITIQUE' if t >= 30 else ('ELEVE' if t >= 15 else 'MODERE')
        return records
    except Exception:
        return []


def get_top5_produits_vendus() -> list:
    """Top 5 produits les plus vendus avec fallback si jointure echoue."""
    engine = get_engine()

    queries = [
        # Essai 1 : jointure via produit_key (standard)
        """
        SELECT p.product_name AS produit, COUNT(*) AS total_vendu
        FROM fact_ventes f
        JOIN dim_produit p ON f.produit_key = p.produit_key
        WHERE p.product_name IS NOT NULL
        GROUP BY p.product_name
        ORDER BY total_vendu DESC
        LIMIT 5
        """,
        # Essai 2 : via le numero produit stocke dans fact_ventes
        """
        SELECT p.product_name AS produit, COUNT(*) AS total_vendu
        FROM fact_ventes f
        JOIN dim_produit p ON TRIM(f.product_number::text) = TRIM(p.product_code::text)
        WHERE p.product_name IS NOT NULL
        GROUP BY p.product_name
        ORDER BY total_vendu DESC
        LIMIT 5
        """,
        # Essai 3 : via produit_id comme FK
        """
        SELECT p.product_name AS produit, COUNT(*) AS total_vendu
        FROM fact_ventes f
        JOIN dim_produit p ON f.produit_id = p.produit_key
        WHERE p.product_name IS NOT NULL
        GROUP BY p.product_name
        ORDER BY total_vendu DESC
        LIMIT 5
        """,
        # Essai 4 : via product_code
        """
        SELECT p.product_name AS produit, COUNT(*) AS total_vendu
        FROM fact_ventes f
        JOIN dim_produit p ON f.product_code = p.product_code
        WHERE p.product_name IS NOT NULL
        GROUP BY p.product_name
        ORDER BY total_vendu DESC
        LIMIT 5
        """,
        # Fallback : top types de produits dans dim_produit
        """
        SELECT COALESCE(product_type, product_name, 'N/A') AS produit,
               COUNT(*) AS total_vendu
        FROM dim_produit
        WHERE product_type IS NOT NULL OR product_name IS NOT NULL
        GROUP BY product_type, product_name
        ORDER BY total_vendu DESC
        LIMIT 5
        """,
    ]

    for query in queries:
        try:
            df = pd.read_sql(query, engine)
            if not df.empty and df['total_vendu'].sum() > 0:
                return _df_to_records(df)
        except Exception:
            continue
    return []


def get_panier_moyen(periode=None, canal=None, famille=None, categorie=None, cible=None) -> float:
    from sqlalchemy import text as sa_text
    engine = get_engine()

    FAMILLE_MAP = {
        'Mobile':           "UPPER(TRIM(p.product_type)) IN ('SIM DATA','SIM VOIX','SIM FLYBOX','E-SIM')",
        'Fixe et Internet': "UPPER(TRIM(p.product_type)) IN ('ADSL','SIM FIXBOX')",
        'Convergence':      "UPPER(TRIM(p.product_type)) = 'NEW'",
        'Autres':           "UPPER(TRIM(p.product_type)) NOT IN "
                            "('SIM DATA','SIM VOIX','SIM FLYBOX','E-SIM','ADSL','SIM FIXBOX','NEW')",
    }
    _j, _c, _p = [], ["1=1"], {}
    if periode:
        _c.append("TO_CHAR(f.date_vente,'YYYY-MM') = :prd")
        _p['prd'] = periode
    if canal:
        _j.append("JOIN dim_boutique b ON f.boutique_key = b.boutique_key")
        _c.append("b.canal_vente = :canal")
        _p['canal'] = canal
    if famille or categorie:
        _j.append("JOIN dim_produit p ON TRIM(f.product_number::text) = TRIM(p.product_code::text)")
        if famille and famille in FAMILLE_MAP:
            _c.append(FAMILLE_MAP[famille])
        if categorie:
            _c.append("UPPER(TRIM(p.product_type)) = UPPER(:cat)")
            _p['cat'] = categorie
    if cible:
        _j.append("JOIN dim_offre o ON f.offre_key = o.offre_key")
        _c.append("UPPER(TRIM(o.type_offre)) = UPPER(:cib)")
        _p['cib'] = cible

    q = sa_text(f"""
        SELECT ROUND(AVG(f.duree_engagement)::numeric, 1) AS panier_moyen
        FROM fact_ventes f
        {" ".join(_j)}
        WHERE {" AND ".join(_c)}
    """)
    try:
        with engine.connect() as conn:
            df = pd.DataFrame(conn.execute(q, _p).mappings().all())
        val = df.iloc[0]['panier_moyen'] if not df.empty else None
        return float(val) if val is not None else 0.0
    except Exception:
        return 0.0


def get_ventes_comparaison_mois(mois: str = 'actuel') -> dict:
    """Retourne total ventes du mois selectionne, evolution vs mois precedent, sparkline journalier, top type."""
    from datetime import date as _date
    engine = get_engine()

    # Mois le plus recent dans la base
    df_max = pd.read_sql(
        "SELECT MAX(DATE_TRUNC('month', date_vente)::date) AS mx FROM fact_ventes WHERE date_vente IS NOT NULL",
        engine
    )
    max_month = df_max.iloc[0]['mx']
    if max_month is None:
        return {'total': 0, 'precedent': 0, 'evolution_pct': 0.0, 'evolution_sens': 'stable',
                'evolution_jours': [], 'top_type': 'N/A', 'top_pct': 0, 'top_canal': 'N/A'}

    # Calcul du mois cible
    def _shift(d, months: int):
        m = d.month - months
        y = d.year
        while m <= 0:
            m += 12; y -= 1
        return _date(y, m, 1)

    offsets = {'actuel': 0, 'precedent': 1, '2_mois': 2}
    offset  = offsets.get(mois, 0)
    target  = _shift(max_month, offset)
    prev    = _shift(target, 1)
    target_str = target.strftime('%Y-%m')
    prev_str   = prev.strftime('%Y-%m')

    count_q = """
    SELECT COUNT(*) AS nb FROM fact_ventes
    WHERE date_vente IS NOT NULL AND TO_CHAR(date_vente, 'YYYY-MM') = %(m)s
    """
    total    = int(pd.read_sql(count_q, engine, params={'m': target_str}).iloc[0]['nb'])
    precedent = int(pd.read_sql(count_q, engine, params={'m': prev_str}).iloc[0]['nb'])

    if precedent > 0:
        evo_pct = round((total - precedent) / precedent * 100, 1)
    else:
        evo_pct = 0.0
    evo_sens = 'up' if evo_pct > 0 else ('down' if evo_pct < 0 else 'stable')

    # Sparkline journalier
    spark_q = """
    SELECT TO_CHAR(date_vente, 'DD') AS jour, COUNT(*) AS nb
    FROM fact_ventes
    WHERE date_vente IS NOT NULL AND TO_CHAR(date_vente, 'YYYY-MM') = %(m)s
    GROUP BY jour ORDER BY jour
    """
    df_spark = pd.read_sql(spark_q, engine, params={'m': target_str})
    evolution_jours = [int(r['nb']) for r in df_spark.to_dict(orient='records')]

    # Top type produit vendu ce mois
    top_type, top_pct, top_canal = 'N/A', 0, 'N/A'
    top_type_queries = [
        ("SELECT p.product_type AS tp, COUNT(*) AS nb FROM fact_ventes f "
         "JOIN dim_produit p ON f.produit_key = p.produit_key "
         "WHERE f.date_vente IS NOT NULL AND TO_CHAR(f.date_vente,'YYYY-MM')=%(m)s "
         "AND p.product_type IS NOT NULL GROUP BY p.product_type ORDER BY nb DESC LIMIT 1"),
        ("SELECT p.product_type AS tp, COUNT(*) AS nb FROM fact_ventes f "
         "JOIN dim_produit p ON TRIM(f.product_number::text)=TRIM(p.product_code::text) "
         "WHERE f.date_vente IS NOT NULL AND TO_CHAR(f.date_vente,'YYYY-MM')=%(m)s "
         "AND p.product_type IS NOT NULL GROUP BY p.product_type ORDER BY nb DESC LIMIT 1"),
    ]
    for q in top_type_queries:
        try:
            df_t = pd.read_sql(q, engine, params={'m': target_str})
            if not df_t.empty:
                top_type = str(df_t.iloc[0]['tp'] or 'N/A')
                top_nb   = int(df_t.iloc[0]['nb'])
                top_pct  = round(top_nb / total * 100, 1) if total > 0 else 0
                break
        except Exception:
            continue

    # Top canal ce mois
    top_canal_q = """
    SELECT COALESCE(b.canal_vente,'N/A') AS canal, COUNT(*) AS nb
    FROM fact_ventes f JOIN dim_boutique b ON f.boutique_key=b.boutique_key
    WHERE f.date_vente IS NOT NULL AND TO_CHAR(f.date_vente,'YYYY-MM')=%(m)s
    GROUP BY b.canal_vente ORDER BY nb DESC LIMIT 1
    """
    try:
        df_c = pd.read_sql(top_canal_q, engine, params={'m': target_str})
        if not df_c.empty:
            top_canal = str(df_c.iloc[0]['canal'] or 'N/A')
    except Exception:
        pass

    return {
        'total': total, 'precedent': precedent,
        'evolution_pct': evo_pct, 'evolution_sens': evo_sens,
        'evolution_jours': evolution_jours,
        'top_type': top_type, 'top_pct': top_pct, 'top_canal': top_canal,
    }


def get_evolution_journaliere(mois: str = None) -> list:
    """Ventes jour par jour pour le mois selectionne (ou mois le plus recent)."""
    engine = get_engine()
    if not mois:
        df_max = pd.read_sql(
            "SELECT TO_CHAR(MAX(date_vente),'YYYY-MM') AS mx FROM fact_ventes WHERE date_vente IS NOT NULL",
            engine
        )
        mois = str(df_max.iloc[0]['mx']) if not df_max.empty and df_max.iloc[0]['mx'] else None
    if not mois:
        return []
    query = """
    SELECT
        TO_CHAR(date_vente, 'DD') AS jour,
        TO_CHAR(date_vente, 'YYYY-MM-DD') AS date_str,
        COUNT(*) AS nb_ventes
    FROM fact_ventes
    WHERE date_vente IS NOT NULL AND TO_CHAR(date_vente, 'YYYY-MM') = %(m)s
    GROUP BY jour, date_str
    ORDER BY date_str
    """
    df = pd.read_sql(query, engine, params={'m': mois})
    records = _df_to_records(df)
    # Calcul moyenne journaliere
    total = sum(r['nb_ventes'] for r in records)
    moy = round(total / len(records), 0) if records else 0
    return {'jours': records, 'moyenne': int(moy), 'mois': mois}


def get_top_vendeurs_perf(limit: int = 5) -> list:
    """Top N vendeurs avec canal pour le tableau enrichi."""
    engine = get_engine()
    query = f"""
    SELECT
        v.seller_name AS nom,
        v.seller_id   AS code,
        COALESCE(b.canal_vente, 'N/A') AS canal,
        COUNT(*)                          AS nb_ventes,
        COUNT(*) FILTER (WHERE f.first_month_bill = 1) AS factures_1_payees
    FROM fact_ventes f
    JOIN dim_vendeur  v ON f.vendeur_key  = v.vendeur_key
    LEFT JOIN (
        SELECT DISTINCT ON (boutique_key) boutique_key, canal_vente
        FROM dim_boutique ORDER BY boutique_key
    ) b ON f.boutique_key = b.boutique_key
    GROUP BY v.seller_name, v.seller_id, b.canal_vente
    ORDER BY nb_ventes DESC
    LIMIT {limit}
    """
    try:
        df = pd.read_sql(query, engine)
        return _df_to_records(df)
    except Exception:
        return get_top_vendeurs(limit)


def get_repartition_famille() -> list:
    """Repartition des ventes par groupe (dim_groupe.prgname) — jointure confirmee a 100%."""
    engine = get_engine()
    query = """
    SELECT d.prgname AS famille, COUNT(*) AS nb_ventes
    FROM fact_ventes f
    JOIN dim_groupe d ON f.groupe_key = d.groupe_key
    WHERE d.prgname IS NOT NULL
      AND d.prgname NOT IN ('NON_RENSEIGNE', 'Purge_Synchro_CRM_Bscs_Lot2')
    GROUP BY d.prgname ORDER BY nb_ventes DESC
    """
    try:
        df = pd.read_sql(query, engine)
        if not df.empty:
            total = int(df['nb_ventes'].sum())
            return [
                {'famille': r['famille'],
                 'nb_ventes': int(r['nb_ventes']),
                 'pourcentage': round(int(r['nb_ventes']) / total * 100, 1) if total > 0 else 0}
                for r in df.to_dict(orient='records')
            ]
    except Exception as e:
        print(f"[get_repartition_famille] {e}")
    return []


def get_top5_offres(periode=None, canal=None, famille=None, categorie=None, cible=None) -> list:
    """Top 5 offres les plus vendues, avec filtres optionnels."""
    from sqlalchemy import text as sa_text
    engine = get_engine()

    FAMILLE_MAP = {
        'Mobile':           "UPPER(TRIM(p.product_type)) IN ('SIM DATA','SIM VOIX','SIM FLYBOX','E-SIM')",
        'Fixe et Internet': "UPPER(TRIM(p.product_type)) IN ('ADSL','SIM FIXBOX')",
        'Convergence':      "UPPER(TRIM(p.product_type)) = 'NEW'",
        'Autres':           "UPPER(TRIM(p.product_type)) NOT IN "
                            "('SIM DATA','SIM VOIX','SIM FLYBOX','E-SIM','ADSL','SIM FIXBOX','NEW')",
    }

    _j, _c, _p = [], ["o.offre_name IS NOT NULL"], {}
    if periode:
        _c.append("TO_CHAR(f.date_vente,'YYYY-MM') = :prd")
        _p['prd'] = periode
    if canal:
        _j.append("JOIN dim_boutique b ON f.boutique_key = b.boutique_key")
        _c.append("b.canal_vente = :canal")
        _p['canal'] = canal
    if famille or categorie:
        _j.append("JOIN dim_produit p ON TRIM(f.product_number::text) = TRIM(p.product_code::text)")
        if famille and famille in FAMILLE_MAP:
            _c.append(FAMILLE_MAP[famille])
        if categorie:
            _c.append("UPPER(TRIM(p.product_type)) = UPPER(:cat)")
            _p['cat'] = categorie
    if cible:
        _c.append("UPPER(TRIM(o.type_offre)) = UPPER(:cib)")
        _p['cib'] = cible

    q = sa_text(f"""
        SELECT o.offre_name AS offre, COUNT(*) AS total_vendu
        FROM fact_ventes f
        JOIN dim_offre o ON f.offre_key = o.offre_key
        {" ".join(_j)}
        WHERE {" AND ".join(_c)}
        GROUP BY o.offre_name ORDER BY total_vendu DESC LIMIT 5
    """)
    try:
        with engine.connect() as conn:
            df = pd.DataFrame(conn.execute(q, _p).mappings().all())
        if not df.empty and int(df['total_vendu'].sum()) > 0:
            return _df_to_records(df)
    except Exception as exc:
        print(f"[get_top5_offres] {exc}")
    # Fallback global sans filtres
    try:
        df = pd.read_sql(
            "SELECT o.offre_name AS offre, COUNT(*) AS total_vendu "
            "FROM fact_ventes f JOIN dim_offre o ON f.offre_key = o.offre_key "
            "WHERE o.offre_name IS NOT NULL "
            "GROUP BY o.offre_name ORDER BY total_vendu DESC LIMIT 5",
            engine,
        )
        if not df.empty:
            return _df_to_records(df)
    except Exception:
        pass
    return get_top5_produits_vendus()


def get_repartition_ligne_produits(periode=None, canal=None, famille=None,
                                    categorie=None, cible=None) -> list:
    """Répartition des ventes par ligne de produits (product_type), avec filtres optionnels."""
    from sqlalchemy import text as sa_text
    engine = get_engine()

    FAMILLE_MAP = {
        'Mobile':           "UPPER(TRIM(p.product_type)) IN ('SIM DATA','SIM VOIX','SIM FLYBOX','E-SIM')",
        'Fixe et Internet': "UPPER(TRIM(p.product_type)) IN ('ADSL','SIM FIXBOX')",
        'Convergence':      "UPPER(TRIM(p.product_type)) = 'NEW'",
        'Autres':           "UPPER(TRIM(p.product_type)) NOT IN "
                            "('SIM DATA','SIM VOIX','SIM FLYBOX','E-SIM','ADSL','SIM FIXBOX','NEW')",
    }

    _j, _c, _p = [], ["p.product_type IS NOT NULL"], {}
    if periode:
        _c.append("TO_CHAR(f.date_vente,'YYYY-MM') = :prd")
        _p['prd'] = periode
    if canal:
        _j.append("JOIN dim_boutique b ON f.boutique_key = b.boutique_key")
        _c.append("b.canal_vente = :canal")
        _p['canal'] = canal
    if famille and famille in FAMILLE_MAP:
        _c.append(FAMILLE_MAP[famille])
    if categorie:
        _c.append("UPPER(TRIM(p.product_type)) = UPPER(:cat)")
        _p['cat'] = categorie
    if cible:
        _j.append("JOIN dim_offre o ON f.offre_key = o.offre_key")
        _c.append("UPPER(TRIM(o.type_offre)) = UPPER(:cib)")
        _p['cib'] = cible

    q = sa_text(f"""
        SELECT COALESCE(p.product_type, 'Autre') AS ligne, COUNT(*) AS nb_ventes
        FROM fact_ventes f
        JOIN dim_produit p ON TRIM(f.product_number::text) = TRIM(p.product_code::text)
        {" ".join(_j)}
        WHERE {" AND ".join(_c)}
        GROUP BY p.product_type ORDER BY nb_ventes DESC LIMIT 10
    """)
    try:
        with engine.connect() as conn:
            df = pd.DataFrame(conn.execute(q, _p).mappings().all())
        if not df.empty and int(df['nb_ventes'].sum()) > 0:
            total = int(df['nb_ventes'].sum())
            return [{'ligne': r['ligne'], 'nb_ventes': int(r['nb_ventes']),
                     'pourcentage': round(int(r['nb_ventes']) / total * 100, 1) if total else 0}
                    for r in df.to_dict(orient='records')]
    except Exception as exc:
        print(f"[get_repartition_ligne_produits] {exc}")
    # Fallback global sans filtres
    try:
        df = pd.read_sql(
            "SELECT COALESCE(p.product_type,'Autre') AS ligne, COUNT(*) AS nb_ventes "
            "FROM fact_ventes f "
            "JOIN dim_produit p ON TRIM(f.product_number::text) = TRIM(p.product_code::text) "
            "WHERE p.product_type IS NOT NULL "
            "GROUP BY p.product_type ORDER BY nb_ventes DESC LIMIT 10",
            engine,
        )
        if not df.empty:
            total = int(df['nb_ventes'].sum())
            return [{'ligne': r['ligne'], 'nb_ventes': int(r['nb_ventes']),
                     'pourcentage': round(int(r['nb_ventes']) / total * 100, 1) if total else 0}
                    for r in df.to_dict(orient='records')]
    except Exception:
        pass
    return []


def get_data_quality_kpis() -> dict:
    """Indicateurs simples de qualite pour expliquer les limites du DWH."""
    engine = get_engine()
    query = """
    SELECT
        COUNT(*) AS total_ventes,
        COUNT(*) FILTER (WHERE vendeur_key IS NULL) AS sans_vendeur,
        COUNT(*) FILTER (WHERE boutique_key IS NULL) AS sans_boutique,
        COUNT(*) FILTER (WHERE offre_key IS NULL) AS sans_offre,
        COUNT(*) FILTER (WHERE groupe_key IS NULL) AS sans_groupe,
        COUNT(*) FILTER (WHERE p.produit_key IS NULL) AS produit_non_mappe,
        COUNT(*) FILTER (WHERE first_month_bill IS NULL) AS paiement_1_null,
        COUNT(*) FILTER (WHERE second_month_bill IS NULL) AS paiement_2_null,
        COUNT(*) FILTER (WHERE third_month_bill IS NULL) AS paiement_3_null,
        TO_CHAR(MIN(date_vente), 'YYYY-MM-DD') AS date_min,
        TO_CHAR(MAX(date_vente), 'YYYY-MM-DD') AS date_max,
        COUNT(DISTINCT DATE_TRUNC('month', date_vente)) AS nb_mois
    FROM fact_ventes f
    LEFT JOIN dim_produit p
      ON TRIM(f.product_number::text) = TRIM(p.product_code::text)
    """
    try:
        df = pd.read_sql(query, engine)
        row = _row_to_python(df.iloc[0].to_dict()) if not df.empty else {}
    except Exception:
        row = {}

    total = int(row.get('total_ventes') or 0)

    def pct(value):
        return round((int(value or 0) / total * 100), 1) if total else 0

    metrics = [
        {'label': 'Vendeur manquant', 'value': int(row.get('sans_vendeur') or 0), 'pct': pct(row.get('sans_vendeur'))},
        {'label': 'Boutique manquante', 'value': int(row.get('sans_boutique') or 0), 'pct': pct(row.get('sans_boutique'))},
        {'label': 'Offre manquante', 'value': int(row.get('sans_offre') or 0), 'pct': pct(row.get('sans_offre'))},
        {'label': 'Groupe manquant', 'value': int(row.get('sans_groupe') or 0), 'pct': pct(row.get('sans_groupe'))},
        {'label': 'Produit non mappe', 'value': int(row.get('produit_non_mappe') or 0), 'pct': pct(row.get('produit_non_mappe'))},
        {'label': 'Paiement 1 null', 'value': int(row.get('paiement_1_null') or 0), 'pct': pct(row.get('paiement_1_null'))},
        {'label': 'Paiement 2 null', 'value': int(row.get('paiement_2_null') or 0), 'pct': pct(row.get('paiement_2_null'))},
        {'label': 'Paiement 3 null', 'value': int(row.get('paiement_3_null') or 0), 'pct': pct(row.get('paiement_3_null'))},
    ]
    return {
        'total_ventes': total,
        'date_min': row.get('date_min') or 'N/A',
        'date_max': row.get('date_max') or 'N/A',
        'nb_mois': int(row.get('nb_mois') or 0),
        'metrics': metrics,
    }


# ============================================================
# PERFORMANCE UNIFIEE (endpoint unique avec filtres globaux)
# ============================================================

def _perf_filter(periode=None, canal=None, famille=None, categorie=None, cible=None,
                 f_alias='f', b_alias='bx'):
    """
    Retourne (join_sql, where_sql, params_dict) pour les filtres de performance.
    Supporte periode, canal, famille, categorie et cible.
    """
    joins  = []
    where  = []
    params = {}

    if canal:
        joins.append(
            f"LEFT JOIN dim_boutique {b_alias} ON {f_alias}.boutique_key = {b_alias}.boutique_key"
        )
        where.append(f"{b_alias}.canal_vente = %(pf_canal)s")
        params['pf_canal'] = canal

    if periode:
        where.append(f"TO_CHAR({f_alias}.date_vente, 'YYYY-MM') = %(pf_periode)s")
        params['pf_periode'] = periode

    # famille + categorie → un seul JOIN dim_produit
    if famille or categorie:
        joins.append(
            f"LEFT JOIN dim_produit pfam ON TRIM({f_alias}.product_number::text) = TRIM(pfam.product_code::text)"
        )
        famille_map = {
            'Mobile':           ("SIM DATA", "SIM VOIX", "SIM FLYBOX", "E-SIM"),
            'Fixe et Internet': ("ADSL", "SIM FIXBOX"),
            'Convergence':      ("NEW",),
        }
        if famille and famille in famille_map:
            types = famille_map[famille]
            keys  = [f"pf_fam_{i}" for i in range(len(types))]
            where.append(
                f"UPPER(TRIM(pfam.product_type)) IN ({','.join(['%('+k+')s' for k in keys])})"
            )
            for k, t in zip(keys, types):
                params[k] = t
        if categorie:
            where.append("UPPER(TRIM(pfam.product_type)) = UPPER(%(pf_cat)s)")
            params['pf_cat'] = categorie

    # cible → JOIN dim_offre
    if cible:
        joins.append(
            f"LEFT JOIN dim_offre pofl ON {f_alias}.offre_key = pofl.offre_key"
        )
        where.append("UPPER(TRIM(pofl.type_offre)) = UPPER(%(pf_cib)s)")
        params['pf_cib'] = cible

    join_sql  = " ".join(joins)
    where_sql = "WHERE " + " AND ".join(where) if where else ""
    return join_sql, where_sql, params


def get_performance_all(periode=None, canal=None, famille=None, categorie=None, cible=None):
    """Retourne toutes les donnees de la page Performance avec filtres globaux."""
    import math
    engine = get_engine()

    join_sql, where_sql, params = _perf_filter(periode, canal, famille, categorie, cible)

    result = {}

    # ---- KPIs ----
    try:
        kpi_q = f"""
        SELECT
            COUNT(*) AS total_ventes,
            ROUND(100.0 * COUNT(*) FILTER (WHERE f.first_month_bill = 1)
                  / NULLIF(COUNT(*), 0)::numeric, 2) AS taux_paiement,
            ROUND(AVG(f.duree_engagement)::numeric, 1) AS panier_moyen
        FROM fact_ventes f {join_sql} {where_sql}
        """
        row = pd.read_sql(kpi_q, engine, params=params).iloc[0]
        result['kpis'] = {
            'total_ventes':  int(row.get('total_ventes') or 0),
            'taux_paiement': float(row.get('taux_paiement') or 0),
            'panier_moyen':  float(row.get('panier_moyen') or 0),
        }
    except Exception:
        result['kpis'] = {'total_ventes': 0, 'taux_paiement': 0, 'panier_moyen': 0}

    # ---- Evolution journalière ----
    try:
        mois_eff = periode
        if not mois_eff:
            mx = pd.read_sql(
                "SELECT TO_CHAR(MAX(date_vente),'YYYY-MM') AS mx FROM fact_ventes WHERE date_vente IS NOT NULL",
                engine,
            ).iloc[0]['mx']
            mois_eff = str(mx) if mx else None

        if mois_eff:
            evo_params = dict(params)
            evo_params['evo_mois'] = mois_eff
            if not periode:
                evo_where = f"WHERE TO_CHAR(f.date_vente,'YYYY-MM') = %(evo_mois)s"
                if canal:
                    evo_where = f"WHERE TO_CHAR(f.date_vente,'YYYY-MM') = %(evo_mois)s AND bx.canal_vente = %(pf_canal)s"
            else:
                evo_where = where_sql

            evo_q = f"""
            SELECT TO_CHAR(f.date_vente,'DD') AS jour,
                   TO_CHAR(f.date_vente,'YYYY-MM-DD') AS date_str,
                   COUNT(*) AS nb_ventes
            FROM fact_ventes f {join_sql}
            {evo_where}
            GROUP BY jour, date_str ORDER BY date_str
            """
            evo_df = pd.read_sql(evo_q, engine, params=evo_params)
            records = _df_to_records(evo_df)
            total_evo = sum(r['nb_ventes'] for r in records)
            moy = round(total_evo / len(records), 0) if records else 0
            result['evolution'] = {'jours': records, 'moyenne': int(moy), 'mois': mois_eff}
        else:
            result['evolution'] = {'jours': [], 'moyenne': 0}
    except Exception:
        result['evolution'] = {'jours': [], 'moyenne': 0}

    # ---- Ventes par canal ----
    try:
        canal_q = f"""
        SELECT COALESCE(b.canal_vente,'Non specifie') AS canal,
               COUNT(*) AS nb_ventes,
               ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER ()::numeric, 2) AS pourcentage
        FROM fact_ventes f
        JOIN dim_boutique b ON f.boutique_key = b.boutique_key
        {join_sql.replace('bx', 'bcanal')} {where_sql.replace('bx.', 'bcanal.')}
        GROUP BY b.canal_vente ORDER BY nb_ventes DESC
        """
        canal_df = pd.read_sql(canal_q, engine, params=params)
        c_rows   = _df_to_records(canal_df)
        result['ventes_canal'] = {
            'canaux':       [r['canal']       for r in c_rows],
            'nb_ventes':    [r['nb_ventes']   for r in c_rows],
            'pourcentages': [float(r.get('pourcentage') or 0) for r in c_rows],
        }
    except Exception:
        result['ventes_canal'] = {'canaux': [], 'nb_ventes': [], 'pourcentages': []}

    # ---- Ventes par famille ----
    # Diagnostic confirme : fact_ventes.groupe_key → dim_groupe.prgname (100% coverage)
    # ventes_contrats n'existe pas, dim_groupe.famille est NULL partout.
    try:
        _noise = "('NON_RENSEIGNE','Purge_Synchro_CRM_Bscs_Lot2')"
        _fam_extra = f"d.prgname IS NOT NULL AND d.prgname NOT IN {_noise}"
        _fam_where = (where_sql + " AND " + _fam_extra) if where_sql else ("WHERE " + _fam_extra)
        fam_q = f"""
            SELECT d.prgname AS famille, COUNT(*) AS nb_ventes
            FROM fact_ventes f {join_sql}
            JOIN dim_groupe d ON f.groupe_key = d.groupe_key
            {_fam_where}
            GROUP BY d.prgname ORDER BY nb_ventes DESC
        """
        fam_df  = pd.read_sql(fam_q, engine, params=params or None)
        fam_rows = _df_to_records(fam_df) if not fam_df.empty else []
        total_f  = sum(r['nb_ventes'] for r in fam_rows)
        for r in fam_rows:
            r['pourcentage'] = round(r['nb_ventes'] / total_f * 100, 1) if total_f else 0
        result['ventes_famille'] = {
            'familles':    [r['famille']     for r in fam_rows],
            'nb_ventes':   [r['nb_ventes']   for r in fam_rows],
            'pourcentages':[r['pourcentage'] for r in fam_rows],
        }
    except Exception:
        result['ventes_famille'] = {'familles': [], 'nb_ventes': [], 'pourcentages': []}

    # ---- Top 5 offres ----
    try:
        result['top5_offres'] = get_top5_offres(periode, canal, famille, categorie, cible)
    except Exception:
        result['top5_offres'] = []

    # ---- Objectif vs Realisation ----
    try:
        mois_obj = periode or (
            pd.read_sql(
                "SELECT TO_CHAR(MAX(date_vente),'YYYY-MM') AS mx FROM fact_ventes WHERE date_vente IS NOT NULL",
                engine,
            ).iloc[0]['mx'] or ''
        )

        def _safe_f(v):
            if v is None: return 0
            try:
                f2 = float(v)
                return 0 if (math.isnan(f2) or math.isinf(f2)) else round(f2, 2)
            except Exception:
                return 0

        obj_rows = get_objectif_canal_mois(str(mois_obj), canal=canal)
        filtered = [r for r in obj_rows if _safe_f(r['objectif']) > 0 or _safe_f(r['realisation']) > 0]
        result['objectif_canal'] = {
            'canaux':       [r['canal']              for r in filtered],
            'objectifs':    [_safe_f(r['objectif'])  for r in filtered],
            'realisations': [_safe_f(r['realisation'])for r in filtered],
            'taux':         [_safe_f(r['taux'])       for r in filtered],
        }
    except Exception:
        result['objectif_canal'] = {'canaux': [], 'objectifs': [], 'realisations': [], 'taux': []}

    # ---- taux_realisation filtré (ventes filtrées / objectifs du canal+periode) ----
    try:
        total_obj  = sum(result['objectif_canal']['objectifs'])
        total_real = sum(result['objectif_canal']['realisations'])
        result['kpis']['taux_realisation'] = round(total_real / total_obj * 100, 2) if total_obj > 0 else 0
    except Exception:
        result['kpis']['taux_realisation'] = 0

    # ---- Repartition ligne de produits ----
    try:
        result['ligne_produits'] = get_repartition_ligne_produits(periode, canal, famille, categorie, cible)
    except Exception:
        result['ligne_produits'] = []

    return result


# ============================================================
# KPIs FILTRÉS — Paiements
# ============================================================

def get_paiements_kpis_filtered(periode: str = None, canal: str = None,
                                 famille: str = None, categorie: str = None,
                                 cible: str = None) -> dict:
    """KPIs paiements avec filtres optionnels."""
    from sqlalchemy import text as sa_text
    engine = get_engine()

    famille_map = {
        'Mobile':           ('SIM DATA', 'SIM VOIX', 'SIM FLYBOX', 'E-SIM'),
        'Fixe et Internet': ('ADSL', 'SIM FIXBOX'),
        'Convergence':      ('NEW',),
    }

    joins, where, params = [], ["f.date_vente IS NOT NULL"], {}

    if periode:
        where.append("TO_CHAR(f.date_vente, 'YYYY-MM') = :periode")
        params['periode'] = periode

    if canal:
        joins.append("LEFT JOIN dim_boutique b ON f.boutique_key = b.boutique_key")
        where.append("b.canal_vente = :canal")
        params['canal'] = canal

    if famille or categorie:
        joins.append("LEFT JOIN dim_produit pfam ON TRIM(f.product_number::text) = TRIM(pfam.product_code::text)")
        if famille and famille in famille_map:
            types = famille_map[famille]
            keys = [f'fam_{i}' for i in range(len(types))]
            where.append(f"UPPER(TRIM(pfam.product_type)) IN ({','.join([':'+k for k in keys])})")
            for k, t in zip(keys, types):
                params[k] = t
        if categorie:
            where.append("UPPER(TRIM(pfam.product_type)) = UPPER(:categorie)")
            params['categorie'] = categorie

    if cible:
        joins.append("LEFT JOIN dim_offre ofl ON f.offre_key = ofl.offre_key")
        where.append("UPPER(TRIM(ofl.type_offre)) = UPPER(:cible)")
        params['cible'] = cible

    join_sql  = " ".join(joins)
    where_sql = "WHERE " + " AND ".join(where)

    query = sa_text(f"""
    SELECT
        COUNT(*)                                                             AS total_factures,
        COUNT(CASE WHEN f.first_month_bill = 0
                    OR f.first_month_bill IS NULL THEN 1 END)               AS factures_impayees,
        ROUND(100.0 * COUNT(CASE WHEN f.first_month_bill  > 0 THEN 1 END)
              / NULLIF(COUNT(*), 0)::numeric, 2)                            AS taux_1ere,
        ROUND(100.0 * COUNT(CASE WHEN f.second_month_bill > 0 THEN 1 END)
              / NULLIF(COUNT(*), 0)::numeric, 2)                            AS taux_2eme,
        ROUND(100.0 * COUNT(CASE WHEN f.third_month_bill  > 0 THEN 1 END)
              / NULLIF(COUNT(*), 0)::numeric, 2)                            AS taux_3eme
    FROM fact_ventes f {join_sql}
    {where_sql}
    """)
    try:
        with engine.connect() as conn:
            df = pd.read_sql(query, conn, params=params)
        row = _row_to_python(df.iloc[0].to_dict()) if not df.empty else {}
        total    = int(row.get('total_factures') or 0)
        impayees = int(row.get('factures_impayees') or 0)
        t1 = float(row.get('taux_1ere') or 0)
        return {
            'total_factures':   total,
            'factures_impayees': impayees,
            'taux_paiement':    t1,
            'taux_1ere':        t1,
            'taux_2eme':        float(row.get('taux_2eme') or 0),
            'taux_3eme':        float(row.get('taux_3eme') or 0),
        }
    except Exception:
        return {'total_factures': 0, 'factures_impayees': 0,
                'taux_paiement': 0, 'taux_1ere': 0, 'taux_2eme': 0, 'taux_3eme': 0}


# ============================================================
# KPIs FILTRÉS — Objectifs
# ============================================================

def get_objectifs_kpis_filtered(canal: str = None, periode: str = None) -> dict:
    """KPIs objectifs boutiques filtrés par canal et/ou periode."""
    from sqlalchemy import text as sa_text
    engine = get_engine()

    canal_cond   = "AND b.canal_vente = :canal" if canal else ""
    periode_cond = "AND LEFT(o.mois_objectif::text, 7) = :periode" if periode else ""
    ventes_periode_cond = "AND TO_CHAR(v.date_vente,'YYYY-MM') = :periode" if periode else ""
    params = {}
    if canal:   params['canal']   = canal
    if periode: params['periode'] = periode

    query = sa_text(f"""
    WITH boutiques_cibles AS (
        SELECT b.boutique_key
        FROM dim_boutique b
        WHERE 1=1 {canal_cond}
    ),
    objectifs_b AS (
        SELECT o.boutique_key, SUM(o.montant_objectif) AS objectif
        FROM fact_objectifs o
        JOIN boutiques_cibles bc ON o.boutique_key = bc.boutique_key
        WHERE o.montant_objectif IS NOT NULL {periode_cond}
        GROUP BY o.boutique_key HAVING SUM(o.montant_objectif) > 0
    ),
    ventes_b AS (
        SELECT v.boutique_key, COUNT(*) AS realise
        FROM fact_ventes v
        JOIN boutiques_cibles bc ON v.boutique_key = bc.boutique_key
        WHERE 1=1 {ventes_periode_cond}
        GROUP BY v.boutique_key
    ),
    combined AS (
        SELECT
            o.objectif,
            COALESCE(v.realise, 0) AS realise,
            ROUND((COALESCE(v.realise, 0) / NULLIF(o.objectif, 0) * 100)::numeric, 2) AS taux_pct
        FROM objectifs_b o
        LEFT JOIN ventes_b v ON o.boutique_key = v.boutique_key
    )
    SELECT
        COUNT(*)                                             AS nb_total,
        ROUND(AVG(taux_pct)::numeric, 2)                     AS taux_global,
        COUNT(CASE WHEN taux_pct >= 70 THEN 1 END)           AS nb_atteignent,
        COUNT(CASE WHEN taux_pct <  70 THEN 1 END)           AS nb_difficulte,
        COALESCE(SUM(objectif), 0)::bigint                   AS objectif_total,
        COALESCE(SUM(realise),  0)::bigint                   AS realise_total
    FROM combined
    """)
    # Requete detail : liste par boutique (memes CTEs)
    detail_query = sa_text(f"""
    WITH boutiques_cibles AS (
        SELECT b.boutique_key
        FROM dim_boutique b
        WHERE 1=1 {canal_cond}
    ),
    objectifs_b AS (
        SELECT o.boutique_key, SUM(o.montant_objectif) AS objectif
        FROM fact_objectifs o
        JOIN boutiques_cibles bc ON o.boutique_key = bc.boutique_key
        WHERE o.montant_objectif IS NOT NULL {periode_cond}
        GROUP BY o.boutique_key HAVING SUM(o.montant_objectif) > 0
    ),
    ventes_b AS (
        SELECT v.boutique_key, COUNT(*) AS realise
        FROM fact_ventes v
        JOIN boutiques_cibles bc ON v.boutique_key = bc.boutique_key
        WHERE 1=1 {ventes_periode_cond}
        GROUP BY v.boutique_key
    )
    SELECT
        b.entity_name                                                        AS boutique,
        COALESCE(b.canal_vente, 'N/A')                                       AS canal,
        COALESCE(b.region, 'N/A')                                            AS region,
        o.objectif,
        COALESCE(v.realise, 0)                                               AS realise,
        ROUND((COALESCE(v.realise, 0) / NULLIF(o.objectif, 0) * 100)::numeric, 2) AS taux_pct
    FROM objectifs_b o
    JOIN dim_boutique b ON o.boutique_key = b.boutique_key
    LEFT JOIN ventes_b v ON o.boutique_key = v.boutique_key
    ORDER BY taux_pct DESC NULLS LAST
    """)
    try:
        with engine.connect() as conn:
            df_agg    = pd.read_sql(query, conn, params=params if params else None)
            df_detail = pd.read_sql(detail_query, conn, params=params if params else None)

        row     = _row_to_python(df_agg.iloc[0].to_dict()) if not df_agg.empty else {}
        records = _df_to_records(df_detail) if not df_detail.empty else []

        atteignent = [r for r in records if float(r.get('taux_pct') or 0) >= 70]
        difficulte = sorted(
            [r for r in records if float(r.get('taux_pct') or 0) < 70],
            key=lambda r: float(r.get('taux_pct') or 0)
        )
        top_b = atteignent[0] if atteignent else {}

        return {
            'nb_total':            int(row.get('nb_total')       or 0),
            'taux_global':         float(row.get('taux_global')  or 0),
            'nb_atteignent':       int(row.get('nb_atteignent')  or 0),
            'nb_difficulte':       int(row.get('nb_difficulte')  or 0),
            'objectif_total':      int(row.get('objectif_total') or 0),
            'realise_total':       int(row.get('realise_total')  or 0),
            'boutiques_atteignent': atteignent,
            'boutiques_difficulte': difficulte,
            'top_boutique':        top_b,
        }
    except Exception:
        return {'nb_total': 0, 'taux_global': 0, 'nb_atteignent': 0,
                'nb_difficulte': 0, 'objectif_total': 0, 'realise_total': 0,
                'boutiques_atteignent': [], 'boutiques_difficulte': [], 'top_boutique': {}}


def get_objectifs_par_mois_filtered(canal: str = None, periode: str = None) -> list:
    """Evolution mensuelle objectif/realisation/taux, filtrée par canal et/ou periode."""
    if not canal and not periode:
        return get_objectifs_par_mois()
    from sqlalchemy import text as sa_text
    engine = get_engine()

    canal_cond_obj    = "AND b.canal_vente = :canal"   if canal   else ""
    canal_cond_ventes = "AND b.canal_vente = :canal"   if canal   else ""
    # Pour la periode : filtrer les ventes (pas les objectifs qui sont mensuels par nature)
    periode_cond      = "AND TO_CHAR(DATE_TRUNC('month', f.date_vente), 'YYYY-MM') = :periode" if periode else ""

    params: dict = {}
    if canal:   params['canal']   = canal
    if periode: params['periode'] = periode

    boutique_join_obj    = "JOIN dim_boutique b ON o.boutique_key = b.boutique_key" if canal else ""
    boutique_join_ventes = "JOIN dim_boutique b ON f.boutique_key = b.boutique_key" if canal else ""

    query = sa_text(f"""
    WITH objectifs AS (
        SELECT
            TO_DATE(LEFT(o.mois_objectif::text, 7), 'YYYY-MM') AS month_date,
            ROUND(SUM(o.montant_objectif)::numeric, 0) AS objectif_total
        FROM fact_objectifs o
        {boutique_join_obj}
        WHERE o.mois_objectif IS NOT NULL
          {canal_cond_obj}
        GROUP BY TO_DATE(LEFT(o.mois_objectif::text, 7), 'YYYY-MM')
    ),
    ventes AS (
        SELECT
            DATE_TRUNC('month', f.date_vente)::date AS month_date,
            COUNT(*) AS nb_ventes,
            COUNT(*) AS realise_total
        FROM fact_ventes f
        {boutique_join_ventes}
        WHERE f.date_vente IS NOT NULL
          {canal_cond_ventes}
          {periode_cond}
        GROUP BY DATE_TRUNC('month', f.date_vente)::date
    )
    SELECT
        TO_CHAR(COALESCE(v.month_date, o.month_date), 'Mon YYYY') AS mois,
        TO_CHAR(COALESCE(v.month_date, o.month_date), 'YYYY-MM') AS mois_sort,
        COALESCE(v.nb_ventes, 0) AS nb_ventes,
        COALESCE(o.objectif_total, 0) AS objectif_total,
        COALESCE(v.realise_total, 0) AS realise_total,
        ROUND(
            (COALESCE(v.realise_total, 0) / NULLIF(o.objectif_total, 0) * 100)::numeric, 2
        ) AS taux
    FROM ventes v
    FULL OUTER JOIN objectifs o ON v.month_date = o.month_date
    ORDER BY mois_sort
    """)
    try:
        with engine.connect() as conn:
            df = pd.read_sql(query, conn, params=params)
        return _df_to_records(df)
    except Exception:
        return []


def get_objectifs_charts_filtered(canal: str = None, periode: str = None) -> dict:
    """Données des deux graphiques objectifs (mois + canal) avec filtres optionnels."""
    return {
        'par_mois':    get_objectifs_par_mois_filtered(canal=canal, periode=periode),
        'canaux_taux': get_taux_par_canal(canal=canal, periode=periode),
    }


# ============================================================
# FILTRES EN CASCADE — options compatibles avec la selection
# ============================================================

def get_cascade_filter_options(periode=None, canal=None, famille=None,
                                categorie=None, cible=None) -> dict:
    """
    Retourne les valeurs disponibles pour chaque dimension de filtre
    en appliquant tous les AUTRES filtres actifs (sauf celui calcule).
    Ainsi famille=Mobile ne propose que les categories SIM VOIX/SIM DATA/...
    et non SIM FLYBOX si absent des donnees pour cette famille.
    """
    from sqlalchemy import text as sa_text
    engine = get_engine()

    FAMILLE_MAP = {
        'Mobile':           "UPPER(TRIM(p.product_type)) IN ('SIM DATA','SIM VOIX','SIM FLYBOX','E-SIM')",
        'Fixe et Internet': "UPPER(TRIM(p.product_type)) IN ('ADSL','SIM FIXBOX')",
        'Convergence':      "UPPER(TRIM(p.product_type)) = 'NEW'",
        'Autres':           "UPPER(TRIM(p.product_type)) NOT IN "
                            "('SIM DATA','SIM VOIX','SIM FLYBOX','E-SIM','ADSL','SIM FIXBOX','NEW')",
    }

    def _type_to_famille(t: str) -> str:
        u = t.upper().strip()
        if u in ('SIM DATA', 'SIM VOIX', 'SIM FLYBOX', 'E-SIM'):
            return 'Mobile'
        if u in ('ADSL', 'SIM FIXBOX'):
            return 'Fixe et Internet'
        if u == 'NEW':
            return 'Convergence'
        return 'Autres'

    def _run(sql: str, params: dict = None):
        try:
            with engine.connect() as conn:
                r = conn.execute(sa_text(sql), params or {})
                return sorted([str(v[0]) for v in r if v[0] and str(v[0]).strip()])
        except Exception as exc:
            print(f"[cascade_opts] {exc}")
            return []

    result = {}

    # ── CANAL : exclure filtre canal, appliquer periode+famille+categorie+cible ──
    _j, _c, _p = [], ["1=1"], {}
    if periode:
        _c.append("TO_CHAR(f.date_vente,'YYYY-MM') = :prd")
        _p['prd'] = periode
    need_prod_c = bool(famille or categorie)
    if need_prod_c:
        _j.append("JOIN dim_produit p ON TRIM(f.product_number::text) = TRIM(p.product_code::text)")
    if famille and famille in FAMILLE_MAP:
        _c.append(FAMILLE_MAP[famille])
    if categorie:
        _c.append("UPPER(TRIM(p.product_type)) = UPPER(:cat)")
        _p['cat'] = categorie
    if cible:
        _j.append("JOIN dim_offre o ON f.offre_key = o.offre_key")
        _c.append("UPPER(TRIM(o.type_offre)) = UPPER(:cib)")
        _p['cib'] = cible
    result['canal'] = _run(f"""
        SELECT DISTINCT TRIM(b.canal_vente)
        FROM fact_ventes f
        JOIN dim_boutique b ON f.boutique_key = b.boutique_key
        {" ".join(_j)}
        WHERE {" AND ".join(_c)}
          AND b.canal_vente IS NOT NULL AND TRIM(b.canal_vente) <> ''
        ORDER BY 1
    """, _p)

    # ── FAMILLE : exclure filtre famille, appliquer periode+canal+categorie+cible ──
    _j, _c, _p = [], ["1=1"], {}
    if periode:
        _c.append("TO_CHAR(f.date_vente,'YYYY-MM') = :prd")
        _p['prd'] = periode
    if canal:
        _j.append("JOIN dim_boutique b ON f.boutique_key = b.boutique_key")
        _c.append("b.canal_vente = :canal")
        _p['canal'] = canal
    if categorie:
        _c.append("UPPER(TRIM(p.product_type)) = UPPER(:cat)")
        _p['cat'] = categorie
    if cible:
        _j.append("JOIN dim_offre o ON f.offre_key = o.offre_key")
        _c.append("UPPER(TRIM(o.type_offre)) = UPPER(:cib)")
        _p['cib'] = cible
    raw_types = _run(f"""
        SELECT DISTINCT TRIM(p.product_type)
        FROM fact_ventes f
        JOIN dim_produit p ON TRIM(f.product_number::text) = TRIM(p.product_code::text)
        {" ".join(_j)}
        WHERE {" AND ".join(_c)}
          AND p.product_type IS NOT NULL AND TRIM(p.product_type) <> ''
        ORDER BY 1
    """, _p)
    result['famille'] = sorted(set(_type_to_famille(t) for t in raw_types))

    # ── CATEGORIE : exclure filtre categorie, appliquer periode+canal+famille+cible ──
    _j, _c, _p = [], ["1=1"], {}
    if periode:
        _c.append("TO_CHAR(f.date_vente,'YYYY-MM') = :prd")
        _p['prd'] = periode
    if canal:
        _j.append("JOIN dim_boutique b ON f.boutique_key = b.boutique_key")
        _c.append("b.canal_vente = :canal")
        _p['canal'] = canal
    if famille and famille in FAMILLE_MAP:
        _c.append(FAMILLE_MAP[famille])
    if cible:
        _j.append("JOIN dim_offre o ON f.offre_key = o.offre_key")
        _c.append("UPPER(TRIM(o.type_offre)) = UPPER(:cib)")
        _p['cib'] = cible
    result['categorie'] = _run(f"""
        SELECT DISTINCT TRIM(p.product_type)
        FROM fact_ventes f
        JOIN dim_produit p ON TRIM(f.product_number::text) = TRIM(p.product_code::text)
        {" ".join(_j)}
        WHERE {" AND ".join(_c)}
          AND p.product_type IS NOT NULL AND TRIM(p.product_type) <> ''
        ORDER BY 1
    """, _p)

    # ── CIBLE : exclure filtre cible, appliquer periode+canal+famille+categorie ──
    _j, _c, _p = [], ["1=1"], {}
    if periode:
        _c.append("TO_CHAR(f.date_vente,'YYYY-MM') = :prd")
        _p['prd'] = periode
    if canal:
        _j.append("JOIN dim_boutique b ON f.boutique_key = b.boutique_key")
        _c.append("b.canal_vente = :canal")
        _p['canal'] = canal
    need_prod_ci = bool(famille or categorie)
    if need_prod_ci:
        _j.append("JOIN dim_produit p ON TRIM(f.product_number::text) = TRIM(p.product_code::text)")
    if famille and famille in FAMILLE_MAP:
        _c.append(FAMILLE_MAP[famille])
    if categorie:
        _c.append("UPPER(TRIM(p.product_type)) = UPPER(:cat)")
        _p['cat'] = categorie
    result['cible'] = _run(f"""
        SELECT DISTINCT TRIM(o.type_offre)
        FROM fact_ventes f
        JOIN dim_offre o ON f.offre_key = o.offre_key
        {" ".join(_j)}
        WHERE {" AND ".join(_c)}
          AND o.type_offre IS NOT NULL AND TRIM(o.type_offre) <> ''
        ORDER BY 1
    """, _p)

    return result

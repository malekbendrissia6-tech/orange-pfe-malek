"""Executeur SQL securise — lecture seule."""
import re
import os
import psycopg2
import psycopg2.extras
from decimal import Decimal
from datetime import date, datetime
from dotenv import load_dotenv

load_dotenv()


class SQLExecutor:

    FORBIDDEN = [
        'INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER',
        'TRUNCATE', 'GRANT', 'REVOKE', 'EXEC', 'EXECUTE',
        'xp_', '/*', '*/', ';--',
    ]

    # Tables reelles du DWH Orange Tunisie
    ALLOWED_TABLES = [
        'fact_ventes', 'fact_objectifs',
        'dim_boutique', 'dim_vendeur', 'dim_produit',
        'dim_offre', 'dim_groupe', 'dim_date', 'dim_ref_objectifs',
    ]

    def __init__(self):
        self.conn_params = {
            'host':     os.getenv('DB_HOST', 'localhost'),
            'port':     os.getenv('DB_PORT', '5432'),
            'database': os.getenv('DB_NAME', 'orange_dwh'),
            'user':     os.getenv('DB_USER', 'postgres'),
            'password': os.getenv('DB_PASSWORD', 'malek1'),
        }

    def is_safe(self, sql: str) -> tuple[bool, str]:
        upper = sql.upper().strip()
        if not upper.startswith('SELECT'):
            return False, "La requete doit commencer par SELECT."
        for kw in self.FORBIDDEN:
            if kw.upper() in upper:
                return False, f"Mot-cle interdit : {kw}"
        if sql.count(';') > 1:
            return False, "Une seule instruction autorisee."
        # Supprimer les clauses EXTRACT(...FROM...) avant de chercher les tables
        # pour eviter que EXTRACT(MONTH FROM f.date_vente) soit lu comme table 'f'
        sql_for_check = re.sub(r'EXTRACT\s*\([^)]*\)', 'EXTRACT()', sql, flags=re.IGNORECASE)
        tables = re.findall(r'(?:FROM|JOIN)\s+(\w+)', sql_for_check, re.IGNORECASE)
        allowed_lower = [t.lower() for t in self.ALLOWED_TABLES]
        for t in tables:
            if t.lower() not in allowed_lower:
                return False, f"Table non autorisee : {t}"
        return True, "OK"

    def execute_safe(self, sql: str, max_rows: int = 50) -> list:
        ok, msg = self.is_safe(sql)
        if not ok:
            raise ValueError(f"Requete refusee : {msg}")
        if 'LIMIT' not in sql.upper():
            sql = sql.rstrip(';').rstrip() + f' LIMIT {max_rows}'
        conn = None
        try:
            conn = psycopg2.connect(**self.conn_params)
            conn.set_session(readonly=True)
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(sql)
            rows = [dict(r) for r in cur.fetchall()]
            cur.close()
            return self._json_safe(rows)
        except Exception as e:
            print(f"[SQLExecutor] Erreur : {e}")
            return []
        finally:
            if conn:
                conn.close()

    @staticmethod
    def _json_safe(rows: list) -> list:
        def cv(v):
            if isinstance(v, Decimal):
                return float(v)
            if isinstance(v, (date, datetime)):
                return v.isoformat()
            return v
        return [{k: cv(v) for k, v in r.items()} for r in rows]

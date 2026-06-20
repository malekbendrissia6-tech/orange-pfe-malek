"""
Agent chatbot Orange Tunisie — Claude Sonnet (Anthropic) + PostgreSQL.
"""
import os
import json
import re
from pathlib import Path
from dotenv import load_dotenv

import anthropic

from .intent_classifier import IntentClassifier
from .sql_executor import SQLExecutor
from .chart_generator import ChartGenerator

PROJECT_ROOT = Path(__file__).parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL      = "claude-sonnet-4-6"
MAX_TOKENS        = 1500

# ============================================================
# DETECTION DES FILTRES DANS LES QUESTIONS NATURELLES
# ============================================================

_MOIS_MAP = {
    'janvier': 1, 'jan': 1, 'january': 1,
    'fevrier': 2, 'fev': 2, 'february': 2, 'février': 2,
    'mars': 3, 'march': 3,
    'avril': 4, 'avr': 4, 'april': 4,
    'mai': 5, 'may': 5,
    'juin': 6, 'june': 6,
    'juillet': 7, 'juil': 7, 'july': 7,
    'aout': 8, 'août': 8, 'august': 8,
    'septembre': 9, 'sept': 9, 'sep': 9, 'september': 9,
    'octobre': 10, 'oct': 10, 'october': 10,
    'novembre': 11, 'nov': 11, 'november': 11,
    'decembre': 12, 'dec': 12, 'december': 12, 'décembre': 12,
}

_NOMS_MOIS = {
    1: 'Janvier', 2: 'Février', 3: 'Mars', 4: 'Avril',
    5: 'Mai', 6: 'Juin', 7: 'Juillet', 8: 'Août',
    9: 'Septembre', 10: 'Octobre', 11: 'Novembre', 12: 'Décembre',
}

_CANAUX_CONNUS = [
    'FRANCHISE', 'BTQ', 'LAB2.0', 'PDV LAB', 'PDV EXP',
    'PDV ADSL', 'PRO_VI', 'DISTRIBUTEUR',
]

_FAMILLE_SQL = {
    'Mobile':           "UPPER(TRIM(p.product_type)) IN ('SIM DATA','SIM VOIX','SIM FLYBOX','E-SIM')",
    'Fixe et Internet': "UPPER(TRIM(p.product_type)) IN ('ADSL','SIM FIXBOX')",
    'Convergence':      "UPPER(TRIM(p.product_type)) = 'NEW'",
}


def _detect_mois(msg_lower: str) -> int | None:
    for mot, num in _MOIS_MAP.items():
        if re.search(r'\b' + re.escape(mot) + r'\b', msg_lower):
            return num
    m = re.search(r'\b(0?[1-9]|1[0-2])\b', msg_lower)
    if m:
        n = int(m.group(1))
        if 1 <= n <= 12:
            return n
    return None


def _detect_annee(msg_lower: str) -> int | None:
    m = re.search(r'\b(202[0-9])\b', msg_lower)
    return int(m.group(1)) if m else None


def _detect_canal(msg_orig: str) -> str | None:
    u = msg_orig.upper()
    for c in _CANAUX_CONNUS:
        if c in u:
            return c
    # variante sans point pour LAB2.0
    if 'LAB2' in u:
        return 'LAB2.0'
    return None


def _detect_famille(msg_lower: str) -> str | None:
    if 'mobile' in msg_lower:
        return 'Mobile'
    if 'fixe' in msg_lower or 'internet fixe' in msg_lower:
        return 'Fixe et Internet'
    if 'convergence' in msg_lower:
        return 'Convergence'
    return None


# Schema reel du DWH (colonnes exactes)
_SCHEMA = """
Tables disponibles dans le DWH Orange Tunisie (PostgreSQL) :

fact_ventes(ventes_id, vendeur_key, boutique_key, produit_key, offre_key, groupe_key,
            date_vente DATE, first_month_bill NUMERIC, second_month_bill NUMERIC,
            third_month_bill NUMERIC, product_number)
  -> nb ventes = COUNT(*), paiement 1ere facture = first_month_bill = 1

fact_objectifs(objectif_id, boutique_key, ref_obj_key, date_objectif,
               mois_objectif, montant_objectif NUMERIC)

dim_vendeur(vendeur_key, seller_id, seller_name, code_stock, month)
  -> nom du vendeur = seller_name

dim_boutique(boutique_key, entity_code, entity_name, responsable, canal_vente, region)
  -> nom boutique = entity_name, canal = canal_vente (pas de table dim_canal separee)

dim_produit(produit_key, product_code, product_name, product_type, famille_produit)

dim_offre(offre_key, ...)
dim_groupe(groupe_key, ...)
dim_date(date_key, ...)
dim_ref_objectifs(ref_obj_key, ...)

JOINTURES STANDARD :
  fact_ventes JOIN dim_vendeur  ON fact_ventes.vendeur_key  = dim_vendeur.vendeur_key
  fact_ventes JOIN dim_boutique ON fact_ventes.boutique_key = dim_boutique.boutique_key
  fact_ventes JOIN dim_produit  ON TRIM(fact_ventes.product_number::text) = TRIM(dim_produit.product_code::text)
  fact_objectifs JOIN dim_boutique ON fact_objectifs.boutique_key = dim_boutique.boutique_key
"""

_REGLES = """Tu es ORYA, l'Assistant Intelligent de la plateforme Orange Tunisie.
REGLES STRICTES :
- Reponds TOUJOURS et UNIQUEMENT en francais, peu importe la langue de la question
- Ton professionnel, analytique, chaleureux
- Donne des reponses DETAILLEES et RICHES en informations : contexte, chiffres precis, comparaisons, tendances, interpretations
- Minimum 3-5 phrases par reponse, avec des details concrets
- Lorsqu on te demande des donnees, fournis les chiffres exacts, le contexte et une interpretation
- Pas de markdown (**, ##, *, #) sauf pour structurer les donnees dans un tableau
- Formate les grands chiffres avec espace (ex: 63 615)
- Si tu fais une analyse, mentionne: le chiffre principal, la tendance, et une recommandation actionnable
- Pour les comparaisons, indique toujours la variation en pourcentage et en valeur absolue
"""


class ChatbotAgent:

    def __init__(self):
        self._client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None
        self.classifier  = IntentClassifier()
        self.sql_exec    = SQLExecutor()
        self.chart_gen   = ChartGenerator()

    # ------------------------------------------------------------------ #
    # Point d entree principal
    # ------------------------------------------------------------------ #

    def process_message(self, message: str, user_id: int, history=None) -> dict:
        intent = self.classifier.classify(message)
        handlers = {
            'data_visualization': self._handle_chart,
            'kpi_query':          self._handle_kpi,
            'app_help':           self._handle_help,
            'general_business':   self._handle_business,
        }
        handler = handlers.get(intent, self._handle_general)
        return handler(message, history)

    # ------------------------------------------------------------------ #
    # Handlers
    # ------------------------------------------------------------------ #

    def _handle_kpi(self, message: str, history) -> dict:
        try:
            # Essayer d'abord le SQL direct base sur mots-cles (fonctionne sans API)
            sql_json = self._keyword_sql(message)

            # Si pas de match direct, essayer Gemini
            if not sql_json:
                sql_prompt = (
                    "Tu es un generateur SQL pour Orange Tunisie.\n"
                    f"{_SCHEMA}\n\n"
                    f"Question : \"{message}\"\n\n"
                    "Genere une requete SQL PostgreSQL valide. "
                    "Reponds UNIQUEMENT avec du JSON valide, sans markdown, sans explication :\n"
                    '{"sql":"SELECT ...","description":"...","expected_format":"scalar|table"}'
                )
                sql_json = self._ask_json(sql_prompt)

            if not sql_json or 'sql' not in sql_json:
                return self._fallback()

            results = self.sql_exec.execute_safe(sql_json['sql'])
            if not results:
                f_check = self._extract_filters(message.lower(), message)
                fdesc   = self._filter_desc(f_check)
                hint = (
                    f"Aucune donnee trouvee{fdesc}.\n"
                    "Verifiez que la periode contient des ventes, "
                    "ou essayez sans filtre."
                )
                return self._ok(hint, intent='kpi_query',
                )

            # Formater la reponse sans Gemini pour les resultats keyword
            answer = self._format_results(message, results, sql_json.get('description', ''))
            return {
                'text':    answer,
                'chart':   None,
                'data':    results[:8],
                'sources': self._tables(sql_json['sql']),
                'intent':  'kpi_query',
            }
        except Exception as e:
            print(f"[ChatbotAgent._handle_kpi] {e}")
            return self._fallback()

    def _handle_chart(self, message: str, history) -> dict:
        cfg = self._keyword_chart(message)
        if cfg:
            try:
                results = self.sql_exec.execute_safe(cfg['sql'])
                chart   = self.chart_gen.build_chart_config(results, cfg)
                n = len(results)
                return {
                    'text':    f"Voici {cfg.get('title', 'le graphique')} avec {n} element{'s' if n > 1 else ''}.",
                    'chart':   chart,
                    'data':    results,
                    'sources': self._tables(cfg['sql']),
                    'intent':  'data_visualization',
                }
            except Exception as e:
                print(f"[ChatbotAgent._handle_chart.keyword] {e}")

        sql_prompt = (
            "Tu es un generateur SQL pour Orange Tunisie.\n"
            f"{_SCHEMA}\n\n"
            f"L utilisateur veut un graphique : \"{message}\"\n\n"
            "Reponds UNIQUEMENT avec du JSON valide, sans markdown :\n"
            '{"sql":"SELECT label_col, value_col FROM ... LIMIT 10",'
            '"chart_type":"bar|line|pie|doughnut",'
            '"title":"Titre","label_column":"col","value_column":"col"}'
        )
        try:
            cfg = self._ask_json(sql_prompt)
            if not cfg:
                return self._fallback()
            results = self.sql_exec.execute_safe(cfg['sql'])
            chart   = self.chart_gen.build_chart_config(results, cfg)
            n = len(results)
            text = f"Voici {cfg.get('title', 'le graphique')} avec {n} element{'s' if n > 1 else ''}."
            return {
                'text':    text,
                'chart':   chart,
                'data':    results,
                'sources': self._tables(cfg['sql']),
                'intent':  'data_visualization',
            }
        except Exception as e:
            print(f"[ChatbotAgent._handle_chart] {e}")
            return self._fallback()

    def _handle_help(self, message: str, history) -> dict:
        prompt = (
            f"{_REGLES}\n\n"
            f"L utilisateur a une question sur l application : \"{message}\"\n\n"
            "L application Orange Tunisie comporte 4 pages : Accueil, Dashboard (performances + "
            "KPIs commerciaux), Produits (catalogue + top ventes), Objectifs (taux realisation "
            "par boutique et canal). Le mode sombre se bascule via le bouton en bas de la sidebar. "
            "La connexion se fait avec email et mot de passe. Chaque page affiche des interpretations IA.\n\n"
            "Reponds en 2 phrases max, guide vers la bonne page."
        )
        return self._ok(self._ask_text(prompt), intent='app_help', sources=['application'])

    def _handle_business(self, message: str, history) -> dict:
        prompt = (
            f"{_REGLES}\n\n"
            f"Question business Orange Tunisie : \"{message}\"\n\n"
            "Contexte : environ 63 000 contrats vendus, taux de realisation des objectifs ~35%, "
            "canal Franchise dominant (~51% des ventes), boutiques reparties sur plusieurs regions.\n\n"
            "Donne une analyse courte + une recommandation concrete en 3 phrases max."
        )
        return self._ok(self._ask_text(prompt), intent='general_business', sources=['analyse_business'])

    def _handle_general(self, message: str, history) -> dict:
        prompt = f"{_REGLES}\n\nUtilisateur : \"{message}\"\n\nReponds brievement."
        return self._ok(self._ask_text(prompt), intent='general')

    # ------------------------------------------------------------------ #
    # Helpers Gemini
    # ------------------------------------------------------------------ #

    def _call(self, prompt: str) -> str:
        if not self._client:
            return "Analyse indisponible (cle API manquante — ANTHROPIC_API_KEY)."
        try:
            response = self._client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=MAX_TOKENS,
                messages=[{"role": "user", "content": prompt}]
            )
            txt = response.content[0].text.strip()
            for ch in ('**', '##', '#', '*', '`'):
                txt = txt.replace(ch, '')
            return txt
        except Exception as e:
            print(f"[ChatbotAgent._call] {e}")
            return "Je ne suis pas disponible pour le moment."

    def _ask_text(self, prompt: str) -> str:
        return self._call(prompt)

    def _ask_json(self, prompt: str) -> dict | None:
        raw = self._call(prompt)
        try:
            txt = raw.strip()
            if '```json' in txt:
                txt = txt.split('```json')[1].split('```')[0]
            elif '```' in txt:
                txt = txt.split('```')[1].split('```')[0]
            return json.loads(txt.strip())
        except Exception:
            return None

    # ------------------------------------------------------------------ #
    # Helpers filtres (mois / annee / canal / famille)
    # ------------------------------------------------------------------ #

    def _extract_filters(self, msg_lower: str, msg_orig: str) -> dict:
        """Detecte mois, annee, canal, famille dans la question."""
        return {
            'mois':    _detect_mois(msg_lower),
            'annee':   _detect_annee(msg_lower),
            'canal':   _detect_canal(msg_orig),
            'famille': _detect_famille(msg_lower),
        }

    def _filter_desc(self, f: dict) -> str:
        """Texte descriptif des filtres pour les reponses."""
        parts = []
        if f['mois'] and f['annee']:
            parts.append(f"{_NOMS_MOIS[f['mois']]} {f['annee']}")
        elif f['mois']:
            parts.append(f"mois de {_NOMS_MOIS[f['mois']]}")
        elif f['annee']:
            parts.append(str(f['annee']))
        if f['canal']:
            parts.append(f"canal {f['canal']}")
        if f['famille']:
            parts.append(f"famille {f['famille']}")
        return f" ({', '.join(parts)})" if parts else ""

    def _kw_joins_where(self, f: dict,
                         has_boutique: bool = False,
                         has_produit: bool = False,
                         alias_f: str = 'f',
                         alias_b: str = 'b',
                         alias_p: str = 'p') -> tuple[str, str]:
        """
        Construit les JOINs additionnels et conditions WHERE pour fact_ventes.
        Retourne (joins_sql, where_conditions_sql).
        where_conditions_sql est vide '' si aucun filtre detecte.
        """
        joins, conds = [], []

        # Jointures conditionnelles (si pas deja presentes)
        if f['canal'] and not has_boutique:
            joins.append(
                f"JOIN dim_boutique {alias_b} ON {alias_f}.boutique_key = {alias_b}.boutique_key"
            )
        if f['famille'] and not has_produit:
            joins.append(
                f"JOIN dim_produit {alias_p} ON TRIM({alias_f}.product_number::text) = TRIM({alias_p}.product_code::text)"
            )

        # Conditions WHERE
        if f['mois']:
            conds.append(f"EXTRACT(MONTH FROM {alias_f}.date_vente) = {f['mois']}")
        if f['annee']:
            conds.append(f"EXTRACT(YEAR FROM {alias_f}.date_vente) = {f['annee']}")
        if f['canal']:
            c_sql = f['canal'].replace("'", "''")
            conds.append(f"{alias_b}.canal_vente = '{c_sql}'")
        if f['famille'] and f['famille'] in _FAMILLE_SQL:
            conds.append(_FAMILLE_SQL[f['famille']])

        return (" ".join(joins), " AND ".join(conds))

    # ------------------------------------------------------------------ #
    # Detection du LIMIT (nombre explicite ou singulier/pluriel)
    # ------------------------------------------------------------------ #

    @staticmethod
    def _detect_limit(msg: str, default: int = 5) -> int:
        """
        Retourne le LIMIT à appliquer selon la formulation :
          - nombre explicite après "top" : "top 3 vendeurs" → 3
          - nombre avant l'entité        : "5 meilleurs vendeurs" → 5
          - singulier sans nombre        : "top vendeur" → 1
          - pluriel sans nombre          : "top vendeurs" → default (5)
        """
        # Nombre explicite après "top" : "top 10", "top 3"
        m = re.search(r'\btop\s+(\d+)\b', msg)
        if m:
            return int(m.group(1))
        # Nombre avant un mot-clé entité : "5 meilleurs vendeurs", "3 boutiques"
        m = re.search(
            r'\b(\d+)\s+(?:meilleur[se]?|premier[se]?|vendeur|vendeurs|'
            r'boutique|boutiques|agent|agents|commercial|commerciaux)\b', msg
        )
        if m:
            return int(m.group(1))
        # Singulier explicite (sans 's' final ni nombre) → LIMIT 1
        if re.search(
            r'\b(?:top|meilleur|premier|le\s+meilleur|la\s+meilleure)\s+'
            r'(?:vendeur|boutique|agent|commercial|conseiller)\b',
            msg
        ):
            return 1
        return default

    # ------------------------------------------------------------------ #
    # Keyword SQL — avec detection de filtres
    # ------------------------------------------------------------------ #

    def _keyword_sql(self, message: str) -> dict | None:
        """SQL direct base sur mots-cles avec detection mois/annee/canal/famille."""
        msg = message.lower()
        f   = self._extract_filters(msg, message)
        fdesc = self._filter_desc(f)
        limit = self._detect_limit(msg)

        def _has(words):
            return any(w in msg for w in words)

        _boutique_kw = ['boutique', 'magasin', 'point de vente', 'agence']
        _vendeur_kw  = ['vendeur', 'commercial', 'agent', 'conseiller']
        _top_kw      = ['top', 'meilleur', 'mieux', 'plus', 'premier',
                         'classement', 'rang', 'quelle', 'quel', 'liste']
        _ventes_kw   = ['vente', 'ventes', 'contrat', 'contrats', 'vendu', 'vend']
        _paiement_kw = ['taux', 'paiement', 'facture', 'impaye', 'recouvrement', 'paye']
        _canal_kw    = ['canal', 'franchise', 'repartition', 'distribution']
        _objectif_kw = ['objectif', 'realisation', 'cible', 'atteindre']
        _region_kw   = ['region', 'zone', 'geographie', 'localisation']
        _produit_kw  = ['produit', 'offre', 'forfait', 'sim', 'mobile', 'fixe']
        _diffic_kw   = ['difficulte', 'difficile', 'sous-performance', 'manque', 'retard', 'en retard']

        # ── Top vendeurs ──────────────────────────────────────────────
        if _has(_vendeur_kw) and _has(_top_kw + _ventes_kw):
            extra_j, extra_w = self._kw_joins_where(f, has_boutique=False, has_produit=False)
            where = f"WHERE {extra_w}" if extra_w else ""
            grp   = "v.seller_name, b.canal_vente" if f['canal'] else "v.seller_name"
            sel_canal = ", b.canal_vente AS canal" if f['canal'] else ""
            boutique_j = ("JOIN dim_boutique b ON f.boutique_key = b.boutique_key "
                          if f['canal'] else "")
            produit_j  = ("JOIN dim_produit p ON TRIM(f.product_number::text) = TRIM(p.product_code::text) "
                          if f['famille'] else "")
            return {
                'sql': (
                    f"SELECT v.seller_name AS vendeur{sel_canal}, COUNT(*) AS nb_ventes, "
                    "ROUND(100.0 * COUNT(CASE WHEN f.first_month_bill > 0 THEN 1 END) "
                    "/ NULLIF(COUNT(*),0)::numeric,1) AS taux_paiement_pct "
                    "FROM fact_ventes f "
                    f"JOIN dim_vendeur v ON f.vendeur_key = v.vendeur_key "
                    f"{boutique_j}{produit_j}"
                    f"{where} "
                    f"GROUP BY {grp} ORDER BY nb_ventes DESC LIMIT {limit}"
                ),
                'description': f'Top {limit} vendeur{"s" if limit != 1 else ""} par nombre de ventes{fdesc}',
                'expected_format': 'table',
            }

        # ── Top boutiques ─────────────────────────────────────────────
        if _has(_boutique_kw) and _has(_top_kw + _ventes_kw):
            extra_j, extra_w = self._kw_joins_where(
                f, has_boutique=True, has_produit=False)
            produit_j = ("JOIN dim_produit p ON TRIM(f.product_number::text) = TRIM(p.product_code::text) "
                         if f['famille'] else "")
            where = f"WHERE {extra_w}" if extra_w else ""
            return {
                'sql': (
                    "SELECT b.entity_name AS boutique, b.canal_vente AS canal, "
                    "COUNT(*) AS nb_ventes "
                    "FROM fact_ventes f "
                    f"JOIN dim_boutique b ON f.boutique_key = b.boutique_key "
                    f"{produit_j}"
                    f"{where} "
                    f"GROUP BY b.entity_name, b.canal_vente ORDER BY nb_ventes DESC LIMIT {limit}"
                ),
                'description': f'Top {limit} boutique{"s" if limit != 1 else ""} par nombre de ventes{fdesc}',
                'expected_format': 'table',
            }

        # ── Boutiques en difficulte ───────────────────────────────────
        if _has(_boutique_kw) and _has(_diffic_kw):
            canal_cond = f"AND b.canal_vente = '{f['canal']}'" if f['canal'] else ""
            mois_cond  = (f"AND EXTRACT(MONTH FROM fo.date_objectif) = {f['mois']}"
                          if f['mois'] else "")
            annee_cond = (f"AND EXTRACT(YEAR FROM fo.date_objectif) = {f['annee']}"
                          if f['annee'] else "")
            return {
                'sql': (
                    "SELECT b.entity_name AS boutique, b.canal_vente AS canal, "
                    "ROUND(100.0 * SUM(fo.montant_objectif) / NULLIF(SUM(fo.montant_objectif),0) * 0, 2) AS taux_pct "
                    "FROM fact_objectifs fo "
                    "JOIN dim_boutique b ON fo.boutique_key = b.boutique_key "
                    f"WHERE fo.montant_objectif > 0 {canal_cond} {mois_cond} {annee_cond} "
                    "GROUP BY b.entity_name, b.canal_vente "
                    "ORDER BY taux_pct ASC LIMIT 10"
                ),
                'description': f'Boutiques en difficulte{fdesc}',
                'expected_format': 'table',
            }

        # ── Boutiques par region ──────────────────────────────────────
        if _has(_boutique_kw) and _has(_region_kw):
            extra_j, extra_w = self._kw_joins_where(
                f, has_boutique=True, has_produit=False, alias_f='f')
            produit_j = ("JOIN dim_produit p ON TRIM(f.product_number::text) = TRIM(p.product_code::text) "
                         if f['famille'] else "")
            where = f"WHERE {extra_w}" if extra_w else ""
            return {
                'sql': (
                    "SELECT COALESCE(b.region, 'Non specifie') AS region, "
                    "COUNT(DISTINCT b.boutique_key) AS nb_boutiques, "
                    "COUNT(f.ventes_id) AS nb_ventes "
                    "FROM dim_boutique b "
                    f"LEFT JOIN fact_ventes f ON b.boutique_key = f.boutique_key "
                    f"{produit_j} {where} "
                    "GROUP BY b.region ORDER BY nb_ventes DESC"
                ),
                'description': f'Boutiques et ventes par region{fdesc}',
                'expected_format': 'table',
            }

        # ── Total ventes ──────────────────────────────────────────────
        if 'total' in msg and _has(_ventes_kw):
            extra_j, extra_w = self._kw_joins_where(f, has_boutique=False, has_produit=False)
            where = f"WHERE {extra_w}" if extra_w else ""
            return {
                'sql': (
                    f"SELECT COUNT(*) AS total_ventes "
                    f"FROM fact_ventes f {extra_j} {where}"
                ),
                'description': f'Total de ventes{fdesc}',
                'expected_format': 'scalar',
            }

        # ── Taux paiement / factures ──────────────────────────────────
        if _has(_paiement_kw):
            extra_j, extra_w = self._kw_joins_where(f, has_boutique=False, has_produit=False)
            where = f"WHERE {extra_w}" if extra_w else ""
            return {
                'sql': (
                    "SELECT COUNT(*) AS total_factures, "
                    "COUNT(CASE WHEN first_month_bill > 0 THEN 1 END) AS factures_payees, "
                    "ROUND(100.0 * COUNT(CASE WHEN first_month_bill > 0 THEN 1 END) "
                    "/ NULLIF(COUNT(*),0)::numeric,2) AS taux_1ere_facture_pct "
                    f"FROM fact_ventes f {extra_j} {where}"
                ),
                'description': f'Taux de paiement des factures{fdesc}',
                'expected_format': 'table',
            }

        # ── Ventes par canal ──────────────────────────────────────────
        if _has(_canal_kw):
            extra_j, extra_w = self._kw_joins_where(
                f, has_boutique=True, has_produit=False)
            produit_j = ("JOIN dim_produit p ON TRIM(f.product_number::text) = TRIM(p.product_code::text) "
                         if f['famille'] else "")
            # Pour ventes par canal, on ne filtre pas sur canal (on veut tous les canaux)
            conds_no_canal = []
            if f['mois']:
                conds_no_canal.append(f"EXTRACT(MONTH FROM f.date_vente) = {f['mois']}")
            if f['annee']:
                conds_no_canal.append(f"EXTRACT(YEAR FROM f.date_vente) = {f['annee']}")
            if f['famille'] and f['famille'] in _FAMILLE_SQL:
                conds_no_canal.append(_FAMILLE_SQL[f['famille']])
            where = f"WHERE {' AND '.join(conds_no_canal)}" if conds_no_canal else ""
            return {
                'sql': (
                    "SELECT COALESCE(b.canal_vente,'Non specifie') AS canal, "
                    "COUNT(*) AS nb_ventes, "
                    "ROUND(100.0 * COUNT(*) / NULLIF((SELECT COUNT(*) FROM fact_ventes),0)::numeric,1) AS part_pct "
                    f"FROM fact_ventes f "
                    f"JOIN dim_boutique b ON f.boutique_key = b.boutique_key "
                    f"{produit_j} {where} "
                    "GROUP BY b.canal_vente ORDER BY nb_ventes DESC"
                ),
                'description': f'Repartition des ventes par canal{fdesc}',
                'expected_format': 'table',
            }

        # ── Objectifs / taux realisation ──────────────────────────────
        if _has(_objectif_kw):
            canal_cond = (f"AND b.canal_vente = '{f['canal']}'"
                          if f['canal'] else "")
            mois_cond  = (f"AND EXTRACT(MONTH FROM fo.date_objectif) = {f['mois']}"
                          if f['mois'] else "")
            annee_cond = (f"AND EXTRACT(YEAR FROM fo.date_objectif) = {f['annee']}"
                          if f['annee'] else "")
            has_filter = bool(f['canal'] or f['mois'] or f['annee'])
            if has_filter:
                return {
                    'sql': (
                        "SELECT b.canal_vente AS canal, "
                        "ROUND(SUM(fo.montant_objectif)::numeric, 0) AS objectif_total "
                        "FROM fact_objectifs fo "
                        "JOIN dim_boutique b ON fo.boutique_key = b.boutique_key "
                        f"WHERE fo.montant_objectif IS NOT NULL {canal_cond} {mois_cond} {annee_cond} "
                        "GROUP BY b.canal_vente ORDER BY objectif_total DESC"
                    ),
                    'description': f'Objectifs{fdesc}',
                    'expected_format': 'table',
                }
            return {
                'sql': (
                    "SELECT ROUND((SELECT COUNT(*) FROM fact_ventes)::numeric "
                    "/ NULLIF((SELECT SUM(montant_objectif) FROM fact_objectifs),0) * 100, 2) "
                    "AS taux_realisation_pct"
                ),
                'description': 'Taux de realisation des objectifs',
                'expected_format': 'scalar',
            }

        # ── Top produits / offres ─────────────────────────────────────
        if _has(_produit_kw) and _has(_top_kw + _ventes_kw):
            extra_j, extra_w = self._kw_joins_where(
                f, has_boutique=False, has_produit=True)
            base_w = "p.product_name IS NOT NULL"
            full_w = f"{base_w} AND {extra_w}" if extra_w else base_w
            return {
                'sql': (
                    "SELECT p.product_name AS produit, p.product_type AS type, "
                    "COUNT(*) AS nb_ventes "
                    "FROM fact_ventes f "
                    f"JOIN dim_produit p ON TRIM(f.product_number::text) = TRIM(p.product_code::text) "
                    f"{extra_j} "
                    f"WHERE {full_w} "
                    f"GROUP BY p.product_name, p.product_type ORDER BY nb_ventes DESC LIMIT {limit}"
                ),
                'description': f'Top {limit} produit{"s" if limit != 1 else ""} les plus vendus{fdesc}',
                'expected_format': 'table',
            }

        return None

    def _keyword_chart(self, message: str) -> dict | None:
        """Graphiques directs pour les demandes courantes, avec filtres."""
        msg = message.lower()
        f   = self._extract_filters(msg, message)
        fdesc = self._filter_desc(f)

        if 'canal' in msg and 'vente' in msg:
            extra_j, extra_w = self._kw_joins_where(
                {**f, 'canal': None},  # pas de filtre canal ici — on veut tous les canaux
                has_boutique=True, has_produit=False)
            conds = []
            if f['mois']:
                conds.append(f"EXTRACT(MONTH FROM f.date_vente) = {f['mois']}")
            if f['annee']:
                conds.append(f"EXTRACT(YEAR FROM f.date_vente) = {f['annee']}")
            if f['famille'] and f['famille'] in _FAMILLE_SQL:
                conds.append(_FAMILLE_SQL[f['famille']])
                extra_j = "JOIN dim_produit p ON TRIM(f.product_number::text) = TRIM(p.product_code::text)"
            where = f"WHERE {' AND '.join(conds)}" if conds else ""
            return {
                'sql': (
                    "SELECT COALESCE(b.canal_vente, 'Non specifie') AS canal, COUNT(*) AS nb_ventes "
                    "FROM fact_ventes f "
                    f"JOIN dim_boutique b ON f.boutique_key = b.boutique_key {extra_j} "
                    f"{where} "
                    "GROUP BY b.canal_vente ORDER BY nb_ventes DESC"
                ),
                'chart_type': 'bar',
                'title': f'Ventes par canal{fdesc}',
                'label_column': 'canal',
                'value_column': 'nb_ventes',
            }

        if ('produit' in msg or 'offre' in msg) and ('top' in msg or 'vente' in msg):
            extra_j, extra_w = self._kw_joins_where(
                f, has_boutique=False, has_produit=True)
            base_w = "p.product_name IS NOT NULL"
            full_w = f"{base_w} AND {extra_w}" if extra_w else base_w
            return {
                'sql': (
                    "SELECT p.product_name AS produit, COUNT(*) AS nb_ventes "
                    "FROM fact_ventes f "
                    f"JOIN dim_produit p ON TRIM(f.product_number::text) = TRIM(p.product_code::text) "
                    f"{extra_j} WHERE {full_w} "
                    "GROUP BY p.product_name ORDER BY nb_ventes DESC LIMIT 10"
                ),
                'chart_type': 'bar',
                'title': f'Top produits vendus{fdesc}',
                'label_column': 'produit',
                'value_column': 'nb_ventes',
            }

        if 'paiement' in msg or 'facture' in msg:
            extra_j, extra_w = self._kw_joins_where(f, has_boutique=False, has_produit=False)
            base_w = "date_vente IS NOT NULL"
            full_w = f"{base_w} AND {extra_w}" if extra_w else base_w
            return {
                'sql': (
                    "SELECT TO_CHAR(DATE_TRUNC('month', f.date_vente), 'YYYY-MM') AS mois, "
                    "ROUND(100.0 * COUNT(CASE WHEN first_month_bill = 1 THEN 1 END) / NULLIF(COUNT(*),0)::numeric, 2) AS taux "
                    f"FROM fact_ventes f {extra_j} WHERE {full_w} "
                    "GROUP BY DATE_TRUNC('month', f.date_vente) ORDER BY mois"
                ),
                'chart_type': 'line',
                'title': f'Evolution du taux de paiement{fdesc}',
                'label_column': 'mois',
                'value_column': 'taux',
            }
        if 'objectif' in msg:
            return {
                'sql': (
                    "SELECT c.canal, ROUND(COALESCE(v.realisation,0) / NULLIF(o.objectif,0) * 100, 2) AS taux "
                    "FROM (SELECT DISTINCT COALESCE(canal_vente, 'Non specifie') AS canal FROM dim_boutique) c "
                    "LEFT JOIN (SELECT COALESCE(b.canal_vente, 'Non specifie') AS canal, SUM(o.montant_objectif) AS objectif "
                    "FROM fact_objectifs o JOIN dim_boutique b ON o.boutique_key = b.boutique_key GROUP BY b.canal_vente) o "
                    "ON c.canal = o.canal "
                    "LEFT JOIN (SELECT COALESCE(b.canal_vente, 'Non specifie') AS canal, COUNT(*) AS realisation "
                    "FROM fact_ventes f JOIN dim_boutique b ON f.boutique_key = b.boutique_key GROUP BY b.canal_vente) v "
                    "ON c.canal = v.canal ORDER BY taux DESC NULLS LAST"
                ),
                'chart_type': 'bar',
                'title': 'Taux objectif par canal',
                'label_column': 'canal',
                'value_column': 'taux',
            }
        return None

    def _format_results(self, _question: str, results: list, description: str) -> str:
        """Formatte les resultats SQL sans appel API — utilisable offline."""
        if not results:
            return "Aucune donnee trouvee."
        first = results[0]
        keys = list(first.keys())

        # Valeur scalaire unique
        if len(results) == 1 and len(keys) == 1:
            val = first[keys[0]]
            if isinstance(val, float):
                val = round(val, 2)
            label = description or keys[0].replace('_', ' ')
            formatted = f"{val:,.0f}".replace(',', ' ') if isinstance(val, (int, float)) else str(val)
            return f"{label.capitalize()} : {formatted}"

        # Table de resultats — une ligne par entree, colonnes identifiees
        title = (description or "Resultats") + " :"
        lines = [title]
        for i, row in enumerate(results[:10], 1):
            parts = []
            for k, v in row.items():
                if isinstance(v, float):
                    v = f"{v:,.1f}".replace(',', ' ')
                elif isinstance(v, int):
                    v = f"{v:,}".replace(',', ' ')
                parts.append(str(v) if v is not None else "—")
            lines.append(f"{i}. " + "  |  ".join(parts))
        if len(results) > 10:
            lines.append(f"... et {len(results) - 10} autres resultats.")
        return "\n".join(lines)

    def _natural_answer(self, question: str, results: list) -> str:
        prompt = (
            f"{_REGLES}\n\n"
            f"Question : \"{question}\"\n"
            f"Donnees SQL obtenues : {json.dumps(results[:5], default=str, ensure_ascii=False)}\n\n"
            "Reponds en 2 phrases avec les chiffres. Format milliers avec espace."
        )
        return self._ask_text(prompt)

    # ------------------------------------------------------------------ #
    # Utilitaires
    # ------------------------------------------------------------------ #

    @staticmethod
    def _tables(sql: str) -> list:
        found = re.findall(r'(?:FROM|JOIN)\s+(\w+)', sql, re.IGNORECASE)
        seen, result = set(), []
        for t in found:
            if t not in seen:
                seen.add(t)
                result.append(t)
        return result

    @staticmethod
    def _ok(text: str, intent: str = 'general', sources: list = None) -> dict:
        return {'text': text, 'chart': None, 'data': None,
                'sources': sources or [], 'intent': intent}

    @staticmethod
    def _fallback() -> dict:
        return {'text': "Je n'ai pas pu traiter cette question. Pouvez-vous la reformuler ?",
                'chart': None, 'data': None, 'sources': [], 'intent': 'fallback'}

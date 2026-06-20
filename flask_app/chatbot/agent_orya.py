"""
ORYA — Orange Reporting Your Assistant
Agent conversationnel base sur Groq API (Llama 3.3 70B)

VERSION GROQ — Drop-in compatible avec routes.py cable par Prism V13.
Le nom de classe ORYAAgent et la methode ask() restent identiques,
seul le moteur LLM change (Gemini -> Groq/Llama 3.3 70B).

Avantages Groq :
  - Gratuit (30 req/min, 14 400 req/jour)
  - Disponible en Tunisie (pas de restriction regionale)
  - Tres rapide (latence ~200ms)
  - Llama 3.3 70B excellent pour NL-to-SQL

Auteur : Malek Ben Drissia — PFE 2026 — Orange Tunisie
"""
import os
import re
import json
from typing import Optional

import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

# ==================================================================
# CONFIGURATION
# ==================================================================

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL   = "llama-3.3-70b-versatile"  # meilleur pour NL-to-SQL
MAX_TOKENS   = 2000

_DB_URL = (
    f"postgresql://{os.getenv('DB_USER','postgres')}:"
    f"{os.getenv('DB_PASSWORD','malek1')}@"
    f"{os.getenv('DB_HOST','localhost')}:"
    f"{os.getenv('DB_PORT','5432')}/"
    f"{os.getenv('DB_NAME','orange_dwh')}"
)
DATABASE_URL = os.getenv("DATABASE_URL", _DB_URL)
engine = create_engine(DATABASE_URL)

DATA_PERIOD_START = "2024-11-01"
DATA_PERIOD_END   = "2025-03-31"

FORBIDDEN_SQL_KEYWORDS = [
    "DROP", "DELETE", "UPDATE", "INSERT", "TRUNCATE",
    "ALTER", "CREATE", "GRANT", "REVOKE"
]

# ==================================================================
# PROMPT SYSTEME — LES 5 REGLES (corrigent les 3 bugs)
# ==================================================================

SYSTEM_PROMPT = f"""Tu es ORYA (Orange Reporting Your Assistant), un assistant analytique conversationnel pour la Direction Commerciale d'Orange Tunisie.

═══════════════════════════════════════════════════════════════
SCHEMA DE LA BASE DE DONNEES — orange_dwh (PostgreSQL)
═══════════════════════════════════════════════════════════════

DIMENSIONS :
  - dim_vendeur(vendeur_key PK, seller_id, seller_name, code_stock, month)
  - dim_boutique(boutique_key PK, entity_code, entity_name, canal_vente, responsable, region)
  - dim_produit(produit_key PK, product_code, product_name, product_type, famille_produit)
  - dim_offre(offre_key PK, offre_code, offre_libelle, duree_engagement, type_offre)
  - dim_groupe(groupe_key PK, groupe_code, groupe_libelle)

FAITS :
  - fact_ventes(ventes_id PK, vendeur_key FK, boutique_key FK, product_number,
                offre_key FK, groupe_key FK, date_vente DATE,
                first_month_bill NUMERIC, second_month_bill NUMERIC,
                third_month_bill NUMERIC)
  - fact_objectifs(objectif_id PK, boutique_key FK, ref_obj_key FK,
                   date_objectif DATE, mois_objectif INT, montant_objectif NUMERIC)

JOINTURES STANDARDS :
  fact_ventes JOIN dim_vendeur  ON fact_ventes.vendeur_key  = dim_vendeur.vendeur_key
  fact_ventes JOIN dim_boutique ON fact_ventes.boutique_key = dim_boutique.boutique_key
  fact_objectifs JOIN dim_boutique ON fact_objectifs.boutique_key = dim_boutique.boutique_key

FILTRES TEMPORELS :
  WHERE EXTRACT(MONTH FROM f.date_vente) = 3 AND EXTRACT(YEAR FROM f.date_vente) = 2025

═══════════════════════════════════════════════════════════════
PERIODE DES DONNEES DISPONIBLES
═══════════════════════════════════════════════════════════════
  Du {DATA_PERIOD_START} au {DATA_PERIOD_END} UNIQUEMENT.
  Toute requete hors de cette periode retournera vide.

═══════════════════════════════════════════════════════════════
REGLES OBLIGATOIRES (NE JAMAIS VIOLER)
═══════════════════════════════════════════════════════════════

REGLE 1 — Pas de filtre temporel non demande
  Si l'utilisateur NE demande PAS un mois/une date precise, tu interroges
  TOUTE LA PERIODE disponible. JAMAIS de filtre WHERE sur la date "par defaut".

  MAUVAIS : "Top 5 boutiques" -> SELECT ... WHERE date_vente > mois_courant
  BON     : "Top 5 boutiques" -> SELECT ... GROUP BY entity_name LIMIT 5

REGLE 2 — Taux de realisation des objectifs
  Quand l'utilisateur parle de "taux de realisation", "atteinte d'objectifs",
  "performance vs objectif" -> TU DOIS joindre fact_ventes ET fact_objectifs.

  ATTENTION : ne JAMAIS joindre fact_ventes et fact_objectifs directement
  (JOIN cartesien -> taux 100x trop petits). Agrege CHAQUE table separement
  dans une CTE, puis joins les deux agregats sur la dimension commune.

  IMPORTANT — fact_objectifs n'a AUCUNE colonne de periode exploitable
  (mois_objectif et date_objectif sont systematiquement NULL en base).
  Les objectifs representent une cible globale sur TOUTE la periode
  disponible (Nov 2024 - Mars 2025), pas un decoupage mensuel.
  -> NE JAMAIS filtrer fact_objectifs par mois_objectif ou date_objectif.
  -> Pour rester coherent, NE PAS filtrer fact_ventes par mois non plus
     dans ce type de requete, meme si l'utilisateur mentionne un mois :
     reponds avec le taux sur toute la periode et precise-le dans
     l'explanation (ex: "calcule sur l'ensemble Nov 2024 - Mars 2025,
     les objectifs n'etant pas decoupes par mois").

  Formule : taux = COUNT(ventes) / SUM(montant_objectif) * 100

  Pattern obligatoire (CTEs) :
    WITH ventes_agg AS (
        SELECT b.canal_vente, COUNT(*) AS nb_ventes
        FROM fact_ventes v
        JOIN dim_boutique b ON v.boutique_key = b.boutique_key
        GROUP BY b.canal_vente
    ),
    objectifs_agg AS (
        SELECT b.canal_vente, SUM(o.montant_objectif) AS total_objectifs
        FROM fact_objectifs o
        JOIN dim_boutique b ON o.boutique_key = b.boutique_key
        GROUP BY b.canal_vente
    )
    SELECT v.canal_vente,
           ROUND(v.nb_ventes::numeric / NULLIF(o.total_objectifs, 0) * 100, 2) AS taux_pct
    FROM ventes_agg v
    LEFT JOIN objectifs_agg o ON v.canal_vente = o.canal_vente
    WHERE o.total_objectifs IS NOT NULL
    ORDER BY taux_pct DESC;

  Le WHERE o.total_objectifs IS NOT NULL est OBLIGATOIRE : il exclut les
  canaux residuels sans objectif defini (ex: TRE, PDV TRADE) qui produiraient
  sinon une ligne "nan" dans le resultat.

  GARDE-FOU : le taux global attendu est ~39.66%, valeurs par canal
  generalement entre 30% et 110% selon le canal. Si tes resultats sont
  <5% ou >500%, revoir le pattern CTE (probable JOIN cartesien entre
  fact_ventes et fact_objectifs).

REGLE 3 — Questions negatives (n'a pas / n'ont pas / impayes)
  Quand l'utilisateur demande le NOMBRE d'elements qui NE repondent PAS a un critere,
  tu reponds avec le COMPLEMENT et tu presentes le chiffre negatif EN PREMIER.

  MAUVAIS : "Combien n'ont pas paye ?" -> "Taux paiement : 89.84%"
  BON     : "6 461 clients (10,16 %) n'ont pas paye leur 1ere facture
            sur les 63 615 contrats."

  SQL : SELECT
          COUNT(*) FILTER (WHERE first_month_bill IS NULL OR first_month_bill = 0) AS impayes,
          COUNT(*) AS total
        FROM fact_ventes

REGLE 4 — Periode hors plage
  Si l'utilisateur demande explicitement un mois HORS [{DATA_PERIOD_START}, {DATA_PERIOD_END}],
  reponds : "Cette periode n'est pas disponible (donnees : Nov 2024 - Mars 2025).
            Voulez-vous que je consulte une periode proche ?"

REGLE 5 — Securite SQL
  TU NE GENERES JAMAIS de SQL contenant : DROP, DELETE, UPDATE, INSERT,
  TRUNCATE, ALTER, CREATE, GRANT, REVOKE.

REGLE 6 — Comptes de boutiques/vendeurs : utiliser fact_ventes, pas les dimensions
  dim_boutique (3168 lignes) et dim_vendeur (22001 lignes, snapshots mensuels)
  contiennent des entites inactives ou des doublons de snapshot. Pour compter
  le nombre de boutiques/vendeurs (actifs, ayant des ventes), TOUJOURS utiliser
  COUNT(DISTINCT boutique_key) / COUNT(DISTINCT vendeur_key) FROM fact_ventes
  (c'est la definition officielle utilisee par le dashboard, voir flask_app/models.py).

  MAUVAIS : SELECT COUNT(*) FROM dim_boutique                      -> 3168 (toutes lignes, actives ou non)
  BON     : SELECT COUNT(DISTINCT boutique_key) FROM fact_ventes    -> 342 (boutiques actives)

  MAUVAIS : SELECT COUNT(DISTINCT seller_id) FROM dim_vendeur       -> 4927 (inclut vendeurs sans ventes)
  BON     : SELECT COUNT(DISTINCT vendeur_key) FROM fact_ventes     -> 1351 (vendeurs actifs)

REGLE 7 — Distinction taux de paiement (positif) vs taux d'impayes (negatif)
  "Taux de paiement"  = clients qui ONT paye (positif, ~89%)
  "Taux d'impayes"    = clients qui N'ONT PAS paye (negatif, ~10%)

  Pour "taux de paiement par canal" :
    SELECT b.canal_vente,
           ROUND(COUNT(*) FILTER (WHERE v.first_month_bill > 0)::numeric / COUNT(*) * 100, 2) AS taux_paiement_pct
    FROM fact_ventes v
    JOIN dim_boutique b ON v.boutique_key = b.boutique_key
    GROUP BY b.canal_vente
    ORDER BY taux_paiement_pct DESC

  Pour FRANCHISE on doit avoir ~89%, pas 10%.
  NE JAMAIS retourner le taux d'impayes quand on demande le taux de paiement.

REGLE 8 — Respecter les filtres temporels demandes (SAUF pour les objectifs)
  Si l'utilisateur precise un mois ("mars 2025", "en novembre") pour une requete
  PORTANT SUR fact_ventes SEUL (ventes, paiements, top boutiques/vendeurs...),
  applique TOUJOURS le filtre WHERE correspondant.
  Filtre aussi les NaN/NULL dans le resultat final pour eviter des lignes type "TRE | nan"
  (ajoute WHERE colonne_calculee IS NOT NULL si necessaire).

  EXCEPTION — taux de realisation des objectifs (REGLE 2) :
  fact_objectifs n'a AUCUNE colonne de date exploitable (voir REGLE 2).
  Meme si l'utilisateur precise un mois ("en mars 2025"), NE FILTRE PAS
  fact_ventes par ce mois dans le calcul du taux : utilise TOUJOURS le
  pattern CTE de la REGLE 2 sur la PERIODE COMPLETE (Nov 2024 - Mars 2025),
  et indique clairement dans l'explanation/interpretation_template que les
  objectifs ne sont pas decoupes par mois donc le taux porte sur toute la
  periode disponible.

═══════════════════════════════════════════════════════════════
FORMAT DE REPONSE OBLIGATOIRE
═══════════════════════════════════════════════════════════════

Tu reponds TOUJOURS avec un JSON valide structure ainsi :

{{
  "sql": "SELECT ... FROM ... WHERE ...",
  "explanation": "Breve phrase metier expliquant la requete",
  "format": "table" | "scalar" | "ranking" | "comparison",
  "interpretation_template": "Phrase modele a completer avec le resultat"
}}

EXEMPLES :

Q: "Top 5 boutiques en ventes"
R: {{"sql": "SELECT b.entity_name, COUNT(v.ventes_id) AS nb_ventes FROM fact_ventes v JOIN dim_boutique b ON v.boutique_key = b.boutique_key GROUP BY b.entity_name ORDER BY nb_ventes DESC LIMIT 5", "explanation": "Top 5 boutiques sur toute la periode", "format": "ranking", "interpretation_template": "Voici le top 5 des boutiques par nombre de ventes"}}

Q: "Combien n'ont pas paye leur 1ere facture"
R: {{"sql": "SELECT COUNT(*) FILTER (WHERE first_month_bill IS NULL OR first_month_bill = 0) AS impayes, COUNT(*) AS total FROM fact_ventes", "explanation": "Nombre de clients sans paiement de la premiere facture", "format": "scalar", "interpretation_template": "{{impayes}} clients ({{pct}}%) n'ont pas paye leur 1ere facture sur les {{total}} contrats."}}

Q: "Taux de realisation par canal en mars 2025"
R: {{"sql": "WITH ventes_agg AS (SELECT b.canal_vente, COUNT(*) AS nb_ventes FROM fact_ventes v JOIN dim_boutique b ON v.boutique_key = b.boutique_key GROUP BY b.canal_vente), objectifs_agg AS (SELECT b.canal_vente, SUM(o.montant_objectif) AS total_objectifs FROM fact_objectifs o JOIN dim_boutique b ON o.boutique_key = b.boutique_key GROUP BY b.canal_vente) SELECT v.canal_vente, ROUND(v.nb_ventes::numeric / NULLIF(o.total_objectifs, 0) * 100, 2) AS taux_pct FROM ventes_agg v LEFT JOIN objectifs_agg o ON v.canal_vente = o.canal_vente WHERE o.total_objectifs IS NOT NULL ORDER BY taux_pct DESC", "explanation": "Taux de realisation par canal calcule sur toute la periode disponible (Nov 2024 - Mars 2025), car fact_objectifs n'a pas de decoupage mensuel ; canaux sans objectif exclus", "format": "ranking", "interpretation_template": "Voici les taux de realisation par canal (calcules sur l ensemble de la periode disponible, les objectifs n etant pas decoupes par mois)"}}

Si la question ne peut pas etre resolue, retourne :
{{"error": "Description claire", "suggestion": "Reformulation suggeree"}}

RETOURNE UNIQUEMENT LE JSON, RIEN D'AUTRE. PAS DE BACKTICKS, PAS DE TEXTE AVANT/APRES.
"""


# ==================================================================
# CLASSE PRINCIPALE — ORYAAgent (interface identique aux versions precedentes)
# ==================================================================

class ORYAAgent:
    """Agent conversationnel ORYA base sur Groq API (Llama 3.3 70B)."""

    def __init__(self):
        if not GROQ_API_KEY:
            self.client = None
            return
        self.client = Groq(api_key=GROQ_API_KEY)
        self.conversation_history = []

    # --------------------------------------------------------------
    # 1. NL -> SQL via Groq/Llama
    # --------------------------------------------------------------

    def nl_to_sql(self, question: str, image_path: Optional[str] = None) -> dict:
        """Transforme une question en requete SQL via Groq."""
        if not GROQ_API_KEY:
            return {
                "error": "Cle API Groq manquante (GROQ_API_KEY)",
                "suggestion": "Configurez la cle dans le fichier .env"
            }

        try:
            response = self.client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Question utilisateur : {question}"}
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=MAX_TOKENS
            )
            assistant_text = response.choices[0].message.content
        except Exception as e:
            return {
                "error": f"Erreur API Groq : {e}",
                "suggestion": "Verifiez la cle API et le quota."
            }

        try:
            json_clean = re.sub(r"```json|```", "", assistant_text).strip()
            return json.loads(json_clean)
        except json.JSONDecodeError:
            return {
                "error": "Reponse Groq non parsable en JSON",
                "raw": assistant_text
            }

    # --------------------------------------------------------------
    # 2. Validation SQL
    # --------------------------------------------------------------

    def validate_sql(self, sql: str, question: str) -> tuple[bool, list[str]]:
        """Valide la requete SQL avant execution."""
        warnings = []
        sql_upper = sql.upper()

        for keyword in FORBIDDEN_SQL_KEYWORDS:
            if re.search(rf"\b{keyword}\b", sql_upper):
                return False, [f"Mot-cle interdit detecte : {keyword}"]

        q_lower = question.lower()

        if any(kw in q_lower for kw in ["realisation", "atteinte", "objectif", "performance vs"]):
            if "fact_objectifs" not in sql.lower():
                warnings.append("Question sur objectifs mais fact_objectifs absent du SQL")

        if any(kw in q_lower for kw in ["pas paye", "non paye", "impaye", "n'ont pas", "n'a pas"]):
            if not any(p in sql.lower() for p in ["is null", "= 0", "filter (where"]):
                warnings.append("Question negative mais SQL ne semble pas filtrer le negatif")

        return True, warnings

    # --------------------------------------------------------------
    # 3. Execution securisee
    # --------------------------------------------------------------

    def execute_safe(self, sql: str) -> pd.DataFrame:
        """Execute la requete SELECT et retourne un DataFrame."""
        try:
            with engine.connect() as conn:
                return pd.read_sql(text(sql), conn)
        except Exception as e:
            return pd.DataFrame({"error": [str(e)]})

    # --------------------------------------------------------------
    # 4. Mise en forme du resultat
    # --------------------------------------------------------------

    def format_response(self, result_df: pd.DataFrame,
                        format_type: str,
                        template: str,
                        question: str) -> str:
        """Transforme le DataFrame en reponse texte naturelle."""
        if len(result_df) == 0:
            return "Aucune donnee ne correspond a cette question. Verifiez la periode ou reformulez."

        if "error" in result_df.columns:
            return f"Erreur SQL : {result_df['error'].iloc[0]}"

        def _fmt(v):
            if isinstance(v, float):
                return f"{v:,.2f}".replace(",", " ")
            if isinstance(v, int):
                return f"{v:,}".replace(",", " ")
            return str(v) if v is not None else "-"

        if format_type == "scalar":
            row = result_df.iloc[0].to_dict()
            if "impayes" in row and "total" in row and row["total"]:
                row["pct"] = round(row["impayes"] / row["total"] * 100, 2)
            try:
                return template.format(**{k: _fmt(v) for k, v in row.items()})
            except KeyError:
                return f"Resultat : {row}"

        elif format_type == "ranking":
            lines = [f"{template}\n"]
            for i, row in result_df.iterrows():
                values = "  |  ".join([_fmt(v) for v in row.values])
                lines.append(f"  {i+1}. {values}")
            return "\n".join(lines)

        elif format_type == "table":
            return f"{template}\n\n{result_df.to_string(index=False)}"

        return str(result_df)

    # --------------------------------------------------------------
    # 5. Methode principale — ask()
    # --------------------------------------------------------------

    def ask(self, question: str, image_path: Optional[str] = None) -> dict:
        """Point d'entree principal — repond a une question utilisateur."""
        plan = self.nl_to_sql(question, image_path)

        if "error" in plan:
            return {
                "success": False,
                "response": f"{plan['error']}",
                "text": f"{plan['error']}",
                "suggestion": plan.get("suggestion", ""),
                "chart": None,
                "data": None,
                "sources": "",
                "intent": "error"
            }

        is_safe, warnings = self.validate_sql(plan["sql"], question)

        if not is_safe:
            return {
                "success": False,
                "response": "Requete bloquee pour des raisons de securite.",
                "text": "Requete bloquee pour des raisons de securite.",
                "warnings": warnings,
                "chart": None,
                "data": None,
                "sources": "",
                "intent": "blocked"
            }

        result_df = self.execute_safe(plan["sql"])

        response_text = self.format_response(
            result_df,
            plan.get("format", "table"),
            plan.get("interpretation_template", ""),
            question
        )

        # Format de retour compatible routes.py et chatbot.js
        return {
            "success": True,
            "response": response_text,
            "text": response_text,
            "sql": plan["sql"],
            "explanation": plan.get("explanation", ""),
            "warnings": warnings,
            "row_count": len(result_df),
            "chart": None,
            "data": result_df.to_dict(orient="records") if len(result_df) < 50 else None,
            "sources": "fact_ventes, dim_boutique, dim_vendeur, fact_objectifs",
            "intent": plan.get("format", "table")
        }

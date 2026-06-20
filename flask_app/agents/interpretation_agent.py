"""
=============================================================
  FICHIER : flask_app/agents/interpretation_agent.py
  ROLE   : Interpretations IA des KPIs - Orange Tunisie
  MODELE : Google Gemini 2.0 Flash
  CACHE  : TTL 2h  |  FILE : prioritaire  |  FALLBACK : regles metier
=============================================================
"""

import os
import json
from pathlib import Path
from dotenv import load_dotenv

from google import genai

from .cache_manager   import gemini_cache
from .api_queue       import gemini_queue, GeminiQueue, is_quota_blocked, set_quota_blocked
from .fallback_engine import fallback

PROJECT_ROOT = Path(__file__).parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
MODEL_NAME     = "gemini-2.0-flash"

_REGLES = (
    "Tu es un analyste senior en business intelligence chez Orange Tunisie.\n"
    "REGLES STRICTES :\n"
    "- Reponds en 2 a 3 phrases maximum, en francais\n"
    "- Ton professionnel, concret, actionnable\n"
    "- N'utilise JAMAIS : IA, intelligence artificielle, DWH, SRM, ETL\n"
    "- Aucun emoji, aucune puce, aucun markdown (pas de **, pas de #)\n"
    "- Un seul paragraphe fluide, pas de liste\n"
    "- Mets en valeur les chiffres cles dans le texte\n"
)

_client = None


def _get_client():
    global _client
    if _client is None and GEMINI_API_KEY:
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


def _generate(prompt: str) -> str:
    """Appel direct Gemini — execute par le worker de gemini_queue."""
    client = _get_client()
    if not client:
        return ""
    if is_quota_blocked():
        return ""
    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=_REGLES + "\n\n" + prompt,
        )
        text = response.text.strip()
        for ch in ('**', '##', '#', '*', '`'):
            text = text.replace(ch, '')
        return text
    except Exception as e:
        err = str(e)
        if "429" in err or "RESOURCE_EXHAUSTED" in err or "quota" in err.lower():
            set_quota_blocked(120)
        return ""


def _smart_generate(cache_key: str, prompt_fn, fallback_fn,
                    priority: int = GeminiQueue.NORMAL) -> str:
    """
    Couche 1 : cache (TTL 2h)
    Couche 2 : appel Gemini via file prioritaire
    Couche 3 : fallback regles metier (toujours utile, jamais vide)
    """
    cached = gemini_cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        result = gemini_queue.submit(
            lambda: _generate(prompt_fn()),
            priority=priority,
        )
    except Exception:
        result = None

    if result:
        gemini_cache.set(cache_key, result)
        return result

    gemini_queue.incr_fallbacks()
    return fallback_fn()


# ── Helpers admin ─────────────────────────────────────────────────────────────

def cache_clear() -> None:
    gemini_cache.clear()


def cache_stats() -> dict:
    return {**gemini_cache.stats(), **gemini_queue.stats()}


# ── Fonctions de compatibilite (V1) ──────────────────────────────────────────

def interpret_top_n(donnees: list, type_entite: str = "items",
                    critere: str = "ventes") -> str:
    key = gemini_cache.make_key("top_n", type_entite, critere, str(donnees[:5]))
    return _smart_generate(
        key,
        lambda: (
            f"Top {len(donnees)} {type_entite} d'Orange Tunisie classes par {critere}. "
            f"Donnees : {json.dumps(donnees[:10], ensure_ascii=False, default=str)}. "
            "Analyse business en 2 phrases : tendance principale et recommandation."
        ),
        lambda: (
            f"Les {len(donnees)} meilleurs {type_entite} tirent la performance "
            "commerciale d'Orange Tunisie vers le haut."
        ),
        GeminiQueue.LOW,
    )


def interpret_kpis(kpis: dict, page_name: str = "dashboard") -> str:
    key = gemini_cache.make_key("kpis", page_name, str(kpis))
    return _smart_generate(
        key,
        lambda: (
            f"KPIs de la page {page_name} Orange Tunisie : "
            f"{json.dumps(kpis, ensure_ascii=False, default=str)}. "
            "Synthese en 2 phrases."
        ),
        lambda: f"Les indicateurs de la page {page_name} sont disponibles dans le tableau de bord.",
        GeminiQueue.LOW,
    )


# ── Agent classe (V2) ─────────────────────────────────────────────────────────

class InterpretationAgent:

    # --- Dashboard ---

    @staticmethod
    def dashboard_global(kpis: dict) -> str:
        key = gemini_cache.make_key("dash_global", str(kpis))
        return _smart_generate(
            key,
            lambda: (
                "KPIs Orange Tunisie - Dashboard :\n"
                f"- Total ventes : {kpis.get('total_ventes', 0)} contrats\n"
                f"- Taux paiement 1ere facture : {kpis.get('taux_paiement', 0)}%\n"
                f"- Taux realisation objectifs : {kpis.get('taux_realisation', 0)}%\n"
                f"- Duree engagement moyenne : {kpis.get('panier_moyen', 0)} mois\n"
                f"- Top vendeur : {kpis.get('top_vendeur_nom', 'N/A')} "
                f"({kpis.get('top_vendeur_ventes', 0)} ventes)\n"
                f"- Top boutique : {kpis.get('top_boutique_nom', 'N/A')} "
                f"({kpis.get('top_boutique_ventes', 0)} ventes)\n"
                "Synthese executive : etat global, point fort, recommandation prioritaire."
            ),
            lambda: fallback.dashboard_global(kpis),
            GeminiQueue.NORMAL,
        )

    @staticmethod
    def kpi_total_ventes(total: int) -> str:
        key = gemini_cache.make_key("kpi_total_ventes", total)
        return _smart_generate(
            key,
            lambda: (
                f"Volume total de ventes Orange Tunisie : {total} contrats consolides. "
                "Que represente ce volume en termes de performance commerciale ? "
                "Analyse courte en 2 phrases."
            ),
            lambda: fallback.kpi_total_ventes(total),
            GeminiQueue.LOW,
        )

    @staticmethod
    def kpi_taux_paiement(taux: float) -> str:
        key = gemini_cache.make_key("kpi_taux_paiement", taux)
        return _smart_generate(
            key,
            lambda: (
                f"Taux de paiement de la 1ere facture : {taux}%. "
                "Objectif sectoriel telecom : 85%. "
                "Diagnostic + recommandation actionnable."
            ),
            lambda: fallback.kpi_taux_paiement(taux),
            GeminiQueue.LOW,
        )

    @staticmethod
    def kpi_taux_realisation(taux: float) -> str:
        key = gemini_cache.make_key("kpi_taux_real", taux)
        return _smart_generate(
            key,
            lambda: (
                f"Taux de realisation des objectifs commerciaux : {taux}%. "
                "Levier d'amelioration le plus pertinent en 2 phrases."
            ),
            lambda: fallback.kpi_taux_realisation(taux),
            GeminiQueue.LOW,
        )

    @staticmethod
    def kpi_panier_moyen(montant: float) -> str:
        key = gemini_cache.make_key("kpi_panier", montant)
        return _smart_generate(
            key,
            lambda: (
                f"Duree d'engagement moyenne par contrat : {montant} mois. "
                "Interpretation de ce niveau et recommandation commerciale associee."
            ),
            lambda: fallback.kpi_panier_moyen(montant),
            GeminiQueue.LOW,
        )

    @staticmethod
    def kpi_top_vendeur(vendeur: dict) -> str:
        key = gemini_cache.make_key("kpi_top_vendeur", str(vendeur))
        return _smart_generate(
            key,
            lambda: (
                f"Top vendeur : {vendeur.get('nom', 'N/A')} avec "
                f"{vendeur.get('nb_ventes', 0)} ventes, "
                f"boutique principale : {vendeur.get('boutique', 'N/A')}, "
                f"canal : {vendeur.get('canal', 'N/A')}. "
                "Profil de performance et implication pour la strategie commerciale."
            ),
            lambda: fallback.kpi_top_vendeur(vendeur),
            GeminiQueue.LOW,
        )

    @staticmethod
    def kpi_top_boutique(boutique: dict) -> str:
        key = gemini_cache.make_key("kpi_top_boutique", str(boutique))
        return _smart_generate(
            key,
            lambda: (
                f"Top boutique : {boutique.get('nom', 'N/A')} "
                f"(type {boutique.get('type', 'N/A')}), "
                f"{boutique.get('nb_ventes', 0)} ventes, "
                f"{boutique.get('factures_1_payees', 0)} premieres factures payees. "
                f"Taux objectif atteint : {boutique.get('taux_objectif', 0)}%. "
                "Analyse business et enseignements pour le reseau."
            ),
            lambda: fallback.kpi_top_boutique(boutique),
            GeminiQueue.LOW,
        )

    @staticmethod
    def canal_repartition(data_str: str) -> str:
        key = gemini_cache.make_key("canal_repartition", data_str)
        return _smart_generate(
            key,
            lambda: (
                f"Repartition des ventes par canal Orange Tunisie : {data_str}. "
                "Canal dominant, canal sous-performant, recommandation strategique."
            ),
            lambda: fallback.canal_repartition(data_str),
            GeminiQueue.NORMAL,
        )

    @staticmethod
    def canal_objectif(data_str: str, month: str) -> str:
        key = gemini_cache.make_key("canal_objectif", month, data_str)
        return _smart_generate(
            key,
            lambda: (
                f"Performance par canal pour {month} - Orange Tunisie : {data_str}. "
                "Canal le plus performant, ecart le plus preoccupant, action prioritaire."
            ),
            lambda: fallback.canal_objectif(data_str, month),
            GeminiQueue.NORMAL,
        )

    # --- Produits ---

    @staticmethod
    def produits_global(total: int, types: int, familles: int) -> str:
        key = gemini_cache.make_key("produits_global", total, types, familles)
        return _smart_generate(
            key,
            lambda: (
                f"Catalogue Orange Tunisie : {total} references produits, "
                f"{types} types distincts, {familles} familles. "
                "Analyse de la diversite et couverture du marche."
            ),
            lambda: fallback.produits_global(total, types, familles),
            GeminiQueue.LOW,
        )

    @staticmethod
    def produits_top5(top5_str: str) -> str:
        key = gemini_cache.make_key("produits_top5", top5_str)
        return _smart_generate(
            key,
            lambda: (
                f"Top 5 produits les plus vendus chez Orange Tunisie : {top5_str}. "
                "Produits stars, dependance, opportunites de cross-sell."
            ),
            lambda: fallback.produits_top5(top5_str),
            GeminiQueue.LOW,
        )

    # --- Objectifs ---

    @staticmethod
    def objectifs_global(taux: float, canaux_str: str) -> str:
        key = gemini_cache.make_key("objectifs_global", taux, canaux_str)
        niveau = "critique" if taux < 50 else ("insuffisant" if taux < 80 else "satisfaisant")
        return _smart_generate(
            key,
            lambda: (
                f"Synthese commerciale Orange Tunisie : taux global de realisation "
                f"{taux}% ({niveau}). "
                f"Performance par canal : {canaux_str}. "
                "Identifier le canal prioritaire a renforcer, l'action la plus impactante "
                "et le risque principal si aucune correction n'est apportee."
            ),
            lambda: fallback.objectifs_global(taux, canaux_str),
            GeminiQueue.NORMAL,
        )

    @staticmethod
    def objectifs_taux_global(taux: float) -> str:
        key = gemini_cache.make_key("obj_taux_global", taux)
        manque = round(100 - taux, 1)
        return _smart_generate(
            key,
            lambda: (
                f"Taux global de realisation des objectifs Orange Tunisie : {taux}% "
                f"(ecart restant vers 100% : {manque} points). "
                "Diagnostic precis du niveau actuel, causes probables de l'ecart "
                "et levier operationnel concret pour accelerer la realisation."
            ),
            lambda: fallback.objectifs_taux_global(taux),
            GeminiQueue.NORMAL,
        )

    @staticmethod
    def canal_detail(canal: str, taux: float, realisation: float, objectif: float) -> str:
        key = gemini_cache.make_key("canal_detail", canal, taux)
        ecart = round(objectif - realisation)
        statut = "depasse l'objectif de" if ecart <= 0 else "est en retard de"
        return _smart_generate(
            key,
            lambda: (
                f"Canal {canal} - Orange Tunisie : taux de realisation {taux}%, "
                f"realisation {int(realisation):,} contrats sur objectif {int(objectif):,} contrats. "
                f"Ce canal {statut} {abs(int(ecart)):,} contrats. "
                "Diagnostic precis de la performance de ce canal et recommandation "
                "operationnelle concrete et actionnable."
            ),
            lambda: fallback.canal_detail(canal, taux, realisation, objectif),
            GeminiQueue.NORMAL,
        )

    @staticmethod
    def objectifs_top15(boutiques: list) -> str:
        if not boutiques:
            return "Donnees non disponibles."
        top5_str = ', '.join(
            f"{b['boutique']} ({b['taux_pct']}%)" for b in boutiques[:5]
        )
        last = boutiques[-1]
        key = gemini_cache.make_key("obj_top15", top5_str)
        return _smart_generate(
            key,
            lambda: (
                "Top 15 boutiques par taux de realisation - Orange Tunisie. "
                f"Meilleures boutiques : {top5_str}. "
                f"Boutique en difficulte : {last['boutique']} ({last['taux_pct']}%). "
                "Analyser l'ecart de performance entre les boutiques leaders et celles en retard, "
                "identifier les facteurs cles de succes des boutiques en tete, "
                "et proposer une action concrete pour les points de vente sous-performants."
            ),
            lambda: fallback.objectifs_top15(boutiques),
            GeminiQueue.NORMAL,
        )

    @staticmethod
    def prediction_global(realise: int, objectif: float, prediction: int, mape: float) -> str:
        ecart = prediction - objectif
        sens  = "superieure" if ecart >= 0 else "inferieure"
        key   = gemini_cache.make_key("pred_global", realise, int(objectif), prediction)
        return _smart_generate(
            key,
            lambda: (
                f"Prediction de cloture mensuelle Orange Tunisie : "
                f"realise a ce jour {realise} ventes, "
                f"prediction Prophet (MAPE {mape}%) : {prediction} ventes. "
                f"La projection est {sens} a l'objectif de {int(objectif):,} ventes "
                f"avec un ecart de {abs(int(ecart)):,}. "
                "Synthese executive de la performance previsionnelle et recommandation strategique prioritaire."
            ),
            lambda: fallback.prediction_global(realise, objectif, prediction, mape),
            GeminiQueue.NORMAL,
        )

    @staticmethod
    def paiements_global(taux: float, impayes: int, taux_1ere: float) -> str:
        key = gemini_cache.make_key("paiements_global", taux, impayes, taux_1ere)
        return _smart_generate(
            key,
            lambda: (
                f"Suivi des paiements Orange Tunisie : taux global {taux}%, "
                f"{impayes:,} factures impayees, "
                f"taux premiere facture {taux_1ere}% (objectif sectoriel 85%). "
                "Analyser le risque client et proposer une recommandation operationnelle concrete "
                "pour ameliorer le recouvrement et reduire les impayes."
            ),
            lambda: fallback.paiements_global(taux, impayes, taux_1ere),
            GeminiQueue.NORMAL,
        )

    @staticmethod
    def objectifs_canal_compare(data_str: str, best: dict, worst: dict) -> str:
        key = gemini_cache.make_key("canal_compare", data_str)
        return _smart_generate(
            key,
            lambda: (
                f"Comparaison des canaux de distribution Orange Tunisie : {data_str}. "
                f"Canal le plus performant : {best.get('canal')} avec "
                f"{best.get('taux')}% de realisation. "
                f"Canal le plus en retard : {worst.get('canal')} avec {worst.get('taux')}%. "
                "Analyser les ecarts entre canaux, les raisons probables et proposer "
                "une strategie concrete pour equilibrer le portefeuille."
            ),
            lambda: fallback.objectifs_canal_compare(data_str, best, worst),
            GeminiQueue.NORMAL,
        )

"""
Moteur de repli — Orange Tunisie.
Analyses deterministes (sans Gemini) pour tous les KPIs.
L utilisateur voit toujours une analyse utile, meme sans quota Gemini.
"""
from __future__ import annotations


def _fmt(n) -> str:
    return f"{int(n):,}".replace(',', ' ')  # espace fine insecable


class FallbackEngine:

    # ── Dashboard ─────────────────────────────────────────────────────────────

    @staticmethod
    def dashboard_global(kpis: dict) -> str:
        total  = kpis.get('total_ventes', 0)
        taux_r = kpis.get('taux_realisation', 0)
        taux_p = kpis.get('taux_paiement', 0)
        top_v  = kpis.get('top_vendeur_nom', 'N/A')
        niveau = "solide" if taux_r >= 80 else ("a renforcer" if taux_r >= 50 else "critique")
        return (
            f"Le reseau commercial affiche {_fmt(total)} contrats avec un taux de realisation "
            f"{niveau} a {taux_r}%. "
            f"Le taux de paiement de la 1re facture est de {taux_p}% ; "
            f"{top_v} se distingue comme meilleur vendeur. "
            "Concentrer les actions sur les canaux sous-performants pour accelerer l'atteinte des objectifs."
        )

    @staticmethod
    def kpi_total_ventes(total: int) -> str:
        niveau = "fort" if total > 50000 else ("moyen" if total > 20000 else "a developper")
        return (
            f"Le volume total de {_fmt(total)} contrats consolides represente un niveau {niveau} "
            "de production commerciale. "
            "Maintenir la cadence sur les boutiques leaders et renforcer les points de vente en sous-performance."
        )

    @staticmethod
    def kpi_taux_paiement(taux: float) -> str:
        ecart = round(85.0 - taux, 1)
        if ecart <= 0:
            return (
                f"Le taux de paiement de la 1re facture ({taux}%) depasse l'objectif sectoriel de 85%. "
                "Ce niveau reflete une bonne qualite du portefeuille client et une gestion efficace des souscriptions."
            )
        return (
            f"Le taux de paiement de la 1re facture est de {taux}%, soit {ecart} points sous "
            "l'objectif sectoriel de 85%. "
            "Renforcer le conseil client en boutique et verifier la qualite des donnees saisies pour reduire les impayes."
        )

    @staticmethod
    def kpi_taux_realisation(taux: float) -> str:
        if taux >= 100:
            return (
                f"Objectifs commerciaux depasses avec un taux de {taux}% — performance exceptionnelle. "
                "Capitaliser sur les pratiques gagnantes pour les diffuser sur l'ensemble du reseau."
            )
        manque = round(100 - taux, 1)
        return (
            f"Le taux de realisation de {taux}% indique un ecart de {manque} points par rapport aux objectifs. "
            "Prioriser les boutiques dont le taux est inferieur a 50% et intensifier le coaching commercial."
        )

    @staticmethod
    def kpi_panier_moyen(montant: float) -> str:
        niveau = "long" if montant > 18 else ("moyen" if montant >= 12 else "court")
        return (
            f"La duree d'engagement moyenne est de {montant} mois, soit un niveau {niveau}. "
            "Suivre les offres sans engagement separement pour proteger la fidelisation et la recurrence des paiements."
        )

    @staticmethod
    def kpi_top_vendeur(vendeur: dict) -> str:
        nom = vendeur.get('nom', 'N/A')
        nb  = vendeur.get('nb_ventes', 0)
        bq  = vendeur.get('boutique', 'N/A')
        return (
            f"{nom} se distingue avec {_fmt(nb)} ventes depuis {bq}, "
            "constituant un profil de reference pour le reseau. "
            "Valoriser ses pratiques et organiser un partage d'experience avec les equipes sous-performantes."
        )

    @staticmethod
    def kpi_top_boutique(boutique: dict) -> str:
        nom  = boutique.get('nom', 'N/A')
        nb   = boutique.get('nb_ventes', 0)
        taux = boutique.get('taux_objectif', 0)
        return (
            f"La boutique {nom} realise {_fmt(nb)} contrats "
            f"avec un taux d'objectif de {taux}%. "
            "Analyser son organisation et son mix produit pour repliquer les bonnes pratiques sur les boutiques voisines."
        )

    @staticmethod
    def canal_repartition(data_str: str) -> str:
        return (
            f"La repartition par canal ({data_str}) illustre la structure du reseau de distribution. "
            "Verifier si la part du canal dominant correspond aux investissements commerciaux realises. "
            "Un canal sous-represente peut constituer un levier de croissance a activer en priorite."
        )

    @staticmethod
    def canal_objectif(data_str: str, month: str) -> str:
        return (
            f"Performance des canaux pour {month} : {data_str}. "
            "Les ecarts entre canaux signalent des disparites operationnelles a corriger. "
            "Priorite aux canaux dont le taux est inferieur a 70% pour eviter un retard cumulatif."
        )

    # ── Produits ──────────────────────────────────────────────────────────────

    @staticmethod
    def produits_global(total: int, types: int, familles: int) -> str:
        return (
            f"Le catalogue Orange Tunisie comprend {total} references reparties sur "
            f"{types} types et {familles} familles. "
            "Cette diversite couvre la majorite des segments du marche ; "
            "veiller a la rotation des references les moins vendues."
        )

    @staticmethod
    def produits_top5(top5_str: str) -> str:
        return (
            f"Les cinq produits les plus vendus ({top5_str}) captent l'essentiel des volumes. "
            "Cette concentration est un signe de maturite commerciale mais expose au risque de dependance. "
            "Encourager la montee en gamme et le cross-sell pour elargir le mix produit."
        )

    # ── Objectifs ─────────────────────────────────────────────────────────────

    @staticmethod
    def objectifs_global(taux: float, canaux_str: str) -> str:
        niveau = "critique" if taux < 50 else ("insuffisant" if taux < 80 else "satisfaisant")
        return (
            f"Taux global de realisation : {taux}% ({niveau}). Canaux : {canaux_str}. "
            "Le canal le plus en retard doit faire l'objet d'un plan d'action correctif immediat. "
            "Revoir la repartition des objectifs si certains canaux sont structurellement desavantages."
        )

    @staticmethod
    def objectifs_taux_global(taux: float) -> str:
        if taux >= 100:
            return (
                f"Objectifs depasses : {taux}% de realisation — performance remarquable du reseau. "
                "Fixer des objectifs revises a la hausse pour maintenir la dynamique de croissance."
            )
        manque = round(100 - taux, 1)
        return (
            f"Le taux global de {taux}% laisse {manque} points a combler pour atteindre les objectifs. "
            "Agir en priorite sur les boutiques dont le taux est inferieur a la moyenne nationale "
            "et verifier la coherence des objectifs avec le potentiel reel de chaque canal."
        )

    @staticmethod
    def canal_detail(canal: str, taux: float, realisation: float, objectif: float) -> str:
        ecart  = round(objectif - realisation)
        statut = ("depasse l'objectif"
                  if ecart <= 0
                  else f"est en retard de {_fmt(abs(ecart))} contrats")
        niveau = ("tres bon" if taux >= 90
                  else ("correct" if taux >= 70
                        else ("faible" if taux >= 50 else "critique")))
        return (
            f"Le canal {canal} affiche un taux de {taux}% ({niveau}) : "
            f"{_fmt(realisation)} contrats realises sur {_fmt(objectif)} contrats d'objectif. "
            f"Ce canal {statut}. "
            "Identifier les boutiques de ce canal sous la moyenne et mettre en place un suivi hebdomadaire."
        )

    @staticmethod
    def objectifs_top15(boutiques: list) -> str:
        if not boutiques:
            return "Donnees non disponibles."
        top1  = boutiques[0]
        last  = boutiques[-1]
        top3  = ', '.join(f"{b['boutique']} ({b['taux_pct']}%)" for b in boutiques[1:4])
        return (
            f"Le classement est conduit par {top1['boutique']} a {top1['taux_pct']}%, "
            f"suivi de {top3}. "
            f"La boutique {last['boutique']} ({last['taux_pct']}%) ferme le classement "
            "et necessite un accompagnement renforce. "
            "L'ecart entre la premiere et la derniere boutique revele des disparites "
            "importantes a traiter via le coaching terrain."
        )

    @staticmethod
    def objectifs_canal_compare(data_str: str, best: dict, worst: dict) -> str:
        return (
            f"Parmi les canaux, {best.get('canal')} se distingue avec {best.get('taux')}% de realisation, "
            f"tandis que {worst.get('canal')} est le plus en retard avec {worst.get('taux')}%. "
            "Cet ecart appelle une revue des ressources allouees et des objectifs fixes pour chaque canal."
        )


# Singleton
    @staticmethod
    def prediction_global(realise: int, objectif: float, prediction: int, mape: float) -> str:
        ecart = prediction - objectif
        if ecart >= 0:
            return (
                f"La prevision de cloture etablie a {_fmt(prediction)} ventes est superieure "
                f"a l'objectif mensuel, avec un ecart favorable de {_fmt(int(ecart))} ventes. "
                f"L'algorithme Prophet (MAPE {mape}%) confirme la trajectoire positive — "
                "maintenir la dynamique commerciale en cours."
            )
        return (
            f"La prevision de cloture a {_fmt(prediction)} ventes est inferieure a l'objectif "
            f"de {_fmt(int(objectif))} ({_fmt(int(abs(ecart)))} ventes d'ecart). "
            f"L'algorithme Prophet (MAPE {mape}%) recommande une action corrective immediate "
            "sur les boutiques les moins performantes pour combler l'ecart."
        )

    @staticmethod
    def paiements_global(taux: float, impayes: int, taux_1ere: float) -> str:
        ecart = round(taux_1ere - 85.0, 1)
        statut = f"depasse l'objectif de 85% de {ecart} points" if ecart >= 0 else f"est en retard de {abs(ecart)} points sur l'objectif de 85%"
        return (
            f"Le taux de paiement global est de {taux}% avec {_fmt(impayes)} factures impayees. "
            f"Le taux de premiere facture a {taux_1ere}% {statut}. "
            "Renforcer le suivi des clients a risque et le coaching boutique pour ameliorer le recouvrement."
        )


fallback = FallbackEngine()

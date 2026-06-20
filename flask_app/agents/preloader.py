"""
Prechauffage du cache Gemini apres connexion — Orange Tunisie.
Lance en arriere-plan (thread daemon), priorite LOW.
Retour immediat : ne bloque pas la reponse de login.
"""
import threading


def preload_interpretations_async() -> None:
    """Declenche le prechauffage en thread daemon. Appel non bloquant."""
    t = threading.Thread(target=_run, daemon=True, name='GeminiPreloader')
    t.start()


def _run() -> None:
    try:
        from flask_app.models import (
            get_kpis, get_taux_paiement, get_panier_moyen,
            get_top_vendeur_detail, get_top_boutique_detail,
            get_produits_kpis, get_top5_produits_vendus,
            get_objectifs_kpis, get_taux_par_canal, get_repartition_canal,
        )
        from flask_app.agents.interpretation_agent import InterpretationAgent
        from flask_app.agents.api_queue import GeminiQueue

        agent = InterpretationAgent()

        # --- Dashboard ---
        kpis   = get_kpis()
        total  = int(kpis.get('total_ventes', 0))
        taux_r = round(float(kpis.get('taux_realisation', 0)), 2)
        taux_p = get_taux_paiement()
        pm     = get_panier_moyen()

        agent.kpi_total_ventes(total)
        agent.kpi_taux_paiement(taux_p)
        agent.kpi_taux_realisation(taux_r)
        agent.kpi_panier_moyen(pm)

        top_v = get_top_vendeur_detail() or {}
        if top_v:
            agent.kpi_top_vendeur(top_v)

        top_b = get_top_boutique_detail() or {}
        if top_b:
            agent.kpi_top_boutique(top_b)

        # --- Canaux ---
        rep = get_repartition_canal() or []
        if rep:
            rep_str = ', '.join(
                f"{r.get('canal', '?')}: {r.get('nb_ventes', 0)} ventes ({r.get('pourcentage', 0)}%)"
                for r in rep[:5]
            )
            agent.canal_repartition(rep_str)

        # --- Produits ---
        kpis_p = get_produits_kpis()
        agent.produits_global(
            int(kpis_p.get('total_produits', 0)),
            int(kpis_p.get('nb_types', 0)),
            int(kpis_p.get('nb_familles', 0)),
        )
        top5 = get_top5_produits_vendus() or []
        if top5:
            top5_str = ', '.join(r.get('produit', '?') for r in top5[:5])
            agent.produits_top5(top5_str)

        # --- Objectifs ---
        kpis_o = get_objectifs_kpis()
        canaux  = get_taux_par_canal() or []
        canaux_str = ', '.join(f"{c['canal']}: {c['taux']}%" for c in canaux)
        agent.objectifs_global(
            round(float(kpis_o.get('taux_realisation', 0)), 2),
            canaux_str,
        )
        agent.objectifs_taux_global(
            round(float(kpis_o.get('taux_realisation', 0)), 2)
        )

        print("[Preloader] Cache Gemini prechauffage termine.")

    except Exception as e:
        print(f"[Preloader] Erreur non bloquante : {e}")

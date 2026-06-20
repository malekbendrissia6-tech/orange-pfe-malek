"""
=============================================================
  FICHIER : flask_app/routes.py
  ROLE   : Routes de l'application Flask - Orange Tunisie
=============================================================
"""

from datetime import datetime
from flask import Blueprint, render_template, jsonify, request, session
from flask_app.agents.interpretation_agent import (
    interpret_top_n, InterpretationAgent, cache_clear, cache_stats,
)
from flask_app.auth.decorators import login_required, admin_required
from flask_app.models import (
    get_kpis, get_top_vendeurs, get_top_boutiques,
    get_produits_kpis, get_top_produits_detail, get_produits_par_type,
    get_objectifs_kpis, get_objectifs_par_boutique, get_objectifs_par_mois,
    get_taux_paiement, get_top_vendeur_detail, get_top_boutique_detail,
    get_repartition_canal, get_objectif_canal_mois,
    get_taux_par_canal, get_top5_produits_vendus, get_panier_moyen,
    get_ventes_comparaison_mois, get_repartition_famille,
    get_evolution_journaliere, get_top_vendeurs_perf,
    get_top10_produits_vendus, get_boutiques_objectifs_listes,
    get_mois_disponibles,
    get_prediction_evolution, get_prediction_algorithmes,
    get_paiements_kpis, get_paiements_evolution,
    get_paiements_top_boutiques_impayees, get_paiements_clients_risque,
    get_data_quality_kpis,
    get_top5_offres, get_repartition_ligne_produits,
    get_performance_all,
    get_paiements_kpis_filtered, get_objectifs_kpis_filtered,
    get_objectifs_charts_filtered,
    get_cascade_filter_options,
)

main_bp = Blueprint("main", __name__)
agent   = InterpretationAgent()


# ============================================================
# PAGES
# ============================================================

@main_bp.route("/")
@login_required
def index():
    last_update = datetime.now().strftime("%d/%m/%Y a %H:%M")
    current_date = datetime.now().strftime("%A %d %B %Y a %H:%M")
    last_login = session.get('last_login_str', 'premiere visite')
    return render_template("index.html",
        last_update=last_update,
        current_date=current_date,
        last_login=last_login,
    )


@main_bp.route("/dashboard")
@login_required
def dashboard():
    kpis          = get_kpis()
    taux_paiement = get_taux_paiement()
    panier_moyen  = get_panier_moyen()
    top_vendeur   = get_top_vendeur_detail()
    top_boutique  = get_top_boutique_detail()

    return render_template(
        "dashboard.html",
        total_ventes    = int(kpis.get('total_ventes', 0)),
        taux_paiement   = taux_paiement,
        taux_realisation= round(float(kpis.get('taux_realisation', 0)), 2),
        panier_moyen    = panier_moyen,
        top_vendeur     = top_vendeur,
        top_boutique    = top_boutique,
    )


@main_bp.route("/prediction")
@login_required
def prediction():
    import calendar
    from datetime import datetime as _dt
    data    = get_prediction_evolution()
    algos   = get_prediction_algorithmes()
    obj_m   = data.get('objectif_mensuel', 0)
    realise = data.get('realise_actuel', 0)
    pred    = data.get('prediction_cloture', 0)
    mape    = data.get('mape_prophet', 3.6)
    is_ok   = pred >= obj_m
    # KPI Atterrissage : ventes réalisées / nb jours du mois
    now = _dt.now()
    nb_jours = calendar.monthrange(now.year, now.month)[1]
    atterrissage = round(float(realise) / nb_jours, 1) if nb_jours > 0 else 0
    return render_template(
        "prediction.html",
        realise_actuel      = int(realise),
        objectif_mensuel    = round(float(obj_m or 0), 0),
        prediction_cloture  = int(pred),
        mape_meilleur       = mape,
        atterrissage        = atterrissage,
        nb_jours_mois       = nb_jours,
        algorithmes         = algos,
        alerte_type         = 'success' if is_ok else 'danger',
        alerte_msg          = (
            f"Projection favorable : {int(pred):,} contrats prevus, objectif atteignable."
            if is_ok else
            f"Alerte : projection {int(pred):,} contrats sous l'objectif de {int(obj_m or 0):,}."
        ),
    )


@main_bp.route("/paiements")
@login_required
def paiements():
    kpis    = get_paiements_kpis()
    top_bq  = get_paiements_top_boutiques_impayees(5)
    risques = get_paiements_clients_risque()
    return render_template(
        "paiements.html",
        total_factures    = kpis.get('total_factures', 0),
        taux_paiement     = kpis.get('taux_paiement', 0),
        taux_1ere         = kpis.get('taux_1ere_facture', 0),
        taux_2eme         = kpis.get('taux_2eme_facture', 0),
        taux_3eme         = kpis.get('taux_3eme_facture', 0),
        factures_impayees = kpis.get('factures_impayees', 0),
        top_boutiques     = top_bq,
        clients_risque    = risques,
    )


@main_bp.route("/qualite-donnees")
@login_required
def qualite_donnees():
    return render_template("qualite_donnees.html", qualite=get_data_quality_kpis())


@main_bp.route("/produits")
@login_required
def produits():
    kpis_p = get_produits_kpis()
    top10  = get_top10_produits_vendus()
    top1   = top10[0] if top10 else {}
    par_type = get_produits_par_type()
    return render_template(
        "produits.html",
        total_produits = int(kpis_p.get('total_produits', 0)),
        types_count    = int(kpis_p.get('nb_types', 0)),
        familles_count = int(kpis_p.get('nb_familles', 0)),
        top1_produit   = top1.get('produit', 'N/A'),
        top1_ventes    = int(top1.get('total_vendu', 0)),
        top1_famille   = top1.get('famille', 'N/A'),
        par_type       = par_type,
    )


@main_bp.route("/objectifs")
@login_required
def objectifs():
    kpis_o  = get_objectifs_kpis()
    listes  = get_boutiques_objectifs_listes()
    top_b   = listes.get('top_boutique', {})
    return render_template(
        "objectifs.html",
        taux_global      = round(float(kpis_o.get('taux_realisation', 0)), 2),
        objectif_total   = round(float(kpis_o.get('objectif_total', 0)), 2),
        realise_total    = round(float(kpis_o.get('realise_total', 0)), 2),
        nb_atteignent    = listes.get('nb_atteignent', 0),
        nb_difficulte    = listes.get('nb_difficulte', 0),
        nb_total         = listes.get('total', 0),
        top_boutique_nom = top_b.get('boutique', 'N/A'),
        top_boutique_taux= round(float(top_b.get('taux_pct') or 0), 0),
        boutiques_atteignent = listes.get('atteignent', []),
        boutiques_difficulte = listes.get('difficulte', []),
        canaux_taux      = get_taux_par_canal(),
        par_mois         = get_objectifs_par_mois(),
    )


# ============================================================
# API DONNEES
# ============================================================

@main_bp.route("/api/last-update")
def api_last_update():
    return jsonify({'last_update': datetime.now().strftime("%d/%m/%Y a %H:%M")})


@main_bp.route("/api/kpis")
@login_required
def api_kpis():
    return jsonify(get_kpis())


@main_bp.route("/api/canal-repartition")
@login_required
def api_canal_repartition():
    rows = get_repartition_canal()
    return jsonify({
        'canaux'      : [r['canal']       for r in rows],
        'nb_ventes'   : [r['nb_ventes']   for r in rows],
        'pourcentages': [float(r['pourcentage']) for r in rows],
    })


@main_bp.route("/api/objectif-canal")
@login_required
def api_objectif_canal():
    import math
    month   = request.args.get('month', datetime.now().strftime('%Y-%m'))
    results = get_objectif_canal_mois(month)

    def _safe(v):
        if v is None:
            return 0
        try:
            f = float(v)
            return 0 if (math.isnan(f) or math.isinf(f)) else round(f, 2)
        except Exception:
            return 0

    # Exclure les canaux dont objectif ET realisation sont tous les deux 0
    filtered = [r for r in results if _safe(r['objectif']) > 0 or _safe(r['realisation']) > 0]

    return jsonify({
        'canaux'      : [r['canal']          for r in filtered],
        'objectifs'   : [_safe(r['objectif'])    for r in filtered],
        'realisations': [_safe(r['realisation']) for r in filtered],
        'taux'        : [_safe(r['taux'])        for r in filtered],
    })


# ============================================================
# API NOUVELLES ROUTES - DASHBOARD PRO
# ============================================================

@main_bp.route("/api/kpi/total-ventes-comparaison")
@login_required
def api_total_ventes_comparaison():
    mois = request.args.get('mois', 'actuel')
    try:
        return jsonify(get_ventes_comparaison_mois(mois))
    except Exception:
        return jsonify({'total': 0, 'precedent': 0, 'evolution_pct': 0,
                        'evolution_sens': 'stable', 'evolution_jours': [],
                        'top_type': 'N/A', 'top_pct': 0, 'top_canal': 'N/A'})


@main_bp.route("/api/repartition-famille")
@login_required
def api_repartition_famille():
    rows = get_repartition_famille()
    return jsonify({
        'familles'    : [r['famille']    for r in rows],
        'nb_ventes'   : [r['nb_ventes']  for r in rows],
        'pourcentages': [r['pourcentage'] for r in rows],
    })


@main_bp.route("/api/evolution-journaliere")
@login_required
def api_evolution_journaliere():
    mois = request.args.get('mois', None)
    try:
        return jsonify(get_evolution_journaliere(mois))
    except Exception:
        return jsonify({'jours': [], 'moyenne': 0, 'mois': ''})


@main_bp.route("/api/top-vendeurs-perf")
@login_required
def api_top_vendeurs_perf():
    try:
        rows = get_top_vendeurs_perf(limit=5)
        return jsonify(rows)
    except Exception:
        return jsonify([])


@main_bp.route("/api/top10-produits")
@login_required
def api_top10_produits():
    try:
        rows = get_top10_produits_vendus()
        return jsonify(rows)
    except Exception:
        return jsonify([])


@main_bp.route("/api/mois-disponibles")
@login_required
def api_mois_disponibles():
    try:
        return jsonify(get_mois_disponibles())
    except Exception:
        return jsonify([])


@main_bp.route("/api/prediction/evolution")
@login_required
def api_prediction_evolution():
    periode   = request.args.get('periode')   or None
    canal     = request.args.get('canal')     or None
    famille   = request.args.get('famille')   or None
    categorie = request.args.get('categorie') or None
    cible     = request.args.get('cible')     or None
    algo      = request.args.get('algo')      or 'prophet'
    try:
        return jsonify(get_prediction_evolution(periode=periode, canal=canal,
                                                famille=famille, categorie=categorie,
                                                cible=cible, algo=algo))
    except Exception:
        return jsonify({'historique': [], 'projection': [], 'objectif_mensuel': 0})


@main_bp.route("/api/prediction/algorithmes")
@login_required
def api_prediction_algorithmes():
    try:
        return jsonify(get_prediction_algorithmes())
    except Exception:
        return jsonify([])


@main_bp.route("/api/paiements/kpis")
@login_required
def api_paiements_kpis_filtered():
    periode   = request.args.get('periode')   or None
    canal     = request.args.get('canal')     or None
    famille   = request.args.get('famille')   or None
    categorie = request.args.get('categorie') or None
    cible     = request.args.get('cible')     or None
    try:
        return jsonify(get_paiements_kpis_filtered(periode, canal, famille, categorie, cible))
    except Exception:
        return jsonify({})


@main_bp.route("/api/objectifs/kpis")
@login_required
def api_objectifs_kpis_filtered():
    canal   = request.args.get('canal')   or None
    periode = request.args.get('periode') or None
    try:
        return jsonify(get_objectifs_kpis_filtered(canal, periode))
    except Exception:
        return jsonify({})


@main_bp.route("/api/objectifs/charts")
@login_required
def api_objectifs_charts():
    canal   = request.args.get('canal')   or None
    periode = request.args.get('periode') or None
    try:
        return jsonify(get_objectifs_charts_filtered(canal, periode))
    except Exception:
        return jsonify({'par_mois': [], 'canaux_taux': []})


@main_bp.route("/api/paiements/evolution-mensuelle")
@login_required
def api_paiements_evolution():
    try:
        periode   = request.args.get('periode')   or None
        canal     = request.args.get('canal')     or None
        famille   = request.args.get('famille')   or None
        categorie = request.args.get('categorie') or None
        cible     = request.args.get('cible')     or None
        return jsonify(get_paiements_evolution(periode=periode, canal=canal,
                                               famille=famille, categorie=categorie,
                                               cible=cible))
    except Exception:
        return jsonify([])


@main_bp.route("/api/paiements/top-boutiques")
@login_required
def api_paiements_top_boutiques():
    periode   = request.args.get('periode')   or None
    canal     = request.args.get('canal')     or None
    famille   = request.args.get('famille')   or None
    categorie = request.args.get('categorie') or None
    cible     = request.args.get('cible')     or None
    try:
        return jsonify(get_paiements_top_boutiques_impayees(
            canal=canal, famille=famille, categorie=categorie, periode=periode, cible=cible))
    except Exception:
        return jsonify([])


@main_bp.route("/api/paiements/clients-risque")
@login_required
def api_paiements_clients_risque():
    periode   = request.args.get('periode')   or None
    canal     = request.args.get('canal')     or None
    famille   = request.args.get('famille')   or None
    categorie = request.args.get('categorie') or None
    cible     = request.args.get('cible')     or None
    try:
        return jsonify(get_paiements_clients_risque(
            canal=canal, famille=famille, categorie=categorie, periode=periode, cible=cible))
    except Exception:
        return jsonify([])


@main_bp.route("/api/qualite-donnees")
@login_required
def api_qualite_donnees():
    try:
        return jsonify(get_data_quality_kpis())
    except Exception:
        return jsonify({'total_ventes': 0, 'metrics': []})


@main_bp.route("/api/filter-options/cascade")
@login_required
def api_filter_options_cascade():
    """Options compatibles pour chaque filtre etant donne les selections courantes.
    Chaque dimension est calculee en appliquant tous les AUTRES filtres actifs."""
    periode   = request.args.get('periode')   or None
    canal     = request.args.get('canal')     or None
    famille   = request.args.get('famille')   or None
    categorie = request.args.get('categorie') or None
    cible     = request.args.get('cible')     or None
    try:
        return jsonify(get_cascade_filter_options(periode, canal, famille, categorie, cible))
    except Exception as e:
        return jsonify({'canal': [], 'famille': [], 'categorie': [], 'cible': [], 'error': str(e)})


@main_bp.route("/api/filter-options")
@login_required
def api_filter_options():
    """Valeurs distinctes pour filtres dynamiques — sources validees sur le DWH reel."""
    from flask_app.models import get_engine
    import pandas as pd
    engine = get_engine()
    result = {}
    queries = {
        # CANAL : dim_boutique.canal_vente
        'canal': """
            SELECT DISTINCT TRIM(b.canal_vente) AS val
            FROM dim_boutique b
            WHERE b.canal_vente IS NOT NULL AND TRIM(b.canal_vente) <> ''
            ORDER BY val
        """,
        # FAMILLE : groupes produits derives de dim_produit.product_type
        # Ces 4 valeurs correspondent exactement aux famille_cond_map utilises
        # dans get_paiements_evolution / get_prediction_evolution / _perf_filter.
        # On ne liste que les groupes reellement presents dans la base.
        'famille': """
            SELECT DISTINCT
                CASE
                    WHEN UPPER(TRIM(p.product_type)) IN ('SIM DATA','SIM VOIX','SIM FLYBOX','E-SIM')
                        THEN 'Mobile'
                    WHEN UPPER(TRIM(p.product_type)) IN ('ADSL','SIM FIXBOX')
                        THEN 'Fixe et Internet'
                    WHEN UPPER(TRIM(p.product_type)) = 'NEW'
                        THEN 'Convergence'
                    ELSE 'Autres'
                END AS val
            FROM dim_produit p
            WHERE p.product_type IS NOT NULL AND TRIM(p.product_type) <> ''
            ORDER BY val
        """,
        # CATEGORIE : dim_produit.product_type (valeurs reelles)
        'categorie': """
            SELECT DISTINCT TRIM(p.product_type) AS val
            FROM dim_produit p
            WHERE p.product_type IS NOT NULL AND TRIM(p.product_type) <> ''
            ORDER BY val
        """,
        # CIBLE : dim_offre.type_offre (ADSL, POSTPAYE, PREPAYE)
        'cible': """
            SELECT DISTINCT TRIM(o.type_offre) AS val
            FROM dim_offre o
            WHERE o.type_offre IS NOT NULL AND TRIM(o.type_offre) <> ''
            ORDER BY val
        """,
    }
    for key, q in queries.items():
        try:
            df = pd.read_sql(q, engine)
            result[key] = [str(v) for v in df['val'].dropna().tolist() if str(v).strip()]
        except Exception:
            result[key] = []
    return jsonify(result)


@main_bp.route("/api/performance/data")
@login_required
def api_performance_data():
    periode   = request.args.get('periode') or None
    canal     = request.args.get('canal') or None
    famille   = request.args.get('famille') or None
    categorie = request.args.get('categorie') or None
    cible     = request.args.get('cible') or None
    try:
        return jsonify(get_performance_all(periode, canal, famille, categorie, cible))
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@main_bp.route("/api/top5-offres")
@login_required
def api_top5_offres():
    try:
        return jsonify(get_top5_offres())
    except Exception:
        return jsonify([])


@main_bp.route("/api/repartition-ligne-produits")
@login_required
def api_repartition_ligne_produits():
    try:
        return jsonify(get_repartition_ligne_produits())
    except Exception:
        return jsonify([])


# ============================================================
# API ADMIN - CACHE
# ============================================================

@main_bp.route("/api/admin/cache/clear", methods=['POST'])
@admin_required
def admin_cache_clear():
    cache_clear()
    return jsonify({'status': 'Cache vide avec succes', 'stats': cache_stats()})


@main_bp.route("/api/admin/cache/stats")
@admin_required
def admin_cache_stats():
    return jsonify(cache_stats())


@main_bp.route("/api/admin/quota-status")
@admin_required
def admin_quota_status():
    from flask_app.agents.api_queue import is_quota_blocked, quota_unblocks_in
    stats = cache_stats()
    return jsonify({
        **stats,
        'quota_blocked':      is_quota_blocked(),
        'quota_unblocks_in':  quota_unblocks_in(),
        'cache_ttl_hours':    round(stats.get('ttl_seconds', 0) / 3600, 1),
        'hit_rate_pct':       stats.get('hit_rate', 0),
    })


# ============================================================
# API INTERPRETATIONS IA
# ============================================================

def _build_dashboard_kpis() -> dict:
    kpis  = get_kpis()
    top_v = get_top_vendeur_detail()
    top_b = get_top_boutique_detail()
    return {
        'total_ventes'      : int(kpis.get('total_ventes', 0)),
        'taux_paiement'     : get_taux_paiement(),
        'taux_realisation'  : round(float(kpis.get('taux_realisation', 0)), 2),
        'duree_engagement_moyenne': get_panier_moyen(),
        'panier_moyen'      : get_panier_moyen(),
        'top_vendeur_nom'   : top_v.get('nom', 'N/A'),
        'top_vendeur_ventes': top_v.get('nb_ventes', 0),
        'top_boutique_nom'  : top_b.get('nom', 'N/A'),
        'top_boutique_ventes': top_b.get('nb_ventes', 0),
    }


@main_bp.route("/api/interpret/dashboard-global")
@login_required
def api_interpret_dashboard_global():
    try:
        kpis = _build_dashboard_kpis()
        return jsonify({'interpretation': agent.dashboard_global(kpis)})
    except Exception:
        return jsonify({'interpretation': 'Analyse indisponible.'})


@main_bp.route("/api/interpret/kpi/<kpi_name>")
@login_required
def api_interpret_kpi(kpi_name):
    try:
        kpis  = _build_dashboard_kpis()
        top_v = get_top_vendeur_detail()
        top_b = get_top_boutique_detail()
        mapping = {
            'total-ventes'    : lambda: agent.kpi_total_ventes(kpis['total_ventes']),
            'taux-paiement'   : lambda: agent.kpi_taux_paiement(kpis['taux_paiement']),
            'taux-realisation': lambda: agent.kpi_taux_realisation(kpis['taux_realisation']),
            'panier-moyen'    : lambda: agent.kpi_panier_moyen(kpis['panier_moyen']),
            'top-vendeur'     : lambda: agent.kpi_top_vendeur(top_v),
            'top-boutique'    : lambda: agent.kpi_top_boutique(top_b),
        }
        fn = mapping.get(kpi_name)
        result = fn() if fn else 'Analyse non disponible pour ce KPI.'
        return jsonify({'interpretation': result})
    except Exception:
        return jsonify({'interpretation': 'Analyse indisponible.'})


@main_bp.route("/api/interpret/canal-repartition")
@login_required
def api_interpret_canal_repartition():
    try:
        rows     = get_repartition_canal()
        data_str = ', '.join(
            f"{r['canal']}: {r['nb_ventes']} ventes ({r['pourcentage']}%)"
            for r in rows
        )
        return jsonify({'interpretation': agent.canal_repartition(data_str)})
    except Exception:
        return jsonify({'interpretation': 'Analyse indisponible.'})


@main_bp.route("/api/interpret/canal-objectif")
@login_required
def api_interpret_canal_objectif():
    try:
        month    = request.args.get('month', datetime.now().strftime('%Y-%m'))
        rows     = get_objectif_canal_mois(month)
        data_str = ', '.join(
            f"{r['canal']}: {r['realisation']}/{r['objectif']} contrats"
            for r in rows
        )
        return jsonify({'interpretation': agent.canal_objectif(data_str, month)})
    except Exception:
        return jsonify({'interpretation': 'Analyse indisponible.'})


@main_bp.route("/api/interpret/produits-global")
@login_required
def api_interpret_produits_global():
    try:
        kpis_p = get_produits_kpis()
        return jsonify({'interpretation': agent.produits_global(
            int(kpis_p.get('total_produits', 0)),
            int(kpis_p.get('nb_types', 0)),
            int(kpis_p.get('nb_familles', 0)),
        )})
    except Exception:
        return jsonify({'interpretation': 'Analyse indisponible.'})


@main_bp.route("/api/interpret/produits-top5")
@login_required
def api_interpret_produits_top5():
    try:
        top5     = get_top5_produits_vendus()
        data_str = ', '.join(
            f"{r['produit']}: {r['total_vendu']} ventes" for r in top5
        ) if top5 else 'donnees non disponibles'
        return jsonify({'interpretation': agent.produits_top5(data_str)})
    except Exception:
        return jsonify({'interpretation': 'Analyse indisponible.'})


@main_bp.route("/api/interpret/objectifs-global")
@login_required
def api_interpret_objectifs_global():
    try:
        kpis_o     = get_objectifs_kpis()
        canaux     = get_taux_par_canal()
        canaux_str = ', '.join(
            f"{c['canal']}: {c['taux']}%" for c in canaux
        )
        return jsonify({'interpretation': agent.objectifs_global(
            round(float(kpis_o.get('taux_realisation', 0)), 2),
            canaux_str,
        )})
    except Exception:
        return jsonify({'interpretation': 'Analyse indisponible.'})


@main_bp.route("/api/interpret/objectifs-taux-global")
@login_required
def api_interpret_objectifs_taux_global():
    try:
        kpis_o = get_objectifs_kpis()
        taux   = round(float(kpis_o.get('taux_realisation', 0)), 2)
        return jsonify({'interpretation': agent.objectifs_taux_global(taux)})
    except Exception:
        return jsonify({'interpretation': 'Analyse indisponible.'})


@main_bp.route("/api/interpret/canal-detail/<canal_id>")
@login_required
def api_interpret_canal_detail(canal_id):
    try:
        canaux = get_taux_par_canal()
        canal  = next((c for c in canaux if c.get('canal_id') == canal_id), None)
        if not canal:
            return jsonify({'interpretation': 'Donnees canal non disponibles.'})
        return jsonify({'interpretation': agent.canal_detail(
            canal['canal'],
            float(canal.get('taux') or 0),
            float(canal.get('realisation') or 0),
            float(canal.get('objectif') or 0),
        )})
    except Exception:
        return jsonify({'interpretation': 'Analyse indisponible.'})


@main_bp.route("/api/interpret/objectifs-top15")
@login_required
def api_interpret_objectifs_top15():
    try:
        boutiques = get_objectifs_par_boutique(limit=15)
        if not boutiques:
            return jsonify({'interpretation': 'Donnees non disponibles.'})
        return jsonify({'interpretation': agent.objectifs_top15(boutiques)})
    except Exception:
        return jsonify({'interpretation': 'Analyse indisponible.'})


@main_bp.route("/api/interpret/objectifs-canal-compare")
@login_required
def api_interpret_objectifs_canal_compare():
    try:
        canaux = get_taux_par_canal()
        if not canaux:
            return jsonify({'interpretation': 'Donnees non disponibles.'})
        valid = [c for c in canaux if c.get('taux') is not None]
        if not valid:
            return jsonify({'interpretation': 'Donnees insuffisantes pour la comparaison.'})
        best  = max(valid, key=lambda c: c.get('taux') or 0)
        worst = min(valid, key=lambda c: c.get('taux') or 0)
        data_str = '; '.join(
            f"{c['canal']}: {c['taux']}% ({int(c.get('realisation') or 0):,}/{int(c.get('objectif') or 0):,} contrats)"
            for c in canaux
        )
        return jsonify({'interpretation': agent.objectifs_canal_compare(data_str, best, worst)})
    except Exception:
        return jsonify({'interpretation': 'Analyse indisponible.'})


@main_bp.route("/api/interpret/prediction-global")
@login_required
def api_interpret_prediction_global():
    try:
        data = get_prediction_evolution()
        return jsonify({'interpretation': agent.prediction_global(
            data.get('realise_actuel', 0),
            data.get('objectif_mensuel', 0),
            data.get('prediction_cloture', 0),
            data.get('mape_prophet', 3.6),
        )})
    except Exception:
        return jsonify({'interpretation': 'Analyse indisponible.'})


@main_bp.route("/api/interpret/paiements-global")
@login_required
def api_interpret_paiements_global():
    try:
        kpis = get_paiements_kpis()
        return jsonify({'interpretation': agent.paiements_global(
            kpis.get('taux_paiement', 0),
            kpis.get('factures_impayees', 0),
            kpis.get('taux_1ere_facture', 0),
        )})
    except Exception:
        return jsonify({'interpretation': 'Analyse indisponible.'})

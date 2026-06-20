/* =============================================================
   PALETTE ORANGE TUNISIE — PFE 2026 — Malek Ben Drissia
   Conforme au guide d'identité visuelle Orange Groupe.
   Source de vérité unique pour TOUTES les couleurs de graphiques.
============================================================= */
window.PALETTE = {
    /* ── Primaires Orange Groupe (charte officielle #FF6600) ── */
    orange   : '#FF6600',   // orange officiel charte Orange
    noir     : '#000000',
    blanc    : '#FFFFFF',

    /* ── Secondaires Orange Groupe (graphiques uniquement) ──── */
    bleu     : '#4BB4E6',   // Pantone 291 C
    vert     : '#50BE87',   // Pantone 346 C
    jaune    : '#FFD200',   // Pantone 109 C
    violet   : '#A885D8',   // Pantone 267 C
    rose     : '#FFB4E6',   // Pantone 705 C

    /* ── Statuts (exception charte : communiquent un STATUT) ── */
    rouge    : '#C62828',   // critique
    bleuNuit : '#000000',   // noir (objectifs, reference)
    carrot   : '#FF8533',   // orange intermediaire

    /* ── Séries charte (orange dominant + noir + secondaires officiels) ── */
    series : ['#FF6600', '#000000', '#4BB4E6', '#FFD200', '#50BE87', '#A885D8', '#FFB4E6', '#424242'],

    /* ── Dégradé orangé clair→foncé ────────────────────────── */
    degrade : ['#FFD4B3', '#FFA366', '#FF6600', '#E55C00', '#CC5200'],
};

/* ── Helpers ─────────────────────────────────────────────── */

PALETTE.lerpHex = function(h1, h2, t) {
    function r(h){ return parseInt(h.slice(1,3),16); }
    function g(h){ return parseInt(h.slice(3,5),16); }
    function b(h){ return parseInt(h.slice(5,7),16); }
    var R = Math.round(r(h1)+(r(h2)-r(h1))*t);
    var G = Math.round(g(h1)+(g(h2)-g(h1))*t);
    var B = Math.round(b(h1)+(b(h2)-b(h1))*t);
    return 'rgb('+R+','+G+','+B+')';
};

PALETTE.barColor = function(index, total) {
    var stops = PALETTE.degrade;
    var n = stops.length;
    var t = total > 1 ? index / (total - 1) : 0;
    var scaled = t * (n - 1);
    var i = Math.min(Math.floor(scaled), n - 2);
    return PALETTE.lerpHex(stops[i], stops[i + 1], scaled - i);
};

PALETTE.degradeColors = function(total) {
    var out = [];
    for (var i = 0; i < total; i++) out.push(PALETTE.barColor(i, total));
    return out;
};

PALETTE.statut = function(taux) {
    return taux >= 70 ? PALETTE.vert : taux >= 40 ? PALETTE.jaune : PALETTE.rouge;
};

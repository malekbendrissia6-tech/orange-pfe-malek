/**
 * dashboard.js - Graphiques et interpretations du Dashboard
 * Orange Tunisie - PFE 2026
 */

document.addEventListener('DOMContentLoaded', function () {
    // ===== REPARTITION CANAL =====
    loadCanalRepartition();

    // ===== FILTRE MOIS =====
    initMonthFilter();

    // ===== INTERPRETATIONS IA =====
    loadAllInterpretations();
});


// ===== CANAL REPARTITION =====
function loadCanalRepartition() {
    fetch('/api/canal-repartition')
        .then(function (r) { return r.json(); })
        .then(function (data) {
            if (!data.canaux || !data.canaux.length) return;

            var colors = [
                '#FF6600', '#1a1a1a', '#FFA366', '#555555',
                '#cc4400', '#888888', '#FF8533', '#333333'
            ];

            // Plugin inline: affiche "X ventes (Y%)" a droite de chaque barre
            var inlineLabelPlugin = {
                id: 'inlineLabels',
                afterDatasetsDraw: function (chart) {
                    var ctx = chart.ctx;
                    var meta = chart.getDatasetMeta(0);
                    var textCol = window.getChartTextColor ? window.getChartTextColor() : '#212529';
                    ctx.save();
                    ctx.font = '600 11px Inter, sans-serif';
                    ctx.fillStyle = textCol;
                    ctx.textBaseline = 'middle';
                    ctx.textAlign = 'left';
                    meta.data.forEach(function (bar, i) {
                        var nb  = (data.nb_ventes[i] || 0).toLocaleString('fr-FR');
                        var pct = data.pourcentages[i] || 0;
                        ctx.fillText(nb + ' ventes (' + pct + '%)', bar.x + 8, bar.y);
                    });
                    ctx.restore();
                }
            };

            new Chart(document.getElementById('chart-canal-bar'), {
                type: 'bar',
                plugins: [inlineLabelPlugin],
                data: {
                    labels: data.canaux,
                    datasets: [{
                        label: 'Nombre de ventes',
                        data: data.nb_ventes,
                        backgroundColor: data.canaux.map(function (_, i) {
                            return colors[i % colors.length];
                        }),
                        borderRadius: 5,
                        barThickness: 22
                    }]
                },
                options: {
                    indexAxis: 'y',
                    responsive: true,
                    maintainAspectRatio: false,
                    layout: { padding: { right: 170 } },
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            callbacks: {
                                label: function (ctx) {
                                    var i = ctx.dataIndex;
                                    return ' ' + ctx.parsed.x.toLocaleString('fr-FR') +
                                           ' ventes (' + data.pourcentages[i] + '%)';
                                }
                            }
                        }
                    },
                    scales: {
                        x: {
                            ticks: { color: window.getChartTextColor() },
                            grid:  { color: window.getChartGridColor() }
                        },
                        y: {
                            ticks: { color: window.getChartTextColor(), font: { size: 12, weight: '500' } },
                            grid:  { display: false }
                        }
                    }
                }
            });

            window.queueAI('/api/interpret/canal-repartition', 'ai-canal-repartition');
        })
        .catch(function () {});
}


// ===== FILTRE MOIS =====
function initMonthFilter() {
    var select = document.getElementById('filter-month');
    if (!select) return;

    var months = [
        { value: '2026-01', label: 'Janvier 2026' },
        { value: '2026-02', label: 'Fevrier 2026' },
        { value: '2026-03', label: 'Mars 2026' },
        { value: '2026-04', label: 'Avril 2026' },
        { value: '2026-05', label: 'Mai 2026' },
        { value: '2026-06', label: 'Juin 2026' },
        { value: '2026-07', label: 'Juillet 2026' },
        { value: '2026-08', label: 'Aout 2026' },
        { value: '2026-09', label: 'Septembre 2026' },
        { value: '2026-10', label: 'Octobre 2026' },
        { value: '2026-11', label: 'Novembre 2026' },
        { value: '2026-12', label: 'Decembre 2026' }
    ];

    var now = new Date();
    var currentMonth = now.getFullYear() + '-' + String(now.getMonth() + 1).padStart(2, '0');

    months.forEach(function (m) {
        var opt = document.createElement('option');
        opt.value = m.value;
        opt.textContent = m.label;
        if (m.value === currentMonth) opt.selected = true;
        select.appendChild(opt);
    });

    loadObjectifData(currentMonth);
    select.addEventListener('change', function (e) { loadObjectifData(e.target.value); });
}


var chartObjectifCanal = null;

function loadObjectifData(month) {
    fetch('/api/objectif-canal?month=' + encodeURIComponent(month))
        .then(function (r) { return r.json(); })
        .then(function (data) {
            if (chartObjectifCanal) chartObjectifCanal.destroy();

            chartObjectifCanal = new Chart(
                document.getElementById('chart-objectif-canal'), {
                type: 'bar',
                data: {
                    labels: data.canaux,
                    datasets: [
                        {
                            label: 'Objectif assigne (DT)',
                            data: data.objectifs,
                            backgroundColor: 'rgba(0,0,0,0.7)',
                            borderRadius: 4
                        },
                        {
                            label: 'Realisation effective (DT)',
                            data: data.realisations,
                            backgroundColor: '#FF6600',
                            borderRadius: 4
                        },
                        {
                            label: 'Taux (%)',
                            data: data.taux,
                            type: 'line',
                            borderColor: '#28a745',
                            backgroundColor: 'rgba(40,167,69,0.1)',
                            yAxisID: 'y1',
                            tension: 0.3,
                            pointBackgroundColor: '#28a745',
                            pointRadius: 5
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { position: 'top' },
                        tooltip: {
                            callbacks: {
                                label: function (ctx) {
                                    if (ctx.dataset.yAxisID === 'y1') {
                                        return ' ' + (ctx.parsed.y || 0).toLocaleString('fr-FR') + ' %';
                                    }
                                    return ' ' + (ctx.parsed.y || 0).toLocaleString('fr-FR') + ' DT';
                                }
                            }
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            title: { display: true, text: 'Montants (DT)', color: window.getChartTextColor() },
                            ticks: { color: window.getChartTextColor() },
                            grid:  { color: window.getChartGridColor() }
                        },
                        y1: {
                            position: 'right',
                            beginAtZero: true,
                            title: { display: true, text: 'Taux (%)', color: window.getChartTextColor() },
                            grid:  { drawOnChartArea: false },
                            ticks: {
                                color: window.getChartTextColor(),
                                callback: function (v) { return v + '%'; }
                            }
                        },
                        x: {
                            ticks: { color: window.getChartTextColor() },
                            grid:  { color: window.getChartGridColor() }
                        }
                    }
                }
            });

            window.queueAI('/api/interpret/canal-objectif?month=' + month, 'ai-canal-objectif');
        })
        .catch(function () {});
}


// ===== INTERPRETATIONS IA (via queue sequentielle globale) =====
function loadAllInterpretations() {
    window.queueAI('/api/interpret/dashboard-global',    'ai-dashboard-global');
    window.queueAI('/api/interpret/kpi/total-ventes',    'ai-total-ventes');
    window.queueAI('/api/interpret/kpi/taux-paiement',   'ai-taux-paiement');
    window.queueAI('/api/interpret/kpi/taux-realisation','ai-taux-realisation');
    window.queueAI('/api/interpret/kpi/panier-moyen',    'ai-panier-moyen');
    window.queueAI('/api/interpret/kpi/top-vendeur',     'ai-top-vendeur');
    window.queueAI('/api/interpret/kpi/top-boutique',    'ai-top-boutique');
}

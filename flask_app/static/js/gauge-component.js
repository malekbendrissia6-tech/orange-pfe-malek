/**
 * Composant Jauge Donut - Orange Tunisie
 * Usage : createGauge('canvas-id', value, options)
 */

function getGaugeColor(value, max) {
    const pct = (value / (max || 100)) * 100;
    if (pct < 50) return '#dc3545';
    if (pct < 80) return '#FF6600';
    return '#28a745';
}

function createGauge(canvasId, value, options) {
    options = options || {};
    var max       = options.max      || 100;
    var label     = options.label    || '';
    var color     = options.color    || getGaugeColor(value, max);
    var bgColor   = options.bgColor  || '#f0f0f0';
    var displayVal = Math.min(value, max);

    var canvas = document.getElementById(canvasId);
    if (!canvas) return null;

    return new Chart(canvas, {
        type: 'doughnut',
        data: {
            datasets: [{
                data: [displayVal, Math.max(max - displayVal, 0)],
                backgroundColor: [color, bgColor],
                borderWidth: 0,
                circumference: 270,
                rotation: 225
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '72%',
            plugins: {
                legend:  { display: false },
                tooltip: { enabled: false }
            }
        },
        plugins: [{
            id: 'centerText',
            afterDraw: function(chart) {
                var ctx = chart.ctx;
                var ca  = chart.chartArea;
                var cx  = ca.left + (ca.right  - ca.left) / 2;
                var cy  = ca.top  + (ca.bottom - ca.top)  / 2;

                ctx.save();
                ctx.font = 'bold 20px Inter, sans-serif';
                ctx.fillStyle = color;
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.fillText(value + '%', cx, cy - 6);

                if (label) {
                    ctx.font = '11px Inter, sans-serif';
                    ctx.fillStyle = '#888';
                    ctx.fillText(label, cx, cy + 16);
                }
                ctx.restore();
            }
        }]
    });
}

function createProgressBar(containerId, value, max, label) {
    var container = document.getElementById(containerId);
    if (!container) return;
    var pct   = ((value / (max || 1)) * 100).toFixed(1);
    var color = getGaugeColor(value, max);
    container.innerHTML =
        '<div class="d-flex justify-content-between mb-1">' +
            '<small><strong>' + label + '</strong></small>' +
            '<small>' + value + ' / ' + max + ' (' + pct + '%)</small>' +
        '</div>' +
        '<div class="progress" style="height: 12px;">' +
            '<div class="progress-bar" role="progressbar" ' +
                 'style="width:' + pct + '%; background-color:' + color + ';">' +
            '</div>' +
        '</div>';
}

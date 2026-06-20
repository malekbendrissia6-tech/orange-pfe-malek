/**
 * theme.js - Utilitaires JS communs : queue IA + accordeon banners
 * Orange Tunisie - PFE 2026
 */

// Couleurs Chart.js (mode clair uniquement)
window.getChartTextColor = function () { return '#212529'; };
window.getChartGridColor = function () { return '#e9ecef'; };


// ===== QUEUE INTERPRETATIONS IA (chargement sequentiel, anti-quota) =====

(function () {
    var _queue   = [];
    var _running = false;
    var _DELAY   = 250;

    function _next() {
        if (_queue.length === 0) { _running = false; return; }
        _running = true;
        var task = _queue.shift();
        var el   = document.getElementById(task.id);

        fetch(task.url, { credentials: 'same-origin' })
            .then(function (r) {
                if (r.status === 401) {
                    window.location.href = '/auth/login';
                    return null;
                }
                return r.ok ? r.json() : null;
            })
            .then(function (d) {
                if (!d) { _scheduleNext(); return; }
                var txt = (d.interpretation || '').trim();
                if (el) {
                    if (txt) {
                        el.innerHTML = txt;
                        el.classList.remove('ai-error');
                    } else {
                        _showError(el, task.url);
                    }
                }
                _scheduleNext();
            })
            .catch(function () {
                if (el) _showError(el, task.url);
                _scheduleNext();
            });
    }

    function _scheduleNext() {
        setTimeout(_next, _DELAY);
    }

    function _showError(el, url) {
        el.innerHTML =
            '<span class="ai-error-msg text-muted" style="font-size:12px;">' +
            'Analyse momentanement indisponible. ' +
            '<button class="btn-ai-retry" onclick="window._retryAI(this,\'' + url + '\',\'' + el.id + '\')" ' +
            'style="background:none;border:none;color:#FF6600;cursor:pointer;font-size:12px;padding:0;text-decoration:underline;">' +
            'Reessayer' +
            '</button></span>';
    }

    window.queueAI = function (url, elementId) {
        var el = document.getElementById(elementId);
        if (el) {
            el.innerHTML = '<em class="kpi-ai-loading" style="color:#6c757d;font-size:12px;">Analyse en cours...</em>';
        }
        _queue.push({ url: url, id: elementId });
        if (!_running) _next();
    };

    window._retryAI = function (btn, url, elementId) {
        var el = document.getElementById(elementId);
        if (el) el.innerHTML = '<em class="kpi-ai-loading" style="color:#6c757d;font-size:12px;">Analyse en cours...</em>';
        _queue.unshift({ url: url, id: elementId });
        if (!_running) _next();
    };
})();


// ===== BANNERS IA ACCORDEON =====

function toggleAiBanner(bannerId) {
    var banner = document.getElementById(bannerId);
    if (!banner) return;
    banner.classList.toggle('collapsed');
    var isCollapsed = banner.classList.contains('collapsed');
    sessionStorage.setItem('banner_' + bannerId, isCollapsed ? '1' : '0');
}

document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('.global-ai-banner[id]').forEach(function (banner) {
        var id    = banner.id;
        var saved = sessionStorage.getItem('banner_' + id);
        if (saved === '1') {
            banner.classList.add('collapsed');
        }
    });
});

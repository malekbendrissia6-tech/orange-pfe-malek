/**
 * Chatbot Orange Tunisie — chatbot.js
 * Ctrl+K pour ouvrir / fermer
 */

var _cbConvId   = null;
var _cbCharts   = [];
var _cbSending  = false;

// ================================================================
// Ouverture / Fermeture
// ================================================================

function toggleChatbot() {
  var sidebar = document.getElementById('chatbot-sidebar');
  var btn     = document.getElementById('chatbot-toggle-btn');
  var isOpen  = sidebar.classList.toggle('open');
  if (isOpen) {
    btn.classList.add('hidden');
    document.getElementById('chatbot-input').focus();
  } else {
    btn.classList.remove('hidden');
  }
}

// ================================================================
// Nouvelle conversation
// ================================================================

function newConversation() {
  if (!confirm('Demarrer une nouvelle conversation ?')) return;
  _cbConvId = null;
  _cbCharts.forEach(function (c) { try { c.destroy(); } catch(e){} });
  _cbCharts = [];
  document.getElementById('chatbot-messages').innerHTML =
    '<div class="cb-msg cb-msg-assistant">' +
    '<div class="cb-avatar">O</div>' +
    '<div class="cb-content"><p>Nouvelle conversation. Comment puis-je vous aider ?</p></div>' +
    '</div>';
}

// ================================================================
// Suggestion rapide
// ================================================================

function askQuestion(q) {
  document.getElementById('chatbot-input').value = q;
  sendMessage(null);
}

// ================================================================
// Envoi message
// ================================================================

function sendMessage(evt) {
  if (evt) evt.preventDefault();
  if (_cbSending) return;

  var input   = document.getElementById('chatbot-input');
  var message = input.value.trim();
  if (!message) return;

  // Supprimer suggestions
  var sugg = document.getElementById('cb-suggestions');
  if (sugg) sugg.remove();

  _addMsg('user', message);
  input.value = '';
  _cbSending  = true;
  _setLoading(true);

  var btn = document.getElementById('cb-send-btn');
  if (btn) btn.disabled = true;

  fetch('/chatbot/api/send', {
    method:      'POST',
    headers:     { 'Content-Type': 'application/json' },
    credentials: 'same-origin',
    body: JSON.stringify({ message: message, conversation_id: _cbConvId }),
  })
  .then(function (r) {
    if (r.status === 401) { window.location.href = '/auth/login'; return null; }
    if (!r.ok) throw new Error('HTTP ' + r.status);
    return r.json();
  })
  .then(function (data) {
    if (!data) return;
    _cbConvId = data.conversation_id;
    _addMsg('assistant', data.response);
  })
  .catch(function () {
    _addMsg('assistant', { text: "Une erreur est survenue. Reessayez.", chart: null, data: null, sources: [] });
  })
  .finally(function () {
    _cbSending = false;
    _setLoading(false);
    if (btn) btn.disabled = false;
    input.focus();
  });
}

// ================================================================
// Ajouter message a l UI
// ================================================================

function _addMsg(role, content) {
  var messagesDiv = document.getElementById('chatbot-messages');
  var wrap = document.createElement('div');
  wrap.className = 'cb-msg cb-msg-' + role;

  var avatarLabel = role === 'user' ? 'U' : 'O';
  var html;

  if (typeof content === 'string') {
    html = '<p>' + _esc(content) + '</p>';
  } else {
    html = '<p>' + _esc(content.text || '') + '</p>';

    if (content.chart) {
      var chartId = 'cb-chart-' + Date.now();
      html += '<div class="cb-chart-wrap"><canvas id="' + chartId + '"></canvas></div>';
      setTimeout(function () { _renderChart(chartId, content.chart); }, 80);
    }

    if (!content.chart && content.data && content.data.length > 0) {
      html += _buildTable(content.data);
    }

    if (content.sources && content.sources.length > 0) {
      html += '<div class="cb-source">Sources : ' + content.sources.join(', ') + '</div>';
    }
  }

  wrap.innerHTML =
    '<div class="cb-avatar">' + avatarLabel + '</div>' +
    '<div class="cb-content">' + html + '</div>';

  messagesDiv.appendChild(wrap);
  messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

// ================================================================
// Tableau de donnees
// ================================================================

function _buildTable(data) {
  if (!data || data.length === 0) return '';
  var keys = Object.keys(data[0]).slice(0, 5);
  var maxR = Math.min(data.length, 7);
  var h = '<div class="cb-table-wrap"><table><thead><tr>';
  keys.forEach(function (k) { h += '<th>' + _esc(k) + '</th>'; });
  h += '</tr></thead><tbody>';
  for (var i = 0; i < maxR; i++) {
    h += '<tr>';
    keys.forEach(function (k) {
      var v = data[i][k];
      if (typeof v === 'number') v = v.toLocaleString('fr-FR');
      h += '<td>' + _esc(String(v == null ? '' : v)) + '</td>';
    });
    h += '</tr>';
  }
  if (data.length > maxR) {
    h += '<tr><td colspan="' + keys.length + '" style="text-align:center;color:#adb5bd;font-style:italic;">' +
         '... et ' + (data.length - maxR) + ' autres</td></tr>';
  }
  h += '</tbody></table></div>';
  return h;
}

// ================================================================
// Rendu graphique Chart.js
// ================================================================

function _renderChart(canvasId, config) {
  var canvas = document.getElementById(canvasId);
  if (!canvas || !window.Chart) return;
  try {
    var chart = new Chart(canvas, config);
    _cbCharts.push(chart);
  } catch (e) {
    console.warn('[Chatbot] Erreur Chart.js:', e);
  }
}

// ================================================================
// Typing indicator
// ================================================================

function _setLoading(show) {
  var el = document.getElementById('chatbot-typing');
  if (!el) return;
  el.style.display = show ? 'flex' : 'none';
  if (show) {
    var msgs = document.getElementById('chatbot-messages');
    msgs.scrollTop = msgs.scrollHeight;
  }
}

// ================================================================
// Export PDF
// ================================================================

function exportCurrentPdf() {
  if (!_cbConvId) {
    alert('Aucune conversation a exporter. Posez d abord une question.');
    return;
  }
  window.open('/chatbot/api/conversation/' + _cbConvId + '/export', '_blank');
}

// ================================================================
// Historique des conversations
// ================================================================

function showHistory() {
  fetch('/chatbot/api/conversations', { credentials: 'same-origin' })
    .then(function (r) { return r.json(); })
    .then(function (data) {
      var convs = data.conversations || [];
      var listEl = document.getElementById('cb-history-list');
      if (!listEl) return;

      if (convs.length === 0) {
        listEl.innerHTML = '<p style="text-align:center; padding:20px; color:var(--text-secondary);">Aucune conversation precedente.</p>';
      } else {
        listEl.innerHTML = '';
        convs.forEach(function (c) {
          var item = document.createElement('div');
          item.className = 'cb-history-item';
          item.innerHTML =
            '<div class="cb-history-item-title">' + _esc(c.titre) + '</div>' +
            '<div class="cb-history-item-date">' +
              new Date(c.updated).toLocaleString('fr-FR') +
            '</div>';
          item.addEventListener('click', function () {
            closeHistoryModal();
            loadConversation(c.id);
          });
          listEl.appendChild(item);
        });
      }

      document.getElementById('cb-history-modal').style.display = 'flex';
    })
    .catch(function () { alert('Impossible de charger l historique.'); });
}

function closeHistoryModal() {
  var modal = document.getElementById('cb-history-modal');
  if (modal) modal.style.display = 'none';
}

function loadConversation(convId) {
  fetch('/chatbot/api/conversation/' + convId, { credentials: 'same-origin' })
    .then(function (r) { return r.json(); })
    .then(function (data) {
      _cbConvId = convId;
      _cbCharts.forEach(function (c) { try { c.destroy(); } catch(e){} });
      _cbCharts = [];

      var messagesDiv = document.getElementById('chatbot-messages');
      messagesDiv.innerHTML = '';

      (data.messages || []).forEach(function (m) {
        if (m.role === 'user') {
          _addMsg('user', m.content);
        } else if (m.role === 'assistant') {
          var meta = m.metadata || {};
          _addMsg('assistant', {
            text:    m.content,
            chart:   meta.chart   || null,
            data:    meta.data    || null,
            sources: meta.sources || [],
          });
        }
      });
    })
    .catch(function (e) { console.error(e); });
}

// ================================================================
// Helpers
// ================================================================

function _esc(str) {
  var d = document.createElement('div');
  d.textContent = String(str);
  return d.innerHTML;
}

// ================================================================
// Raccourci clavier Ctrl+K
// ================================================================

document.addEventListener('keydown', function (e) {
  if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
    e.preventDefault();
    toggleChatbot();
  }
  if (e.key === 'Escape') {
    var modal = document.getElementById('cb-history-modal');
    if (modal && modal.style.display !== 'none') {
      closeHistoryModal();
      return;
    }
    var sidebar = document.getElementById('chatbot-sidebar');
    if (sidebar && sidebar.classList.contains('open')) {
      toggleChatbot();
    }
  }
});

// Fermer la modal si clic en dehors
document.addEventListener('click', function (e) {
  var modal = document.getElementById('cb-history-modal');
  if (modal && e.target === modal) closeHistoryModal();
});

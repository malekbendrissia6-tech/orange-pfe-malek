"""Routes API du chatbot Orange Tunisie."""
import os
import json
from datetime import datetime

import psycopg2
import psycopg2.extras
from flask import Blueprint, request, jsonify, session, send_file
from dotenv import load_dotenv

from flask_app.auth.decorators import login_required
from .agent_orya import ORYAAgent
from .pdf_exporter import PDFExporter

load_dotenv()

chatbot_bp = Blueprint('chatbot', __name__, url_prefix='/chatbot')

_orya_agents: dict[int, ORYAAgent] = {}
_pdf_exp = PDFExporter()


def _get_orya(user_id: int) -> ORYAAgent:
    """Une instance ORYAAgent par utilisateur (contexte conversationnel isolé)."""
    if user_id not in _orya_agents:
        _orya_agents[user_id] = ORYAAgent()
    return _orya_agents[user_id]


def _db():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        port=os.getenv('DB_PORT', '5432'),
        database=os.getenv('DB_NAME', 'orange_dwh'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', 'malek1'),
    )


# ============================================================
# SEND MESSAGE
# ============================================================

@chatbot_bp.route('/api/send', methods=['POST'])
@login_required
def send_message():
    data    = request.get_json(silent=True) or {}
    message = data.get('message', '').strip()
    conv_id = data.get('conversation_id')

    if not message:
        return jsonify({'error': 'Message vide'}), 400

    user_id = session['user_id']
    conn = _db()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    try:
        # Creer conversation si necessaire
        if not conv_id:
            titre = message[:50] + ('...' if len(message) > 50 else '')
            cur.execute(
                "INSERT INTO chatbot_conversations (user_id, titre) VALUES (%s,%s) RETURNING conversation_id",
                (user_id, titre)
            )
            conv_id = cur.fetchone()['conversation_id']

        # Sauvegarder message utilisateur
        cur.execute(
            "INSERT INTO chatbot_messages (conversation_id, role, content) VALUES (%s,'user',%s)",
            (conv_id, message)
        )
        conn.commit()

        # Traitement IA via Groq/Llama (ORYAAgent)
        result = _get_orya(user_id).ask(message)

        # Format compatible frontend {text, chart, data, sources, intent}
        if result['success']:
            response = {
                'text':    result['response'],
                'chart':   None,
                'data':    None,
                'sources': ['Llama 3.3 70B (Groq)'],
                'intent':  'kpi_query',
            }
        else:
            response = {
                'text':    result.get('response', 'Une erreur est survenue.'),
                'chart':   None,
                'data':    None,
                'sources': [],
                'intent':  'error',
            }

        # Sauvegarder reponse assistant
        meta = json.dumps({
            'chart':       None,
            'data':        None,
            'sources':     response['sources'],
            'intent':      response['intent'],
            'sql':         result.get('sql'),
            'explanation': result.get('explanation'),
            'warnings':    result.get('warnings'),
        }, default=str)

        cur.execute(
            "INSERT INTO chatbot_messages (conversation_id, role, content, metadata) "
            "VALUES (%s,'assistant',%s,%s::jsonb) RETURNING message_id, created_at",
            (conv_id, response['text'], meta)
        )
        row = cur.fetchone()

        cur.execute(
            "UPDATE chatbot_conversations SET updated_at=CURRENT_TIMESTAMP WHERE conversation_id=%s",
            (conv_id,)
        )
        conn.commit()

        return jsonify({
            'conversation_id': conv_id,
            'message_id':      row['message_id'],
            'response':        response,
            'timestamp':       row['created_at'].isoformat(),
        })

    except Exception as e:
        conn.rollback()
        print(f"[chatbot/send] {e}")
        return jsonify({'error': 'Erreur serveur'}), 500
    finally:
        cur.close()
        conn.close()


# ============================================================
# LIST / GET / DELETE CONVERSATIONS
# ============================================================

@chatbot_bp.route('/api/conversations', methods=['GET'])
@login_required
def list_conversations():
    user_id = session['user_id']
    conn = _db()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        "SELECT conversation_id, titre, updated_at FROM chatbot_conversations "
        "WHERE user_id=%s ORDER BY updated_at DESC LIMIT 50",
        (user_id,)
    )
    rows = cur.fetchall()
    cur.close(); conn.close()
    return jsonify({'conversations': [
        {'id': r['conversation_id'], 'titre': r['titre'], 'updated': r['updated_at'].isoformat()}
        for r in rows
    ]})


@chatbot_bp.route('/api/conversation/<int:conv_id>', methods=['GET'])
@login_required
def get_conversation(conv_id):
    user_id = session['user_id']
    conn = _db()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute(
        "SELECT * FROM chatbot_conversations WHERE conversation_id=%s AND user_id=%s",
        (conv_id, user_id)
    )
    conv = cur.fetchone()
    if not conv:
        cur.close(); conn.close()
        return jsonify({'error': 'Non trouve'}), 404

    cur.execute(
        "SELECT role, content, metadata, created_at FROM chatbot_messages "
        "WHERE conversation_id=%s ORDER BY created_at ASC",
        (conv_id,)
    )
    msgs = cur.fetchall()
    cur.close(); conn.close()

    return jsonify({
        'conversation': {'id': conv['conversation_id'], 'titre': conv['titre']},
        'messages': [
            {'role': m['role'], 'content': m['content'],
             'metadata': m['metadata'], 'timestamp': m['created_at'].isoformat()}
            for m in msgs
        ],
    })


@chatbot_bp.route('/api/conversation/<int:conv_id>', methods=['DELETE'])
@login_required
def delete_conversation(conv_id):
    user_id = session['user_id']
    conn = _db()
    cur  = conn.cursor()
    cur.execute(
        "DELETE FROM chatbot_conversations WHERE conversation_id=%s AND user_id=%s",
        (conv_id, user_id)
    )
    conn.commit(); cur.close(); conn.close()
    return jsonify({'success': True})


# ============================================================
# EXPORT PDF
# ============================================================

@chatbot_bp.route('/api/conversation/<int:conv_id>/export', methods=['GET'])
@login_required
def export_pdf(conv_id):
    user_id = session['user_id']
    conn = _db()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute(
        "SELECT c.*, u.nom_complet FROM chatbot_conversations c "
        "JOIN users u ON c.user_id=u.user_id "
        "WHERE c.conversation_id=%s AND c.user_id=%s",
        (conv_id, user_id)
    )
    conv = cur.fetchone()
    if not conv:
        cur.close(); conn.close()
        return jsonify({'error': 'Non trouve'}), 404

    cur.execute(
        "SELECT role, content, created_at FROM chatbot_messages "
        "WHERE conversation_id=%s ORDER BY created_at ASC",
        (conv_id,)
    )
    msgs = cur.fetchall()
    cur.close(); conn.close()

    try:
        pdf_buf = _pdf_exp.export_conversation(
            dict(conv),
            [dict(m) for m in msgs],
            {'nom_complet': conv['nom_complet']},
        )
        fname = f"assistant_orange_{conv_id}_{datetime.now().strftime('%Y%m%d')}.pdf"
        return send_file(pdf_buf, as_attachment=True, download_name=fname, mimetype='application/pdf')
    except RuntimeError as e:
        return jsonify({'error': str(e)}), 501

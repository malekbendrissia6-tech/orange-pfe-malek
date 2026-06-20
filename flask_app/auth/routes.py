"""Routes pour l'authentification - Orange Tunisie."""
import json
import random
import string
from datetime import datetime, timedelta

from flask import render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash

from . import auth_bp
from .models import User, get_db_connection
from .decorators import admin_required, login_required
from flask_app.agents.preloader import preload_interpretations_async


# ============================================================
# HELPERS
# ============================================================

def _generate_otp():
    return ''.join(random.choices(string.digits, k=6))


def _send_otp_email(email, code, nom):
    try:
        from flask_mail import Message
        from flask_app import mail
        msg = Message(
            subject='Orange Tunisie — Code de verification',
            recipients=[email],
        )
        msg.html = f"""
        <div style="font-family:Arial,sans-serif;max-width:560px;margin:auto;">
          <div style="background:#FF6600;color:white;padding:20px;text-align:center;border-radius:8px 8px 0 0;">
            <h2 style="margin:0;">orange&#x2122; Tunisie</h2>
          </div>
          <div style="padding:28px;background:#FFF5EE;border-radius:0 0 8px 8px;">
            <p>Bonjour <strong>{nom}</strong>,</p>
            <p>Voici votre code de verification :</p>
            <div style="text-align:center;margin:24px 0;">
              <span style="font-size:40px;font-weight:900;color:#FF6600;letter-spacing:8px;">{code}</span>
            </div>
            <p style="color:#888;font-size:12px;">Ce code expire dans 5 minutes. Ne le partagez pas.</p>
          </div>
        </div>
        """
        mail.send(msg)
        return True
    except Exception as e:
        print(f"[OTP email] {e}")
        return False


def _db_exec(sql, params=()):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        conn.commit()
        cur.close()
    finally:
        conn.close()


def _db_query(sql, params=()):
    import psycopg2.extras
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(sql, params)
        rows = cur.fetchall()
        cur.close()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _redirect_by_role(user):
    """Redirige selon le rôle de l'utilisateur."""
    if user.role == 'data_engineer':
        return redirect(url_for('data_quality.accueil'))
    return redirect(url_for('main.index'))


# ============================================================
# LOGIN / LOGOUT
# ============================================================

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        role = session.get('role')
        if role == 'data_engineer':
            return redirect(url_for('data_quality.accueil'))
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        if not email or not password:
            flash('Email et mot de passe obligatoires.', 'danger')
            return render_template('auth/login.html')

        result = User.find_by_email(email)
        if not result:
            flash('Email ou mot de passe incorrect.', 'danger')
            return render_template('auth/login.html')

        user, password_hash = result

        if not User.verify_password(password_hash, password):
            flash('Email ou mot de passe incorrect.', 'danger')
            return render_template('auth/login.html')

        if user.is_blocked:
            flash('Votre compte a ete bloque. Contactez l\'administrateur.', 'danger')
            return render_template('auth/login.html')

        session['user_id']      = int(user.user_id)
        session['email']        = user.email
        session['nom_complet']  = user.nom_complet
        session['role']         = user.role
        session['allowed_pages']= json.dumps(user.allowed_pages)
        session.permanent       = True

        if user.last_login:
            dt = user.last_login
            session['last_login_str'] = dt.strftime('%d/%m/%Y a %H:%M') if hasattr(dt, 'strftime') else str(dt)
        else:
            session['last_login_str'] = 'premiere visite'

        User.update_last_login(int(user.user_id))

        if user.role != 'data_engineer':
            preload_interpretations_async()

        flash(f"Bienvenue, {user.nom_complet} !", 'success')
        return _redirect_by_role(user)

    return render_template('auth/login.html')


@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('Vous avez ete deconnecte.', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/profile')
@login_required
def profile():
    user = User.find_by_id(session['user_id'])
    return render_template('auth/profile.html', user=user)


# ============================================================
# INSCRIPTION (admin seulement en production)
# ============================================================

@auth_bp.route('/inscription', methods=['GET', 'POST'])
def inscription():
    """Accessible uniquement si non connecté (désactivée en prod — utiliser /admin/users)."""
    if 'user_id' in session:
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        nom       = request.form.get('nom_complet', '').strip()
        email     = request.form.get('email', '').strip().lower()
        telephone = request.form.get('telephone', '').strip()
        password  = request.form.get('password', '')
        password2 = request.form.get('password_confirm', '')

        if not nom or not email or not password:
            flash('Tous les champs obligatoires doivent etre remplis.', 'danger')
            return render_template('auth/inscription.html')

        if password != password2:
            flash('Les mots de passe ne correspondent pas.', 'danger')
            return render_template('auth/inscription.html')

        if len(password) < 8:
            flash('Mot de passe trop court (8 caracteres minimum).', 'danger')
            return render_template('auth/inscription.html')

        existing = _db_query("SELECT user_id FROM users WHERE email = %s", (email,))
        if existing:
            flash('Cet email est deja enregistre.', 'warning')
            return render_template('auth/inscription.html')

        otp        = _generate_otp()
        otp_expire = datetime.now() + timedelta(minutes=5)
        pwd_hash   = generate_password_hash(password)

        _db_exec("""
            INSERT INTO users
              (email, password_hash, nom_complet, telephone, otp_code, otp_expire_at,
               email_verifie, provider, role, is_active, allowed_pages)
            VALUES (%s,%s,%s,%s,%s,%s, FALSE,'local','commercial', TRUE, '[]')
        """, (email, pwd_hash, nom, telephone or None, otp, otp_expire))

        sent = _send_otp_email(email, otp, nom)
        if sent:
            flash(f'Code envoye a {email}. Verifiez votre boite mail.', 'success')
        else:
            flash(f'Email non envoye (config. mail). Code de test : {otp}', 'warning')

        return redirect(url_for('auth.verify_otp', email=email))

    return render_template('auth/inscription.html')


# ============================================================
# OTP
# ============================================================

@auth_bp.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp():
    if request.method == 'GET':
        email = request.args.get('email', '')
        return render_template('auth/verify_otp.html', email=email)

    email = request.form.get('email', '')
    otp   = request.form.get('otp', '').strip()

    rows = _db_query("""
        SELECT user_id, nom_complet, otp_code, otp_expire_at
        FROM users WHERE email = %s
    """, (email,))

    if not rows:
        flash('Utilisateur introuvable.', 'danger')
        return redirect(url_for('auth.inscription'))

    user = rows[0]

    if not user['otp_expire_at'] or datetime.now() > user['otp_expire_at']:
        flash('Code expire. Cliquez sur "Renvoyer".', 'warning')
        return render_template('auth/verify_otp.html', email=email)

    if otp != user['otp_code']:
        flash('Code incorrect.', 'danger')
        return render_template('auth/verify_otp.html', email=email)

    _db_exec("""
        UPDATE users
        SET email_verifie = TRUE, otp_code = NULL, otp_expire_at = NULL
        WHERE email = %s
    """, (email,))

    session['user_id']     = user['user_id']
    session['email']       = email
    session['nom_complet'] = user['nom_complet']
    session['role']        = 'commercial'
    session.permanent      = True

    flash(f"Bienvenue {user['nom_complet']} ! Compte active avec succes.", 'success')
    return redirect(url_for('main.index'))


@auth_bp.route('/resend-otp')
def resend_otp():
    email = request.args.get('email', '')
    rows  = _db_query("SELECT nom_complet FROM users WHERE email = %s", (email,))
    if not rows:
        flash('Email introuvable.', 'danger')
        return redirect(url_for('auth.inscription'))

    otp    = _generate_otp()
    expire = datetime.now() + timedelta(minutes=5)
    _db_exec("UPDATE users SET otp_code=%s, otp_expire_at=%s WHERE email=%s",
             (otp, expire, email))

    sent = _send_otp_email(email, otp, rows[0]['nom_complet'])
    if sent:
        flash('Nouveau code envoye.', 'success')
    else:
        flash(f'Nouveau code (test): {otp}', 'warning')

    return redirect(url_for('auth.verify_otp', email=email))


# ============================================================
# ADMIN — GESTION DES UTILISATEURS
# ============================================================

ALL_PAGES = [
    {'key': 'performance',  'label': 'Performance'},
    {'key': 'objectifs',    'label': 'Objectifs'},
    {'key': 'prediction',   'label': 'Prediction'},
    {'key': 'paiements',    'label': 'Paiements'},
]


@auth_bp.route('/admin/users')
@admin_required
def admin_users():
    users = User.get_all()
    return render_template('admin/users.html', users=users, all_pages=ALL_PAGES)


@auth_bp.route('/admin/users/create', methods=['POST'])
@admin_required
def admin_create_user():
    email         = request.form.get('email', '').strip().lower()
    nom_complet   = request.form.get('nom_complet', '').strip()
    password      = request.form.get('password', '')
    role          = request.form.get('role', 'commercial')
    phone         = request.form.get('phone', '').strip() or None
    allowed_pages = request.form.getlist('allowed_pages')

    if not email or not nom_complet or not password:
        flash('Email, nom et mot de passe sont obligatoires.', 'danger')
        return redirect(url_for('auth.admin_users'))

    existing = _db_query("SELECT user_id FROM users WHERE email = %s", (email,))
    if existing:
        flash('Cet email est deja utilise.', 'warning')
        return redirect(url_for('auth.admin_users'))

    uid = User.create(email, password, nom_complet, role, phone, allowed_pages)
    if uid:
        flash(f'Utilisateur {nom_complet} cree avec succes.', 'success')
    else:
        flash('Erreur lors de la creation.', 'danger')
    return redirect(url_for('auth.admin_users'))


@auth_bp.route('/admin/users/<int:user_id>/edit', methods=['POST'])
@admin_required
def admin_edit_user(user_id):
    nom_complet   = request.form.get('nom_complet', '').strip()
    role          = request.form.get('role', 'commercial')
    phone         = request.form.get('phone', '').strip() or None
    allowed_pages = request.form.getlist('allowed_pages')

    User.update(user_id, nom_complet, role, phone, allowed_pages)
    flash('Utilisateur mis a jour.', 'success')
    return redirect(url_for('auth.admin_users'))


@auth_bp.route('/admin/users/<int:user_id>/toggle-block', methods=['POST'])
@admin_required
def admin_toggle_block(user_id):
    # Empêcher de se bloquer soi-même
    if user_id == session.get('user_id'):
        flash('Vous ne pouvez pas bloquer votre propre compte.', 'warning')
        return redirect(url_for('auth.admin_users'))
    new_state = User.toggle_blocked(user_id)
    status = 'bloque' if new_state else 'debloque'
    flash(f'Utilisateur {status} avec succes.', 'success')
    return redirect(url_for('auth.admin_users'))


@auth_bp.route('/admin/users/<int:user_id>/delete', methods=['POST'])
@admin_required
def admin_delete_user(user_id):
    if user_id == session.get('user_id'):
        flash('Vous ne pouvez pas supprimer votre propre compte.', 'warning')
        return redirect(url_for('auth.admin_users'))
    User.delete(user_id)
    flash('Utilisateur supprime.', 'success')
    return redirect(url_for('auth.admin_users'))

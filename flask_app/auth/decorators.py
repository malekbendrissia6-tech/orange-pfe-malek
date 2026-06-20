from functools import wraps
from flask import session, redirect, url_for, flash, request, jsonify
from .models import User


def _get_current_user():
    uid = session.get('user_id')
    if not uid:
        return None
    return User.find_by_id(uid)


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if request.path.startswith('/api/'):
                return jsonify({'error': 'non_authentifie'}), 401
            flash('Connexion requise pour acceder a cette page.', 'warning')
            return redirect(url_for('auth.login', next=request.url))
        # Vérifier si bloqué à chaque requête
        user = _get_current_user()
        if user and user.is_blocked:
            session.clear()
            flash('Votre compte a ete bloque. Contactez l\'administrateur.', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        if session.get('role') != 'admin':
            flash('Acces administrateur requis.', 'danger')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function


def page_required(page_name):
    """Vérifie que l'utilisateur a accès à la page donnée (admin = bypass)."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                return redirect(url_for('auth.login'))
            if session.get('role') == 'admin':
                return f(*args, **kwargs)
            user = _get_current_user()
            if not user or not user.can_access_page(page_name):
                flash('Vous n\'avez pas acces a cette page.', 'warning')
                return redirect(url_for('main.index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

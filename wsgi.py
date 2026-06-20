"""
wsgi.py — Point d'entree WSGI pour Gunicorn / tout serveur WSGI compatible.

Lancement production :
    gunicorn wsgi:app --workers 4 --bind 0.0.0.0:8000

Lancement development :
    python run.py
"""
from flask_app import create_app

app = create_app()

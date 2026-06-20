"""
=============================================================
  FICHIER : flask_app/__init__.py
  ROLE   : Initialisation de l'application Flask
  PROJET : PFE Orange Tunisie - Application metier
=============================================================
"""

import os
from datetime import timedelta
from flask import Flask
from flask_cors import CORS
from flask_mail import Mail
from dotenv import load_dotenv

load_dotenv()

mail = Mail()


def create_app(config_object=None):
    """Factory pattern pour creer l'application Flask."""
    if config_object is None:
        env = os.getenv("FLASK_ENV", "development")
        if env == "production":
            config_object = "flask_app.config.ProductionConfig"
        else:
            config_object = "flask_app.config.DevelopmentConfig"
    app = Flask(__name__)
    app.config.from_object(config_object)

    # Duree de vie des sessions (30 jours)
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)

    # Flask-Mail
    app.config['MAIL_SERVER']   = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    app.config['MAIL_PORT']     = int(os.getenv('MAIL_PORT', 587))
    app.config['MAIL_USE_TLS']  = os.getenv('MAIL_USE_TLS', 'True') == 'True'
    app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME', '')
    app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD', '')
    app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_USERNAME', '')
    mail.init_app(app)

    # CORS pour permettre les appels API
    CORS(app)

    # Blueprint principal (dashboard, produits, objectifs, API)
    from flask_app.routes import main_bp
    app.register_blueprint(main_bp)

    # Blueprint authentification
    from flask_app.auth import auth_bp
    app.register_blueprint(auth_bp)

    # Blueprint chatbot IA
    from flask_app.chatbot.routes import chatbot_bp
    app.register_blueprint(chatbot_bp)

    # Blueprint Data Quality (remplace Streamlit)
    from flask_app.blueprints.data_quality import dq_bp
    app.register_blueprint(dq_bp)

    return app

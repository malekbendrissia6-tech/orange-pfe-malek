"""
Point d'entree developpement : python run.py
Point d'entree production    : gunicorn "run:app" (ou wsgi:app)
"""
from flask_app import create_app

app = create_app()

if __name__ == "__main__":
    import os
    debug = os.getenv("FLASK_ENV", "development") != "production"
    app.run(debug=debug, host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
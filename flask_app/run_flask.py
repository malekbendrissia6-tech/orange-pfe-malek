"""
=============================================================
  FICHIER : flask_app/run_flask.py
  ROLE   : Lance l'application Flask en developpement
=============================================================

Utilisation :
  python flask_app/run_flask.py

Puis ouvrir : http://localhost:5000
=============================================================
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import os
from flask_app import create_app

if __name__ == "__main__":
    app = create_app()
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)

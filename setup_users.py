"""
Script de configuration des comptes utilisateurs.
A executer UNE SEULE FOIS depuis la racine du projet.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import psycopg2
from werkzeug.security import generate_password_hash
from dotenv import load_dotenv
import os

load_dotenv()

DB_CONFIG = {
    'host':     os.getenv('DB_HOST', 'localhost'),
    'port':     os.getenv('DB_PORT', '5432'),
    'database': os.getenv('DB_NAME', 'orange_dwh'),
    'user':     os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'malek1'),
}

USERS = [
    {'email': 'admin@orange.tn', 'password': 'admin123',  'nom': 'Administrateur Orange', 'role': 'admin'},
    {'email': 'malek@esb.tn',    'password': 'malek2026', 'nom': 'Malek Ben Drissia',      'role': 'admin'},
]

def main():
    print("Connexion a PostgreSQL...")
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        print("OK - connecte a", DB_CONFIG['database'])
    except Exception as e:
        print(f"ERREUR connexion : {e}")
        sys.exit(1)

    # Creer la table
    print("\nCreation de la table users...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id       SERIAL PRIMARY KEY,
            email         VARCHAR(255) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            nom_complet   VARCHAR(100) NOT NULL,
            role          VARCHAR(20) NOT NULL DEFAULT 'user'
                          CHECK (role IN ('admin', 'user')),
            avatar_url    VARCHAR(500),
            is_active     BOOLEAN DEFAULT TRUE,
            created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login    TIMESTAMP
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
    conn.commit()
    print("OK - table users prete")

    # Inserer les comptes
    print("\nInsertion des comptes...")
    for u in USERS:
        pwd_hash = generate_password_hash(u['password'])
        cursor.execute("""
            INSERT INTO users (email, password_hash, nom_complet, role, is_active)
            VALUES (%s, %s, %s, %s, TRUE)
            ON CONFLICT (email) DO UPDATE
                SET password_hash = EXCLUDED.password_hash,
                    nom_complet   = EXCLUDED.nom_complet,
                    role          = EXCLUDED.role,
                    is_active     = TRUE
        """, (u['email'], pwd_hash, u['nom'], u['role']))
        print(f"  OK - {u['email']} / {u['password']}")

    conn.commit()
    cursor.close()
    conn.close()

    print("\n" + "="*50)
    print("CONFIGURATION TERMINEE")
    print("="*50)
    print("Comptes disponibles :")
    for u in USERS:
        print(f"  Email : {u['email']}")
        print(f"  Mdp   : {u['password']}")
        print()
    print("Lancer l'application :")
    print("  python flask_app/run_flask.py")
    print("="*50)

if __name__ == '__main__':
    main()

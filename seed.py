"""
seed.py - Crée les comptes de démonstration Orange Tunisie
Exécuter: python seed.py
"""
import os
import sys
import json
import psycopg2
from werkzeug.security import generate_password_hash
from dotenv import load_dotenv

load_dotenv()

def get_conn():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        port=os.getenv('DB_PORT', '5432'),
        database=os.getenv('DB_NAME', 'orange_dwh'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', 'malek1')
    )

USERS = [
    {
        'email': 'admin@orange.tn',
        'password': 'admin123',
        'nom_complet': 'Administrateur Orange',
        'role': 'admin',
        'phone': '+216 70 000 000',
        'allowed_pages': json.dumps(['performance', 'objectifs', 'prediction', 'paiements']),
        'is_blocked': False,
    },
    {
        'email': 'malek@esb.tn',
        'password': 'malek2026',
        'nom_complet': 'Malek Ben Drissia',
        'role': 'admin',
        'phone': '+216 50 000 000',
        'allowed_pages': json.dumps(['performance', 'objectifs', 'prediction', 'paiements']),
        'is_blocked': False,
    },
    {
        'email': 'data.engineer@orange.tn',
        'password': 'data2026',
        'nom_complet': 'Data Engineer Orange',
        'role': 'data_engineer',
        'phone': '+216 51 000 000',
        'allowed_pages': json.dumps([]),
        'is_blocked': False,
    },
    {
        'email': 'commercial@orange.tn',
        'password': 'comm2026',
        'nom_complet': 'Commercial Demo',
        'role': 'commercial',
        'phone': '+216 52 000 000',
        'allowed_pages': json.dumps(['performance', 'objectifs']),
        'is_blocked': False,
    },
]

CANONICAL_EMAILS = [u['email'] for u in USERS]


def cleanup_duplicates(cur):
    """Remove accounts not in the canonical list (duplicate demo accounts)."""
    placeholders = ','.join(['%s'] * len(CANONICAL_EMAILS))
    cur.execute(
        f"SELECT id, email, nom_complet, role FROM users WHERE email NOT IN ({placeholders}) ORDER BY id",
        CANONICAL_EMAILS
    )
    extras = cur.fetchall()
    if extras:
        print(f"\n  Suppression de {len(extras)} compte(s) hors liste canonique :")
        for eid, email, nom, role in extras:
            print(f"    - [{eid}] {email} ({nom} / {role})")
        ids = [row[0] for row in extras]
        cur.execute(f"DELETE FROM users WHERE id = ANY(%s)", (ids,))
    else:
        print("  Aucun doublon detecte.")


def run():
    conn = get_conn()
    cur = conn.cursor()

    # Ensure columns exist
    cur.execute("""
        ALTER TABLE users
            ADD COLUMN IF NOT EXISTS phone         VARCHAR(20),
            ADD COLUMN IF NOT EXISTS is_blocked    BOOLEAN DEFAULT FALSE,
            ADD COLUMN IF NOT EXISTS allowed_pages TEXT    DEFAULT '[]';
    """)

    # Update role constraint (drop all known variants)
    for cname in ['users_role_check', 'chk_role', 'users_role_check1']:
        cur.execute(f"ALTER TABLE users DROP CONSTRAINT IF EXISTS {cname};")
    cur.execute("""
        ALTER TABLE users ADD CONSTRAINT users_role_check
            CHECK (role IN ('admin', 'commercial', 'data_engineer', 'user'));
    """)

    # Migrate old 'user' role to 'commercial'
    cur.execute("UPDATE users SET role = 'commercial' WHERE role = 'user';")

    # Remove duplicate demo accounts
    cleanup_duplicates(cur)

    for u in USERS:
        h = generate_password_hash(u['password'])
        cur.execute("""
            INSERT INTO users (email, password_hash, nom_complet, role, phone, allowed_pages, is_blocked, is_active)
            VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE)
            ON CONFLICT (email) DO UPDATE
              SET password_hash  = EXCLUDED.password_hash,
                  nom_complet    = EXCLUDED.nom_complet,
                  role           = EXCLUDED.role,
                  phone          = EXCLUDED.phone,
                  allowed_pages  = EXCLUDED.allowed_pages,
                  is_blocked     = EXCLUDED.is_blocked;
        """, (u['email'], h, u['nom_complet'], u['role'],
              u['phone'], u['allowed_pages'], u['is_blocked']))
        print(f"  OK {u['email']} ({u['role']}) - mot de passe: {u['password']}")

    conn.commit()
    cur.close()
    conn.close()
    print("\nSeed terminé avec succès.")

if __name__ == '__main__':
    print("=== Seed Orange Tunisie ===")
    run()

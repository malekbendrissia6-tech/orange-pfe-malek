"""
Script pour generer les hashs des mots de passe demo.
A executer UNE SEULE FOIS.
"""
from werkzeug.security import generate_password_hash

# Comptes demo pour la soutenance
users = [
    {
        'email': 'admin@orange.tn',
        'password': 'admin123',
        'nom_complet': 'Administrateur Orange',
        'role': 'admin'
    },
    {
        'email': 'malek@esb.tn',
        'password': 'malek2026',
        'nom_complet': 'Malek Ben Drissia',
        'role': 'admin'
    },
    {
        'email': 'demo@orange.tn',
        'password': 'demo123',
        'nom_complet': 'Utilisateur Demo',
        'role': 'user'
    }
]

print("=" * 70)
print("REQUETES SQL A COPIER DANS PGADMIN :")
print("=" * 70)
print()

for u in users:
    pwd_hash = generate_password_hash(u['password'])
    sql = f"""
INSERT INTO users (email, password_hash, nom_complet, role, is_active)
VALUES (
    '{u['email']}',
    '{pwd_hash}',
    '{u['nom_complet']}',
    '{u['role']}',
    TRUE
)
ON CONFLICT (email) DO UPDATE 
SET password_hash = EXCLUDED.password_hash,
    nom_complet = EXCLUDED.nom_complet,
    role = EXCLUDED.role;
"""
    print(sql)
    print()

print("=" * 70)
print("RECAP DES COMPTES DEMO :")
print("=" * 70)
for u in users:
    print(f"  Email : {u['email']:25s} | Mot de passe : {u['password']}")
print("=" * 70)
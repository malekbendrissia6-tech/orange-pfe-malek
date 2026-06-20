"""Modele User - Authentification SANS pandas (psycopg2 direct)."""
import json
import psycopg2
import psycopg2.extras
import os
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()


def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        port=os.getenv('DB_PORT', '5432'),
        database=os.getenv('DB_NAME', 'orange_dwh'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', 'malek1')
    )


def _parse_allowed_pages(raw):
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except Exception:
            return []
    return []


class User:
    def __init__(self, user_id, email, nom_complet, role,
                 avatar_url=None, is_active=True, last_login=None,
                 phone=None, is_blocked=False, allowed_pages=None):
        self.user_id = user_id
        self.email = email
        self.nom_complet = nom_complet
        self.role = role
        self.avatar_url = avatar_url
        self.is_active = is_active
        self.last_login = last_login
        self.phone = phone
        self.is_blocked = bool(is_blocked)
        self.allowed_pages = _parse_allowed_pages(allowed_pages)

    @property
    def is_admin(self):
        return self.role == 'admin'

    @property
    def is_data_engineer(self):
        return self.role == 'data_engineer'

    @property
    def is_commercial(self):
        return self.role == 'commercial'

    def can_access_page(self, page_name):
        """Admin accède à tout, les autres vérifient allowed_pages."""
        if self.role == 'admin':
            return True
        return page_name in self.allowed_pages

    @staticmethod
    def _row_to_user(row):
        return User(
            user_id=row['user_id'],
            email=row['email'],
            nom_complet=row['nom_complet'],
            role=row['role'],
            avatar_url=row.get('avatar_url'),
            is_active=row.get('is_active', True),
            last_login=row.get('last_login'),
            phone=row.get('phone'),
            is_blocked=row.get('is_blocked', False),
            allowed_pages=row.get('allowed_pages', '[]'),
        )

    @staticmethod
    def find_by_email(email):
        """Retourne (User, password_hash) ou None. Ne bloque pas les comptes bloqués ici."""
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cursor.execute(
                "SELECT * FROM users WHERE email = %s AND is_active = TRUE",
                (email,)
            )
            row = cursor.fetchone()
            cursor.close()
            if not row:
                return None
            return User._row_to_user(row), row['password_hash']
        except Exception as e:
            print(f"Erreur find_by_email : {e}")
            return None
        finally:
            if conn:
                conn.close()

    @staticmethod
    def find_by_id(user_id):
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cursor.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
            row = cursor.fetchone()
            cursor.close()
            if not row:
                return None
            return User._row_to_user(row)
        except Exception as e:
            print(f"Erreur find_by_id : {e}")
            return None
        finally:
            if conn:
                conn.close()

    @staticmethod
    def get_all():
        """Retourne tous les utilisateurs (pour l'admin)."""
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cursor.execute(
                "SELECT * FROM users ORDER BY created_at DESC"
            )
            rows = cursor.fetchall()
            cursor.close()
            return [User._row_to_user(r) for r in rows]
        except Exception as e:
            print(f"Erreur get_all : {e}")
            return []
        finally:
            if conn:
                conn.close()

    @staticmethod
    def create(email, password, nom_complet, role, phone=None, allowed_pages=None):
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            pwd_hash = generate_password_hash(password)
            pages_json = json.dumps(allowed_pages or [])
            cursor.execute("""
                INSERT INTO users
                  (email, password_hash, nom_complet, role, phone, allowed_pages, is_blocked, is_active)
                VALUES (%s, %s, %s, %s, %s, %s, FALSE, TRUE)
                RETURNING user_id
            """, (email, pwd_hash, nom_complet, role, phone, pages_json))
            uid = cursor.fetchone()[0]
            conn.commit()
            cursor.close()
            return uid
        except Exception as e:
            print(f"Erreur create user : {e}")
            if conn:
                conn.rollback()
            return None
        finally:
            if conn:
                conn.close()

    @staticmethod
    def update(user_id, nom_complet, role, phone, allowed_pages):
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            pages_json = json.dumps(allowed_pages or [])
            cursor.execute("""
                UPDATE users
                SET nom_complet = %s, role = %s, phone = %s, allowed_pages = %s
                WHERE user_id = %s
            """, (nom_complet, role, phone, pages_json, user_id))
            conn.commit()
            cursor.close()
        except Exception as e:
            print(f"Erreur update user : {e}")
            if conn:
                conn.rollback()
        finally:
            if conn:
                conn.close()

    @staticmethod
    def toggle_blocked(user_id):
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE users SET is_blocked = NOT is_blocked WHERE user_id = %s
                RETURNING is_blocked
            """, (user_id,))
            row = cursor.fetchone()
            conn.commit()
            cursor.close()
            return row[0] if row else None
        except Exception as e:
            print(f"Erreur toggle_blocked : {e}")
            if conn:
                conn.rollback()
            return None
        finally:
            if conn:
                conn.close()

    @staticmethod
    def delete(user_id):
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM users WHERE user_id = %s", (user_id,))
            conn.commit()
            cursor.close()
        except Exception as e:
            print(f"Erreur delete user : {e}")
            if conn:
                conn.rollback()
        finally:
            if conn:
                conn.close()

    @staticmethod
    def verify_password(stored_hash, password):
        return check_password_hash(stored_hash, password)

    @staticmethod
    def update_last_login(user_id):
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users SET last_login = %s WHERE user_id = %s",
                (datetime.now(), user_id)
            )
            conn.commit()
            cursor.close()
        except Exception as e:
            print(f"Erreur update_last_login : {e}")
        finally:
            if conn:
                conn.close()

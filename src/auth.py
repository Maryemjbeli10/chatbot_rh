"""
Authentification simple mais réelle : mots de passe hachés (PBKDF2-SHA256 + sel).
"""

import json
import os
import hashlib
import secrets

USERS_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "users.json")


def _hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000).hex()


def _load_users() -> dict:
    if not os.path.exists(USERS_FILE):
        return {}
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_users(users: dict):
    os.makedirs(os.path.dirname(USERS_FILE), exist_ok=True)
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=2, ensure_ascii=False)


def ensure_default_users():
    if os.path.exists(USERS_FILE):
        return
    default_accounts = {
        "employee1": {"password": "conges2026", "role": "employee", "department": "IT", "full_name": "Employé Démo"},
        "rh_admin": {"password": "admin2026", "role": "hr_admin", "department": "RH", "full_name": "Admin RH"},
    }
    users = {}
    for username, info in default_accounts.items():
        salt = secrets.token_hex(16)
        users[username] = {
            "salt": salt,
            "hash": _hash_password(info["password"], salt),
            "role": info["role"],
            "department": info["department"],
            "full_name": info["full_name"],
        }
    _save_users(users)


def create_user(username: str, password: str, role: str = "employee", department: str = "", full_name: str = ""):
    users = _load_users()
    salt = secrets.token_hex(16)
    users[username] = {
        "salt": salt,
        "hash": _hash_password(password, salt),
        "role": role,
        "department": department,
        "full_name": full_name or username,
    }
    _save_users(users)


def username_exists(username: str) -> bool:
    return username in _load_users()


def register_user(username: str, password: str, confirm_password: str, full_name: str, department: str):
    """
    Inscription self-service d'un nouvel employé (rôle "employee" par défaut ;
    les comptes hr_admin restent créés manuellement, hors de ce formulaire).
    Retourne (succès: bool, message_erreur: str | None).
    """
    username = username.strip()
    full_name = full_name.strip()

    if not username or not password or not full_name:
        return False, "Tous les champs obligatoires doivent être remplis."
    if len(username) < 3:
        return False, "L'identifiant doit contenir au moins 3 caractères."
    if username_exists(username):
        return False, "Cet identifiant est déjà utilisé, choisis-en un autre."
    if len(password) < 8:
        return False, "Le mot de passe doit contenir au moins 8 caractères."
    if password != confirm_password:
        return False, "Les deux mots de passe ne correspondent pas."

    create_user(username, password, role="employee", department=department or "Non renseigné", full_name=full_name)
    return True, None


def verify_login(username: str, password: str):
    users = _load_users()
    user = users.get(username)
    if not user:
        return None
    if _hash_password(password, user["salt"]) == user["hash"]:
        return {
            "username": username,
            "role": user["role"],
            "department": user["department"],
            "full_name": user.get("full_name", username),
        }
    return None
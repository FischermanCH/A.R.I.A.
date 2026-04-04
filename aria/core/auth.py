from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from aria.core.secure_store import SecureConfigStore


class AuthManager:
    def __init__(self, store: SecureConfigStore):
        self.store = store
        self.ph = PasswordHasher()

    def upsert_user(self, username: str, password: str, role: str = "user") -> None:
        pwd = str(password)
        if len(pwd) < 8:
            raise ValueError("Passwort muss mindestens 8 Zeichen haben.")
        password_hash = self.ph.hash(pwd)
        self.store.upsert_user(username=username, password_hash=password_hash, role=role)

    def verify(self, username: str, password: str) -> bool:
        user = self.store.get_user(username)
        if not user or not user.get("active"):
            return False
        password_hash = str(user.get("password_hash", ""))
        try:
            return self.ph.verify(password_hash, str(password))
        except VerifyMismatchError:
            return False
        except Exception:
            return False

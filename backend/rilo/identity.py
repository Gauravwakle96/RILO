"""Persistent hosted identities and request-scoped object ownership."""

from __future__ import annotations

import base64
import contextvars
import hashlib
import hmac
import re
import secrets
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

_owner: contextvars.ContextVar[str | None] = contextvars.ContextVar("rilo_owner", default=None)


def current_owner() -> str | None:
    return _owner.get()


@contextmanager
def owner_context(owner_id: str | None):
    token = _owner.set(owner_id)
    try:
        yield
    finally:
        _owner.reset(token)


def normalize_email(value: str) -> str:
    email = value.strip().lower()
    if len(email) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise ValueError("Enter a valid email address.")
    return email


def password_hash(password: str) -> str:
    if len(password) < 12 or len(password) > 256:
        raise ValueError("Password must contain 12 to 256 characters.")
    salt = secrets.token_bytes(16)
    value = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return (
        "scrypt$16384$"
        + base64.urlsafe_b64encode(salt).decode()
        + "$"
        + base64.urlsafe_b64encode(value).decode()
    )


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, rounds, salt, expected = encoded.split("$", 3)
        if algorithm != "scrypt" or rounds != "16384":
            return False
        actual = hashlib.scrypt(
            password.encode(), salt=base64.urlsafe_b64decode(salt), n=2**14, r=8, p=1, dklen=32
        )
        return hmac.compare_digest(actual, base64.urlsafe_b64decode(expected))
    except (ValueError, TypeError):
        return False


def session_expiry(hours: int = 24) -> str:
    return (datetime.now(UTC) + timedelta(hours=hours)).isoformat()


def token_hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()

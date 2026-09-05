from __future__ import annotations

import base64
import hashlib
import hmac
import os


def hash_demo_password(password: str) -> str:
    salt = os.urandom(16)
    iterations = 600_000
    derived = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations, dklen=32)
    return f"pbkdf2_sha256${iterations}$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(derived).decode()


def verify_demo_password(password: str, encoded: str | None) -> bool:
    if not encoded:
        return False
    try:
        algorithm, iteration_value, salt_value, expected_value = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        iterations = int(iteration_value)
        if iterations < 100_000 or iterations > 2_000_000:
            return False
        salt = base64.b64decode(salt_value)
        expected = base64.b64decode(expected_value)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations, dklen=len(expected))
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False

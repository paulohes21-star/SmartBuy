import hashlib
import hmac
import os
import secrets

SECRET = os.getenv(
    "SMARTBUY_SECRET",
    "smartbuy-local-secret-change-before-production",
)

def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt, 200_000
    )
    return f"{salt.hex()}:{digest.hex()}"

def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, digest_hex = stored.split(":", 1)
        candidate = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), 200_000
        ).hex()
        return hmac.compare_digest(candidate, digest_hex)
    except Exception:
        return False

def sign_session(user_id: int) -> str:
    payload = str(user_id)
    signature = hmac.new(
        SECRET.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()
    return f"{payload}.{signature}"

def read_session(token: str | None) -> int | None:
    if not token or "." not in token:
        return None
    payload, signature = token.split(".", 1)
    expected = hmac.new(
        SECRET.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return None
    try:
        return int(payload)
    except ValueError:
        return None

"""
Password hashing and JWT issuance/verification built on Python's standard
library only (hashlib, hmac, base64, json) — no external auth package.
Implements the actual JWT spec (header.payload.signature, HS256, base64url,
constant-time signature comparison) rather than depending on PyJWT.
"""
import base64
import hashlib
import hmac
import json
import os
import time

SECRET_KEY = os.environ.get("APP_SECRET_KEY", "dev-secret-change-in-production")
TOKEN_TTL_SECONDS = 60 * 60  # 1 hour


# ---------------------------------------------------------------- passwords
def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000)
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt_hex, digest_hex = stored_hash.split("$")
    except ValueError:
        return False
    salt = bytes.fromhex(salt_hex)
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000)
    return hmac.compare_digest(candidate.hex(), digest_hex)


# ---------------------------------------------------------------------- jwt
def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def create_access_token(subject: str, extra_claims: dict | None = None) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {"sub": subject, "iat": int(time.time()), "exp": int(time.time()) + TOKEN_TTL_SECONDS}
    payload.update(extra_claims or {})

    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode())
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode())
    signing_input = f"{header_b64}.{payload_b64}".encode()

    signature = hmac.new(SECRET_KEY.encode(), signing_input, hashlib.sha256).digest()
    signature_b64 = _b64url_encode(signature)

    return f"{header_b64}.{payload_b64}.{signature_b64}"


class TokenError(Exception):
    pass


def decode_access_token(token: str) -> dict:
    try:
        header_b64, payload_b64, signature_b64 = token.split(".")
    except ValueError:
        raise TokenError("Malformed token")

    signing_input = f"{header_b64}.{payload_b64}".encode()
    expected_sig = hmac.new(SECRET_KEY.encode(), signing_input, hashlib.sha256).digest()
    actual_sig = _b64url_decode(signature_b64)

    if not hmac.compare_digest(expected_sig, actual_sig):
        raise TokenError("Invalid signature")

    payload = json.loads(_b64url_decode(payload_b64))
    if payload.get("exp", 0) < time.time():
        raise TokenError("Token expired")

    return payload

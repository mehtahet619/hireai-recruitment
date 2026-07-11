"""Simple JWT auth for employer accounts."""
from __future__ import annotations

import json
import time
import base64
import hmac
import hashlib
import os


def _get_secret() -> str:
    return os.getenv("JWT_SECRET", "dev-secret-change-in-production")


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    pad = 4 - len(s) % 4
    return base64.urlsafe_b64decode(s + "=" * pad)


def create_token(employer_id: str, email: str, company_name: str, expires_in: int = 86400 * 7) -> str:
    SECRET = _get_secret()
    header = _b64url(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = _b64url(json.dumps({
        "sub": employer_id,
        "email": email,
        "company": company_name,
        "exp": int(time.time()) + expires_in,
    }).encode())
    sig_input = f"{header}.{payload}".encode()
    sig = _b64url(hmac.new(SECRET.encode(), sig_input, hashlib.sha256).digest())
    return f"{header}.{payload}.{sig}"


def verify_token(token: str) -> dict | None:
    SECRET = _get_secret()
    try:
        header, payload, sig = token.split(".")
        sig_input = f"{header}.{payload}".encode()
        expected_sig = _b64url(hmac.new(SECRET.encode(), sig_input, hashlib.sha256).digest())
        if not hmac.compare_digest(sig, expected_sig):
            return None
        data = json.loads(_b64url_decode(payload))
        if data.get("exp", 0) < time.time():
            return None
        return data
    except Exception:
        return None


def get_current_employer(authorization: str | None) -> dict | None:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization[7:]
    return verify_token(token)

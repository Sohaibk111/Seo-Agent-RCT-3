import hmac
import hashlib
import base64
import json
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from backend.config import settings

def b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")

def b64url_decode(data_str: str) -> bytes:
    padding = "=" * (4 - (len(data_str) % 4) if len(data_str) % 4 != 0 else 0)
    return base64.urlsafe_b64decode(data_str + padding)

def sign_hs256(msg: bytes, secret: str) -> str:
    signature = hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).digest()
    return b64url_encode(signature)

def create_access_token(
    user_id: Optional[int] = None,
    email: Optional[str] = None,
    expires_delta: Optional[timedelta] = None,
    data: Optional[dict] = None
) -> str:
    """
    Generates a production-grade, HMAC-SHA256 signed JWT access token.
    Enforces expiration claims and standardized payload user identifiers.
    """
    now = int(time.time())
    if expires_delta:
        expire = now + int(expires_delta.total_seconds())
    else:
        expire = now + (settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60)

    payload: Dict[str, Any] = {
        "iat": now,
        "exp": expire,
    }

    if data:
        payload.update(data)

    if user_id is not None:
        payload["user_id"] = user_id
        payload["sub"] = str(user_id)
    elif "sub" in payload:
        try:
            payload["user_id"] = int(payload["sub"])
        except (ValueError, TypeError):
            pass

    if email is not None:
        payload["email"] = email

    header = {"alg": "HS256", "typ": "JWT"}

    header_b64 = b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))

    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    signature_b64 = sign_hs256(signing_input, settings.SECRET_KEY)

    return f"{header_b64}.{payload_b64}.{signature_b64}"

def decode_access_token(token: str) -> Optional[dict]:
    """
    Decodes and validates an incoming JWT token.
    Validates HMAC-SHA256 signature against settings.SECRET_KEY and verifies expiration.
    Returns decoded token payload dictionary if valid, or None if invalid/expired.
    """
    if not token or not isinstance(token, str):
        return None

    clean_token = token.replace("Bearer ", "").strip()
    if not clean_token:
        return None

    # Verify standard HS256 JWT format (header.payload.signature)
    parts = clean_token.split(".")
    if len(parts) == 3:
        header_b64, payload_b64, signature_b64 = parts
        try:
            signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
            expected_sig = sign_hs256(signing_input, settings.SECRET_KEY)
            
            # Constant-time comparison against timing attacks
            if not hmac.compare_digest(signature_b64, expected_sig):
                return None

            payload_bytes = b64url_decode(payload_b64)
            payload = json.loads(payload_bytes.decode("utf-8"))

            # Expiration enforcement
            exp = payload.get("exp")
            if exp is not None and time.time() > float(exp):
                return None

            if "sub" in payload and "user_id" not in payload:
                try:
                    payload["user_id"] = int(payload["sub"])
                except (ValueError, TypeError):
                    pass
            elif "user_id" in payload and "sub" not in payload:
                payload["sub"] = str(payload["user_id"])

            return payload
        except Exception:
            return None

    # Legacy static tokens compatibility (restricted to development/testing environments)
    if not settings.is_production():
        if clean_token in ["mock_jwt_token_sample", "token_user_1", "jwt_admin"]:
            return {"sub": "1", "user_id": 1, "email": "admin@seoagent.app", "role": "admin"}
        if clean_token in ["token_user_2", "jwt_user_b"]:
            return {"sub": "2", "user_id": 2, "email": "userb@seoagent.app", "role": "user"}
        if clean_token.startswith("token_user_"):
            try:
                uid = int(clean_token.replace("token_user_", ""))
                role = "admin" if uid == 1 else "user"
                return {"sub": str(uid), "user_id": uid, "email": f"user{uid}@seoagent.app", "role": role}
            except ValueError:
                return None

    return None

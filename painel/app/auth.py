import secrets

import bcrypt
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

from .config import SECRET_KEY, PASSWORD_HASH, SESSION_MAX_AGE

_serializer = URLSafeTimedSerializer(SECRET_KEY, salt="painel-session")


def hash_password(plain: str) -> str:
    """Gera um hash bcrypt para uma senha em texto plano."""
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(plain: str) -> bool:
    """Compara a senha informada com o hash configurado em PAINEL_SENHA_HASH."""
    if not PASSWORD_HASH:
        return False
    try:
        return bcrypt.checkpw(plain.encode(), PASSWORD_HASH.encode())
    except ValueError:
        return False


def make_session() -> tuple[str, str]:
    """Cria um token de sessão assinado. Retorna (cookie_value, csrf_token)."""
    csrf = secrets.token_hex(16)
    token = _serializer.dumps({"u": "admin", "csrf": csrf})
    return token, csrf


def parse_session(token: str | None) -> dict | None:
    """Valida e decodifica um token de sessão. Retorna None se inválido/expirado."""
    if not token:
        return None
    try:
        return _serializer.loads(token, max_age=SESSION_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None

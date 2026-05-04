import uuid

from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from config import Config
from datetime import datetime, timedelta
from utils.token_blacklist import blacklist_token, is_blacklisted

security = HTTPBearer()


def create_access_token(identity: str, additional_claims: dict = None) -> str:
    if additional_claims is None:
        additional_claims = {}
    expire = datetime.utcnow() + timedelta(hours=10)
    payload = {
        "sub": str(identity),
        "exp": expire,
        "jti": str(uuid.uuid4()),
        **additional_claims,
    }
    return jwt.encode(payload, Config.JWT_SECRET_KEY, algorithm="HS256")


def create_refresh_token(identity: str) -> str:
    expire = datetime.utcnow() + timedelta(days=7)
    payload = {
        "sub": str(identity),
        "exp": expire,
        "jti": str(uuid.uuid4()),
        "refresh": True,
    }
    return jwt.encode(payload, Config.JWT_SECRET_KEY, algorithm="HS256")


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, Config.JWT_SECRET_KEY, algorithms=["HS256"])
        user_id: str = payload.get("sub")
        jti: str = payload.get("jti", "")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Token inválido")
        if jti and is_blacklisted(jti):
            raise HTTPException(status_code=401, detail="Sesión cerrada. Inicie sesión nuevamente.")
        return user_id
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")


def get_current_user_payload(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, Config.JWT_SECRET_KEY, algorithms=["HS256"])
        if payload.get("sub") is None:
            raise HTTPException(status_code=401, detail="Token inválido")
        jti = payload.get("jti", "")
        if jti and is_blacklisted(jti):
            raise HTTPException(status_code=401, detail="Sesión cerrada. Inicie sesión nuevamente.")
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")


def get_admin_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    user_id = get_current_user(credentials)
    if user_id not in Config.ADMIN_USER_IDS:
        raise HTTPException(status_code=403, detail="Acceso restringido a administradores")
    return user_id


def get_refresh_payload(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Valida refresh token y retorna su payload completo."""
    token = credentials.credentials
    try:
        payload = jwt.decode(token, Config.JWT_SECRET_KEY, algorithms=["HS256"])
        if not payload.get("refresh"):
            raise HTTPException(status_code=401, detail="Se requiere refresh token")
        if payload.get("sub") is None:
            raise HTTPException(status_code=401, detail="Token inválido")
        jti = payload.get("jti", "")
        if jti and is_blacklisted(jti):
            raise HTTPException(status_code=401, detail="Sesión cerrada. Inicie sesión nuevamente.")
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")


def get_refresh_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    return get_refresh_payload(credentials)["sub"]

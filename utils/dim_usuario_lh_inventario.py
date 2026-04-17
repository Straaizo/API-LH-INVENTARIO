"""
Dimensión: general_dim_usuario
- id (UUID varchar 45), usuario, nombre, correo, clave
Login: correo o usuario + clave (JWT).
"""

import hashlib
import hmac
import json
import logging
import re
import uuid
from typing import Optional, Tuple

import bcrypt
from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from schemas.auth import LoginRequest, LoginResponse, RegisterRequest, UsuarioListResponse, UsuarioOut
from schemas.base import RESP_400, RESP_401, RESP_404, RESP_409, RESP_500
from utils.auth import create_access_token, get_admin_user, get_current_user, get_current_user_payload
from utils.db import get_db_connection
from utils.errors import server_error
from utils.rate_limit import is_blocked, record_failure, record_success

logger = logging.getLogger(__name__)
router = APIRouter()

TABLE    = "general_dim_usuario"
PK       = "id"          # UUID varchar(45)
COL_PASS = "clave"
COL_NOMBRE = "nombre"


def _safe_value(val):
    if val is None:
        return None
    if isinstance(val, bytes):
        return val.decode("utf-8", errors="replace")
    return val


def _validar_correo(correo):
    if not correo or len(correo) > 255:
        return False
    return bool(re.match(r"^[\w\.-]+@[\w\.-]+\.\w+$", correo))


def _validar_identificador_login(ident: str) -> Tuple[bool, Optional[str]]:
    s = (ident or "").strip()
    if not s:
        return False, "Usuario y contraseña son requeridos"
    if "@" in s:
        if not _validar_correo(s.lower()):
            return False, "correo inválido"
    elif len(s) > 128:
        return False, "nombre de usuario demasiado largo"
    return True, None


def _is_sha256_hex(value: str) -> bool:
    s = (value or "").strip()
    if len(s) != 64:
        return False
    try:
        int(s, 16)
    except ValueError:
        return False
    return True


def _hash_password_sha256(plain: str) -> str:
    return hashlib.sha256(plain.encode("utf-8")).hexdigest()


def _hash_password_bcrypt(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


_DUMMY_HASH = bcrypt.hashpw(b"dummy_lh_inventario_placeholder", bcrypt.gensalt(rounds=12)).decode("utf-8")


def _verify_password(plain: str, stored) -> bool:
    stored_s = str(_safe_value(stored) or "").strip()
    if not plain or not stored_s:
        return False
    if stored_s.startswith(("$2a$", "$2b$", "$2y$")):
        try:
            return bcrypt.checkpw(plain.encode("utf-8"), stored_s.encode("utf-8"))
        except Exception:
            return False
    if _is_sha256_hex(stored_s):
        digest = _hash_password_sha256(plain)
        return hmac.compare_digest(digest.lower(), stored_s.lower())
    return plain == stored_s


@router.post(
    "/login",
    summary="Iniciar sesión",
    description=(
        "Autentica con **correo o usuario** + clave. "
        "Retorna un token JWT Bearer para todos los demás endpoints.\n\n"
        "Acepta JSON, form-data y cuerpo raw (compatible con Flutter)."
    ),
    response_model=LoginResponse,
    responses={
        **RESP_400,
        401: {"description": "Credenciales incorrectas"},
        **RESP_500,
    },
)
async def login(request: Request, _body: LoginRequest = Body(default=None)):
    blocked, ip = is_blocked(request)
    if blocked:
        return JSONResponse(
            status_code=429,
            content={"error": "Demasiados intentos fallidos. Intente más tarde."},
        )

    try:
        data = {}
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            try:
                data = await request.json()
            except Exception:
                pass
        elif "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
            form = await request.form()
            data = dict(form)
        else:
            raw = await request.body()
            if raw:
                try:
                    data = json.loads(raw)
                except Exception:
                    pass
        if not isinstance(data, dict):
            data = {}

        ident_raw = (
            data.get("correo")
            or data.get("email")
            or data.get("usuario")
            or data.get("nombre_usuario")
            or data.get("username")
            or data.get("userEmail")
            or data.get("user_email")
            or ""
        )
        ident_raw = str(ident_raw or "").strip()
        ident_lower = ident_raw.lower()

        contrasena = (
            data.get("clave")
            or data.get("contrasenia")
            or data.get("contrasena")
            or data.get("password")
            or data.get("Password")
            or ""
        )
        if contrasena is not None and not isinstance(contrasena, str):
            contrasena = str(contrasena)

        if not ident_raw or not contrasena:
            record_failure(request)
            return JSONResponse(status_code=400, content={"error": "Usuario y contraseña son requeridos"})

        ok_ident, err_msg = _validar_identificador_login(ident_raw)
        if not ok_ident:
            em = err_msg or "identificador inválido"
            code = "INVALID_EMAIL" if "correo" in em.lower() else "INVALID_IDENT"
            return JSONResponse(status_code=400, content={"error": em, "code": code})

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            f"""
            SELECT {PK}, usuario, correo, {COL_PASS}, {COL_NOMBRE}
            FROM {TABLE}
            WHERE LOWER(TRIM(correo)) = %s OR LOWER(TRIM(usuario)) = %s
            LIMIT 1
            """,
            (ident_lower, ident_lower),
        )
        row = cursor.fetchone()
        cursor.close()
        conn.close()

        if not row:
            bcrypt.checkpw(contrasena.encode("utf-8"), _DUMMY_HASH.encode("utf-8"))
            record_failure(request)
            return JSONResponse(status_code=401, content={"error": "Credenciales incorrectas"})

        id_u, usuario_db, correo_db, clave_hash, nombre_persona = (
            row[0], row[1], row[2], row[3],
            row[4] if len(row) > 4 else None,
        )
        if not _verify_password(contrasena, clave_hash):
            record_failure(request)
            return JSONResponse(status_code=401, content={"error": "Credenciales incorrectas"})

        record_success(request)
        access_token = create_access_token(
            identity=str(id_u),
            additional_claims={"tipo": "dim_usuario_lh_inventario", "correo": correo_db},
        )
        usuario_data = {
            "id": str(id_u),
            "usuario": _safe_value(usuario_db) or "",
            "correo": _safe_value(correo_db) or "",
            "nombre": _safe_value(nombre_persona) or "",
        }
        return {
            "success": True,
            "access_token": access_token,
            "accessToken": access_token,
            "token": access_token,
            "token_type": "bearer",
            "usuario": usuario_data,
            "user": usuario_data,
            "message": "Login correcto",
        }
    except Exception as e:
        return server_error(e, "login")


@router.post(
    "/register",
    status_code=201,
    summary="Registrar nuevo usuario (admin)",
    description="Crea un nuevo usuario. Requiere autenticación de administrador.",
    responses={
        **RESP_400,
        **RESP_401,
        **RESP_409,
        **RESP_500,
    },
)
def register(body: dict = Body(default={}), current_user: str = Depends(get_admin_user)):
    try:
        usuario_val = (body.get("usuario") or body.get("nombre_usuario") or "").strip()
        correo = (body.get("correo") or "").strip().lower()
        nombre = (body.get("nombre") or "").strip()
        contrasena = (
            body.get("clave") or body.get("contrasenia") or body.get("contrasena") or body.get("password") or ""
        )

        if not usuario_val or not correo or not contrasena:
            return JSONResponse(status_code=400, content={"error": "usuario, correo y clave son requeridos"})
        if not _validar_correo(correo):
            return JSONResponse(status_code=400, content={"error": "correo inválido"})

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f"SELECT {PK} FROM {TABLE} WHERE correo = %s", (correo,))
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return JSONResponse(status_code=409, content={"error": "El correo ya está registrado"})

        new_id = str(uuid.uuid4())
        pass_hash = _hash_password_bcrypt(contrasena)
        cursor.execute(
            f"INSERT INTO {TABLE} ({PK}, usuario, correo, {COL_NOMBRE}, {COL_PASS}) VALUES (%s, %s, %s, %s, %s)",
            (new_id, usuario_val, correo, nombre, pass_hash),
        )
        conn.commit()
        cursor.close()
        conn.close()

        access_token = create_access_token(
            identity=new_id,
            additional_claims={"tipo": "dim_usuario_lh_inventario", "correo": correo},
        )
        return {
            "access_token": access_token,
            "usuario": {"id": new_id, "usuario": usuario_val, "correo": correo},
            "message": "Usuario registrado",
        }
    except Exception as e:
        return server_error(e, "register")


@router.get(
    "/perfil",
    summary="Consultar perfil por correo o usuario",
    description="Retorna datos del perfil buscando por `email`, `correo` o `usuario`. Requiere autenticación.",
    responses={
        **RESP_400,
        **RESP_401,
        **RESP_404,
        **RESP_500,
    },
)
def perfil(
    email: Optional[str] = Query(default=None),
    correo: Optional[str] = Query(default=None),
    usuario: Optional[str] = Query(default=None),
    current_user: str = Depends(get_current_user),
):
    try:
        ident = (email or correo or usuario or "").strip().lower()
        if not ident:
            return JSONResponse(status_code=400, content={"error": "Parámetro email, correo o usuario requerido"})
        ok_p, err_p = _validar_identificador_login(ident)
        if not ok_p:
            return JSONResponse(status_code=400, content={"error": err_p or "identificador inválido"})

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            f"""
            SELECT {PK}, usuario, correo, {COL_NOMBRE}
            FROM {TABLE}
            WHERE LOWER(TRIM(correo)) = %s OR LOWER(TRIM(usuario)) = %s
            LIMIT 1
            """,
            (ident, ident),
        )
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        if not row:
            return JSONResponse(status_code=404, content={"error": "Usuario no encontrado"})
        u = {
            "id": str(row[0]),
            "usuario": _safe_value(row[1]) or "",
            "correo": _safe_value(row[2]) or "",
            "nombre": _safe_value(row[3]) if len(row) > 3 else "",
        }
        return {"usuario": u, "user": u}
    except Exception as e:
        logger.exception("perfil")
        return server_error(e)


@router.get(
    "/me",
    summary="Obtener usuario autenticado",
    description="Retorna el perfil del usuario propietario del token JWT.",
    responses={
        **RESP_401,
        **RESP_404,
        **RESP_500,
    },
)
def me(payload: dict = Depends(get_current_user_payload)):
    try:
        id_u = payload.get("sub")
        if payload.get("tipo") != "dim_usuario_lh_inventario":
            return JSONResponse(status_code=403, content={"error": "Token no válido para este recurso"})

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT {PK}, usuario, correo, {COL_NOMBRE} FROM {TABLE} WHERE {PK} = %s",
            (id_u,),
        )
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        if not row:
            return JSONResponse(status_code=404, content={"error": "Usuario no encontrado"})
        u = {
            "id": str(row[0]),
            "usuario": _safe_value(row[1]) or "",
            "correo": _safe_value(row[2]) or "",
            "nombre": _safe_value(row[3]) if len(row) > 3 else "",
        }
        return {"usuario": u, "user": u}
    except Exception as e:
        return server_error(e)


@router.get(
    "",
    summary="Listar todos los usuarios",
    description="Retorna el listado completo de usuarios. Requiere autenticación.",
    response_model=UsuarioListResponse,
    responses={
        **RESP_401,
        **RESP_500,
    },
)
def listar(current_user: str = Depends(get_current_user)):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT {PK}, usuario, correo, {COL_NOMBRE} FROM {TABLE} ORDER BY usuario"
        )
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        data = [
            {
                "id": str(r[0]),
                "usuario": _safe_value(r[1]) or "",
                "correo": _safe_value(r[2]) or "",
                "nombre": _safe_value(r[3]) if len(r) > 3 else "",
            }
            for r in rows
        ]
        return {"data": data}
    except Exception as e:
        logger.exception("dim_usuario listar")
        return server_error(e)


@router.get(
    "/{id_usuario}",
    summary="Obtener usuario por ID",
    description="Retorna datos de un usuario por su UUID.",
    responses={
        **RESP_401,
        **RESP_404,
        **RESP_500,
    },
)
def obtener(id_usuario: str, current_user: str = Depends(get_current_user)):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT {PK}, usuario, correo, {COL_NOMBRE} FROM {TABLE} WHERE {PK} = %s",
            (id_usuario,),
        )
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        if not row:
            return JSONResponse(status_code=404, content={"error": "Usuario no encontrado"})
        return {
            "id": str(row[0]),
            "usuario": _safe_value(row[1]) or "",
            "correo": _safe_value(row[2]) or "",
            "nombre": _safe_value(row[3]) if len(row) > 3 else "",
        }
    except Exception as e:
        return server_error(e)


@router.post(
    "",
    status_code=201,
    summary="Crear usuario (admin)",
    description="Crea un nuevo usuario desde el panel administrativo. Requiere autenticación de administrador.",
    responses={
        **RESP_400,
        **RESP_401,
        **RESP_409,
        **RESP_500,
    },
)
def crear(body: dict = Body(default={}), current_user: str = Depends(get_admin_user)):
    try:
        usuario_val = (body.get("usuario") or body.get("nombre_usuario") or "").strip()
        correo = (body.get("correo") or "").strip().lower()
        nombre = (body.get("nombre") or "").strip()
        contrasena = (
            body.get("clave") or body.get("contrasenia") or body.get("contrasena") or body.get("password") or ""
        )
        if not usuario_val or not correo or not contrasena:
            return JSONResponse(status_code=400, content={"error": "usuario, correo y clave son requeridos"})
        if not _validar_correo(correo):
            return JSONResponse(status_code=400, content={"error": "correo inválido"})
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f"SELECT 1 FROM {TABLE} WHERE correo = %s", (correo,))
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return JSONResponse(status_code=409, content={"error": "El correo ya existe"})
        new_id = str(uuid.uuid4())
        pass_hash = _hash_password_bcrypt(contrasena)
        cursor.execute(
            f"INSERT INTO {TABLE} ({PK}, usuario, correo, {COL_NOMBRE}, {COL_PASS}) VALUES (%s, %s, %s, %s, %s)",
            (new_id, usuario_val, correo, nombre, pass_hash),
        )
        conn.commit()
        cursor.close()
        conn.close()
        return {"message": "Usuario creado", "id": new_id}
    except Exception as e:
        return server_error(e)


@router.put(
    "/{id_usuario}",
    summary="Actualizar datos de usuario",
    description="Actualiza usuario, correo o clave. Solo enviar los campos a modificar. Requiere administrador.",
    responses={
        **RESP_400,
        **RESP_401,
        **RESP_404,
        **RESP_409,
        **RESP_500,
    },
)
def actualizar(id_usuario: str, body: dict = Body(default={}), current_user: str = Depends(get_admin_user)):
    try:
        usuario_val = body.get("usuario") or body.get("nombre_usuario")
        correo = body.get("correo")
        nombre = body.get("nombre")
        contrasena = body.get("clave") or body.get("contrasenia") or body.get("contrasena") or body.get("password")

        if usuario_val is not None:
            usuario_val = str(usuario_val).strip()
        if correo is not None:
            correo = str(correo).strip().lower()
            if not _validar_correo(correo):
                return JSONResponse(status_code=400, content={"error": "correo inválido"})
        if nombre is not None:
            nombre = str(nombre).strip()

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f"SELECT {PK} FROM {TABLE} WHERE {PK} = %s", (id_usuario,))
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return JSONResponse(status_code=404, content={"error": "Usuario no encontrado"})
        if correo is not None:
            cursor.execute(f"SELECT 1 FROM {TABLE} WHERE correo = %s AND {PK} != %s", (correo, id_usuario))
            if cursor.fetchone():
                cursor.close()
                conn.close()
                return JSONResponse(status_code=409, content={"error": "El correo ya está en uso"})

        updates, params = [], []
        if usuario_val is not None:
            updates.append("usuario = %s")
            params.append(usuario_val)
        if correo is not None:
            updates.append("correo = %s")
            params.append(correo)
        if nombre is not None:
            updates.append(f"{COL_NOMBRE} = %s")
            params.append(nombre)
        if contrasena is not None:
            updates.append(f"{COL_PASS} = %s")
            params.append(_hash_password_bcrypt(str(contrasena)))
        if not updates:
            cursor.close()
            conn.close()
            return JSONResponse(status_code=400, content={"error": "Nada que actualizar"})
        params.append(id_usuario)
        sql = f"UPDATE {TABLE} SET {', '.join(updates)} WHERE {PK} = %s"
        cursor.execute(sql, params)
        conn.commit()
        cursor.close()
        conn.close()
        return {"message": "Usuario actualizado"}
    except Exception as e:
        return server_error(e)


@router.delete(
    "/{id_usuario}",
    summary="Eliminar usuario",
    description="Elimina permanentemente un usuario. Esta acción no se puede deshacer.",
    responses={
        **RESP_401,
        **RESP_404,
        **RESP_500,
    },
)
def eliminar(id_usuario: str, current_user: str = Depends(get_admin_user)):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f"DELETE FROM {TABLE} WHERE {PK} = %s", (id_usuario,))
        conn.commit()
        n = cursor.rowcount
        cursor.close()
        conn.close()
        if n == 0:
            return JSONResponse(status_code=404, content={"error": "Usuario no encontrado"})
        return {"message": "Usuario eliminado"}
    except Exception as e:
        return server_error(e)

"""
Dimensión: DIM_TIPO_MOVIMIENTO_LH_INVENTARIO
- id_tipo_movimiento (PK), nombre_movimiento
"""

import logging

from fastapi import APIRouter, Body, Depends
from fastapi.responses import JSONResponse

from schemas.base import RESP_400, RESP_401, RESP_404, RESP_500
from schemas.movimientos import TipoMovimientoCreate, TipoMovimientoListResponse
from utils.auth import get_current_user
from utils.db import get_db_connection
from utils.errors import server_error

logger = logging.getLogger(__name__)
router = APIRouter()

TABLE = "inventario_tipo_movimiento"
PK = "id_tipo_movimiento"


def _safe_value(val):
    if val is None:
        return None
    if isinstance(val, bytes):
        return val.decode("utf-8", errors="replace")
    return val


@router.get(
    "",
    summary="Listar tipos de movimiento",
    description=(
        "Retorna el catálogo de tipos de movimiento disponibles. "
        "Los valores estándar son **ENTRADA** y **SALIDA**."
    ),
    response_model=TipoMovimientoListResponse,
    responses={
        **RESP_401,
        **RESP_500,
    },
)
def listar(current_user: str = Depends(get_current_user)):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f"SELECT {PK}, nombre_movimiento FROM {TABLE} ORDER BY {PK}")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        data = [
            {
                "id": int(r[0]),
                "id_tipo_movimiento": int(r[0]),
                "id_tipo_mov": int(r[0]),
                "nombre_movimiento": _safe_value(r[1]) or "",
            }
            for r in rows
        ]
        return {"data": data}
    except Exception as e:
        logger.exception("dim_tipo_movimiento listar")
        return server_error(e)


@router.get(
    "/{id_tipo_movimiento}",
    summary="Obtener tipo de movimiento por ID",
    description="Retorna el detalle de un tipo de movimiento específico.",
    responses={
        **RESP_401,
        **RESP_404,
        **RESP_500,
    },
)
def obtener(id_tipo_movimiento: int, current_user: str = Depends(get_current_user)):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f"SELECT {PK}, nombre_movimiento FROM {TABLE} WHERE {PK} = %s", (id_tipo_movimiento,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        if not row:
            return JSONResponse(status_code=404, content={"error": "Tipo de movimiento no encontrado"})
        i = int(row[0])
        return {
            "id": i,
            "id_tipo_movimiento": i,
            "id_tipo_mov": i,
            "nombre_movimiento": _safe_value(row[1]) or "",
        }
    except Exception as e:
        return server_error(e)


@router.post(
    "",
    status_code=201,
    summary="Crear tipo de movimiento",
    description=(
        "Agrega un nuevo tipo de movimiento al catálogo. "
        "Los valores estándar son ENTRADA y SALIDA; solo crear nuevos tipos si el flujo lo requiere."
    ),
    responses={
        **RESP_400,
        **RESP_401,
        **RESP_500,
    },
)
def crear(body: dict = Body(default={}), current_user: str = Depends(get_current_user)):
    try:
        nombre = (body.get("nombre_movimiento") or "").strip()
        if not nombre:
            return JSONResponse(status_code=400, content={"error": "nombre_movimiento es requerido"})
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f"INSERT INTO {TABLE} (nombre_movimiento) VALUES (%s)", (nombre,))
        conn.commit()
        new_id = cursor.lastrowid
        cursor.close()
        conn.close()
        return {"message": "Tipo creado", "id": new_id, "id_tipo_movimiento": new_id, "id_tipo_mov": new_id}
    except Exception as e:
        return server_error(e)


@router.put(
    "/{id_tipo_movimiento}",
    summary="Actualizar tipo de movimiento",
    description="Modifica el nombre de un tipo de movimiento existente.",
    responses={
        **RESP_400,
        **RESP_401,
        **RESP_404,
        **RESP_500,
    },
)
def actualizar(id_tipo_movimiento: int, body: dict = Body(default={}), current_user: str = Depends(get_current_user)):
    try:
        nombre = body.get("nombre_movimiento")
        if nombre is not None:
            nombre = str(nombre).strip()
            if not nombre:
                return JSONResponse(status_code=400, content={"error": "nombre_movimiento no puede estar vacío"})
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f"SELECT {PK} FROM {TABLE} WHERE {PK} = %s", (id_tipo_movimiento,))
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return JSONResponse(status_code=404, content={"error": "Tipo de movimiento no encontrado"})
        if nombre is None:
            cursor.close()
            conn.close()
            return JSONResponse(status_code=400, content={"error": "Nada que actualizar"})
        cursor.execute(f"UPDATE {TABLE} SET nombre_movimiento = %s WHERE {PK} = %s", (nombre, id_tipo_movimiento))
        conn.commit()
        cursor.close()
        conn.close()
        return {"message": "Tipo actualizado"}
    except Exception as e:
        return server_error(e)


@router.delete(
    "/{id_tipo_movimiento}",
    summary="Eliminar tipo de movimiento",
    description=(
        "Elimina un tipo de movimiento del catálogo. "
        "No eliminar ENTRADA ni SALIDA si existen movimientos asociados."
    ),
    responses={
        **RESP_401,
        **RESP_404,
        **RESP_500,
    },
)
def eliminar(id_tipo_movimiento: int, current_user: str = Depends(get_current_user)):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f"DELETE FROM {TABLE} WHERE {PK} = %s", (id_tipo_movimiento,))
        conn.commit()
        n = cursor.rowcount
        cursor.close()
        conn.close()
        if n == 0:
            return JSONResponse(status_code=404, content={"error": "Tipo de movimiento no encontrado"})
        return {"message": "Tipo eliminado"}
    except Exception as e:
        return server_error(e)

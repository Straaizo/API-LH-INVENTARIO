"""
Dimensión: DIM_DESTINO_LH_INVENTARIO
- id_destino (PK), nombre_destino
"""

import logging

from fastapi import APIRouter, Body, Depends
from fastapi.responses import JSONResponse

from schemas.base import RESP_400, RESP_401, RESP_404, RESP_500
from schemas.movimientos import DestinoCreate, DestinoListResponse
from utils.auth import get_current_user
from utils.db import get_db_connection
from utils.errors import server_error

logger = logging.getLogger(__name__)
router = APIRouter()

TABLE = "inventario_dim_destino"
PK = "id_destino"


def _safe_value(val):
    if val is None:
        return None
    if isinstance(val, bytes):
        return val.decode("utf-8", errors="replace")
    return val


@router.get(
    "",
    summary="Listar destinos de salida",
    description=(
        "Retorna el catálogo de destinos disponibles para los movimientos de tipo SALIDA. "
        "Ej: Administración, Recepción, Cocina, Bodega Central."
    ),
    response_model=DestinoListResponse,
    responses={
        **RESP_401,
        **RESP_500,
    },
)
def listar(current_user: str = Depends(get_current_user)):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f"SELECT {PK}, nombre_destino FROM {TABLE} ORDER BY nombre_destino")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        data = [
            {
                "id": int(r[0]),
                "id_destino": int(r[0]),
                "destino_id": int(r[0]),
                "nombre_destino": _safe_value(r[1]) or "",
            }
            for r in rows
        ]
        return {"data": data}
    except Exception as e:
        logger.exception("dim_destino listar")
        return server_error(e)


@router.get(
    "/{destino_id}",
    summary="Obtener destino por ID",
    description="Retorna el nombre y datos de un destino específico.",
    responses={
        **RESP_401,
        **RESP_404,
        **RESP_500,
    },
)
def obtener(destino_id: int, current_user: str = Depends(get_current_user)):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f"SELECT {PK}, nombre_destino FROM {TABLE} WHERE {PK} = %s", (destino_id,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        if not row:
            return JSONResponse(status_code=404, content={"error": "Destino no encontrado"})
        i = int(row[0])
        return {
            "id": i,
            "id_destino": i,
            "destino_id": i,
            "nombre_destino": _safe_value(row[1]) or "",
        }
    except Exception as e:
        return server_error(e)


@router.post(
    "",
    status_code=201,
    summary="Crear destino de salida",
    description=(
        "Agrega un nuevo destino al catálogo. "
        "Ej: Administración, Recepción, Cocina, Caja, Bodega Central."
    ),
    responses={
        **RESP_400,
        **RESP_401,
        **RESP_500,
    },
)
def crear(body: dict = Body(default={}), current_user: str = Depends(get_current_user)):
    try:
        nombre = (body.get("nombre_destino") or "").strip()
        if not nombre:
            return JSONResponse(status_code=400, content={"error": "nombre_destino es requerido"})
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f"INSERT INTO {TABLE} (nombre_destino) VALUES (%s)", (nombre,))
        conn.commit()
        new_id = cursor.lastrowid
        cursor.close()
        conn.close()
        return {"message": "Destino creado", "id": new_id, "destino_id": new_id}
    except Exception as e:
        return server_error(e)


@router.put(
    "/{destino_id}",
    summary="Actualizar destino",
    description="Modifica el nombre de un destino existente.",
    responses={
        **RESP_400,
        **RESP_401,
        **RESP_404,
        **RESP_500,
    },
)
def actualizar(destino_id: int, body: dict = Body(default={}), current_user: str = Depends(get_current_user)):
    try:
        nombre = body.get("nombre_destino")
        if nombre is not None:
            nombre = str(nombre).strip()
            if not nombre:
                return JSONResponse(status_code=400, content={"error": "nombre_destino no puede estar vacío"})
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f"SELECT {PK} FROM {TABLE} WHERE {PK} = %s", (destino_id,))
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return JSONResponse(status_code=404, content={"error": "Destino no encontrado"})
        if nombre is None:
            cursor.close()
            conn.close()
            return JSONResponse(status_code=400, content={"error": "Nada que actualizar"})
        cursor.execute(f"UPDATE {TABLE} SET nombre_destino = %s WHERE {PK} = %s", (nombre, destino_id))
        conn.commit()
        cursor.close()
        conn.close()
        return {"message": "Destino actualizado"}
    except Exception as e:
        return server_error(e)


@router.delete(
    "/{destino_id}",
    summary="Eliminar destino",
    description="Elimina un destino del catálogo. Verificar que no tenga movimientos asociados antes de eliminar.",
    responses={
        **RESP_401,
        **RESP_404,
        **RESP_500,
    },
)
def eliminar(destino_id: int, current_user: str = Depends(get_current_user)):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f"DELETE FROM {TABLE} WHERE {PK} = %s", (destino_id,))
        conn.commit()
        n = cursor.rowcount
        cursor.close()
        conn.close()
        if n == 0:
            return JSONResponse(status_code=404, content={"error": "Destino no encontrado"})
        return {"message": "Destino eliminado"}
    except Exception as e:
        return server_error(e)

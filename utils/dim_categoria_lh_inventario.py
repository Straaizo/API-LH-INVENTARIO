"""
Dimensión: DIM_CATEGORIA_LH_INVENTARIO
- id_categoria (PK), nombre_categoria
"""

import logging
  
from fastapi import APIRouter, Body, Depends
from fastapi.responses import JSONResponse

from schemas.base import RESP_400, RESP_401, RESP_404, RESP_500
from schemas.inventario import CategoriaCreate, CategoriaListResponse
from utils.auth import get_current_user
from utils.db import get_db_connection
from utils.errors import server_error

logger = logging.getLogger(__name__)
router = APIRouter()

TABLE = "inventario_dim_categoria"
PK = "id_categoria"


def _safe_value(val):
    if val is None:
        return None
    if isinstance(val, bytes):
        return val.decode("utf-8", errors="replace")
    return val


@router.get(
    "",
    summary="Listar categorías de productos",
    description=(
        "Retorna el catálogo de categorías de insumos disponibles. "
        "Ej: Tóner, Tambor, Drum, Kit de mantenimiento."
    ),
    response_model=CategoriaListResponse,
    responses={
        **RESP_401,
        **RESP_500,
    },
)
def listar(current_user: str = Depends(get_current_user)):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f"SELECT {PK}, nombre_categoria FROM {TABLE} ORDER BY nombre_categoria")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        data = [
            {"id": int(r[0]), "id_categoria": int(r[0]), "nombre_categoria": _safe_value(r[1]) or ""}
            for r in rows
        ]
        return {"data": data}
    except Exception as e:
        logger.exception("dim_categoria listar")
        return server_error(e)


@router.get(
    "/{id_categoria}",
    summary="Obtener categoría por ID",
    description="Retorna el nombre y datos de una categoría específica.",
    responses={
        **RESP_401,
        **RESP_404,
        **RESP_500,
    },
)
def obtener(id_categoria: int, current_user: str = Depends(get_current_user)):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f"SELECT {PK}, nombre_categoria FROM {TABLE} WHERE {PK} = %s", (id_categoria,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        if not row:
            return JSONResponse(status_code=404, content={"error": "Categoría no encontrada"})
        return {
            "id": int(row[0]),
            "id_categoria": int(row[0]),
            "nombre_categoria": _safe_value(row[1]) or "",
        }
    except Exception as e:
        return server_error(e)


@router.post(
    "",
    status_code=201,
    summary="Crear categoría de producto",
    description=(
        "Agrega una nueva categoría al catálogo de insumos. "
        "Valores estándar: Tóner, Tambor, Drum, Kit de mantenimiento."
    ),
    responses={
        **RESP_400,
        **RESP_401,
        **RESP_500,
    },
)
def crear(body: dict = Body(default={}), current_user: str = Depends(get_current_user)):
    try:
        nombre = (body.get("nombre_categoria") or "").strip()
        if not nombre:
            return JSONResponse(status_code=400, content={"error": "nombre_categoria es requerido"})
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f"INSERT INTO {TABLE} (nombre_categoria) VALUES (%s)", (nombre,))
        conn.commit()
        new_id = cursor.lastrowid
        cursor.close()
        conn.close()
        return {"message": "Categoría creada", "id": new_id, "id_categoria": new_id}
    except Exception as e:
        return server_error(e)


@router.put(
    "/{id_categoria}",
    summary="Actualizar categoría",
    description="Modifica el nombre de una categoría existente.",
    responses={
        **RESP_400,
        **RESP_401,
        **RESP_404,
        **RESP_500,
    },
)
def actualizar(id_categoria: int, body: dict = Body(default={}), current_user: str = Depends(get_current_user)):
    try:
        nombre = body.get("nombre_categoria")
        if nombre is not None:
            nombre = str(nombre).strip()
            if not nombre:
                return JSONResponse(status_code=400, content={"error": "nombre_categoria no puede estar vacío"})
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f"SELECT {PK} FROM {TABLE} WHERE {PK} = %s", (id_categoria,))
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return JSONResponse(status_code=404, content={"error": "Categoría no encontrada"})
        if nombre is None:
            cursor.close()
            conn.close()
            return JSONResponse(status_code=400, content={"error": "Nada que actualizar"})
        cursor.execute(f"UPDATE {TABLE} SET nombre_categoria = %s WHERE {PK} = %s", (nombre, id_categoria))
        conn.commit()
        cursor.close()
        conn.close()
        return {"message": "Categoría actualizada"}
    except Exception as e:
        return server_error(e)


@router.delete(
    "/{id_categoria}",
    summary="Eliminar categoría",
    description=(
        "Elimina una categoría del catálogo. "
        "No eliminar si existen productos asociados a esta categoría."
    ),
    responses={
        **RESP_401,
        **RESP_404,
        **RESP_500,
    },
)
def eliminar(id_categoria: int, current_user: str = Depends(get_current_user)):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f"DELETE FROM {TABLE} WHERE {PK} = %s", (id_categoria,))
        conn.commit()
        n = cursor.rowcount
        cursor.close()
        conn.close()
        if n == 0:
            return JSONResponse(status_code=404, content={"error": "Categoría no encontrada"})
        return {"message": "Categoría eliminada"}
    except Exception as e:
        return server_error(e)

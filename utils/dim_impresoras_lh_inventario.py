"""
Dimensión: DIM_IMPRESORAS_LH_INVENTARIO
Columnas: id_impresora (PK), estado, ubicacion, impresora,
          conexion, fecha, responsable (texto)
"""

import logging

from fastapi import APIRouter, Body, Depends
from fastapi.responses import JSONResponse

from schemas.activos import ImpresoraCreate, ImpresoraListResponse
from schemas.base import RESP_400, RESP_401, RESP_404, RESP_500
from utils.auth import get_current_user
from utils.db import get_db_connection
from utils.errors import server_error

logger = logging.getLogger(__name__)
router = APIRouter()

TABLE = "inventario_dim_impresoras"
PK = "id_impresoras"

COLS_INSERT = [
    "estado", "ubicacion", "impresora", "conexion", "fecha", "responsable",
]

_JOIN_SQL = f"""
    SELECT
        i.id_impresoras, i.estado, i.ubicacion, i.impresora,
        i.conexion, i.fecha, i.responsable
    FROM {TABLE} i
"""


def _safe(val):
    if val is None:
        return None
    if isinstance(val, bytes):
        return val.decode("utf-8", errors="replace")
    return val


def _row_to_dict(cursor_description, row) -> dict:
    cols = [d[0] for d in cursor_description]
    d = {}
    for col, val in zip(cols, row):
        if hasattr(val, "strftime"):
            d[col] = val.strftime("%Y-%m-%d")
        elif isinstance(val, bytes):
            d[col] = val.decode("utf-8", errors="replace")
        else:
            d[col] = val
    if "id_impresoras" in d:
        d["id"] = d["id_impresoras"]
        d["id_impresora"] = d["id_impresoras"]
    return d


@router.get(
    "",
    summary="Listar impresoras",
    description=(
        "Retorna el inventario de impresoras con ubicación, "
        "tipo de conexión (Red, USB) y responsable asignado."
    ),
    response_model=ImpresoraListResponse,
    responses={
        **RESP_401,
        **RESP_500,
    },
)
def listar(current_user: str = Depends(get_current_user)):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(_JOIN_SQL + " ORDER BY i.impresora")
        rows = cursor.fetchall()
        desc = cursor.description
        cursor.close()
        conn.close()
        return {"data": [_row_to_dict(desc, r) for r in rows]}
    except Exception as e:
        logger.exception("dim_impresoras listar")
        return server_error(e)


@router.get(
    "/{id_impresora}",
    summary="Obtener impresora por ID",
    description="Retorna el detalle completo de una impresora específica.",
    responses={
        **RESP_401,
        **RESP_404,
        **RESP_500,
    },
)
def obtener(id_impresora: int, current_user: str = Depends(get_current_user)):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(_JOIN_SQL + f" WHERE i.{PK} = %s", (id_impresora,))
        row = cursor.fetchone()
        desc = cursor.description
        cursor.close()
        conn.close()
        if not row:
            return JSONResponse(status_code=404, content={"error": "Impresora no encontrada"})
        return _row_to_dict(desc, row)
    except Exception as e:
        return server_error(e)


@router.post(
    "",
    status_code=201,
    summary="Registrar impresora",
    description=(
        "Agrega una nueva impresora al inventario. "
        "El campo `impresora` (nombre/modelo) es obligatorio. "
        "Conexión válida: Red, USB."
    ),
    responses={
        **RESP_400,
        **RESP_401,
        **RESP_500,
    },
)
def crear(body: dict = Body(default={}), current_user: str = Depends(get_current_user)):
    try:
        nombre_imp = (body.get("impresora") or "").strip()
        if not nombre_imp:
            return JSONResponse(status_code=400, content={"error": "impresora es requerido"})
        campos = {"impresora": nombre_imp}
        for col in COLS_INSERT:
            if col == "impresora":
                continue
            val = body.get(col)
            if val is not None:
                campos[col] = str(val).strip() if isinstance(val, str) else val
        conn = get_db_connection()
        cursor = conn.cursor()
        cols_sql = ", ".join(campos.keys())
        placeholders = ", ".join(["%s"] * len(campos))
        cursor.execute(f"INSERT INTO {TABLE} ({cols_sql}) VALUES ({placeholders})", list(campos.values()))
        conn.commit()
        new_id = cursor.lastrowid
        cursor.close()
        conn.close()
        return {"message": "Impresora creada", "id": new_id, "id_impresora": new_id}
    except Exception as e:
        logger.exception("dim_impresoras crear")
        return server_error(e)


@router.put(
    "/{id_impresora}",
    summary="Actualizar impresora",
    description="Modifica los datos de una impresora existente. Solo enviar los campos a modificar.",
    responses={
        **RESP_400,
        **RESP_401,
        **RESP_404,
        **RESP_500,
    },
)
def actualizar(id_impresora: int, body: dict = Body(default={}), current_user: str = Depends(get_current_user)):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f"SELECT {PK} FROM {TABLE} WHERE {PK} = %s", (id_impresora,))
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return JSONResponse(status_code=404, content={"error": "Impresora no encontrada"})
        updates, params = [], []
        for col in COLS_INSERT:
            if col in body:
                updates.append(f"{col} = %s")
                val = body[col]
                params.append(str(val).strip() if isinstance(val, str) else val)
        if not updates:
            cursor.close()
            conn.close()
            return JSONResponse(status_code=400, content={"error": "Nada que actualizar"})
        params.append(id_impresora)
        cursor.execute(f"UPDATE {TABLE} SET {', '.join(updates)} WHERE {PK} = %s", params)
        conn.commit()
        cursor.close()
        conn.close()
        return {"message": "Impresora actualizada"}
    except Exception as e:
        return server_error(e)


@router.delete(
    "/{id_impresora}",
    summary="Eliminar impresora",
    description="Elimina permanentemente una impresora del inventario.",
    responses={
        **RESP_401,
        **RESP_404,
        **RESP_500,
    },
)
def eliminar(id_impresora: int, current_user: str = Depends(get_current_user)):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f"DELETE FROM {TABLE} WHERE {PK} = %s", (id_impresora,))
        conn.commit()
        n = cursor.rowcount
        cursor.close()
        conn.close()
        if n == 0:
            return JSONResponse(status_code=404, content={"error": "Impresora no encontrada"})
        return {"message": "Impresora eliminada"}
    except Exception as e:
        return server_error(e)

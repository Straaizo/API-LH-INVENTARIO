"""
Dimensión: DIM_TABLETS_LH_INVENTARIO
Columnas: id_tablet (PK), codigo_tablet, estado, marca, modelo,
          capacidad, fecha_entrega, responsable (texto)
"""

import logging

from fastapi import APIRouter, Body, Depends
from fastapi.responses import JSONResponse

from schemas.activos import TabletCreate, TabletListResponse
from schemas.base import RESP_400, RESP_401, RESP_404, RESP_500
from utils.auth import get_current_user
from utils.db import get_db_connection
from utils.errors import server_error

logger = logging.getLogger(__name__)
router = APIRouter()

TABLE = "inventario_dim_tablets"
PK = "id_tablet"

COLS_INSERT = [
    "codigo_tablet", "estado", "marca", "modelo",
    "capacidad", "fecha_entrega", "responsable",
]

_JOIN_SQL = f"""
    SELECT
        t.id_tablet, t.codigo_tablet, t.estado, t.marca, t.modelo,
        t.capacidad, t.fecha_entrega, t.responsable
    FROM {TABLE} t
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
    if "id_tablet" in d:
        d["id"] = d["id_tablet"]
    if "codigo_tablet" in d:
        d["codigo"] = d["codigo_tablet"]
    return d


@router.get(
    "",
    summary="Listar tablets corporativas",
    description=(
        "Retorna el inventario de tablets con código de activo, "
        "estado, capacidad y responsable asignado."
    ),
    response_model=TabletListResponse,
    responses={
        **RESP_401,
        **RESP_500,
    },
)
def listar(current_user: str = Depends(get_current_user)):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(_JOIN_SQL + " ORDER BY t.codigo_tablet")
        rows = cursor.fetchall()
        desc = cursor.description
        cursor.close()
        conn.close()
        return {"data": [_row_to_dict(desc, r) for r in rows]}
    except Exception as e:
        logger.exception("dim_tablets listar")
        return server_error(e)


@router.get(
    "/{id_tablet}",
    summary="Obtener tablet por ID",
    description="Retorna el detalle completo de una tablet específica.",
    responses={
        **RESP_401,
        **RESP_404,
        **RESP_500,
    },
)
def obtener(id_tablet: int, current_user: str = Depends(get_current_user)):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(_JOIN_SQL + f" WHERE t.{PK} = %s", (id_tablet,))
        row = cursor.fetchone()
        desc = cursor.description
        cursor.close()
        conn.close()
        if not row:
            return JSONResponse(status_code=404, content={"error": "Tablet no encontrada"})
        return _row_to_dict(desc, row)
    except Exception as e:
        return server_error(e)


@router.post(
    "",
    status_code=201,
    summary="Registrar tablet",
    description=(
        "Agrega una nueva tablet al inventario. "
        "El `codigo_tablet` es obligatorio y debe ser único."
    ),
    responses={
        **RESP_400,
        **RESP_401,
        **RESP_500,
    },
)
def crear(body: dict = Body(default={}), current_user: str = Depends(get_current_user)):
    try:
        codigo = (body.get("codigo_tablet") or body.get("codigo") or "").strip()
        if not codigo:
            return JSONResponse(status_code=400, content={"error": "codigo_tablet es requerido"})
        campos = {"codigo_tablet": codigo}
        for col in COLS_INSERT[1:]:
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
        return {"message": "Tablet creada", "id": new_id, "id_tablet": new_id, "codigo_tablet": codigo}
    except Exception as e:
        logger.exception("dim_tablets crear")
        return server_error(e)


@router.put(
    "/{id_tablet}",
    summary="Actualizar tablet",
    description="Modifica los datos de una tablet existente. Solo enviar los campos a modificar.",
    responses={
        **RESP_400,
        **RESP_401,
        **RESP_404,
        **RESP_500,
    },
)
def actualizar(id_tablet: int, body: dict = Body(default={}), current_user: str = Depends(get_current_user)):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f"SELECT {PK} FROM {TABLE} WHERE {PK} = %s", (id_tablet,))
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return JSONResponse(status_code=404, content={"error": "Tablet no encontrada"})
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
        params.append(id_tablet)
        cursor.execute(f"UPDATE {TABLE} SET {', '.join(updates)} WHERE {PK} = %s", params)
        conn.commit()
        cursor.close()
        conn.close()
        return {"message": "Tablet actualizada"}
    except Exception as e:
        return server_error(e)


@router.delete(
    "/{id_tablet}",
    summary="Eliminar tablet",
    description="Elimina permanentemente una tablet del inventario.",
    responses={
        **RESP_401,
        **RESP_404,
        **RESP_500,
    },
)
def eliminar(id_tablet: int, current_user: str = Depends(get_current_user)):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f"DELETE FROM {TABLE} WHERE {PK} = %s", (id_tablet,))
        conn.commit()
        n = cursor.rowcount
        cursor.close()
        conn.close()
        if n == 0:
            return JSONResponse(status_code=404, content={"error": "Tablet no encontrada"})
        return {"message": "Tablet eliminada"}
    except Exception as e:
        return server_error(e)

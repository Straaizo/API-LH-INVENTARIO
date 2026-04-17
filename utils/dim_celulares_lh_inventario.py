"""
Dimensión: DIM_CELULARES_LH_INVENTARIO
Columnas: id_celular (PK), numero, estado, tipo_celular, compania,
          marca, modelo, imei, fecha_entrega, responsable (texto)
"""

import logging

from fastapi import APIRouter, Body, Depends
from fastapi.responses import JSONResponse

from schemas.activos import CelularCreate, CelularListResponse
from schemas.base import RESP_400, RESP_401, RESP_404, RESP_500
from utils.auth import get_current_user
from utils.db import get_db_connection
from utils.errors import server_error

logger = logging.getLogger(__name__)
router = APIRouter()

TABLE = "inventario_dim_celulares"
PK = "id_celular"

COLS_INSERT = [
    "numero", "estado", "tipo_celular", "compania",
    "marca", "modelo", "imei", "fecha_entrega", "responsable",
]

_JOIN_SQL = f"""
    SELECT
        c.id_celular, c.numero, c.estado, c.tipo_celular, c.compania,
        c.marca, c.modelo, c.imei, c.fecha_entrega, c.responsable
    FROM {TABLE} c
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
    if "id_celular" in d:
        d["id"] = d["id_celular"]
    return d


@router.get(
    "",
    summary="Listar líneas móviles",
    description=(
        "Retorna el inventario completo de celulares corporativos. "
        "Incluye tipo de línea (Voz y Datos, M2M, BAM), compañía y responsable asignado."
    ),
    response_model=CelularListResponse,
    responses={
        **RESP_401,
        **RESP_500,
    },
)
def listar(current_user: str = Depends(get_current_user)):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(_JOIN_SQL + " ORDER BY c.numero")
        rows = cursor.fetchall()
        desc = cursor.description
        cursor.close()
        conn.close()
        return {"data": [_row_to_dict(desc, r) for r in rows]}
    except Exception as e:
        logger.exception("dim_celulares listar")
        return server_error(e)


@router.get(
    "/{id_celular}",
    summary="Obtener celular por ID",
    description="Retorna el detalle completo de una línea móvil específica.",
    responses={
        **RESP_401,
        **RESP_404,
        **RESP_500,
    },
)
def obtener(id_celular: int, current_user: str = Depends(get_current_user)):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(_JOIN_SQL + f" WHERE c.{PK} = %s", (id_celular,))
        row = cursor.fetchone()
        desc = cursor.description
        cursor.close()
        conn.close()
        if not row:
            return JSONResponse(status_code=404, content={"error": "Celular no encontrado"})
        return _row_to_dict(desc, row)
    except Exception as e:
        return server_error(e)


@router.post(
    "",
    status_code=201,
    summary="Registrar línea móvil",
    description=(
        "Agrega una nueva línea móvil al inventario. "
        "El campo `numero` es obligatorio. "
        "Tipos de línea válidos: Voz y Datos, M2M, BAM."
    ),
    responses={
        **RESP_400,
        **RESP_401,
        **RESP_500,
    },
)
def crear(body: dict = Body(default={}), current_user: str = Depends(get_current_user)):
    try:
        numero = (body.get("numero") or "").strip()
        if not numero:
            return JSONResponse(status_code=400, content={"error": "numero es requerido"})
        campos = {"numero": numero}
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
        return {"message": "Celular creado", "id": new_id, "id_celular": new_id}
    except Exception as e:
        logger.exception("dim_celulares crear")
        return server_error(e)


@router.put(
    "/{id_celular}",
    summary="Actualizar línea móvil",
    description="Modifica los datos de una línea móvil existente. Solo enviar los campos a modificar.",
    responses={
        **RESP_400,
        **RESP_401,
        **RESP_404,
        **RESP_500,
    },
)
def actualizar(id_celular: int, body: dict = Body(default={}), current_user: str = Depends(get_current_user)):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f"SELECT {PK} FROM {TABLE} WHERE {PK} = %s", (id_celular,))
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return JSONResponse(status_code=404, content={"error": "Celular no encontrado"})
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
        params.append(id_celular)
        cursor.execute(f"UPDATE {TABLE} SET {', '.join(updates)} WHERE {PK} = %s", params)
        conn.commit()
        cursor.close()
        conn.close()
        return {"message": "Celular actualizado"}
    except Exception as e:
        return server_error(e)


@router.delete(
    "/{id_celular}",
    summary="Eliminar línea móvil",
    description="Elimina permanentemente una línea móvil del inventario.",
    responses={
        **RESP_401,
        **RESP_404,
        **RESP_500,
    },
)
def eliminar(id_celular: int, current_user: str = Depends(get_current_user)):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f"DELETE FROM {TABLE} WHERE {PK} = %s", (id_celular,))
        conn.commit()
        n = cursor.rowcount
        cursor.close()
        conn.close()
        if n == 0:
            return JSONResponse(status_code=404, content={"error": "Celular no encontrado"})
        return {"message": "Celular eliminado"}
    except Exception as e:
        return server_error(e)

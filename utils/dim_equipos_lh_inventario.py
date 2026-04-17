"""
Dimensión: DIM_EQUIPOS_LH_INVENTARIO
Columnas: id_equipos (PK), codigo_equipo, estado, antivirus, ubicacion,
          tipo, marca, modelo, procesador, ram, disco_duro,
          sistema_operativo, office, numero_serie, fecha_revision,
          fk_id_usuario, responsable (texto)
JOIN con DIM_USUARIO_LH_INVENTARIO para datos de usuario asignación.
"""

import logging

from fastapi import APIRouter, Body, Depends
from fastapi.responses import JSONResponse

from schemas.activos import EquipoCreate, EquipoListResponse
from schemas.base import RESP_400, RESP_401, RESP_404, RESP_409, RESP_500
from utils.auth import get_current_user
from utils.db import get_db_connection
from utils.errors import server_error

logger = logging.getLogger(__name__)
router = APIRouter()

TABLE = "inventario_dim_equipos"
TABLE_USUARIO = "general_dim_usuario"
PK = "id_equipos"

COLS_INSERT = [
    "codigo_equipo", "estado", "antivirus", "ubicacion",
    "tipo", "marca", "modelo", "procesador", "ram", "disco_duro",
    "sistema_operativo", "office", "numero_serie", "fecha_revision",
    "fk_id_usuario", "responsable",
]

_JOIN_SQL = f"""
    SELECT
        e.id_equipos, e.codigo_equipo, e.estado, e.antivirus, e.ubicacion,
        e.tipo, e.marca, e.modelo, e.procesador, e.ram, e.disco_duro,
        e.sistema_operativo, e.office, e.numero_serie, e.fecha_revision,
        e.fk_id_usuario, e.responsable,
        COALESCE(NULLIF(TRIM(u.nombre), ''), u.usuario, '') AS usuario_nombre,
        COALESCE(u.correo, '') AS usuario_correo
    FROM {TABLE} e
    LEFT JOIN {TABLE_USUARIO} u ON e.fk_id_usuario = u.id
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
    if "id_equipos" in d:
        d["id"] = d["id_equipos"]
    if "codigo_equipo" in d:
        d["codigo"] = d["codigo_equipo"]
    return d


@router.get(
    "",
    summary="Listar equipos informáticos",
    description=(
        "Retorna el inventario completo de activos tecnológicos (notebooks, desktops, servidores, mini PCs) "
        "con el nombre y correo del usuario asignado cuando corresponde."
    ),
    response_model=EquipoListResponse,
    responses={
        **RESP_401,
        **RESP_500,
    },
)
def listar(current_user: str = Depends(get_current_user)):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(_JOIN_SQL + " ORDER BY e.codigo_equipo")
        rows = cursor.fetchall()
        desc = cursor.description
        cursor.close()
        conn.close()
        return {"data": [_row_to_dict(desc, r) for r in rows]}
    except Exception as e:
        logger.exception("dim_equipos listar")
        return server_error(e)


@router.get(
    "/{id_equipo}",
    summary="Obtener equipo por ID",
    description="Retorna el detalle completo de un equipo específico, incluyendo datos del usuario asignado.",
    responses={
        **RESP_401,
        **RESP_404,
        **RESP_500,
    },
)
def obtener(id_equipo: int, current_user: str = Depends(get_current_user)):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(_JOIN_SQL + f" WHERE e.{PK} = %s", (id_equipo,))
        row = cursor.fetchone()
        desc = cursor.description
        cursor.close()
        conn.close()
        if not row:
            return JSONResponse(status_code=404, content={"error": "Equipo no encontrado"})
        return _row_to_dict(desc, row)
    except Exception as e:
        return server_error(e)


@router.post(
    "",
    status_code=201,
    summary="Registrar equipo",
    description=(
        "Agrega un nuevo equipo al inventario. El `codigo_equipo` debe ser único. "
        "El `fk_id_usuario` se toma automáticamente del token JWT del usuario que realiza el registro."
    ),
    responses={
        **RESP_400,
        **RESP_401,
        **RESP_409,
        **RESP_500,
    },
)
def crear(body: dict = Body(default={}), current_user: str = Depends(get_current_user)):
    try:
        codigo = (body.get("codigo_equipo") or body.get("codigo") or "").strip()
        if not codigo:
            return JSONResponse(status_code=400, content={"error": "codigo_equipo es requerido"})
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f"SELECT {PK} FROM {TABLE} WHERE codigo_equipo = %s", (codigo,))
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return JSONResponse(status_code=409, content={"error": "El código de equipo ya existe"})
        campos = {"codigo_equipo": codigo}
        for col in COLS_INSERT[1:]:
            if col == "fk_id_usuario":
                continue
            val = body.get(col)
            if val is not None:
                campos[col] = str(val).strip() if isinstance(val, str) else val
        if not current_user:
            cursor.close()
            conn.close()
            return JSONResponse(status_code=401, content={"error": "Sesión inválida"})
        campos["fk_id_usuario"] = str(current_user)
        cols_sql = ", ".join(campos.keys())
        placeholders = ", ".join(["%s"] * len(campos))
        cursor.execute(f"INSERT INTO {TABLE} ({cols_sql}) VALUES ({placeholders})", list(campos.values()))
        conn.commit()
        new_id = cursor.lastrowid
        cursor.close()
        conn.close()
        return {"message": "Equipo creado", "id": new_id, "id_equipos": new_id, "codigo_equipo": codigo}
    except Exception as e:
        logger.exception("dim_equipos crear")
        return server_error(e)


@router.put(
    "/{id_equipo}",
    summary="Actualizar equipo",
    description=(
        "Modifica los datos de un equipo existente. "
        "Solo enviar los campos a modificar. El `codigo_equipo` debe ser único."
    ),
    responses={
        **RESP_400,
        **RESP_401,
        **RESP_404,
        **RESP_409,
        **RESP_500,
    },
)
def actualizar(id_equipo: int, body: dict = Body(default={}), current_user: str = Depends(get_current_user)):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f"SELECT {PK} FROM {TABLE} WHERE {PK} = %s", (id_equipo,))
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return JSONResponse(status_code=404, content={"error": "Equipo no encontrado"})
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
        if "codigo_equipo" in body:
            cursor.execute(
                f"SELECT {PK} FROM {TABLE} WHERE codigo_equipo = %s AND {PK} != %s",
                (body["codigo_equipo"], id_equipo),
            )
            if cursor.fetchone():
                cursor.close()
                conn.close()
                return JSONResponse(status_code=409, content={"error": "El código ya está en uso"})
        params.append(id_equipo)
        cursor.execute(f"UPDATE {TABLE} SET {', '.join(updates)} WHERE {PK} = %s", params)
        conn.commit()
        cursor.close()
        conn.close()
        return {"message": "Equipo actualizado"}
    except Exception as e:
        return server_error(e)


@router.delete(
    "/{id_equipo}",
    summary="Eliminar equipo",
    description="Elimina permanentemente un equipo del inventario.",
    responses={
        **RESP_401,
        **RESP_404,
        **RESP_500,
    },
)
def eliminar(id_equipo: int, current_user: str = Depends(get_current_user)):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f"DELETE FROM {TABLE} WHERE {PK} = %s", (id_equipo,))
        conn.commit()
        n = cursor.rowcount
        cursor.close()
        conn.close()
        if n == 0:
            return JSONResponse(status_code=404, content={"error": "Equipo no encontrado"})
        return {"message": "Equipo eliminado"}
    except Exception as e:
        return server_error(e)

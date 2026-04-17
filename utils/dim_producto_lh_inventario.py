"""
Dimensión: DIM_PRODUCTO_LH_INVENTARIO
- id_producto (PK), nombre_producto, id_categoria (FK)
"""

import json
import logging
import unicodedata

from fastapi import APIRouter, Body, Depends, Request
from fastapi.responses import JSONResponse

from schemas.base import RESP_400, RESP_401, RESP_404, RESP_500
from schemas.inventario import ProductoCreate, ProductoListResponse
from utils.auth import get_current_user
from utils.db import get_db_connection
from utils.errors import server_error
from utils.lh_inventario_tables import (
    DIM_CATEGORIA,
    DIM_PRODUCTO,
    FK_PRODUCTO_CATEGORIA,
    PK_CATEGORIA,
    PK_PRODUCTO,
)

logger = logging.getLogger(__name__)
router = APIRouter()

TABLE = DIM_PRODUCTO
TABLE_CAT = DIM_CATEGORIA
PK = PK_PRODUCTO
PK_CAT = PK_CATEGORIA
FK_CAT = FK_PRODUCTO_CATEGORIA


def _safe_value(val):
    if val is None:
        return None
    if isinstance(val, bytes):
        return val.decode("utf-8", errors="replace")
    return val


def _as_int_id(val):
    if val is None:
        return None
    if isinstance(val, bool):
        return None
    if isinstance(val, (int, float)):
        return int(val)
    s = str(val).strip()
    if s.isdigit():
        return int(s)
    return None


def _nombre_categoria_lookup(cursor, nombre_raw):
    nombre = (nombre_raw or "").strip()
    if not nombre:
        return None
    cursor.execute(
        f"SELECT {PK_CAT} FROM {TABLE_CAT} WHERE nombre_categoria = %s LIMIT 1",
        (nombre,),
    )
    row = cursor.fetchone()
    if row:
        return int(row[0])
    cursor.execute(
        f"SELECT {PK_CAT} FROM {TABLE_CAT} WHERE LOWER(TRIM(nombre_categoria)) = LOWER(TRIM(%s)) LIMIT 1",
        (nombre,),
    )
    row = cursor.fetchone()
    if row:
        return int(row[0])

    def _fold(s):
        s = (s or "").strip()
        if not s:
            return ""
        nfd = unicodedata.normalize("NFD", s)
        return "".join(c for c in nfd if unicodedata.category(c) != "Mn").lower()

    target = _fold(nombre_raw)
    if not target:
        return None
    cursor.execute(f"SELECT {PK_CAT}, nombre_categoria FROM {TABLE_CAT}")
    for cid, nom in cursor.fetchall():
        if _fold(_safe_value(nom)) == target:
            return int(cid)
    return None


def _id_categoria_from_body(cursor, data):
    for key in ("id_categoria", "categoria_id", "category_id", "idCategoria", "categoryId"):
        cid = _as_int_id(data.get(key))
        if cid is not None:
            return cid

    cat_scalar = data.get("categoria")
    if not isinstance(cat_scalar, (dict, list)):
        cid = _as_int_id(cat_scalar)
        if cid is not None:
            return cid

    if isinstance(cat_scalar, dict):
        for k in ("id_categoria", "id", "categoria_id", "category_id"):
            cid = _as_int_id(cat_scalar.get(k))
            if cid is not None:
                return cid
        nom = cat_scalar.get("nombre_categoria") or cat_scalar.get("nombre")
        found = _nombre_categoria_lookup(cursor, nom)
        if found is not None:
            return found

    nombre = (
        data.get("nombre_categoria")
        or data.get("categoria_nombre")
        or data.get("nombreCategoria")
    )
    if nombre is None and isinstance(cat_scalar, str):
        nombre = cat_scalar
    found = _nombre_categoria_lookup(cursor, nombre)
    if found is not None:
        return found

    return None


async def _producto_payload(request: Request) -> dict:
    """JSON, form o cuerpo raw (compat Flutter / proxies)."""
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
    return data


@router.get(
    "",
    summary="Listar todos los productos",
    description=(
        "Retorna el catálogo completo de insumos con su categoría asociada, "
        "ordenado por categoría y nombre de producto. "
        "Ej: Tóner HP 85A (Tóner), Tambor Brother DR-3400 (Tambor)."
    ),
    response_model=ProductoListResponse,
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
            f"""
            SELECT p.{PK}, p.nombre_producto, p.{FK_CAT}, c.nombre_categoria
            FROM {TABLE} p
            LEFT JOIN {TABLE_CAT} c ON c.{PK_CAT} = p.{FK_CAT}
            ORDER BY c.nombre_categoria, p.nombre_producto
            """
        )
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        data = [
            {
                "id": int(r[0]),
                "id_producto": int(r[0]),
                "nombre_producto": _safe_value(r[1]) or "",
                "id_categoria": int(r[2]) if r[2] is not None else None,
                "categoria_id": int(r[2]) if r[2] is not None else None,
                "nombre_categoria": _safe_value(r[3]) or "",
            }
            for r in rows
        ]
        return {"data": data}
    except Exception as e:
        logger.exception("dim_producto listar")
        return server_error(e)


@router.get(
    "/{id_producto}",
    summary="Obtener producto por ID",
    description="Retorna los datos de un producto específico con su categoría.",
    responses={
        **RESP_401,
        **RESP_404,
        **RESP_500,
    },
)
def obtener(id_producto: int, current_user: str = Depends(get_current_user)):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            f"""
            SELECT p.{PK}, p.nombre_producto, p.{FK_CAT}, c.nombre_categoria
            FROM {TABLE} p
            LEFT JOIN {TABLE_CAT} c ON c.{PK_CAT} = p.{FK_CAT}
            WHERE p.{PK} = %s
            """,
            (id_producto,),
        )
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        if not row:
            return JSONResponse(status_code=404, content={"error": "Producto no encontrado"})
        return {
            "id": int(row[0]),
            "id_producto": int(row[0]),
            "nombre_producto": _safe_value(row[1]) or "",
            "id_categoria": int(row[2]) if row[2] is not None else None,
            "categoria_id": int(row[2]) if row[2] is not None else None,
            "nombre_categoria": _safe_value(row[3]) or "",
        }
    except Exception as e:
        return server_error(e)


@router.post(
    "",
    status_code=201,
    summary="Crear producto",
    description=(
        "Agrega un nuevo insumo al catálogo. Requiere nombre y categoría. "
        "La categoría puede enviarse como `id_categoria` (int) o `nombre_categoria` (string). "
        "Ej: `{ \"nombre_producto\": \"Tóner HP 85A\", \"id_categoria\": 2 }`"
    ),
    responses={
        **RESP_400,
        **RESP_401,
        404: {"description": "Categoría no encontrada"},
        **RESP_500,
    },
)
async def crear(request: Request, current_user: str = Depends(get_current_user)):
    try:
        data = await _producto_payload(request)
        nombre = (
            data.get("nombre_producto")
            or data.get("nombre")
            or data.get("nombreProducto")
            or ""
        )
        nombre = str(nombre or "").strip()
        if not nombre:
            return JSONResponse(status_code=400, content={"error": "nombre_producto es requerido"})

        conn = get_db_connection()
        cursor = conn.cursor()
        categoria_id = _id_categoria_from_body(cursor, data)
        if categoria_id is None:
            cursor.close()
            conn.close()
            return JSONResponse(status_code=400, content={"error": "id_categoria o nombre_categoria es requerido"})
        cursor.execute(f"SELECT {PK_CAT} FROM {TABLE_CAT} WHERE {PK_CAT} = %s", (categoria_id,))
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return JSONResponse(status_code=404, content={"error": "Categoría no encontrada"})

        cursor.execute(
            f"INSERT INTO {TABLE} (nombre_producto, {FK_CAT}) VALUES (%s, %s)",
            (nombre, categoria_id),
        )
        conn.commit()
        new_id = cursor.lastrowid
        cursor.close()
        conn.close()
        return {"message": "Producto creado", "id": new_id, "id_producto": new_id}
    except Exception as e:
        return server_error(e)


@router.put(
    "/{id_producto}",
    summary="Actualizar producto",
    description=(
        "Modifica el nombre y/o categoría de un producto existente. "
        "Solo enviar los campos a modificar."
    ),
    responses={
        **RESP_400,
        **RESP_401,
        **RESP_404,
        **RESP_500,
    },
)
async def actualizar(id_producto: int, request: Request, current_user: str = Depends(get_current_user)):
    try:
        data = await _producto_payload(request)
        nombre = (
            data.get("nombre_producto")
            if data.get("nombre_producto") is not None
            else data.get("nombreProducto")
            if data.get("nombreProducto") is not None
            else data.get("nombre")
        )
        _cat_keys = (
            "id_categoria", "categoria_id", "category_id", "idCategoria", "categoryId",
            "nombre_categoria", "categoria_nombre", "nombreCategoria", "categoria",
        )
        need_cat = any(k in data for k in _cat_keys)

        conn = get_db_connection()
        cursor = conn.cursor()
        categoria_id = _id_categoria_from_body(cursor, data) if need_cat else None

        if nombre is not None:
            nombre = str(nombre).strip()
            if not nombre:
                cursor.close()
                conn.close()
                return JSONResponse(status_code=400, content={"error": "nombre_producto no puede estar vacío"})
        if need_cat and categoria_id is None:
            cursor.close()
            conn.close()
            return JSONResponse(status_code=400, content={"error": "nombre_categoria no encontrada o id_categoria inválido"})
        if categoria_id is not None:
            categoria_id = int(categoria_id)

        cursor.execute(f"SELECT {PK} FROM {TABLE} WHERE {PK} = %s", (id_producto,))
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return JSONResponse(status_code=404, content={"error": "Producto no encontrado"})
        if categoria_id is not None:
            cursor.execute(f"SELECT {PK_CAT} FROM {TABLE_CAT} WHERE {PK_CAT} = %s", (categoria_id,))
            if not cursor.fetchone():
                cursor.close()
                conn.close()
                return JSONResponse(status_code=404, content={"error": "Categoría no encontrada"})

        updates, params = [], []
        if nombre is not None:
            updates.append("nombre_producto = %s")
            params.append(nombre)
        if categoria_id is not None:
            updates.append(f"{FK_CAT} = %s")
            params.append(categoria_id)
        if not updates:
            cursor.close()
            conn.close()
            return JSONResponse(status_code=400, content={"error": "Nada que actualizar"})
        params.append(id_producto)
        sql = f"UPDATE {TABLE} SET {', '.join(updates)} WHERE {PK} = %s"
        cursor.execute(sql, params)
        conn.commit()
        cursor.close()
        conn.close()
        return {"message": "Producto actualizado"}
    except Exception as e:
        return server_error(e)


@router.delete(
    "/{id_producto}",
    summary="Eliminar producto",
    description=(
        "Elimina un producto del catálogo. "
        "No eliminar si existen movimientos de inventario asociados a este producto."
    ),
    responses={
        **RESP_401,
        **RESP_404,
        **RESP_500,
    },
)
def eliminar(id_producto: int, current_user: str = Depends(get_current_user)):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f"DELETE FROM {TABLE} WHERE {PK} = %s", (id_producto,))
        conn.commit()
        n = cursor.rowcount
        cursor.close()
        conn.close()
        if n == 0:
            return JSONResponse(status_code=404, content={"error": "Producto no encontrado"})
        return {"message": "Producto eliminado"}
    except Exception as e:
        return server_error(e)

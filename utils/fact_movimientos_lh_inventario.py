"""
Hecho: FACT_MOVIMIENTOS_LH_INVENTARIO
- id_movimientos (PK), cantidad, fecha, id_producto, id_tipo_mov, id_destino, id_usuario

Validación SALIDA: lectura de vista vw_stock_actual (sin calcular stock en Python).
"""

import logging
from datetime import datetime

from fastapi import APIRouter, Body, Depends
from fastapi.responses import JSONResponse

from schemas.base import RESP_400, RESP_401, RESP_404, RESP_500
from schemas.movimientos import MovimientoCreate, MovimientoListResponse, MovimientoOut
from utils.auth import get_current_user
from utils.db import get_db_connection
from utils.errors import server_error
from utils.lh_inventario_tables import (
    DIM_CATEGORIA,
    DIM_DESTINO,
    DIM_PRODUCTO,
    DIM_TIPO_MOVIMIENTO,
    DIM_USUARIO,
    FACT_COL_DESTINO,
    FACT_COL_PRODUCTO,
    FACT_COL_TIPO,
    FACT_COL_USUARIO,
    FACT_MOVIMIENTOS,
    FK_PRODUCTO_CATEGORIA,
    PK_CATEGORIA,
    PK_DESTINO,
    PK_FACT,
    PK_PRODUCTO,
    PK_TIPO_MOVIMIENTO,
    PK_USUARIO,
    STOCK_VIEW_DEFAULT,
)

logger = logging.getLogger(__name__)
router = APIRouter()

TABLE = FACT_MOVIMIENTOS
PK = PK_FACT
STOCK_VIEW = STOCK_VIEW_DEFAULT


def _safe_value(val):
    if val is None:
        return None
    if isinstance(val, bytes):
        return val.decode("utf-8", errors="replace")
    return val


def _parse_fact_ids(data):
    id_producto = data.get(FACT_COL_PRODUCTO) or data.get("producto_id")
    id_tipo_mov = data.get(FACT_COL_TIPO) or data.get("tipo_mov_id")
    id_destino = data.get(FACT_COL_DESTINO) or data.get("destino_id")
    id_usuario = data.get(FACT_COL_USUARIO) or data.get("usuario_id")
    return id_producto, id_tipo_mov, id_destino, id_usuario


def _nombre_tipo_mov(cursor, id_tipo_mov):
    cursor.execute(
        f"SELECT nombre_movimiento FROM {DIM_TIPO_MOVIMIENTO} WHERE {PK_TIPO_MOVIMIENTO} = %s",
        (id_tipo_mov,),
    )
    row = cursor.fetchone()
    return (_safe_value(row[0]) or "").strip().upper() if row else ""


def _es_salida(nombre_movimiento_upper):
    if not nombre_movimiento_upper:
        return False
    return "SALIDA" in nombre_movimiento_upper


def _stock_desde_vista(conn, id_producto):
    cursor = conn.cursor(dictionary=True)
    try:
        for col_prod in ("id_producto", "producto_id"):
            cursor.execute(
                f"SELECT * FROM {STOCK_VIEW} WHERE {col_prod} = %s LIMIT 1",
                (id_producto,),
            )
            row = cursor.fetchone()
            if not row:
                continue
            for qty_key in ("stock_actual", "stock", "saldo", "cantidad_stock", "qty", "cantidad"):
                if qty_key in row and row[qty_key] is not None:
                    try:
                        return int(row[qty_key])
                    except (TypeError, ValueError):
                        pass
            for k, v in row.items():
                if k.lower() in (col_prod, "nombre_producto", "nombre", "producto"):
                    continue
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    try:
                        return int(v)
                    except (TypeError, ValueError):
                        pass
        return 0
    finally:
        cursor.close()


def _row_movimiento_dict(row):
    fecha = row[2]
    if hasattr(fecha, "strftime"):
        fecha = fecha.strftime("%Y-%m-%d")
    elif fecha is not None:
        fecha = str(fecha)
    nombre_prod = _safe_value(row[7]) or ""
    nombre_cat = (_safe_value(row[11]) or "") if len(row) > 11 else ""
    id_mov = int(row[0]) if row[0] is not None else None
    id_prod = int(row[3]) if row[3] is not None else None
    id_tipo = int(row[4]) if row[4] is not None else None
    id_dest = int(row[5]) if row[5] is not None else None
    id_usu = str(row[6]) if row[6] is not None else None
    return {
        "id": id_mov,
        "id_movimientos": id_mov,
        "id_movimiento": id_mov,
        "cantidad": int(row[1]) if row[1] is not None else 0,
        "fecha": fecha,
        "id_producto": id_prod,
        "producto_id": id_prod,
        "id_tipo_mov": id_tipo,
        "tipo_mov_id": id_tipo,
        "id_destino": id_dest,
        "destino_id": id_dest,
        "id_usuario": id_usu,
        "usuario_id": id_usu,
        "nombre_producto": nombre_prod,
        "producto": nombre_prod,
        "nombre_categoria": nombre_cat,
        "categoria": nombre_cat,
        "nombre_movimiento": _safe_value(row[8]) or "",
        "nombre_destino": _safe_value(row[9]) or "",
        "nombre_usuario": _safe_value(row[10]) or "",
    }


def _sql_listar():
    return f"""
        SELECT m.{PK}, m.cantidad, m.fecha, m.{FACT_COL_PRODUCTO}, m.{FACT_COL_TIPO},
               m.{FACT_COL_DESTINO}, m.{FACT_COL_USUARIO},
               p.nombre_producto, t.nombre_movimiento, d.nombre_destino, u.nombre,
               c.nombre_categoria
        FROM {TABLE} m
        LEFT JOIN {DIM_PRODUCTO} p ON p.{PK_PRODUCTO} = m.{FACT_COL_PRODUCTO}
        LEFT JOIN {DIM_CATEGORIA} c ON c.{PK_CATEGORIA} = p.{FK_PRODUCTO_CATEGORIA}
        LEFT JOIN {DIM_TIPO_MOVIMIENTO} t ON t.{PK_TIPO_MOVIMIENTO} = m.{FACT_COL_TIPO}
        LEFT JOIN {DIM_DESTINO} d ON d.{PK_DESTINO} = m.{FACT_COL_DESTINO}
        LEFT JOIN {DIM_USUARIO} u ON u.{PK_USUARIO} = m.{FACT_COL_USUARIO}
        ORDER BY m.fecha DESC, m.{PK} DESC
    """


def _sql_salidas():
    return f"""
        SELECT m.{PK}, m.cantidad, m.fecha, m.{FACT_COL_PRODUCTO}, m.{FACT_COL_TIPO},
               m.{FACT_COL_DESTINO}, m.{FACT_COL_USUARIO},
               p.nombre_producto, t.nombre_movimiento, d.nombre_destino, u.nombre,
               c.nombre_categoria
        FROM {TABLE} m
        LEFT JOIN {DIM_PRODUCTO} p ON p.{PK_PRODUCTO} = m.{FACT_COL_PRODUCTO}
        LEFT JOIN {DIM_CATEGORIA} c ON c.{PK_CATEGORIA} = p.{FK_PRODUCTO_CATEGORIA}
        LEFT JOIN {DIM_TIPO_MOVIMIENTO} t ON t.{PK_TIPO_MOVIMIENTO} = m.{FACT_COL_TIPO}
        LEFT JOIN {DIM_DESTINO} d ON d.{PK_DESTINO} = m.{FACT_COL_DESTINO}
        LEFT JOIN {DIM_USUARIO} u ON u.{PK_USUARIO} = m.{FACT_COL_USUARIO}
        WHERE UPPER(COALESCE(t.nombre_movimiento, '')) LIKE %s
        ORDER BY m.fecha DESC, m.{PK} DESC
    """


@router.get(
    "/salidas",
    summary="Listar salidas de inventario",
    description=(
        "Retorna únicamente los movimientos de tipo **SALIDA**, ordenados por fecha descendente. "
        "Incluye producto, categoría, destino y usuario responsable."
    ),
    response_model=MovimientoListResponse,
    responses={
        **RESP_401,
        **RESP_500,
    },
)
def listar_salidas(current_user: str = Depends(get_current_user)):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(_sql_salidas(), ("%SALIDA%",))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return {"data": [_row_movimiento_dict(r) for r in rows]}
    except Exception as e:
        logger.exception("fact_movimientos salidas")
        return server_error(e)


@router.get(
    "",
    summary="Listar todos los movimientos",
    description=(
        "Retorna el historial completo de entradas y salidas de inventario, "
        "ordenado por fecha descendente. Incluye datos enriquecidos de producto, "
        "categoría, tipo de movimiento, destino y usuario."
    ),
    response_model=MovimientoListResponse,
    responses={
        **RESP_401,
        **RESP_500,
    },
)
def listar(current_user: str = Depends(get_current_user)):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(_sql_listar())
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return {"data": [_row_movimiento_dict(r) for r in rows]}
    except Exception as e:
        logger.exception("fact_movimientos listar")
        return server_error(e)


@router.get(
    "/{id_movimiento}",
    summary="Obtener movimiento por ID",
    description="Retorna el detalle completo de un movimiento específico.",
    responses={
        **RESP_401,
        **RESP_404,
        **RESP_500,
    },
)
def obtener(id_movimiento: int, current_user: str = Depends(get_current_user)):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        q = f"""
            SELECT m.{PK}, m.cantidad, m.fecha, m.{FACT_COL_PRODUCTO}, m.{FACT_COL_TIPO},
                   m.{FACT_COL_DESTINO}, m.{FACT_COL_USUARIO},
                   p.nombre_producto, t.nombre_movimiento, d.nombre_destino, u.nombre,
                   c.nombre_categoria
            FROM {TABLE} m
            LEFT JOIN {DIM_PRODUCTO} p ON p.{PK_PRODUCTO} = m.{FACT_COL_PRODUCTO}
            LEFT JOIN {DIM_CATEGORIA} c ON c.{PK_CATEGORIA} = p.{FK_PRODUCTO_CATEGORIA}
            LEFT JOIN {DIM_TIPO_MOVIMIENTO} t ON t.{PK_TIPO_MOVIMIENTO} = m.{FACT_COL_TIPO}
            LEFT JOIN {DIM_DESTINO} d ON d.{PK_DESTINO} = m.{FACT_COL_DESTINO}
            LEFT JOIN {DIM_USUARIO} u ON u.{PK_USUARIO} = m.{FACT_COL_USUARIO}
            WHERE m.{PK} = %s
        """
        cursor.execute(q, (id_movimiento,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        if not row:
            return JSONResponse(status_code=404, content={"error": "Movimiento no encontrado"})
        return _row_movimiento_dict(row)
    except Exception as e:
        return server_error(e)


@router.post(
    "",
    status_code=201,
    summary="Registrar entrada o salida de stock",
    description=(
        "Crea un nuevo movimiento de inventario. "
        "Para movimientos de tipo **SALIDA**, la cantidad no puede superar el stock disponible "
        "(validado contra la vista `vw_stock_actual`). "
        "Si no se envía `fecha`, se usa la fecha y hora actuales."
    ),
    responses={
        **RESP_400,
        **RESP_401,
        404: {"description": "Producto o tipo de movimiento no encontrado"},
        **RESP_500,
    },
)
def crear(body: dict = Body(default={}), current_user: str = Depends(get_current_user)):
    try:
        cantidad = body.get("cantidad")
        id_producto, id_tipo_mov, id_destino, id_usuario = _parse_fact_ids(body)
        fecha = body.get("fecha")

        if cantidad is None or id_producto is None or id_tipo_mov is None:
            return JSONResponse(status_code=400, content={
                "error": "cantidad, id_producto (o producto_id) e id_tipo_mov (o tipo_mov_id) son requeridos",
            })
        cantidad = int(cantidad)
        id_producto = int(id_producto)
        id_tipo_mov = int(id_tipo_mov)
        if cantidad <= 0:
            return JSONResponse(status_code=400, content={"error": "cantidad debe ser mayor que 0"})

        if id_destino is not None:
            id_destino = int(id_destino)
        if id_usuario is None:
            id_usuario = current_user if current_user else None
        else:
            id_usuario = str(id_usuario)

        if not fecha:
            fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f"SELECT {PK_PRODUCTO} FROM {DIM_PRODUCTO} WHERE {PK_PRODUCTO} = %s", (id_producto,))
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return JSONResponse(status_code=404, content={"error": "Producto no encontrado"})
        cursor.execute(
            f"SELECT {PK_TIPO_MOVIMIENTO} FROM {DIM_TIPO_MOVIMIENTO} WHERE {PK_TIPO_MOVIMIENTO} = %s",
            (id_tipo_mov,),
        )
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return JSONResponse(status_code=404, content={"error": "Tipo de movimiento no encontrado"})

        nombre_tipo = _nombre_tipo_mov(cursor, id_tipo_mov)
        if _es_salida(nombre_tipo):
            stock = _stock_desde_vista(conn, id_producto)
            if cantidad > stock:
                cursor.close()
                conn.close()
                return JSONResponse(status_code=400, content={
                    "error": "La cantidad excede el stock disponible",
                    "stock_disponible": stock,
                    "cantidad_solicitada": cantidad,
                })

        cursor.execute(
            f"""
            INSERT INTO {TABLE}
            (cantidad, fecha, {FACT_COL_PRODUCTO}, {FACT_COL_TIPO}, {FACT_COL_DESTINO}, {FACT_COL_USUARIO})
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (cantidad, fecha, id_producto, id_tipo_mov, id_destino, id_usuario),
        )
        conn.commit()
        new_id = cursor.lastrowid
        cursor.close()
        conn.close()
        return {
            "message": "Movimiento registrado",
            "id": new_id,
            "id_movimientos": new_id,
            "id_movimiento": new_id,
        }
    except Exception as e:
        logger.exception("fact_movimientos crear")
        return server_error(e)


@router.put(
    "/{id_movimiento}",
    summary="Corregir un movimiento existente",
    description=(
        "Actualiza los datos de un movimiento ya registrado. "
        "Solo enviar los campos a modificar. "
        "Si el nuevo tipo es SALIDA, se revalida el stock disponible."
    ),
    responses={
        **RESP_400,
        **RESP_401,
        **RESP_404,
        **RESP_500,
    },
)
def actualizar(id_movimiento: int, body: dict = Body(default={}), current_user: str = Depends(get_current_user)):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT cantidad, {FACT_COL_PRODUCTO}, {FACT_COL_TIPO} FROM {TABLE} WHERE {PK} = %s",
            (id_movimiento,),
        )
        old = cursor.fetchone()
        if not old:
            cursor.close()
            conn.close()
            return JSONResponse(status_code=404, content={"error": "Movimiento no encontrado"})

        old_cant = int(old[0])
        old_prod = int(old[1])
        old_tipo = int(old[2])

        cantidad = body.get("cantidad")
        id_producto, id_tipo_mov, id_destino, id_usuario = _parse_fact_ids(body)
        fecha = body.get("fecha")

        new_cant = int(cantidad) if cantidad is not None else old_cant
        new_prod = int(id_producto) if id_producto is not None else old_prod
        new_tipo = int(id_tipo_mov) if id_tipo_mov is not None else old_tipo
        if new_cant <= 0:
            cursor.close()
            conn.close()
            return JSONResponse(status_code=400, content={"error": "cantidad debe ser mayor que 0"})

        nombre_tipo_nuevo = _nombre_tipo_mov(cursor, new_tipo)
        if _es_salida(nombre_tipo_nuevo):
            stock = _stock_desde_vista(conn, new_prod)
            stock_efectivo = stock
            if new_prod == old_prod and _es_salida(_nombre_tipo_mov(cursor, old_tipo)):
                stock_efectivo = stock + old_cant
            if new_cant > stock_efectivo:
                cursor.close()
                conn.close()
                return JSONResponse(status_code=400, content={
                    "error": "La cantidad excede el stock disponible",
                    "stock_disponible": stock_efectivo,
                    "cantidad_solicitada": new_cant,
                })

        updates, params = [], []
        if cantidad is not None:
            updates.append("cantidad = %s")
            params.append(new_cant)
        if id_producto is not None:
            updates.append(f"{FACT_COL_PRODUCTO} = %s")
            params.append(new_prod)
        if id_tipo_mov is not None:
            updates.append(f"{FACT_COL_TIPO} = %s")
            params.append(new_tipo)
        if fecha is not None:
            updates.append("fecha = %s")
            params.append(fecha)
        if FACT_COL_DESTINO in body or "destino_id" in body:
            v = body.get(FACT_COL_DESTINO) if FACT_COL_DESTINO in body else body.get("destino_id")
            updates.append(f"{FACT_COL_DESTINO} = %s")
            params.append(int(v) if v is not None else None)
        if FACT_COL_USUARIO in body or "usuario_id" in body:
            v = body.get(FACT_COL_USUARIO) if FACT_COL_USUARIO in body else body.get("usuario_id")
            updates.append(f"{FACT_COL_USUARIO} = %s")
            params.append(int(v) if v is not None else None)

        if not updates:
            cursor.close()
            conn.close()
            return JSONResponse(status_code=400, content={"error": "Nada que actualizar"})

        params.append(id_movimiento)
        sql = f"UPDATE {TABLE} SET {', '.join(updates)} WHERE {PK} = %s"
        cursor.execute(sql, params)
        conn.commit()
        cursor.close()
        conn.close()
        return {"message": "Movimiento actualizado"}
    except Exception as e:
        return server_error(e)


@router.delete(
    "/{id_movimiento}",
    summary="Eliminar un movimiento del historial",
    description=(
        "Elimina permanentemente un movimiento del historial de inventario. "
        "Esta acción no se puede deshacer y afecta el cálculo del stock actual."
    ),
    responses={
        **RESP_401,
        **RESP_404,
        **RESP_500,
    },
)
def eliminar(id_movimiento: int, current_user: str = Depends(get_current_user)):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f"DELETE FROM {TABLE} WHERE {PK} = %s", (id_movimiento,))
        conn.commit()
        n = cursor.rowcount
        cursor.close()
        conn.close()
        if n == 0:
            return JSONResponse(status_code=404, content={"error": "Movimiento no encontrado"})
        return {"message": "Movimiento eliminado"}
    except Exception as e:
        return server_error(e)

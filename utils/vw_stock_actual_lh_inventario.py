"""
Vista SQL: vw_stock_actual (solo lectura).
Devuelve id_producto, stock_actual, nombre_producto y nombre_categoria.
"""

import logging
from datetime import datetime

from fastapi import APIRouter, Body, Depends
from fastapi.responses import JSONResponse

from schemas.base import RESP_400, RESP_401, RESP_500
from schemas.inventario import StockListResponse
from utils.auth import get_current_user
from utils.db import get_db_connection
from utils.errors import server_error
from utils.lh_inventario_tables import (
    DIM_CATEGORIA,
    DIM_DESTINO,
    DIM_PRODUCTO,
    DIM_TIPO_MOVIMIENTO,
    FACT_MOVIMIENTOS,
    FACT_COL_DESTINO,
    FACT_COL_PRODUCTO,
    FACT_COL_TIPO,
    FACT_COL_USUARIO,
    FK_PRODUCTO_CATEGORIA,
    PK_CATEGORIA,
    PK_DESTINO,
    PK_PRODUCTO,
    PK_TIPO_MOVIMIENTO,
    STOCK_VIEW_DEFAULT,
)

logger = logging.getLogger(__name__)
router = APIRouter()

VIEW = STOCK_VIEW_DEFAULT


def _safe(val):
    if val is None:
        return None
    if isinstance(val, bytes):
        return val.decode("utf-8", errors="replace")
    return val


@router.get(
    "",
    summary="Consultar stock actual por producto",
    description=(
        "Retorna el stock disponible de cada producto calculado en tiempo real "
        "a partir del historial de movimientos (entradas menos salidas). "
        "Fuente: vista `vw_stock_actual`. Solo lectura, no requiere parámetros."
    ),
    response_model=StockListResponse,
    responses={
        **RESP_401,
        **RESP_500,
    },
)
def listar(current_user: str = Depends(get_current_user)):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        sql = f"""
            SELECT COALESCE(v.id_producto, v.producto_id) AS id_producto,
                   COALESCE(v.stock_actual, v.stock, v.saldo, 0) AS stock_actual,
                   COALESCE(p.nombre_producto, '') AS nombre_producto,
                   COALESCE(c.nombre_categoria, '') AS nombre_categoria
            FROM {VIEW} v
            LEFT JOIN {DIM_PRODUCTO} p ON p.{PK_PRODUCTO} = COALESCE(v.id_producto, v.producto_id)
            LEFT JOIN {DIM_CATEGORIA} c ON c.{PK_CATEGORIA} = p.{FK_PRODUCTO_CATEGORIA}
        """
        try:
            cursor.execute(sql)
        except Exception:
            cursor.execute(f"SELECT * FROM {VIEW}")
            rows = cursor.fetchall()
            out = []
            for row in rows:
                m = {k: (v.strftime("%Y-%m-%d") if hasattr(v, "strftime") else v) for k, v in row.items()}
                if not any(k.lower() == "nombre_categoria" for k in m):
                    m["nombre_categoria"] = ""
                if not any(k.lower() == "nombre_producto" for k in m):
                    m["nombre_producto"] = m.get("producto") or m.get("nombre") or ""
                out.append(m)
            cursor.close()
            conn.close()
            return {"data": out}
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        out = []
        for row in rows:
            m = {
                k: (_safe(v).strip() if isinstance(v, str) else (v.strftime("%Y-%m-%d") if hasattr(v, "strftime") else v))
                for k, v in row.items()
            }
            out.append(m)
        return {"data": out}
    except Exception as e:
        logger.exception("vw_stock_actual")
        return server_error(e)


@router.post(
    "/{id_producto}/ajuste",
    summary="Ajustar stock manualmente",
    description=(
        "Establece el stock de un producto a un valor específico creando el movimiento "
        "compensatorio correspondiente (ENTRADA si hay déficit, SALIDA si hay excedente)."
    ),
    responses={
        **RESP_400,
        **RESP_401,
        **RESP_500,
    },
)
def ajustar_stock(
    id_producto: int,
    body: dict = Body(default={}),
    current_user: str = Depends(get_current_user),
):
    nuevo_stock_raw = body.get("nuevo_stock")
    if nuevo_stock_raw is None:
        return JSONResponse(status_code=400, content={"error": "nuevo_stock es requerido"})
    try:
        nuevo_stock = int(nuevo_stock_raw)
        if nuevo_stock < 0:
            raise ValueError
    except (TypeError, ValueError):
        return JSONResponse(status_code=400, content={"error": "nuevo_stock debe ser un entero >= 0"})

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        stock_actual = 0
        for col_prod in ("id_producto", "producto_id"):
            try:
                cursor.execute(f"SELECT * FROM {VIEW} WHERE {col_prod} = %s LIMIT 1", (id_producto,))
                row = cursor.fetchone()
                if row:
                    for qty_key in ("stock_actual", "stock", "saldo"):
                        if qty_key in row and row[qty_key] is not None:
                            try:
                                stock_actual = int(row[qty_key])
                            except (TypeError, ValueError):
                                pass
                            break
                    break
            except Exception:
                pass

        delta = nuevo_stock - stock_actual
        if delta == 0:
            cursor.close()
            conn.close()
            return {"message": "Sin cambios", "stock_actual": stock_actual}

        tipo_nombre = "ENTRADA" if delta > 0 else "SALIDA"
        cursor.execute(
            f"SELECT {PK_TIPO_MOVIMIENTO} FROM {DIM_TIPO_MOVIMIENTO} WHERE UPPER(nombre_movimiento) LIKE %s LIMIT 1",
            (f"%{tipo_nombre}%",),
        )
        tipo_row = cursor.fetchone()
        if not tipo_row:
            cursor.close()
            conn.close()
            return JSONResponse(
                status_code=422,
                content={"error": f"No se encontró tipo de movimiento '{tipo_nombre}'"},
            )
        id_tipo_mov = tipo_row[PK_TIPO_MOVIMIENTO]

        cursor.execute(f"SELECT {PK_DESTINO} FROM {DIM_DESTINO} LIMIT 1")
        dest_row = cursor.fetchone()
        id_destino = dest_row[PK_DESTINO] if dest_row else None

        fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            f"""INSERT INTO {FACT_MOVIMIENTOS}
                (cantidad, fecha, {FACT_COL_PRODUCTO}, {FACT_COL_TIPO}, {FACT_COL_DESTINO}, {FACT_COL_USUARIO})
                VALUES (%s, %s, %s, %s, %s, %s)""",
            (abs(delta), fecha, id_producto, id_tipo_mov, id_destino, current_user),
        )
        conn.commit()
        cursor.close()
        conn.close()
        return {
            "message": "Stock ajustado",
            "stock_anterior": stock_actual,
            "stock_nuevo": nuevo_stock,
            "delta": delta,
        }
    except Exception as e:
        logger.exception("ajustar_stock")
        return server_error(e)

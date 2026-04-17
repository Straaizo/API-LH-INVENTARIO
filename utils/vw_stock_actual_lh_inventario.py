"""
Vista SQL: vw_stock_actual (solo lectura).
Devuelve id_producto, stock_actual, nombre_producto y nombre_categoria.
"""

import logging

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from schemas.base import RESP_401, RESP_500
from schemas.inventario import StockListResponse
from utils.auth import get_current_user
from utils.db import get_db_connection
from utils.errors import server_error
from utils.lh_inventario_tables import (
    DIM_CATEGORIA,
    DIM_PRODUCTO,
    FK_PRODUCTO_CATEGORIA,
    PK_CATEGORIA,
    PK_PRODUCTO,
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

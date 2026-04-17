from typing import Optional

from pydantic import BaseModel, Field


# ── Movimientos ───────────────────────────────────────────────────────────────

class MovimientoOut(BaseModel):
    id: Optional[int] = Field(None, example=42)
    id_movimientos: Optional[int] = Field(None, example=42)
    cantidad: int = Field(..., example=5)
    fecha: Optional[str] = Field(None, example="2026-04-10")
    id_producto: Optional[int] = Field(None, example=15)
    id_tipo_mov: Optional[int] = Field(None, example=1)
    id_destino: Optional[int] = Field(None, example=3)
    id_usuario: Optional[str] = Field(None, example="18d31a76-ac32-423c-853e-8d8224a7a456")
    nombre_producto: str = Field("", example="Tóner HP 85A")
    nombre_categoria: str = Field("", example="Tóner")
    nombre_movimiento: str = Field("", example="ENTRADA")
    nombre_destino: str = Field("", example="Administración")
    nombre_usuario: str = Field("", example="jperez")


class MovimientoCreate(BaseModel):
    cantidad: int = Field(
        ...,
        example=5,
        gt=0,
        description="Unidades a mover. Debe ser mayor a 0. Para SALIDA no puede superar el stock disponible.",
    )
    id_producto: int = Field(
        ..., example=15, description="ID del producto del catálogo de insumos"
    )
    id_tipo_mov: int = Field(
        ..., example=1, description="ID del tipo de movimiento (1=ENTRADA, 2=SALIDA)"
    )
    id_destino: Optional[int] = Field(
        None,
        example=3,
        description="ID del destino. Requerido para movimientos de tipo SALIDA.",
    )
    fecha: Optional[str] = Field(
        None,
        example="2026-04-10",
        description="Fecha del movimiento (YYYY-MM-DD). Si se omite, se usa la fecha actual.",
    )


class MovimientoListResponse(BaseModel):
    data: list[MovimientoOut]


# ── Tipos de Movimiento ───────────────────────────────────────────────────────

class TipoMovimientoOut(BaseModel):
    id: int = Field(..., example=1)
    id_tipo_movimiento: int = Field(..., example=1)
    id_tipo_mov: int = Field(..., example=1)
    nombre_movimiento: str = Field(..., example="ENTRADA")


class TipoMovimientoCreate(BaseModel):
    nombre_movimiento: str = Field(
        ..., example="ENTRADA", description="Nombre del tipo. Valores estándar: ENTRADA, SALIDA"
    )


class TipoMovimientoListResponse(BaseModel):
    data: list[TipoMovimientoOut]


# ── Destinos ──────────────────────────────────────────────────────────────────

class DestinoOut(BaseModel):
    id: int = Field(..., example=3)
    id_destino: int = Field(..., example=3)
    destino_id: int = Field(..., example=3)
    nombre_destino: str = Field(..., example="Administración")


class DestinoCreate(BaseModel):
    nombre_destino: str = Field(
        ...,
        example="Administración",
        description="Nombre del destino. Ej: Administración, Recepción, Cocina, Bodega Central",
    )


class DestinoListResponse(BaseModel):
    data: list[DestinoOut]

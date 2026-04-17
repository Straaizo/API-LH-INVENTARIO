from typing import Optional

from pydantic import BaseModel, Field


# ── Categorías ────────────────────────────────────────────────────────────────

class CategoriaOut(BaseModel):
    id: int = Field(..., example=2)
    id_categoria: int = Field(..., example=2)
    nombre_categoria: str = Field(..., example="Tóner")


class CategoriaCreate(BaseModel):
    nombre_categoria: str = Field(
        ...,
        example="Tóner",
        description="Nombre de la categoría. Ej: Tóner, Tambor, Drum, Kit de mantenimiento",
    )


class CategoriaListResponse(BaseModel):
    data: list[CategoriaOut]


# ── Productos ─────────────────────────────────────────────────────────────────

class ProductoOut(BaseModel):
    id: int = Field(..., example=15)
    id_producto: int = Field(..., example=15)
    nombre_producto: str = Field(..., example="Tóner HP 85A")
    id_categoria: Optional[int] = Field(None, example=2)
    categoria_id: Optional[int] = Field(None, example=2)
    nombre_categoria: str = Field("", example="Tóner")


class ProductoCreate(BaseModel):
    nombre_producto: str = Field(
        ...,
        example="Tóner HP 85A",
        description="Nombre completo del producto. Ej: Tóner HP 85A, Tambor Brother DR-3400",
    )
    id_categoria: int = Field(
        ...,
        example=2,
        description="ID de la categoría a la que pertenece el producto",
    )


class ProductoListResponse(BaseModel):
    data: list[ProductoOut]


# ── Stock ─────────────────────────────────────────────────────────────────────

class StockOut(BaseModel):
    id_producto: Optional[int] = Field(None, example=15)
    stock_actual: int = Field(..., example=24)
    nombre_producto: str = Field("", example="Tóner HP 85A")
    nombre_categoria: str = Field("", example="Tóner")


class StockListResponse(BaseModel):
    data: list[StockOut]

from typing import Optional

from pydantic import BaseModel, Field


# ── Equipos ───────────────────────────────────────────────────────────────────

class EquipoOut(BaseModel):
    id: Optional[int] = Field(None, example=1)
    id_equipos: Optional[int] = Field(None, example=1)
    codigo_equipo: Optional[str] = Field(None, example="NB-001")
    codigo: Optional[str] = Field(None, example="NB-001")
    estado: Optional[str] = Field(None, example="Activo")
    tipo: Optional[str] = Field(None, example="Notebook")
    marca: Optional[str] = Field(None, example="HP")
    modelo: Optional[str] = Field(None, example="ProBook 440 G8")
    procesador: Optional[str] = Field(None, example="Intel Core i5-1135G7")
    ram: Optional[str] = Field(None, example="8GB")
    disco_duro: Optional[str] = Field(None, example="256GB SSD")
    sistema_operativo: Optional[str] = Field(None, example="Windows 11 Pro")
    office: Optional[str] = Field(None, example="Office 365")
    numero_serie: Optional[str] = Field(None, example="5CG1234567")
    ubicacion: Optional[str] = Field(None, example="Administración")
    antivirus: Optional[str] = Field(None, example="Windows Defender")
    fecha_revision: Optional[str] = Field(None, example="2026-01-15")
    fk_id_usuario: Optional[str] = Field(None, example="18d31a76-ac32-423c-853e-8d8224a7a456")
    responsable: Optional[str] = Field(None, example="Ana López")
    usuario_nombre: Optional[str] = Field(None, example="Ana López")
    usuario_correo: Optional[str] = Field(None, example="alopez@lahornilla.cl")


class EquipoCreate(BaseModel):
    codigo_equipo: str = Field(..., example="NB-001", description="Código único del equipo")
    estado: Optional[str] = Field(None, example="Activo")
    tipo: Optional[str] = Field(
        None,
        example="Notebook",
        description="Tipo de equipo: Notebook, Desktop, Servidor, Mini PC",
    )
    marca: Optional[str] = Field(None, example="HP")
    modelo: Optional[str] = Field(None, example="ProBook 440 G8")
    procesador: Optional[str] = Field(None, example="Intel Core i5-1135G7")
    ram: Optional[str] = Field(None, example="8GB")
    disco_duro: Optional[str] = Field(None, example="256GB SSD")
    sistema_operativo: Optional[str] = Field(None, example="Windows 11 Pro")
    office: Optional[str] = Field(None, example="Office 365")
    numero_serie: Optional[str] = Field(None, example="5CG1234567")
    ubicacion: Optional[str] = Field(None, example="Administración")
    antivirus: Optional[str] = Field(None, example="Windows Defender")
    fecha_revision: Optional[str] = Field(None, example="2026-01-15")
    responsable: Optional[str] = Field(None, example="Ana López")


class EquipoListResponse(BaseModel):
    data: list[EquipoOut]


# ── Celulares ─────────────────────────────────────────────────────────────────

class CelularOut(BaseModel):
    id: Optional[int] = Field(None, example=1)
    id_celular: Optional[int] = Field(None, example=1)
    numero: Optional[str] = Field(None, example="+56912345678")
    estado: Optional[str] = Field(None, example="Activo")
    tipo_celular: Optional[str] = Field(None, example="Voz y Datos")
    compania: Optional[str] = Field(None, example="Entel")
    marca: Optional[str] = Field(None, example="Samsung")
    modelo: Optional[str] = Field(None, example="Galaxy A34")
    imei: Optional[str] = Field(None, example="356789012345678")
    fecha_entrega: Optional[str] = Field(None, example="2025-03-01")
    responsable: Optional[str] = Field(None, example="Carlos Muñoz")


class CelularCreate(BaseModel):
    numero: str = Field(..., example="+56912345678", description="Número de línea móvil")
    estado: Optional[str] = Field(None, example="Activo")
    tipo_celular: Optional[str] = Field(
        None,
        example="Voz y Datos",
        description="Tipo de línea: Voz y Datos, M2M, BAM",
    )
    compania: Optional[str] = Field(None, example="Entel")
    marca: Optional[str] = Field(None, example="Samsung")
    modelo: Optional[str] = Field(None, example="Galaxy A34")
    imei: Optional[str] = Field(None, example="356789012345678")
    fecha_entrega: Optional[str] = Field(None, example="2025-03-01")
    responsable: Optional[str] = Field(None, example="Carlos Muñoz")


class CelularListResponse(BaseModel):
    data: list[CelularOut]


# ── Tablets ───────────────────────────────────────────────────────────────────

class TabletOut(BaseModel):
    id: Optional[int] = Field(None, example=1)
    id_tablet: Optional[int] = Field(None, example=1)
    codigo_tablet: Optional[str] = Field(None, example="TAB-001")
    codigo: Optional[str] = Field(None, example="TAB-001")
    estado: Optional[str] = Field(None, example="Activo")
    marca: Optional[str] = Field(None, example="Samsung")
    modelo: Optional[str] = Field(None, example="Galaxy Tab A8")
    capacidad: Optional[str] = Field(None, example="64GB")
    fecha_entrega: Optional[str] = Field(None, example="2025-06-15")
    responsable: Optional[str] = Field(None, example="María Pérez")


class TabletCreate(BaseModel):
    codigo_tablet: str = Field(..., example="TAB-001", description="Código único de la tablet")
    estado: Optional[str] = Field(None, example="Activo")
    marca: Optional[str] = Field(None, example="Samsung")
    modelo: Optional[str] = Field(None, example="Galaxy Tab A8")
    capacidad: Optional[str] = Field(None, example="64GB")
    fecha_entrega: Optional[str] = Field(None, example="2025-06-15")
    responsable: Optional[str] = Field(None, example="María Pérez")


class TabletListResponse(BaseModel):
    data: list[TabletOut]


# ── Impresoras ────────────────────────────────────────────────────────────────

class ImpresoraOut(BaseModel):
    id: Optional[int] = Field(None, example=1)
    id_impresora: Optional[int] = Field(None, example=1)
    estado: Optional[str] = Field(None, example="Activo")
    ubicacion: Optional[str] = Field(None, example="Cocina")
    impresora: Optional[str] = Field(None, example="HP LaserJet Pro M404n")
    conexion: Optional[str] = Field(None, example="Red")
    fecha: Optional[str] = Field(None, example="2024-11-20")
    responsable: Optional[str] = Field(None, example="Pedro Soto")


class ImpresoraCreate(BaseModel):
    impresora: str = Field(..., example="HP LaserJet Pro M404n", description="Nombre/modelo de la impresora")
    estado: Optional[str] = Field(None, example="Activo")
    ubicacion: Optional[str] = Field(
        None,
        example="Cocina",
        description="Ubicación de la impresora en el local. Ej: Cocina, Administración, Caja",
    )
    conexion: Optional[str] = Field(None, example="Red", description="Tipo de conexión: Red, USB")
    fecha: Optional[str] = Field(None, example="2024-11-20")
    responsable: Optional[str] = Field(None, example="Pedro Soto")


class ImpresoraListResponse(BaseModel):
    data: list[ImpresoraOut]

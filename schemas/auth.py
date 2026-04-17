from typing import Optional
from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    usuario: Optional[str] = Field(None, example="esabattini", description="Nombre de usuario o correo")
    correo: Optional[str] = Field(None, example="soporte@lahornilla.cl", description="Correo (alternativo a usuario)")
    clave: Optional[str] = Field(None, example="miClave123", description="Contraseña")
    password: Optional[str] = Field(None, example="miClave123", description="Alias de clave")


class UsuarioOut(BaseModel):
    id: str = Field(..., example="18d31a76-ac32-423c-853e-8d8224a7a456")
    usuario: str = Field(..., example="esabattini")
    correo: str = Field(..., example="soporte@lahornilla.cl")
    nombre: str = Field("", example="Enzo Sabattini")


class LoginResponse(BaseModel):
    success: bool = Field(True, example=True)
    access_token: str = Field(
        ..., example="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIn0.xxxxx"
    )
    token_type: str = Field("bearer", example="bearer")
    usuario: UsuarioOut
    message: str = Field("Login correcto", example="Login correcto")


class RegisterRequest(BaseModel):
    usuario: str = Field(..., example="jperez", description="Nombre de usuario único")
    correo: str = Field(..., example="jperez@lahornilla.cl")
    nombre: Optional[str] = Field("", example="Juan Pérez")
    clave: str = Field(..., example="miClave123", description="Contraseña (mínimo 6 caracteres)")


class UsuarioListResponse(BaseModel):
    data: list[UsuarioOut]

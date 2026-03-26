# Routers

Esta carpeta contiene los módulos de rutas de la API. Cada archivo es un **router** de FastAPI, equivalente a un *Blueprint* en Flask — agrupa endpoints relacionados bajo un mismo prefijo.

---

## Cómo crear un nuevo router

### 1. Crear el archivo

```python
# routers/mi_modulo.py
from fastapi import APIRouter, Depends, HTTPException
from utils.db import get_db_connection
from utils.auth import get_current_user

router = APIRouter()


@router.get("/", summary="Listar elementos")
def listar(current_user: str = Depends(get_current_user)):
    conn   = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM mi_tabla")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return {"status": "success", "data": rows}
```

### 2. Registrarlo en `main.py`

```python
from routers import mi_modulo
app.include_router(mi_modulo.router, prefix="/api/mi_modulo", tags=["Mi Modulo"])
```

---

## Utilidades disponibles

| Import | Uso |
|--------|-----|
| `from utils.db import get_db_connection` | Obtener conexión MySQL (soporta datacenter y Cloud SQL) |
| `from utils.auth import get_current_user` | Dependencia JWT — protege un endpoint con `Depends(get_current_user)` |
| `from utils.auth import get_refresh_user` | Igual pero valida que el token sea de tipo *refresh* |
| `from utils.auth import create_access_token` | Crear token de acceso (10 h) |
| `from utils.auth import create_refresh_token` | Crear refresh token (7 d) |
| `from utils.validar_rut import validar_rut` | Validar RUT chileno |

---

## Módulos planificados

| Archivo | Prefijo | Descripción |
|---------|---------|-------------|
| `auth.py` | `/api/auth` | Login, register, refresh token, cambiar clave |
| `usuarios.py` | `/api/usuarios` | Gestión de usuarios del sistema |
| `trabajadores.py` | `/api/trabajadores` | Personal directo |
| `colaboradores.py` | `/api/colaboradores` | Personal externo / subcontrato |
| `contratistas.py` | `/api/contratistas` | Empresas contratistas |
| `opciones.py` | `/api/opciones` | Listas de valores para selectores del frontend |

---

## Ejemplo completo con validación de RUT

```python
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from utils.db import get_db_connection
from utils.auth import get_current_user
from utils.validar_rut import validar_rut

router = APIRouter()

class TrabajadorCreate(BaseModel):
    rut: str
    nombre: str

@router.post("/", status_code=201)
def crear(body: TrabajadorCreate, current_user: str = Depends(get_current_user)):
    if not validar_rut(body.rut):
        raise HTTPException(status_code=400, detail="RUT inválido")
    conn   = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO mi_tabla (rut, nombre) VALUES (%s, %s)",
        (body.rut.upper(), body.nombre)
    )
    conn.commit()
    cursor.close()
    conn.close()
    return {"message": "Creado", "rut": body.rut.upper()}
```

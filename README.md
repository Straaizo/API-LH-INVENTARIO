# API La Hornilla

API REST construida con **FastAPI** como base para las aplicaciones de gestión de La Hornilla. Diseñada con arquitectura modular, autenticación JWT, y soporte para despliegue local, en datacenter y en **Google Cloud Run**.

---

## Tabla de Contenidos

- [Requisitos](#requisitos)
- [Instalación local](#instalación-local)
- [Variables de entorno](#variables-de-entorno)
- [Ejecutar el servidor](#ejecutar-el-servidor)
- [Estructura del proyecto](#estructura-del-proyecto)
- [Endpoints disponibles](#endpoints-disponibles)
- [Autenticación JWT](#autenticación-jwt)
- [Agregar nuevos módulos (routers)](#agregar-nuevos-módulos-routers)
- [Despliegue con Docker](#despliegue-con-docker)
- [Despliegue en Google Cloud Run](#despliegue-en-google-cloud-run)

---

## Requisitos

- Python **3.10+**
- MySQL **8.0+** (servidor local, datacenter o Cloud SQL)
- Docker (opcional, para despliegue)
- Google Cloud CLI (opcional, para Cloud Run)

---

## Instalación local

```bash
# 1. Clonar el repositorio
git clone <url-del-repositorio>
cd API_BASE-main

# 2. Crear entorno virtual
python -m venv venv
source venv/bin/activate       # Linux / macOS
venv\Scripts\activate          # Windows

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar variables de entorno
cp .env.example .env
# Editar .env con tus credenciales (ver sección Variables de entorno)
```

---

## Variables de entorno

Copia `.env.example` como `.env` y completa los valores:

```env
# Modo debug (True en desarrollo, False en producción)
DEBUG=True

# Puerto del servidor de desarrollo
DEV_PORT=8000

# --- Conexión a base de datos (modo local / datacenter) ---
DB_HOST=localhost
DB_PORT=3306
DB_USER=tu_usuario
DB_PASSWORD=tu_contraseña
DB_NAME=nombre_base_de_datos

# --- Conexión Cloud SQL (solo para Google Cloud Run) ---
# Descomentar y completar al desplegar en GCP
# DATABASE_URL=mysql+pymysql://usuario:contraseña@/nombre_db?unix_socket=/cloudsql/proyecto:region:instancia

# --- Seguridad JWT ---
# IMPORTANTE: Cambiar por una clave secreta larga y aleatoria en produccion
JWT_SECRET_KEY=cambia_esto_en_produccion
```

> **IMPORTANTE:** El archivo `.env` contiene credenciales sensibles. Nunca lo subas al repositorio. Ya está incluido en `.gitignore`.

---

## Ejecutar el servidor

### Modo desarrollo (recomendado)

```bash
python run_dev.py
```

Abre automáticamente Swagger UI en el navegador y activa el hot-reload.

### Modo manual

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Documentación interactiva

| Interfaz | URL |
|----------|-----|
| Swagger UI | http://localhost:8000/docs |
| ReDoc | http://localhost:8000/redoc |
| OpenAPI JSON | http://localhost:8000/openapi.json |

---

## Estructura del proyecto

```
API_BASE-main/
├── .env.example          # Plantilla de variables de entorno (sin valores reales)
├── .gitignore            # Archivos excluidos del repositorio
├── Dockerfile            # Imagen Docker para producción
├── README.md             # Este archivo
├── config.py             # Carga y expone la configuración desde .env
├── main.py               # Punto de entrada de la aplicación FastAPI
├── requirements.txt      # Dependencias Python
├── run_dev.py            # Script de desarrollo con hot-reload y auto-browser
├── routers/
│   ├── __init__.py
│   └── README.md         # Guía para crear nuevos módulos de endpoints
└── utils/
    ├── __init__.py
    ├── auth.py           # Utilidades JWT (crear y validar tokens)
    └── db.py             # Conexión a MySQL (local/datacenter y Cloud SQL)
```

---

## Endpoints disponibles

### Utilidades base

| Método | Endpoint | Descripción | Auth |
|--------|----------|-------------|------|
| GET | `/api/test-db` | Verifica la conexión a la base de datos | No |
| GET | `/api/config` | Muestra la configuración activa (sin contraseñas) | No |

### Módulos planificados

| Prefijo | Descripción |
|---------|-------------|
| `/api/auth` | Login, registro, refresh token, cambio de contraseña |
| `/api/usuarios` | Gestión de usuarios del sistema |
| `/api/trabajadores` | Personal directo |
| `/api/colaboradores` | Personal externo / subcontrato |
| `/api/contratistas` | Empresas contratistas |
| `/api/opciones` | Valores para listas desplegables |

---

## Autenticación JWT

La API usa **JSON Web Tokens (JWT)** con esquema `Bearer`.

### Flujo

1. El cliente hace `POST /api/auth/login` con credenciales.
2. La API devuelve un `access_token` (válido 10 horas) y un `refresh_token` (válido 7 días).
3. El cliente incluye el token en cada request protegido:

```http
Authorization: Bearer <access_token>
```

### Proteger un endpoint

```python
from utils.auth import get_current_user
from fastapi import Depends

@router.get("/datos-privados")
def datos_privados(user_id: int = Depends(get_current_user)):
    return {"usuario": user_id}
```

---

## Agregar nuevos módulos (routers)

Ver [`routers/README.md`](routers/README.md) para la guía completa con ejemplos.

Resumen rápido:

```python
# routers/mi_modulo.py
from fastapi import APIRouter
router = APIRouter()

@router.get("/")
def listar():
    return {"data": []}
```

```python
# main.py — registrar el router
from routers import mi_modulo
app.include_router(mi_modulo.router, prefix="/api/mi-modulo", tags=["Mi Módulo"])
```

---

## Despliegue con Docker

```bash
# Construir imagen
docker build -t api-lahornilla .

# Ejecutar contenedor
docker run -p 8080:8080 --env-file .env api-lahornilla
```

La aplicación queda disponible en `http://localhost:8080`.

---

## Despliegue en Google Cloud Run

```bash
# 1. Autenticarse en GCP
gcloud auth login
gcloud config set project TU_PROYECTO_ID

# 2. Construir y subir imagen a Artifact Registry
gcloud builds submit --tag gcr.io/TU_PROYECTO_ID/api-lahornilla

# 3. Desplegar en Cloud Run
gcloud run deploy api-lahornilla \
  --image gcr.io/TU_PROYECTO_ID/api-lahornilla \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars "DATABASE_URL=mysql+pymysql://usuario:contraseña@/nombre_db?unix_socket=/cloudsql/proyecto:region:instancia" \
  --set-env-vars "JWT_SECRET_KEY=tu_clave_secreta_segura" \
  --add-cloudsql-instances TU_PROYECTO_ID:REGION:INSTANCIA
```

> Para Cloud Run, usa `DATABASE_URL` en lugar de las variables `DB_*` individuales.

---

## Dependencias principales

| Librería | Versión | Uso |
|----------|---------|-----|
| fastapi | 0.115.0 | Framework web |
| uvicorn | 0.30.6 | Servidor ASGI |
| python-jose | 3.3.0 | JWT (crear y validar tokens) |
| bcrypt | 4.3.0 | Hash de contraseñas |
| mysql-connector-python | 9.2.0 | Driver MySQL |
| python-dotenv | 1.0.1 | Carga de variables de entorno |

---

## Seguridad en producción

Antes de desplegar a producción, asegurarse de:

- [ ] Cambiar `JWT_SECRET_KEY` por una clave aleatoria larga (mínimo 32 caracteres)
- [ ] Establecer `DEBUG=False`
- [ ] Configurar CORS solo con los orígenes permitidos en `main.py`
- [ ] Usar HTTPS (Cloud Run lo maneja automáticamente)
- [ ] Gestionar las variables de entorno mediante Secret Manager (GCP) o equivalente
- [ ] Nunca incluir el archivo `.env` en el repositorio

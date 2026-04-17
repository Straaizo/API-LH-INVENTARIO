# API La Hornilla — LH Inventario

API REST con **FastAPI** para el inventario unificado de La Hornilla (tablas y rutas `*_LH_INVENTARIO` / `*_lh_inventario`). Diseñada con arquitectura modular, autenticación JWT, y soporte para despliegue local, en datacenter y en **Google Cloud Run**.

---

## Tabla de Contenidos

- [Requisitos](#requisitos)
- [Instalación local](#instalación-local)
- [Variables de entorno](#variables-de-entorno)
- [Ejecutar el servidor](#ejecutar-el-servidor)
- [Estructura del proyecto](#estructura-del-proyecto)
- [Endpoints de prueba](#endpoints-disponibles-de-prueba)

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


# 2. Crear entorno virtual
python -m venv venv
source venv/bin/activate       # Linux / macOS
venv\Scripts\activate          # Windows

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar variables de entorno
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

## Endpoints disponibles de prueba.

### Utilidades base

| Método | Endpoint | Descripción | Auth |
|--------|----------|-------------|------|
| GET | `/api/test-db` | Verifica la conexión a la base de datos | No |
| GET | `/api/config` | Muestra la configuración activa (sin contraseñas) | No |




## Dependencias principales

| Librería | Versión | Uso |
|----------|---------|-----|
| fastapi | 0.115.0 | Framework web |
| uvicorn | 0.30.6 | Servidor ASGI |
| python-jose | 3.3.0 | JWT (crear y validar tokens) |
| bcrypt | 4.3.0 | Hash de contraseñas |
| mysql-connector-python | 9.2.0 | Driver MySQL |
| python-dotenv | 1.0.1 | Carga de variables de entorno |



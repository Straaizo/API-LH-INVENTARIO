"""
main.py — Entry point de la API FastAPI.

Para levantar el servidor:
    python run_dev.py          ← script con apertura automática del navegador
    python main.py             ← uvicorn directo
    uvicorn main:app --reload  ← desde la terminal

Documentación interactiva disponible en:
    http://localhost:8000/docs        ← Swagger UI  (prueba endpoints visualmente)
    http://localhost:8000/redoc       ← ReDoc       (documentación más limpia)
    http://localhost:8000/openapi.json ← Schema JSON crudo
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
import os

from utils.db import get_db_connection
from config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Aplicación FastAPI ────────────────────────────────────────────────────────
app = FastAPI(
    title="API La Hornilla",
    version="2.0.0",
    description="""
## API Base — FastAPI

Backend para las aplicaciones de gestión de La Hornilla.


### Conexión a base de datos
Configurada via variables de entorno en `.env`:
- **Datacenter/Local**: `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`
- **Cloud SQL (GCP)**: `DATABASE_URL`
""",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
# Agrega aquí la IP de tu datacenter / frontend si es necesario.
# Formato: allow_origin_regex soporta expresiones regulares.
#
# Ejemplos de patrones:
#   localhost y 127.0.0.1 con cualquier puerto:  ya incluidos
#   Red interna 192.168.10.x:                    192\.168\.10\.\d+
#   Dominio fijo:                                agregar en allow_origins abajo
#
CORS_ORIGINS_FIJOS = [
    # Dominios/IPs fijas (sin comodín de puerto)
    # "https://mi-frontend.com",
    # "http://192.168.10.100:3000",
]

app.add_middleware(
    CORSMiddleware,
    # Regex cubre: localhost, 127.0.0.1 y red 192.168.1.x — cualquier puerto
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1|192\.168\.1\.\d+|192\.168\.10\.\d+)(:\d+)?",
    allow_origins=CORS_ORIGINS_FIJOS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
    expose_headers=["Content-Type", "Authorization"],
    max_age=3600,
)

# ── Routers ───────────────────────────────────────────────────────────────────
# Para registrar un nuevo módulo, añadir dos líneas:
#
#   from routers import mi_modulo
#   app.include_router(mi_modulo.router, prefix="/api/mi_modulo", tags=["Mi Modulo"])
#
# Ver routers/README.md para instrucciones detalladas.


# ── Endpoints de utilidad ─────────────────────────────────────────────────────

@app.get("/api/test-db", tags=["Utils"], summary="Verificar conexión a la base de datos")
def test_database():
    """
    Prueba la conexión a MySQL.
    Útil para verificar que el servidor de BD (datacenter o Cloud SQL) es alcanzable.
    """
    try:
        logger.info("Iniciando prueba de conexión a BD...")
        conn   = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT VERSION()")
        version = cursor.fetchone()
        cursor.close()
        conn.close()
        return {
            "status":        "success",
            "message":       "Conexión exitosa",
            "mysql_version": version[0],
            "db_host":       Config.DB_HOST,
            "db_name":       Config.DB_NAME,
        }
    except Exception as e:
        logger.error(f"Error en prueba de BD: {str(e)}")
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )


@app.get("/api/config", tags=["Utils"], summary="Ver configuración activa")
def show_config():
    """
    Muestra la configuración activa (sin contraseñas).
    Útil para verificar que las variables de entorno se cargaron correctamente.
    """
    try:
        modo = "Cloud SQL" if Config.DATABASE_URL else "Datacenter/Local"
        return {
            "status": "success",
            "modo_conexion": modo,
            "config": {
                "DATABASE_URL": "*** definida ***" if Config.DATABASE_URL else "(no definida — usando DB_HOST)",
                "DB_HOST":  Config.DB_HOST,
                "DB_PORT":  Config.DB_PORT,
                "DB_USER":  Config.DB_USER,
                "DB_NAME":  Config.DB_NAME,
                "DEBUG":    Config.DEBUG,
                "K_SERVICE": os.getenv("K_SERVICE", "(local)"),
            }
        }
    except Exception as e:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})


# ── Inicio directo ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

"""
main.py — Entry point de la API FastAPI (LH Inventario).

Para levantar el servidor:
    python run_dev.py          ← script con apertura automática del navegador
    python main.py             ← uvicorn directo
    uvicorn main:app --reload  ← desde la terminal

Documentación interactiva disponible en:
    http://localhost:8000/docs        ← Swagger UI
    http://localhost:8000/redoc       ← ReDoc
    http://localhost:8000/openapi.json ← Schema JSON
"""

import logging
import os

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from utils.auth import get_current_user
from utils import global_rate_limit
from utils.audit_log import audit_middleware

from config import Config
from utils.db import get_db_connection

# ── Routers LH Inventario ─────────────────────────────────────────────────────
from utils import dim_usuario_lh_inventario
from utils import dim_categoria_lh_inventario
from utils import dim_producto_lh_inventario
from utils import dim_tipo_movimiento_lh_inventario
from utils import dim_destino_lh_inventario
from utils import fact_movimientos_lh_inventario
from utils import vw_stock_actual_lh_inventario
from utils import dim_equipos_lh_inventario
from utils import dim_celulares_lh_inventario
from utils import dim_tablets_lh_inventario
from utils import dim_impresoras_lh_inventario

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Descripción global del sistema ────────────────────────────────────────────
# La descripción se renderiza como panel custom via JS en el HTML de /docs
_DESCRIPTION = " "

# ── Aplicación FastAPI ────────────────────────────────────────────────────────
app = FastAPI(
    title="La Hornilla — API de Inventario",
    version="2.1.0",
    description=_DESCRIPTION,
    docs_url=None,   # deshabilitado — se reemplaza con el endpoint custom más abajo
    redoc_url=None,  # deshabilitado — se reemplaza con el endpoint custom más abajo
    openapi_tags=[
        {
            "name": "🔐 Autenticación",
            "description": "Inicio de sesión, registro y consulta de perfil de usuario.",
        },
        {
            "name": "📊 Stock Actual",
            "description": "Consulta del stock disponible por producto en tiempo real.",
        },
        {
            "name": "🚚 Movimientos",
            "description": "Registro de entradas y salidas de insumos del inventario.",
        },
        {
            "name": "📦 Productos",
            "description": "Catálogo de productos: tóners, tambores, kits y repuestos.",
        },
        {
            "name": "🗂️ Categorías",
            "description": "Agrupaciones de productos (Tóner, Tambor, Drum, Kit de mantenimiento).",
        },
        {
            "name": "💻 Equipos",
            "description": (
                "Activos tecnológicos: notebooks, desktops, servidores y mini PCs. "
                "Incluye datos del responsable asignado."
            ),
        },
        {
            "name": "📱 Celulares",
            "description": "Líneas móviles asignadas: Voz y Datos, M2M y BAM.",
        },
        {
            "name": "📟 Tablets",
            "description": "Tablets corporativas con su responsable asignado.",
        },
        {
            "name": "🖨️ Impresoras",
            "description": "Impresoras por sucursal con su responsable asignado.",
        },
        {
            "name": "🔀 Tipos de Movimiento",
            "description": "Catálogo de tipos de movimiento disponibles: ENTRADA y SALIDA.",
        },
        {
            "name": "📍 Destinos",
            "description": "Destinos de salida de insumos: Administración, Cocina, Bodega, etc.",
        },
        {
            "name": "👤 Usuarios",
            "description": "Administración de usuarios del sistema (requiere autenticación).",
        },
        {
            "name": "⚙️ Sistema",
            "description": "Estado general de la API.",
        },
        {
            "name": "🗄️ Base de Datos",
            "description": "Verificación de conectividad con la base de datos MySQL. Requiere autenticación.",
        },
    ],
)

# ── Validación de configuración crítica al arrancar ──────────────────────────
_INSECURE_KEY = "cambia_esto_en_produccion"

@app.on_event("startup")
async def _validate_config():
    if not Config.DEBUG and Config.JWT_SECRET_KEY == _INSECURE_KEY:
        raise RuntimeError(
            "ARRANQUE BLOQUEADO: JWT_SECRET_KEY usa el valor por defecto inseguro. "
            "Define JWT_SECRET_KEY en el archivo .env antes de iniciar en producción."
        )
    if Config.DEBUG and Config.JWT_SECRET_KEY == _INSECURE_KEY:
        logger.warning(
            "[CONFIG] ADVERTENCIA: JWT_SECRET_KEY usa el valor por defecto. "
            "Cambialo en .env antes de desplegar en producción."
        )


# ── Manejador global de excepciones no capturadas ────────────────────────────
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error("Excepción no capturada en %s: %s: %s", request.url, type(exc).__name__, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Error interno del servidor"},
    )


# ── Auditoría ────────────────────────────────────────────────────────────────
app.middleware("http")(audit_middleware)


# ── Rate limiting global ──────────────────────────────────────────────────────
@app.middleware("http")
async def global_rate_limit_middleware(request: Request, call_next):
    blocked, ip = global_rate_limit.check_and_record(request)
    if blocked:
        return JSONResponse(
            status_code=429,
            content={"error": "Demasiadas peticiones. Intente más tarde."},
            headers={"Retry-After": "1800"},
        )
    return await call_next(request)


# ── Security headers — oculta info del servidor y bloquea filtraciones ───────
@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=(), payment=()"
    response.headers["Server"] = "LH-API"
    response.headers["X-Powered-By"] = ""

    # CSP: bloquea ejecución de scripts inline no autorizados y carga de recursos externos no controlados
    if Config.DEBUG:
        # En desarrollo permite CDN para Swagger/ReDoc
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data:; "
            "connect-src 'self'; "
            "frame-ancestors 'none';"
        )
    else:
        # En producción: política estricta
        csp = (
            "default-src 'none'; "
            "script-src 'none'; "
            "style-src 'none'; "
            "img-src 'none'; "
            "connect-src 'self'; "
            "frame-ancestors 'none';"
        )
    response.headers["Content-Security-Policy"] = csp

    # Rutas de la API: no cachear datos sensibles
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"

    if not Config.DEBUG:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"

    return response


# ── CORS ──────────────────────────────────────────────────────────────────────
CORS_ORIGINS_FIJOS = [
    "https://lh-toner.web.app",
    "https://www.lh-toner.web.app",
    "https://lh-inventario.web.app",
    "https://www.lh-inventario.web.app",
]

# En desarrollo se permite red local; en producción se permite localhost para testing desde Flutter Web
_cors_regex = (
    r"http://(localhost|127\.0\.0\.1"
    r"|192\.168\.\d{1,3}\.\d{1,3}"
    r"|10\.\d{1,3}\.\d{1,3}\.\d{1,3}"
    r"|172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}"
    r")(:\d+)?"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS_FIJOS,
    allow_origin_regex=_cors_regex,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=[
        "Content-Type",
        "Authorization",
        "X-Requested-With",
        "Accept",
        "Origin",
        "Access-Control-Request-Method",
        "Access-Control-Request-Headers",
    ],
    expose_headers=["Content-Type"],
    max_age=3600,
)

# ── Routers — rutas de negocio (visibles en Swagger) ──────────────────────────
# Orden = orden de aparición en la documentación
app.include_router(dim_usuario_lh_inventario.router,
                   prefix="/api/auth",
                   tags=["🔐 Autenticación"])

app.include_router(vw_stock_actual_lh_inventario.router,
                   prefix="/api/inventario/stock",
                   tags=["📊 Stock Actual"])

app.include_router(fact_movimientos_lh_inventario.router,
                   prefix="/api/movimientos",
                   tags=["🚚 Movimientos"])

app.include_router(dim_producto_lh_inventario.router,
                   prefix="/api/inventario/productos",
                   tags=["📦 Productos"])

app.include_router(dim_categoria_lh_inventario.router,
                   prefix="/api/inventario/categorias",
                   tags=["🗂️ Categorías"])

app.include_router(dim_equipos_lh_inventario.router,
                   prefix="/api/activos/equipos",
                   tags=["💻 Equipos"])

app.include_router(dim_celulares_lh_inventario.router,
                   prefix="/api/activos/celulares",
                   tags=["📱 Celulares"])

app.include_router(dim_tablets_lh_inventario.router,
                   prefix="/api/activos/tablets",
                   tags=["📟 Tablets"])

app.include_router(dim_impresoras_lh_inventario.router,
                   prefix="/api/activos/impresoras",
                   tags=["🖨️ Impresoras"])

app.include_router(dim_tipo_movimiento_lh_inventario.router,
                   prefix="/api/catalogo/tipos-movimiento",
                   tags=["🔀 Tipos de Movimiento"])

app.include_router(dim_destino_lh_inventario.router,
                   prefix="/api/catalogo/destinos",
                   tags=["📍 Destinos"])

app.include_router(dim_usuario_lh_inventario.router,
                   prefix="/api/usuarios",
                   tags=["👤 Usuarios"])

# ── Aliases de compatibilidad — solo activos en DEBUG ────────────────────────
# En producción devuelven 404 para no revelar estructura interna de la DB
if Config.DEBUG:
    app.include_router(dim_usuario_lh_inventario.router,
                       prefix="/api/dim_usuario_lh_inventario",
                       include_in_schema=False)
    app.include_router(dim_producto_lh_inventario.router,
                       prefix="/api/dim_producto_lh_inventario",
                       include_in_schema=False)
    app.include_router(dim_categoria_lh_inventario.router,
                       prefix="/api/dim_categoria_lh_inventario",
                       include_in_schema=False)
    app.include_router(fact_movimientos_lh_inventario.router,
                       prefix="/api/fact_movimientos_lh_inventario",
                       include_in_schema=False)
    app.include_router(vw_stock_actual_lh_inventario.router,
                       prefix="/api/vw_stock_actual",
                       include_in_schema=False)
    app.include_router(dim_tipo_movimiento_lh_inventario.router,
                       prefix="/api/dim_tipo_movimiento_lh_inventario",
                       include_in_schema=False)
    app.include_router(dim_destino_lh_inventario.router,
                       prefix="/api/dim_destino_lh_inventario",
                       include_in_schema=False)
    app.include_router(dim_equipos_lh_inventario.router,
                       prefix="/api/dim_equipos_lh_inventario",
                       include_in_schema=False)
    app.include_router(dim_celulares_lh_inventario.router,
                       prefix="/api/dim_celulares_lh_inventario",
                       include_in_schema=False)
    app.include_router(dim_tablets_lh_inventario.router,
                       prefix="/api/dim_tablets_lh_inventario",
                       include_in_schema=False)
    app.include_router(dim_impresoras_lh_inventario.router,
                       prefix="/api/dim_impresoras_lh_inventario",
                       include_in_schema=False)
    app.include_router(dim_usuario_lh_inventario.router,
                       prefix="/api/usuarios_lh_inventario",
                       include_in_schema=False)
    app.include_router(dim_usuario_lh_inventario.router,
                       prefix="/api_lh_inventario",
                       include_in_schema=False)
    app.include_router(dim_usuario_lh_inventario.router,
                       prefix="/api/lh_inventario",
                       include_in_schema=False)

# ── Ocultar schema OpenAPI en producción ─────────────────────────────────────
@app.get("/openapi.json", include_in_schema=False)
async def openapi_schema():
    if not Config.DEBUG:
        return JSONResponse(status_code=404, content={"detail": "Not Found"})
    return app.openapi()


# ── Archivos estáticos (logo, etc.) ──────────────────────────────────────────
_STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(_STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")

# ── Swagger UI personalizado ──────────────────────────────────────────────────

@app.get("/redoc", include_in_schema=False)
async def custom_redoc():
    if not Config.DEBUG:
        return JSONResponse(status_code=404, content={"detail": "Not Found"})
    from fastapi.responses import HTMLResponse as _HTML
    return _HTML(
        '<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/redoc/bundles/redoc.standalone.css"/>'
        '<div id="redoc-container"></div>'
        '<script src="https://cdn.jsdelivr.net/npm/redoc/bundles/redoc.standalone.js"></script>'
        '<script>Redoc.init("/openapi.json", {}, document.getElementById("redoc-container"))</script>'
    )


@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui():
    if not Config.DEBUG:
        return JSONResponse(status_code=404, content={"detail": "Not Found"})
    return HTMLResponse("""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>La Hornilla — API de Inventario</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700&display=swap" rel="stylesheet" />
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css" />
  <style>
    /* ── Reset y base ── */
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: 'Montserrat', sans-serif;
      background: #052e16;
      -webkit-font-smoothing: antialiased;
      -moz-osx-font-smoothing: grayscale;
      text-rendering: optimizeLegibility;
    }

    /* ── Header La Hornilla ── */
    #lh-header {
      position: sticky;
      top: 0;
      z-index: 1000;
      background: linear-gradient(135deg, #052e16 0%, #14532d 60%, #052e16 100%);
      border-bottom: 2px solid #16a34a;
      padding: 0 2rem;
      display: flex;
      align-items: center;
      justify-content: space-between;
      min-height: 68px;
      box-shadow: 0 4px 24px rgba(0,0,0,0.5);
    }
    .lh-brand {
      display: flex;
      align-items: center;
      gap: 14px;
    }
    .lh-logo {
      height: 42px;
      width: auto;
      object-fit: contain;
      filter: drop-shadow(0 0 6px #4ade8066);
      border-radius: 6px;
    }
    .lh-logo-fallback {
      display: none;
      width: 42px;
      height: 42px;
      background: #166534;
      border: 2px solid #16a34a;
      border-radius: 8px;
      align-items: center;
      justify-content: center;
      font-size: 1rem;
      font-weight: 800;
      color: #4ade80;
      letter-spacing: -1px;
    }
    .lh-title {
      font-size: 1.35rem;
      font-weight: 700;
      color: #f0fdf4;
      letter-spacing: -0.3px;
    }
    .lh-title span { color: #4ade80; }
    .lh-subtitle {
      font-size: 0.72rem;
      color: #86efac;
      margin-top: 2px;
      letter-spacing: 0.4px;
      text-transform: uppercase;
      opacity: 0.75;
    }
    .lh-badges {
      display: flex;
      align-items: center;
      gap: 10px;
    }
    .lh-nav-link {
      font-size: 0.72rem;
      color: #4ade8099;
      text-decoration: none;
      transition: color .15s;
    }
    .lh-nav-link:hover { color: #4ade80; }

    /* ── Contenedor Swagger ── */
    #swagger-ui {
      background: #f8fafc;
      min-height: calc(100vh - 68px);
      padding-top: 18px;
    }

    /* ── Overrides Swagger UI ── */
    .swagger-ui .topbar { display: none !important; }

    .swagger-ui .info { padding: 24px 0 8px; }
    .swagger-ui .info .title {
      font-family: 'Montserrat', sans-serif !important;
      font-size: 1.6rem !important;
      color: #052e16 !important;
      font-weight: 700 !important;
    }
    .swagger-ui .info .title small {
      background: #16a34a !important;
      color: #f0fdf4 !important;
      border-radius: 6px;
      padding: 2px 8px;
      font-size: 0.7rem;
      font-weight: 700;
    }
    .swagger-ui .info p,
    .swagger-ui .info li,
    .swagger-ui .info td {
      font-family: 'Montserrat', sans-serif !important;
      font-size: 0.85rem !important;
      color: #334155 !important;
    }
    .swagger-ui .info table thead tr th {
      color: #052e16 !important;
      font-weight: 600 !important;
    }

    /* Barra de filtro oculta */
    .swagger-ui .filter-container { display: none !important; }

    /* Tags (secciones) */
    .swagger-ui .opblock-tag {
      font-family: 'Montserrat', sans-serif !important;
      font-size: 0.95rem !important;
      font-weight: 600 !important;
      color: #14532d !important;
      border-bottom: 1px solid #dcfce7 !important;
      padding: 14px 0 !important;
    }
    .swagger-ui .opblock-tag:hover { background: #f0fdf4 !important; }

    /* Bloques de operación */
    .swagger-ui .opblock {
      border-radius: 8px !important;
      margin: 6px 0 !important;
      box-shadow: 0 1px 4px rgba(0,0,0,0.07) !important;
    }
    .swagger-ui .opblock .opblock-summary-method {
      border-radius: 6px !important;
      font-family: 'Montserrat', sans-serif !important;
      font-size: 0.72rem !important;
      font-weight: 700 !important;
      min-width: 60px !important;
    }
    .swagger-ui .opblock .opblock-summary-description {
      font-family: 'Montserrat', sans-serif !important;
      font-size: 0.82rem !important;
      color: #475569 !important;
    }

    /* GET: azul */
    .swagger-ui .opblock-get { border-color: #3b82f6 !important; }
    .swagger-ui .opblock-get .opblock-summary { background: #eff6ff !important; }
    .swagger-ui .opblock-get .opblock-summary-method { background: #3b82f6 !important; }

    /* POST: verde */
    .swagger-ui .opblock-post { border-color: #16a34a !important; }
    .swagger-ui .opblock-post .opblock-summary { background: #f0fdf4 !important; }
    .swagger-ui .opblock-post .opblock-summary-method { background: #16a34a !important; }

    /* PUT: ámbar */
    .swagger-ui .opblock-put { border-color: #f59e0b !important; }
    .swagger-ui .opblock-put .opblock-summary { background: #fffbeb !important; }
    .swagger-ui .opblock-put .opblock-summary-method { background: #f59e0b !important; }

    /* DELETE: rojo */
    .swagger-ui .opblock-delete { border-color: #ef4444 !important; }
    .swagger-ui .opblock-delete .opblock-summary { background: #fef2f2 !important; }
    .swagger-ui .opblock-delete .opblock-summary-method { background: #ef4444 !important; }

    /* Authorize button — oculto */
    .swagger-ui .auth-wrapper,
    .swagger-ui .scheme-container { display: none !important; }

    /* Execute button */
    .swagger-ui .btn.execute {
      background: #14532d !important;
      border-color: #14532d !important;
      border-radius: 8px !important;
      font-family: 'Montserrat', sans-serif !important;
    }

    /* Tablas y respuestas */
    .swagger-ui .responses-inner h4,
    .swagger-ui .responses-inner h5,
    .swagger-ui table thead tr th,
    .swagger-ui table tbody tr td {
      font-family: 'Montserrat', sans-serif !important;
      font-size: 0.8rem !important;
    }

    /* Scrollbar */
    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: #14532d; }
    ::-webkit-scrollbar-thumb { background: #16a34a88; border-radius: 3px; }
    ::-webkit-scrollbar-thumb:hover { background: #4ade80; }

    /* ── Separadores de sección ── */
    .lh-sep {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 18px 20px 4px;
      background: #f8fafc;
    }
    .lh-sep::before,
    .lh-sep::after {
      content: '';
      flex: 1;
      height: 1.5px;
      background: linear-gradient(to right, transparent, #16a34a88, transparent);
    }
    .lh-sep span {
      font-family: 'Montserrat', sans-serif;
      font-size: 0.6rem;
      font-weight: 700;
      letter-spacing: 2.5px;
      text-transform: uppercase;
      color: #16a34a;
      white-space: nowrap;
      padding: 3px 10px;
      border: 1px solid #16a34a44;
      border-radius: 999px;
      background: #f0fdf4;
    }
  </style>
</head>
<body>

  <!-- ── Header La Hornilla ── -->
  <div id="lh-header">
    <div class="lh-brand">
      <img
        class="lh-logo"
        src="/static/logo.png"
        alt="La Hornilla"
        onerror="this.style.display='none'; document.getElementById('lh-logo-fb').style.display='flex';"
      />
      <div id="lh-logo-fb" class="lh-logo-fallback">LH</div>
      <div>
        <div class="lh-title">La <span>Hornilla</span></div>
        <div class="lh-subtitle">API de Inventario </div>
      </div>
    </div>
    <div class="lh-badges">
      <a href="/redoc" class="lh-nav-link">ReDoc</a>
      <a href="/openapi.json" class="lh-nav-link">OpenAPI</a>
    </div>
  </div>

  <!-- ── Swagger UI ── -->
  <div id="swagger-ui"></div>

  <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
  <script>

    // ══════════════════════════════════════════════════════════════
    //  PANEL INFO CUSTOM  — reemplaza el bloque .info de Swagger
    // ══════════════════════════════════════════════════════════════
    const INFO_PANEL_HTML = `
    <div class="lh-info-panel">

      <!-- Fila superior: título -->
      <div class="lh-info-top">
        <div class="lh-info-title-row">
          <span class="lh-info-title">API LH Inventario</span>
        </div>
        <p class="lh-info-sub">Backend de inventario unificado · La Hornilla</p>
      </div>

      <!-- Grilla de módulos -->
      <div class="lh-modules-title">MÓDULOS DEL SISTEMA</div>
      <div class="lh-modules">

        <div class="lh-module lh-module-fact">
          <div class="lh-module-icon">📊</div>
          <div>
            <div class="lh-module-name">Movimientos</div>
            <div class="lh-module-desc">FACT · Entradas y salidas de stock</div>
          </div>
        </div>

        <div class="lh-module lh-module-dim">
          <div class="lh-module-icon">📦</div>
          <div>
            <div class="lh-module-name">Productos & Categorías</div>
            <div class="lh-module-desc">DIM · Catálogo de insumos</div>
          </div>
        </div>

        <div class="lh-module lh-module-dim">
          <div class="lh-module-icon">🔐</div>
          <div>
            <div class="lh-module-name">Usuarios</div>
            <div class="lh-module-desc">DIM · Auth JWT, login y perfiles</div>
          </div>
        </div>

        <div class="lh-module lh-module-dim">
          <div class="lh-module-icon">💻</div>
          <div>
            <div class="lh-module-name">Activos</div>
            <div class="lh-module-desc">DIM · Equipos, celulares, tablets, impresoras</div>
          </div>
        </div>

        <div class="lh-module lh-module-dim">
          <div class="lh-module-icon">🚚</div>
          <div>
            <div class="lh-module-name">Catálogos</div>
            <div class="lh-module-desc">DIM · Tipos de movimiento y destinos</div>
          </div>
        </div>

        <div class="lh-module lh-module-view">
          <div class="lh-module-icon">👁️</div>
          <div>
            <div class="lh-module-name">Stock Actual</div>
            <div class="lh-module-desc">VIEW · vw_stock_actual en tiempo real</div>
          </div>
        </div>

      </div>

      <!-- Widgets de estado -->
      <div class="lh-status-title">ESTADO DEL SERVICIO</div>
      <div class="lh-status-grid">

        <div class="lh-status-card">
          <div class="lh-status-header">
            <span class="lh-status-icon">⚙️</span>
            <div>
              <div class="lh-status-label">Sistema</div>
              <div class="lh-status-desc">Estado general de la API</div>
            </div>
            <span class="lh-status-dot" id="lh-api-dot"></span>
          </div>
          <div class="lh-check-row">
            <div class="lh-status-result" id="lh-api-result">Verificando…</div>
            <button class="lh-check-btn" id="lh-btn-api" onclick="checkApi()"></button>
          </div>
        </div>

        <div class="lh-status-card">
          <div class="lh-status-header">
            <span class="lh-status-icon">🗄️</span>
            <div>
              <div class="lh-status-label">Base de Datos</div>
              <div class="lh-status-desc">Conexión con MySQL</div>
            </div>
            <span class="lh-status-dot" id="lh-db-dot"></span>
          </div>
          <div class="lh-check-row">
            <div class="lh-status-result" id="lh-db-result">Verificando…</div>
            <button class="lh-check-btn" id="lh-btn-db" onclick="checkDb()"></button>
          </div>
        </div>

      </div>
    </div>
    `;

    const INFO_PANEL_CSS = `
      .lh-info-panel {
        font-family: 'Montserrat', sans-serif;
        background: #f0fdf4;
        border: 1px solid #bbf7d0;
        border-radius: 12px;
        padding: 20px 24px;
        margin: 16px 0 8px;
      }

      /* Título */
      .lh-info-top { margin-bottom: 16px; }
      .lh-info-title-row {
        display: flex;
        align-items: center;
        gap: 8px;
        flex-wrap: wrap;
        margin-bottom: 4px;
      }
      .lh-info-title {
        font-size: 1.25rem;
        font-weight: 700;
        color: #052e16;
        letter-spacing: -0.3px;
      }
      .lh-info-sub {
        font-size: 0.78rem;
        color: #166534;
        margin: 0;
      }


      /* Módulos */
      .lh-modules-title {
        font-size: 0.65rem;
        font-weight: 700;
        letter-spacing: 1.5px;
        color: #16a34a;
        text-transform: uppercase;
        margin-bottom: 8px;
        padding-bottom: 4px;
        border-bottom: 1px solid #bbf7d0;
      }
      .lh-modules {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(210px, 1fr));
        gap: 8px;
        margin-bottom: 16px;
      }
      .lh-module {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 10px 12px;
        border-radius: 8px;
        border-left: 3px solid transparent;
      }
      .lh-module-fact { background:#fff; border-color:#16a34a; }
      .lh-module-dim  { background:#fff; border-color:#3b82f6; }
      .lh-module-view { background:#fff; border-color:#8b5cf6; }
      .lh-module-icon { font-size: 1.1rem; line-height:1; }
      .lh-module-name {
        font-size: 0.78rem;
        font-weight: 600;
        color: #0f172a;
        line-height: 1.3;
      }
      .lh-module-desc {
        font-size: 0.67rem;
        color: #64748b;
        margin-top: 1px;
      }

      /* Widgets de estado */
      .lh-status-title {
        font-size: 0.65rem;
        font-weight: 700;
        letter-spacing: 1.5px;
        color: #16a34a;
        text-transform: uppercase;
        margin-bottom: 8px;
        padding-bottom: 4px;
        border-bottom: 1px solid #bbf7d0;
      }
      .lh-status-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 10px;
      }
      @media (max-width: 540px) { .lh-status-grid { grid-template-columns: 1fr; } }
      .lh-status-card {
        background: #fff;
        border: 1px solid #dcfce7;
        border-radius: 8px;
        padding: 12px 14px;
        display: flex;
        flex-direction: column;
        gap: 8px;
      }
      .lh-status-header {
        display: flex;
        align-items: center;
        gap: 10px;
      }
      .lh-status-icon { font-size: 1.2rem; line-height: 1; }
      .lh-status-label {
        font-size: 0.8rem;
        font-weight: 600;
        color: #052e16;
        line-height: 1.2;
      }
      .lh-status-desc {
        font-size: 0.65rem;
        color: #64748b;
      }
      .lh-status-dot {
        margin-left: auto;
        width: 10px;
        height: 10px;
        border-radius: 50%;
        background: #cbd5e1;
        flex-shrink: 0;
        transition: background .3s;
      }
      .lh-status-dot.ok  { background: #16a34a; box-shadow: 0 0 6px #16a34a88; }
      .lh-status-dot.err { background: #ef4444; box-shadow: 0 0 6px #ef444488; }
      .lh-status-result {
        font-size: 0.67rem;
        color: #475569;
        font-family: 'Montserrat', sans-serif;
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 5px;
        padding: 5px 8px;
        min-height: 26px;
      }
      .lh-check-row {
        display: flex;
        gap: 6px;
        align-items: center;
      }
      .lh-check-row .lh-status-result { flex: 1; margin: 0; }
      .lh-check-btn {
        font-family: 'Montserrat', sans-serif;
        font-size: 0.85rem;
        font-weight: 700;
        color: #fff;
        background: #16a34a;
        border: none;
        border-radius: 5px;
        width: 28px;
        height: 28px;
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        flex-shrink: 0;
        transition: background .15s;
        line-height: 1;
      }
      .lh-check-btn:hover { background: #15803d; }
      .lh-check-btn:disabled { background: #86efac; cursor: not-allowed; opacity: .7; }
      .lh-check-btn svg { display: block; }
      @keyframes lh-spin { to { transform: rotate(360deg); } }

      /* Font smoothing global del panel */
      .lh-info-panel, .lh-info-panel * {
        -webkit-font-smoothing: antialiased;
        -moz-osx-font-smoothing: grayscale;
        text-rendering: optimizeLegibility;
      }
    `;

    // ── Verificación de estado ────────────────────────────────────────────────
    const SVG_REFRESH = `<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>`;
    const SVG_SPIN   = `<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="animation:lh-spin .7s linear infinite"><path d="M12 2a10 10 0 0 1 10 10" stroke-opacity="1"/><circle cx="12" cy="12" r="10" stroke-opacity=".2"/></svg>`;

    async function checkApi() {
      const btn = document.getElementById("lh-btn-api");
      const res = document.getElementById("lh-api-result");
      const dot = document.getElementById("lh-api-dot");
      btn.disabled = true; btn.innerHTML = SVG_SPIN;
      try {
        const r = await fetch("/api/");
        const data = await r.json();
        dot.className = "lh-status-dot ok";
        res.textContent = data.message || "API activa";
      } catch {
        dot.className = "lh-status-dot err";
        res.textContent = "No disponible";
      }
      btn.disabled = false; btn.innerHTML = SVG_REFRESH;
    }

    async function checkDb() {
      const btn = document.getElementById("lh-btn-db");
      const res = document.getElementById("lh-db-result");
      const dot = document.getElementById("lh-db-dot");
      btn.disabled = true; btn.innerHTML = SVG_SPIN;
      try {
        const r = await fetch("/api/db/ping");
        const data = await r.json();
        dot.className = r.ok ? "lh-status-dot ok" : "lh-status-dot err";
        res.textContent = data.message || (r.ok ? "Conexión exitosa" : "Error");
      } catch {
        dot.className = "lh-status-dot err";
        res.textContent = "No disponible";
      }
      btn.disabled = false; btn.innerHTML = SVG_REFRESH;
    }

    // Auto-verificación al cargar
    window.addEventListener("load", () => {
      setTimeout(() => { checkApi(); checkDb(); }, 600);
    });

    function injectInfoPanel() {
      // Oculta el bloque .info original de Swagger
      const infoBlock = document.querySelector(".swagger-ui .information-container");
      if (!infoBlock || infoBlock.dataset.lhInjected) return;
      infoBlock.dataset.lhInjected = "1";

      // Inyecta CSS
      const style = document.createElement("style");
      style.textContent = INFO_PANEL_CSS;
      document.head.appendChild(style);

      // Reemplaza el contenido del bloque info
      infoBlock.innerHTML = INFO_PANEL_HTML;

      // Inicializa los íconos SVG de los botones
      const btnApi = document.getElementById("lh-btn-api");
      const btnDb  = document.getElementById("lh-btn-db");
      if (btnApi) btnApi.innerHTML = SVG_REFRESH;
      if (btnDb)  btnDb.innerHTML  = SVG_REFRESH;
    }

    // ── Separadores de sección ────────────────────────────────────────────────
    function mkSep(label) {
      const d = document.createElement("div");
      d.className = "lh-sep";
      d.innerHTML = `<span>${label}</span>`;
      return d;
    }

    function insertSeparators() {
      const sections = document.querySelectorAll(".opblock-tag-section");
      if (!sections.length) return;
      sections.forEach(sec => {
        const h4 = sec.querySelector("h4[data-tag]");
        if (!h4) return;
        const tag = h4.getAttribute("data-tag") || "";
        // Ocultar Sistema y Base de Datos del listado (ya están en el panel info)
        if (tag.includes("Sistema") || tag.includes("Base de Datos")) {
          sec.style.display = "none";
          return;
        }
        if (tag.includes("Autenticación") && !sec.previousElementSibling?.classList.contains("lh-sep")) {
          sec.parentNode.insertBefore(mkSep("● Aplicación — Schemas & Endpoints"), sec);
        }
      });
    }

    // ── MutationObserver — espera que Swagger renderice todo ─────────────────
    let panelDone = false, sepDone = false;
    const observer = new MutationObserver(() => {
      if (!panelDone && document.querySelector(".swagger-ui .information-container")) {
        injectInfoPanel();
        panelDone = true;
      }
      if (!sepDone && document.querySelectorAll(".opblock-tag-section").length > 0) {
        insertSeparators();
        sepDone = true;
      }
      if (panelDone && sepDone) observer.disconnect();
    });
    observer.observe(document.getElementById("swagger-ui"), { childList: true, subtree: true });

    // ── Swagger UI ────────────────────────────────────────────────────────────
    SwaggerUIBundle({
      url: "/openapi.json",
      dom_id: "#swagger-ui",
      presets: [SwaggerUIBundle.presets.apis, SwaggerUIBundle.SwaggerUIStandalonePreset],
      layout: "BaseLayout",
      docExpansion: "none",
      defaultModelsExpandDepth: -1,
      filter: false,
      persistAuthorization: false,
      tryItOutEnabled: false,
      deepLinking: true,
      displayRequestDuration: false,
    });
  </script>
</body>
</html>""")


# ── Endpoints de utilidad ─────────────────────────────────────────────────────

@app.get(
    "/api/",
    tags=["⚙️ Sistema"],
    summary="Estado de la API",
    description="Verifica que la API esté activa.",
)
def index():
    payload = {"message": "API La Hornilla activa", "status": "ok"}
    if Config.DEBUG:
        payload["docs"] = "/docs"
        payload["version"] = "2.1.0"
    return payload


@app.get(
    "/api/db/ping",
    tags=["🗄️ Base de Datos"],
    summary="Verificar conexión a la base de datos",
    description=(
        "Ejecuta un `SELECT 1` para confirmar que la conexión a MySQL está activa. "
        "Solo retorna estado de conectividad, sin exponer datos. Requiere autenticación."
    ),
    responses={
        500: {"description": "Error al conectar con la base de datos"},
    },
)
def test_database():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        cursor.close()
        conn.close()
        return {"status": "ok", "message": "Conexión exitosa"}
    except Exception as e:
        logger.error("Error en prueba de BD: %s", type(e).__name__, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": "Error al conectar con la base de datos"},
        )


# Alias legacy solo en DEBUG
if Config.DEBUG:
    @app.get("/api/test-db", include_in_schema=False)
    def test_database_legacy():
        return test_database()


# ── Inicio directo ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

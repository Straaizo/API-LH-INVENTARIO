import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    DEBUG = os.getenv("DEBUG", "True") == "True"

    # ── Conexión a base de datos ──────────────────────────────────────────────
    # DATABASE_URL se usa en Cloud Run (Cloud SQL Proxy vía unix socket).
    # Si no está definida, se usa la configuración host/user/password.
    DATABASE_URL = os.getenv("DATABASE_URL", "")

    # Cuando corre en Cloud Run (K_SERVICE definido) el proxy escucha en localhost.
    if os.getenv("K_SERVICE"):
        DB_HOST = "localhost"
        DB_PORT = 3306
    else:
        DB_HOST = os.getenv("DB_HOST", "localhost")
        DB_PORT = int(os.getenv("DB_PORT", 3306))

    DB_USER     = os.getenv("DB_USER",     "UserApp")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    DB_NAME     = os.getenv("DB_NAME",     "lahornilla_base_normalizada")

    # ── JWT ───────────────────────────────────────────────────────────────────
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "cambia_esto_en_produccion")
    SECRET_KEY     = os.getenv("SECRET_KEY",     JWT_SECRET_KEY)

    # ── Roles ─────────────────────────────────────────────────────────────────
    # IDs de usuarios con permisos de administrador (separados por coma en .env)
    # Ejemplo: ADMIN_USER_IDS=1,2
    # UUIDs (varchar) de usuarios con permisos de administrador
    ADMIN_USER_IDS: set = {
        x.strip()
        for x in os.getenv("ADMIN_USER_IDS", "").split(",")
        if x.strip()
    }

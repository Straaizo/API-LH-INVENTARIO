"""
Módulo de conexión a la base de datos MySQL.

Soporta dos modos de conexión según las variables de entorno:

┌──────────────────────────────────────────────────────────────────────────────┐
│  MODO 1 — DATACENTER / SERVIDOR REMOTO / LOCAL (recomendado para desarrollo) │
│                                                                              │
│  Dejar DATABASE_URL vacía y configurar:                                      │
│    DB_HOST     = IP o hostname del servidor  (ej: 192.168.10.5)             │
│    DB_PORT     = puerto MySQL                (ej: 3306)                     │
│    DB_USER     = usuario                                                     │
│    DB_PASSWORD = contraseña                                                  │
│    DB_NAME     = nombre de la base de datos                                  │
├──────────────────────────────────────────────────────────────────────────────┤
│  MODO 2 — GOOGLE CLOUD RUN + CLOUD SQL (producción en GCP)                  │
│                                                                              │
│  Definir DATABASE_URL con formato unix socket:                               │
│    DATABASE_URL = mysql+pymysql://user:pass@/dbname?unix_socket=             │
│                   /cloudsql/proyecto:region:instancia                        │
└──────────────────────────────────────────────────────────────────────────────┘
"""

import mysql.connector
from config import Config
import re
import logging

logger = logging.getLogger(__name__)


def get_db_connection():
    """
    Retorna una conexión activa a MySQL.
    Elige automáticamente entre Modo 1 (datacenter/local) y Modo 2 (Cloud SQL).
    """

    # ── MODO 2: Cloud SQL via unix socket (DATABASE_URL definida) ─────────────
    if Config.DATABASE_URL:
        logger.info("Modo Cloud SQL — usando DATABASE_URL")
        return _connect_cloud_sql(Config.DATABASE_URL)

    # ── MODO 1: Conexión directa TCP (datacenter, servidor local, etc.) ───────
    logger.info(f"Modo Datacenter/Local — host: {Config.DB_HOST}:{Config.DB_PORT}")
    return mysql.connector.connect(
        host=Config.DB_HOST,
        port=Config.DB_PORT,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        database=Config.DB_NAME,
        connection_timeout=10,
    )


# ── Helpers privados ──────────────────────────────────────────────────────────

def _connect_cloud_sql(url: str):
    """
    Parsea DATABASE_URL en formato Cloud SQL y retorna la conexión.
    Formato esperado:
        mysql+pymysql://user:password@/database?unix_socket=/cloudsql/proyecto:region:instancia
    """
    # Patrón principal: unix socket explícito
    pattern = r'mysql\+pymysql://([^:]+):([^@]+)@/([^?]+)\?unix_socket=(/cloudsql/)?(.+)'
    match = re.match(pattern, url)

    if match:
        user, password, database, _, instance = match.groups()
        logger.info(f"Cloud SQL — usuario: {user} | base: {database} | instancia: {instance}")
        return mysql.connector.connect(
            host="localhost",
            port=3306,
            user=user,
            password=password,
            database=database,
            unix_socket=f"/cloudsql/{instance}",
        )

    # Fallback: URL con host TCP estándar (mysql+pymysql://user:pass@host/db)
    url_clean = url.replace("mysql+pymysql://", "").replace("mysql://", "")
    if "@" in url_clean:
        credentials, rest = url_clean.split("@", 1)
        user, password = credentials.split(":", 1)
        host_part, database = rest.split("/", 1)
        host = host_part.split(":")[0]
        port = int(host_part.split(":")[1]) if ":" in host_part else 3306
        logger.info(f"Cloud SQL fallback TCP — host: {host} | base: {database}")
        return mysql.connector.connect(
            host=host, port=port,
            user=user, password=password,
            database=database,
        )

    raise ValueError(f"No se pudo parsear DATABASE_URL: {url}")

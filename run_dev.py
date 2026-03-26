"""
run_dev.py — Script de desarrollo para levantar la API y abrir Swagger UI.

Uso:
    python run_dev.py

Qué hace:
  1. Verifica que el archivo .env existe (si no, lo crea desde .env.example)
  2. Muestra la configuración activa (host BD, puerto, etc.)
  3. Levanta uvicorn con recarga automática (hot reload)
  4. Abre el navegador en http://localhost:8000/docs (Swagger UI)
"""

import os
import sys
import time
import shutil
import threading
import webbrowser
from pathlib import Path

# ── Directorio raíz del proyecto ──────────────────────────────────────────────
ROOT = Path(__file__).parent

# ── 1. Verificar / crear .env ─────────────────────────────────────────────────
env_file     = ROOT / ".env"
env_example  = ROOT / ".env.example"

if not env_file.exists():
    if env_example.exists():
        shutil.copy(env_example, env_file)
        print("=" * 60)
        print("  AVISO: Se creó el archivo .env desde .env.example")
        print("  Edita .env con tus credenciales reales antes de continuar.")
        print("=" * 60)
        print()
    else:
        print("ADVERTENCIA: No se encontró .env ni .env.example")

# ── 2. Cargar y mostrar configuración ─────────────────────────────────────────
from dotenv import load_dotenv
load_dotenv(env_file)

HOST    = "127.0.0.1"
PORT    = int(os.getenv("DEV_PORT", 8000))
RELOAD  = True
URL     = f"http://{HOST}:{PORT}"

db_host = os.getenv("DB_HOST", "localhost")
db_name = os.getenv("DB_NAME", "(no definida)")
db_url  = os.getenv("DATABASE_URL", "")
modo_bd = "Cloud SQL (DATABASE_URL)" if db_url else f"Datacenter/Local ({db_host})"

# ── 3 & 4. Levantar uvicorn y abrir navegador ────────────────────────────────
try:
    import uvicorn
except ImportError:
    print("ERROR: uvicorn no está instalado. Ejecuta: pip install -r requirements.txt")
    sys.exit(1)

# IMPORTANTE: el guard if __name__ == "__main__" es obligatorio en Windows
# cuando reload=True usa multiprocessing (spawn). Sin esto, Python 3.12+
# lanza RuntimeError al intentar crear subprocesos.
# El navegador también debe abrirse aquí para que solo lo haga el proceso
# principal, no el proceso hijo del reloader.
if __name__ == "__main__":
    # En Windows con reload=True, uvicorn usa multiprocessing (spawn) y el proceso
    # hijo re-ejecuta este script con __name__ == "__main__" también.
    # La variable de entorno es heredada por el hijo, evitando duplicados.
    if not os.environ.get("_RUN_DEV_STARTED"):
        os.environ["_RUN_DEV_STARTED"] = "1"

        print()
        print("╔══════════════════════════════════════════════════════════╗")
        print("║           API La Hornilla — FASTAPI                      ║")
        print("╠══════════════════════════════════════════════════════════╣")
        print(f"║ Servidor:   {URL:<45}║")
        print(f"║ Swagger UI: {URL + '/docs':<45}║")
        print(f"║ ReDoc:      {URL + '/redoc':<45}║")
        print("╠══════════════════════════════════════════════════════════╣")
        print(f"║ BD Modo:   {modo_bd:<45} ║")
        print(f"║ BD Nombre: {db_name:<45} ║")
        print("╠══════════════════════════════════════════════════════════╣")
        print()

        def abrir_navegador():
            time.sleep(2)
            webbrowser.open(f"{URL}/docs")
            print(f"  → Navegador abierto en {URL}/docs")

        hilo = threading.Thread(target=abrir_navegador, daemon=True)
        hilo.start()

    uvicorn.run(
        "main:app",
        host=HOST,
        port=PORT,
        reload=RELOAD,
        reload_dirs=[str(ROOT)],      # Vigila cambios en todo el proyecto
        log_level="info",
    )

# -*- coding: utf-8 -*-
"""
QA Security Test -- LH Inventario API
Simula los 6 vectores de ataque identificados en el an?lisis.
Ejecutar con: python qa_security_test.py
"""
import json
import time
import urllib.request
import urllib.error

BASE = "http://localhost:8000"

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"


def _req(method, path, body=None, headers=None, token=None):
    url = BASE + path
    h   = {"Content-Type": "application/json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    if headers:
        h.update(headers)
    data = json.dumps(body).encode() if body else None
    req  = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except Exception:
            return e.code, {}
    except Exception as ex:
        return 0, {"error": str(ex)}


def title(text):
    print(f"\n{BOLD}{CYAN}{'-'*60}{RESET}")
    print(f"{BOLD}{CYAN}  {text}{RESET}")
    print(f"{BOLD}{CYAN}{'-'*60}{RESET}")


def check(label, passed, detail=""):
    icon   = f"{GREEN}[PASS]{RESET}" if passed else f"{RED}[FAIL]{RESET}"
    detail = f"  {YELLOW}>> {detail}{RESET}" if detail else ""
    print(f"  {icon}  {label}{detail}")
    return passed


results = []

# ==============================================================================
# TEST 1 ? USER ENUMERATION
# ==============================================================================
title("TEST 1 ? User Enumeration")
print("  Ataque: probar correos distintos para saber cu?les existen en el sistema.\n")

code_nx, body_nx = _req("POST", "/api/auth/login", {"correo": "noexiste_xyz123@fake.cl", "password": "cualquiera"})
code_wp, body_wp = _req("POST", "/api/auth/login", {"correo": "admin@lahornilla.cl",     "password": "password_incorrecta_zzz"})

msg_nx = body_nx.get("error", "")
msg_wp = body_wp.get("error", "")
code_nx_ok = body_nx.get("code", "")
code_wp_ok = body_wp.get("code", "")

print(f"  Usuario inexistente   -> HTTP {code_nx} | msg: '{msg_nx}' | code: '{code_nx_ok}'")
print(f"  Contrase?a incorrecta -> HTTP {code_wp} | msg: '{msg_wp}' | code: '{code_wp_ok}'")

same_msg  = check("Mismo mensaje en ambos casos",  msg_nx == msg_wp,  f"'{msg_nx}' == '{msg_wp}'")
no_code   = check("Sin campo 'code' que revele causa", not code_nx_ok and not code_wp_ok, f"codes: '{code_nx_ok}' / '{code_wp_ok}'")
results.append(same_msg and no_code)


# ==============================================================================
# TEST 2 ? BRUTE FORCE / RATE LIMITING
# ==============================================================================
title("TEST 2 ? Fuerza Bruta ? Rate Limiting")
print("  Ataque: enviar 7 intentos de login fallidos seguidos desde la misma IP.\n")

blocked_at = None
for i in range(1, 8):
    code, body = _req("POST", "/api/auth/login", {"correo": "brute@fake.cl", "password": f"wrong{i}"})
    msg = body.get("error", "")
    print(f"  Intento {i}: HTTP {code} | {msg}")
    if code == 429:
        blocked_at = i
        break
    time.sleep(0.1)

got_blocked   = check("Se bloque? la IP tras intentos fallidos",  blocked_at is not None, f"bloqueado en intento #{blocked_at}")
blocked_early = check("Bloque? antes del intento #7",             blocked_at is not None and blocked_at <= 6)
results.append(got_blocked and blocked_early)

# Verificar que el bloqueo persiste
code_p, body_p = _req("POST", "/api/auth/login", {"correo": "otro@fake.cl", "password": "test"})
persists = check("Bloqueo persiste para la misma IP (correo diferente)", code_p == 429, f"HTTP {code_p}")
results.append(persists)


# ==============================================================================
# TEST 3 ? JWT FORJADO
# ==============================================================================
title("TEST 3 ? JWT Forjado")
print("  Ataque: construir un token JWT firmado con clave incorrecta.\n")

import base64, hmac as _hmac, hashlib as _hs

def _fake_jwt(secret="clave_atacante"):
    header  = base64.urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT"}').rstrip(b"=").decode()
    payload = base64.urlsafe_b64encode(b'{"sub":"1","exp":9999999999}').rstrip(b"=").decode()
    sig_raw = _hmac.new(secret.encode(), f"{header}.{payload}".encode(), _hs.sha256).digest()
    sig     = base64.urlsafe_b64encode(sig_raw).rstrip(b"=").decode()
    return f"{header}.{payload}.{sig}"

fake_token = _fake_jwt("clave_atacante")
code_fj, body_fj = _req("GET", "/api/activos/equipos", token=fake_token)
print(f"  Token forjado -> HTTP {code_fj} | {body_fj.get('detail','')}")

forged_blocked = check("Token forjado rechazado (401)", code_fj == 401, f"HTTP {code_fj}")
results.append(forged_blocked)

# Token vac?o
code_empty, _ = _req("GET", "/api/activos/equipos", token="eyJhbGciOiJIUzI1NiJ9.e30.fakeSignature")
empty_blocked  = check("Token inv?lido/vac?o rechazado (401/403)", code_empty in (401, 403), f"HTTP {code_empty}")
results.append(empty_blocked)


# ==============================================================================
# TEST 4 ? DOCS EXPUESTO (DEBUG=True simulado ? solo verifica que la ruta responde)
# ==============================================================================
title("TEST 4 ? Swagger UI / Docs")
print("  Verificando que /docs est? activo en modo DEBUG (dev) y schema protegido.\n")

# /docs devuelve HTML, usar urllib directamente
try:
    import urllib.request as _ur
    with _ur.urlopen(BASE + "/docs", timeout=5) as _r:
        code_docs = _r.status
except Exception:
    code_docs = 0
code_oapi, _ = _req("GET", "/openapi.json")

print(f"  GET /docs         -> HTTP {code_docs}")
print(f"  GET /openapi.json -> HTTP {code_oapi}")

# En DEBUG=True deben estar disponibles
docs_ok = check("En modo DEBUG, /docs responde 200", code_docs == 200, f"HTTP {code_docs}")
results.append(docs_ok)
print(f"  {YELLOW}[!]  En producci?n (DEBUG=False) ambas rutas devolver?n 404 ? verificar al deployar.{RESET}")


# ==============================================================================
# TEST 5 ? ACCESO SIN TOKEN A ENDPOINTS PROTEGIDOS
# ==============================================================================
title("TEST 5 ? Endpoints sin autenticaci?n")
print("  Ataque: acceder a datos sin enviar ning?n token JWT.\n")

endpoints = [
    ("GET",  "/api/activos/equipos",         "Equipos"),
    ("GET",  "/api/activos/celulares",        "Celulares"),
    ("GET",  "/api/activos/tablets",          "Tablets"),
    ("GET",  "/api/activos/impresoras",       "Impresoras"),
    ("GET",  "/api/movimientos",              "Movimientos"),
    ("GET",  "/api/inventario/stock",         "Stock"),
    ("GET",  "/api/usuarios",                 "Lista usuarios"),
]

all_protected = True
for method, path, label in endpoints:
    code, body = _req(method, path)
    protected  = code in (401, 403, 422)
    ok = check(f"{label} requiere auth ({code})", protected, path)
    if not ok:
        all_protected = False

results.append(all_protected)


# ==============================================================================
# TEST 6 ? ESCALADA DE PRIVILEGIOS (operaciones admin sin ser admin)
# ==============================================================================
title("TEST 6 ? Escalada de privilegios")
print("  Ataque: usuario normal intenta crear/eliminar usuarios (operaciones admin).\n")
print("  Nota: para este test se necesita un token de usuario no-admin.")
print("  Si no hay usuario de prueba disponible, el test se marca como N/A.\n")

# Intentar sin token (debe fallar con 401)
code_cu, body_cu = _req("POST", "/api/usuarios", {"nombre_usuario": "hacker", "correo": "h@x.cl", "contrasenia": "123456"})
code_du, _       = _req("DELETE", "/api/usuarios/999")

no_anon_create = check("Crear usuario sin token -> 401/403", code_cu in (401, 403, 422), f"HTTP {code_cu}")
no_anon_delete = check("Eliminar usuario sin token -> 401/403", code_du in (401, 403, 422), f"HTTP {code_du}")
results.append(no_anon_create and no_anon_delete)


# ==============================================================================
# TEST 7 ? FILTRACI?N DE INFO EN ERRORES
# ==============================================================================
title("TEST 7 ? Filtraci?n de informaci?n en errores 500")
print("  Ataque: provocar error interno y ver si el traceback se expone.\n")

# Enviar payload malformado
code_err, body_err = _req("POST", "/api/auth/login", {"correo": None, "password": None})
has_traceback = "traceback" in str(body_err).lower() or "file \"" in str(body_err).lower()
has_db_info   = any(k in str(body_err).lower() for k in ["mysql", "database", "sqlstate", "1045"])

no_trace = check("Sin traceback en respuesta de error", not has_traceback, str(body_err)[:80])
no_db    = check("Sin info de DB expuesta en errores",  not has_db_info,   str(body_err)[:80])
results.append(no_trace and no_db)


# ==============================================================================
# RESUMEN FINAL
# ==============================================================================
passed = sum(results)
total  = len(results)
print(f"\n{BOLD}{'='*60}{RESET}")
print(f"{BOLD}  RESULTADO FINAL: {passed}/{total} pruebas superadas{RESET}")
if passed == total:
    print(f"{GREEN}{BOLD}  [OK] TODOS LOS CONTROLES DE SEGURIDAD FUNCIONAN CORRECTAMENTE{RESET}")
else:
    failed = total - passed
    print(f"{RED}{BOLD}  [!!] {failed} prueba(s) fallaron -- revisar los detalles arriba{RESET}")
print(f"{BOLD}{'='*60}{RESET}\n")

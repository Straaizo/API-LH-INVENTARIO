"""
test_ratelimit.py — Simula ataque de fuerza bruta desde una IP específica.
Uso:
    python test_ratelimit.py
    python test_ratelimit.py --ip 203.0.113.99 --intentos 8
"""

import argparse
import time
import json
import urllib.request
import urllib.error

URL      = "https://api-lh-inventario-927498545444.us-central1.run.app/api/auth/login"
IP_FAKE  = "203.0.113.42"   # rango TEST-NET RFC 5737 — nunca es una IP real
INTENTOS = 8

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"


def post(url, body, ip):
    data = json.dumps(body).encode()
    req  = urllib.request.Request(
        url, data=data,
        headers={
            "Content-Type":    "application/json",
            "X-Forwarded-For": ip,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:    return e.code, json.loads(e.read())
        except: return e.code, {}
    except Exception as ex:
        return 0, {"error": str(ex)}


def run(url, ip, intentos):
    print(f"\n{BOLD}{CYAN}{'='*56}{RESET}")
    print(f"{BOLD}  SIMULADOR RATE LIMITING — LH Inventario{RESET}")
    print(f"{CYAN}{'='*56}{RESET}")
    print(f"  URL     : {url}")
    print(f"  IP fake : {BOLD}{ip}{RESET}  (X-Forwarded-For)")
    print(f"  Intentos: {intentos}")
    print(f"{CYAN}{'='*56}{RESET}\n")

    bloqueado_en = None

    for i in range(1, intentos + 1):
        code, body = post(url, {"correo": "test@fake.cl", "contrasenia": "wrong"}, ip)

        if code == 429:
            if bloqueado_en is None:
                bloqueado_en = i
            msg = body.get("error", body)
            print(f"  [{BOLD}{RED}BLOQUEADO{RESET}] #{i:02d} → HTTP {code} | {msg}")
        elif code == 401:
            msg = body.get("error", body)
            print(f"  [{YELLOW}FALLIDO  {RESET}] #{i:02d} → HTTP {code} | {msg}")
        elif code == 0:
            print(f"  [{RED}SIN CONN {RESET}] #{i:02d} → {body.get('error')}")
        else:
            print(f"  [HTTP {code}  ] #{i:02d} → {body}")

        time.sleep(0.3)

    print(f"\n{CYAN}{'='*56}{RESET}")
    if bloqueado_en:
        print(f"  {GREEN}[OK]{RESET} IP bloqueada en el intento #{BOLD}{bloqueado_en}{RESET}")
    else:
        print(f"  {RED}[!!]{RESET} La IP NO fue bloqueada en {intentos} intentos")

    print(f"""
  Para ver los logs en GCP:
  {CYAN}https://console.cloud.google.com/run/detail/us-central1/api-lh-inventario/logs?project=gestion-la-hornilla{RESET}

  Filtrá por:
  {BOLD}RATE-LIMIT{RESET}  o  {BOLD}{ip}{RESET}
{CYAN}{'='*56}{RESET}\n""")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url",      default=URL,      help="URL del endpoint de login")
    parser.add_argument("--ip",       default=IP_FAKE,  help="IP a simular (X-Forwarded-For)")
    parser.add_argument("--intentos", default=INTENTOS, type=int)
    args = parser.parse_args()
    run(args.url, args.ip, args.intentos)

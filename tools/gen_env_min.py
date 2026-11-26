#!/usr/bin/env python3
"""#89: env_file MINIMO para unsweep-relayer.

Copia desde product.env SOLO las claves aprobadas a un archivo fuera del repo
(permisos 600). Nunca imprime valores: solo nombres de clave.

Uso:
  python3 tools/gen_env_min.py            # genera DEST
  python3 tools/gen_env_min.py --check    # verifica que DEST tiene exactamente ALLOWED
"""
import os
import sys
import tempfile

# Unica fuente de verdad de las claves aprobadas (#89). Justificacion:
#  TURNSTILE_*  -> svc_core.py (anti-bot)
#  OPS_PK       -> service.py SPONSOR_KEY (patrocina gas)
#  BASE_RPC_URL, ETH_RPC_URL -> svc_mainnet.py CHAINS[...]['env']
#  OP_RPC_URL -> svc_mainnet.py CHAINS['optimism']['env'] (autorizado #161-A, ORDEN #2236)
ALLOWED = ("TURNSTILE_SECRET", "TURNSTILE_SITEKEY", "OPS_PK", "BASE_RPC_URL", "ETH_RPC_URL", "OP_RPC_URL")
SRC = os.environ.get("UNSWEEP_ENV_SRC", "/opt/aire/product.env")
DEST = os.environ.get("UNSWEEP_ENV_DEST", "/opt/aire/unsweep-relayer.env")


def parse(path):
    out = {}
    with open(path) as f:
        for line in f:
            s = line.rstrip("\n")
            if not s.strip() or s.lstrip().startswith("#") or "=" not in s:
                continue
            k, v = s.split("=", 1)
            k = k.strip()
            if k.startswith("export "):
                k = k[7:].strip()
            out[k] = v
    return out


def check(path=DEST):
    keys = sorted(parse(path))
    ok = keys == sorted(ALLOWED)
    print("gen_env_min:", "OK" if ok else "DISTINTO", "claves=" + ",".join(keys))
    mode = oct(os.stat(path).st_mode & 0o777)
    if mode != "0o600":
        print("gen_env_min: permisos", mode, "(se esperaba 0o600)")
        ok = False
    return ok


def generate(src=SRC, dest=DEST):
    env = parse(src)
    missing = [k for k in ALLOWED if not env.get(k, "").strip()]
    if missing:
        print("gen_env_min: FALTAN claves en origen:", ",".join(missing))
        return False
    d = os.path.dirname(os.path.abspath(dest))
    old = os.umask(0o077)
    try:
        fd, tmp = tempfile.mkstemp(dir=d, prefix=".envmin-")
        with os.fdopen(fd, "w") as f:
            for k in ALLOWED:
                f.write(f"{k}={env[k]}\n")
        os.chmod(tmp, 0o600)
        os.replace(tmp, dest)
    finally:
        os.umask(old)
    print("gen_env_min: escrito", dest, "claves=" + ",".join(ALLOWED))
    return True


if __name__ == "__main__":
    if "--check" in sys.argv[1:]:
        sys.exit(0 if check() else 1)
    sys.exit(0 if (generate() and check()) else 1)

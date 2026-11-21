#!/usr/bin/env python3
"""Genera el aviso de portada de web/index.html desde la fuente de verdad (#927).

Cifras: CAP_INITIAL_USD y HIGH_VALUE_USD de relayer/policy.py; numero de
tokens de assets_8453.json. Nunca se editan a mano en el HTML.

Uso:  python3 tools/gen_portada.py          # reescribe web/index.html
      python3 tools/gen_portada.py --check  # exit 1 si el HTML no coincide (CI)
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "web" / "index.html"
POLICY = ROOT / "relayer" / "policy.py"

# Literal #927 (nota humano id 927): 'Rescues above 10,000 USD get automatic
# extra safety checks (a few seconds more)', con simbolo de dolar en el HTML.
NOTE_TMPL = "*Rescues above {hv} get automatic extra safety checks (a few seconds more)."
STRONG_TMPL = ("<strong>Base mainnet: rescue is live ({n} ERC-20 tokens, up to {cap}* per rescue). "
               "Ethereum: free read-only check.</strong>")


def _const(name: str) -> float:
    m = re.search(rf"^{name}\s*=\s*([0-9_\.]+)", POLICY.read_text(), re.M)
    if not m:
        raise SystemExit(f"gen_portada: {name} no encontrado en policy.py")
    return float(m.group(1).replace("_", ""))


def _assets_count() -> int:
    cands = [p for p in ROOT.glob("**/assets_8453.json")
             if ".venv" not in p.parts and "node_modules" not in p.parts and ".git" not in p.parts]
    if len(cands) != 1:
        raise SystemExit(f"gen_portada: se esperaba 1 assets_8453.json, hay {len(cands)}")
    doc = json.loads(cands[0].read_text())
    toks = doc.get("tokens", doc) if isinstance(doc, dict) else doc
    return len(toks)


def usd(x: float) -> str:
    return "${:,.0f}".format(x)


def render(html: str) -> str:
    cap, hv, n = _const("CAP_INITIAL_USD"), _const("HIGH_VALUE_USD"), _assets_count()
    strong = STRONG_TMPL.format(n=n, cap=usd(cap))
    note = f'<p class="small" id="capNote">{NOTE_TMPL.format(hv=usd(hv))}</p>'
    # 1) <strong> del aviso mainnetNotice (exactamente una vez)
    pat = re.compile(r'(<p class="notice" id="mainnetNotice">)<strong>.*?</strong>', re.S)
    out, k = pat.subn(lambda m: m.group(1) + strong, html)
    if k != 1:
        raise SystemExit(f"gen_portada: mainnetNotice encontrado {k} veces")
    # 2) nota capNote justo despues del cierre del aviso (idempotente)
    out = re.sub(r'<p class="small" id="capNote">.*?</p>', "", out, flags=re.S)
    pat2 = re.compile(r'(<p class="notice" id="mainnetNotice">.*?</p>)', re.S)
    out, k = pat2.subn(lambda m: m.group(1) + note, out, count=1)
    if k != 1:
        raise SystemExit("gen_portada: no se pudo insertar capNote")
    return out


def main() -> int:
    html = INDEX.read_text()
    new = render(html)
    if "--check" in sys.argv:
        if new != html:
            print("gen_portada: web/index.html desactualizado; ejecutar tools/gen_portada.py")
            return 1
        print("gen_portada: OK")
        return 0
    INDEX.write_text(new)
    print("gen_portada: escrito" if new != html else "gen_portada: sin cambios")
    return 0


if __name__ == "__main__":
    sys.exit(main())

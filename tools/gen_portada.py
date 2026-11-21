#!/usr/bin/env python3
"""Genera los bloques de web/index.html que dependen de fuentes de verdad.

Bloques (entre <!--gen:X--> y <!--/gen:X-->):
  top    -> recuadro superior literal de la orden #956 (tope 'up to $X*' de CAP_INITIAL_USD).
  cap    -> nota gris bajo el formulario '*Rescues above $X ...' (HIGH_VALUE_USD).
  tokens -> lista plegable de tokens de Base (relayer/data/assets_8453.json).
  faqld  -> JSON-LD FAQPage derivado de los <details class="faq"> del propio HTML
            (una sola fuente de texto; type application/ld+json = bloque de datos,
            no ejecutable, compatible con la CSP actual).
Nunca se editan a mano.

Uso:  python3 tools/gen_portada.py          # reescribe web/index.html
      python3 tools/gen_portada.py --check  # exit 1 si el HTML no coincide (CI)
"""
import html as htmlmod
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "web" / "index.html"
POLICY = ROOT / "relayer" / "policy.py"

TOP_TMPL = ('<p class="notice" id="mainnetNotice"><span id="capLine">Base mainnet: rescue is live '
            '({n} ERC-20 tokens, up to {cap}* per rescue). Ethereum: free read-only check. '
            'Your compromised key never leaves your browser. We will never DM you first and '
            'never ask for your seed phrase.</span></p>')
CAP_TMPL = ('<p class="small muted" id="capNote">*Rescues above {hv} get automatic extra safety '
            'checks (a few seconds more).</p>')


def _const(name: str) -> float:
    m = re.search(rf"^{name}\s*=\s*([0-9_\.]+)", POLICY.read_text(), re.M)
    if not m:
        raise SystemExit(f"gen_portada: {name} no encontrado en policy.py")
    return float(m.group(1).replace("_", ""))


def _assets():
    cands = [p for p in ROOT.glob("**/assets_8453.json")
             if ".venv" not in p.parts and "node_modules" not in p.parts and ".git" not in p.parts]
    if len(cands) != 1:
        raise SystemExit(f"gen_portada: se esperaba 1 assets_8453.json, hay {len(cands)}")
    doc = json.loads(cands[0].read_text())
    toks = doc.get("tokens", doc) if isinstance(doc, dict) else doc
    return toks


def usd(x: float) -> str:
    return "${:,.0f}".format(x)


def _strip(s: str) -> str:
    return htmlmod.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def faq_pairs(html: str):
    pairs = re.findall(r'<details class="faq"><summary>(.*?)</summary>(.*?)</details>', html, re.S)
    return [(_strip(q), _strip(a)) for q, a in pairs]


def _replace(html: str, key: str, body: str) -> str:
    pat = re.compile(rf"<!--gen:{key}-->.*?<!--/gen:{key}-->", re.S)
    if len(pat.findall(html)) != 1:
        raise SystemExit(f"gen_portada: marcador gen:{key} ausente o duplicado")
    return pat.sub(lambda _m: f"<!--gen:{key}-->{body}<!--/gen:{key}-->", html)


def render(html: str) -> str:
    cap, hv = _const("CAP_INITIAL_USD"), _const("HIGH_VALUE_USD")
    toks = _assets()
    html = _replace(html, "top", "\n" + TOP_TMPL.format(n=len(toks), cap=usd(cap)) + "\n")
    html = _replace(html, "cap", "\n" + CAP_TMPL.format(hv=usd(hv)) + "\n")
    syms = ", ".join(htmlmod.escape(t["symbol"]) for t in toks)
    html = _replace(html, "tokens", (f'\n<details class="info" id="tokens"><summary>Supported tokens on Base '
                                     f'({len(toks)})</summary><p class="small">{syms}</p></details>\n'))
    pairs = faq_pairs(html)
    if len(pairs) != 11:
        raise SystemExit(f"gen_portada: se esperaban 11 preguntas FAQ, hay {len(pairs)}")
    ld = {"@context": "https://schema.org", "@type": "FAQPage",
          "mainEntity": [{"@type": "Question", "name": q,
                          "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in pairs]}
    js = json.dumps(ld, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    html = _replace(html, "faqld", f'<script type="application/ld+json" id="faqSchema">{js}</script>')
    return html


def main() -> int:
    cur = INDEX.read_text()
    new = render(cur)
    if "--check" in sys.argv:
        if new != cur:
            print("gen_portada: web/index.html no coincide con la fuente; ejecuta tools/gen_portada.py")
            return 1
        print("gen_portada: OK")
        return 0
    INDEX.write_text(new)
    print("gen_portada: escrito", INDEX)
    return 0


if __name__ == "__main__":
    sys.exit(main())

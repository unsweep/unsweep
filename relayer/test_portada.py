"""Tests de portada (#927 c), cambios web del humano (#93/#95) y rediseno captacion."""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDEX = (ROOT / "web" / "index.html").read_text()
APPJS = (ROOT / "web" / "assets" / "app.js").read_text()
DELEGATE = "0x38bcF425bC4d13624734e09376F2fafc799fA8c8"
CONFIG = "0x56a345661e3999F2b20f1E069aAC14097Fa0D118"


def test_portada_generada_por_pipeline():
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "gen_portada.py"), "--check"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


LITERAL_956 = ("Base mainnet: rescue is live (16+ ERC-20 tokens†, up to $100,000* per rescue). "
               "Ethereum: free read-only check. Your compromised key never leaves your browser. "
               "We will never DM you first and never ask for your seed phrase.")


def _texto(s):
    return re.sub(r"<[^>]+>", "", s).strip()


def test_recuadro_superior_literal_956():
    m = re.findall(r'<p class="notice" id="mainnetNotice">(.*?)</p>', INDEX, re.S)
    assert len(m) == 1
    assert _texto(m[0]) == LITERAL_956
    assert "$100,000*" in m[0] and "USD" not in m[0]  # la FAQ conserva "USD" (no es el recuadro)
    body = INDEX.split("<body>", 1)[1]
    assert body.index('id="mainnetNotice"') < body.index('id="step1"')


def test_frase_seguridad_no_repetida_bajo_scan():
    body = INDEX.split("<body>", 1)[1]
    bajo_scan = body.split('id="btnScan"', 1)[1].split('id="step2"', 1)[0]
    for frag in ("never leaves your browser", "never DM you first", "seed phrase", "Non-custodial"):
        assert frag not in bajo_scan, frag
    assert INDEX.count("Your compromised key never leaves your browser") == 1


def test_nota_asterisco_bajo_formulario():
    nota = ('<p class="small muted" id="capNote">*Rescues above $10,000 get automatic extra '
            'safety checks (a few seconds more).</p>')
    assert INDEX.count(nota) == 1 and INDEX.count('id="capNote"') == 1
    body = INDEX.split("<body>", 1)[1]
    assert body.index('id="btnScan"') < body.index('id="capNote"') < body.index('id="step2"')
    assert "10,000 USD get" not in INDEX and "up to $10,000 per rescue" not in INDEX


def test_orden_portada():
    body = INDEX.split("<body>", 1)[1]
    assert body.index('id="btnScan"') < body.index('id="faq"')
    assert body.index('id="btnScan"') < body.index('id="contracts"') < body.index('id="guides"') < body.index("<footer>")
    intro = re.search(r'<p class="intro">(.*?)</p>', INDEX, re.S).group(1)
    assert "\n" not in intro and len(intro) < 120


def test_contratos_una_sola_vez():
    for a in (DELEGATE, CONFIG):
        assert INDEX.count(a) == 2  # texto del enlace + href, una sola aparicion visible
        assert INDEX.count(f'href="https://basescan.org/address/{a}#code"') == 1
    assert INDEX.count('href="https://github.com/unsweep/unsweep"') == 1
    sec = INDEX.split('id="contracts"', 1)[1].split("</section>", 1)[0]
    assert DELEGATE in sec and CONFIG in sec and "github.com/unsweep/unsweep" in sec
    assert INDEX.count("Verify our contracts") == 1 and "<h2>Verify our contracts</h2>" in sec


def test_tokens_plegables_desde_assets():
    toks = json.loads((ROOT / "relayer" / "data" / "assets_8453.json").read_text())
    toks = toks.get("tokens", toks) if isinstance(toks, dict) else toks
    m = re.search(r'<details class="info" id="tokens"><summary>Supported tokens on Base \((\d+)\)</summary>'
                  r'<p class="small">(.*?)</p></details>', INDEX)
    assert m and int(m.group(1)) == len(toks)
    assert m.group(2).split(", ") == [t["symbol"] for t in toks]
    assert INDEX.count("Supported tokens on Base") == 1


def test_faq_10_y_jsonld_coherente():
    qs = re.findall(r'<details class="faq"><summary>(.*?)</summary><p>(.*?)</p></details>', INDEX, re.S)
    assert len(qs) == 11
    m = re.findall(r'<script type="application/ld\+json" id="faqSchema">(.*?)</script>', INDEX, re.S)
    assert len(m) == 1
    ld = json.loads(m[0])
    assert ld["@type"] == "FAQPage" and len(ld["mainEntity"]) == 11
    assert [e["name"] for e in ld["mainEntity"]] == [q for q, _ in qs]
    texto = " ".join(a for _, a in qs)
    for frag in ("15% below 1,000 USD", "10% from 1,000 to 10,000 USD", "5% above 10,000 USD",
                 "you pay nothing", "case by case", "support@unsweep.com", "never DM you first"):
        assert frag in texto, frag


def test_faq_comisiones_coinciden_con_policy():
    sys.path.insert(0, str(ROOT / "relayer"))
    import policy  # noqa: E402
    assert policy.tier_bps(999) == 1500
    assert policy.tier_bps(1_000) == 1000 and policy.tier_bps(10_000) == 1000
    assert policy.tier_bps(10_001) == 500
    assert policy.CAP_INITIAL_USD == 100_000 and policy.HIGH_VALUE_USD == 10_000


def test_csp_compatible_sin_inline_ejecutable():
    assert "<style" not in INDEX and ' style="' not in INDEX
    assert not re.search(r"\son[a-z]+=", INDEX)
    scripts = re.findall(r"<script([^>]*)>(.*?)</script>", INDEX, re.S)
    for attrs, body in scripts:
        assert ('src="' in attrs and not body.strip()) or 'type="application/ld+json"' in attrs


def test_ids_de_appjs_intactos():
    ids = set(re.findall(r"\$\('([A-Za-z0-9_-]+)'\)", APPJS))
    assert ids, "no se encontraron ids en app.js"
    for i in ids:
        assert INDEX.count(f'id="{i}"') == 1, i
    assert 'id="ts"' in INDEX


def test_web_limpia_humano():
    assert INDEX.count('href="mailto:support@unsweep.com"') == 1
    assert ('Contact: <a href="mailto:support@unsweep.com">support@unsweep.com</a> '
            '(never send keys or seed phrases).') in INDEX
    assert "Supported token:" not in INDEX
    assert "tabRescueMainnet" not in INDEX and "tabScan" not in INDEX


def test_appjs_humano_ethereum_solo_lectura():
    assert "if (chain === 'ethereum') {" in APPJS
    assert "if (chain === 'base' || chain === 'ethereum') {" not in APPJS
    assert re.search(r"Ethereum mainnet: read-only check", APPJS)
